"""Public no-key discovery and provenance-preserving, explicit source collection."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from robinharness.runtime import dump, safe_relative

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
MAX_BYTES = 15_000_000

def now():
    return datetime.now(timezone.utc).isoformat()

def request(url):
    req = urllib.request.Request(url, headers={"User-Agent": "RobinBioMethod/0.1 (public literature research)"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Literature response exceeds 15 MB limit.")
    return data

def search(query, limit=8, provider="europepmc"):
    if not query.strip() or not 1 <= limit <= 25:
        raise ValueError("Provide a query and limit 1..25.")
    if provider not in ("europepmc", "pubmed"):
        raise ValueError("Provider must be europepmc or pubmed.")
    # Europe PMC indexes PubMed (SRC:MED); this path avoids a second API dependency.
    actual = f"({query}) AND SRC:MED" if provider == "pubmed" else query
    url = API + "search?" + urllib.parse.urlencode(dict(query=actual, format="json", resultType="core", pageSize=limit))
    raw = json.loads(request(url))
    rows, seen = [], set()
    for r in raw.get("resultList", {}).get("result", []):
        doi = r.get("doi", "").lower()
        key = doi or r.get("pmcid") or (r.get("source", "") + r.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(title=r.get("title", ""), doi=doi, pmcid=r.get("pmcid"),
                         pmid=r.get("id") if r.get("source") == "MED" else None,
                         year=r.get("pubYear"), journal=r.get("journalInfo", {}).get("journal", {}).get("title"),
                         abstract=r.get("abstractText", ""), open_access=r.get("isOpenAccess") == "Y",
                         url="https://doi.org/" + doi if doi else "https://europepmc.org/article/" + r.get("source", "MED") + "/" + r.get("id", ""),
                         why=None, how=None, what=None, inclusion_reason=None))
    return dict(schema_version=1, query=query, executed_query=actual, provider=provider,
                api="Europe PMC (PubMed subset via SRC:MED)" if provider == "pubmed" else "Europe PMC",
                retrieved=now(), hit_count=raw.get("hitCount"), results=rows,
                coverage="bounded search, not systematic or exhaustive; 3W fields require full-text review")

def text_of(node):
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip() if node is not None else ""

def jats_document(pmcid, raw):
    article = ET.fromstring(raw)
    title = text_of(article.find(".//article-title"))
    doi = next((text_of(x) for x in article.findall(".//article-id") if x.get("pub-id-type") == "doi"), "")
    licenses = article.findall(".//license")
    license_text = " ".join(text_of(x) for x in licenses) or "not stated in retrieved XML"
    blocks = []
    # Paragraphs, tables and captions keep section/table context. References excluded.
    body = article.find("body")
    if body is None:
        raise ValueError("No full-text body; abstract-only content cannot become method evidence.")
    def walk(node, section=""):
        if node.tag == "sec":
            section = text_of(node.find("title")) or section
        if node.tag == "p":
            blocks.append((section, text_of(node)))
            return
        if node.tag == "table-wrap":
            label = text_of(node.find("label"))
            blocks.append((section, label + " " + text_of(node.find("caption"))))
            for row in node.findall(".//tr"):
                blocks.append((section, label + " | " + " | ".join(text_of(x) for x in row if x.tag in ("td", "th"))))
            return
        if node.tag == "fig":
            blocks.append((section, text_of(node.find("label")) + " " + text_of(node.find("caption"))))
            return
        for child in node:
            walk(child, section)
    walk(body)
    content = "\n".join(f"[L{i:04d}] {sec + ': ' if sec else ''}{txt}" for i, (sec, txt) in enumerate(blocks, 1) if txt)
    links = []
    for x in article.findall(".//supplementary-material"):
        for y in x.iter():
            for key, value in y.attrib.items():
                if key.endswith("href"):
                    links.append(value)
    return dict(id=pmcid, title=title, doi=doi, url=f"https://europepmc.org/articles/{pmcid}",
                access="full_text", license=license_text, retrieved=now(), role="unreviewed",
                text_file=f"documents/{pmcid}.txt", sha256=hashlib.sha256(content.encode()).hexdigest(),
                supplement_links=sorted(set(links)), supplement_status="not retrieved; inspect if method depends on it"), content

def collect(pmcids, out: Path, search_file=None):
    if out.exists():
        raise ValueError("Collection output must be a new directory; existing evidence is never overwritten.")
    for pid in pmcids:
        if not re.fullmatch(r"PMC[0-9]+", pid):
            raise ValueError("Explicit PMC identifiers required.")
    out.mkdir(parents=True)
    docs, errors = [], []
    for pid in dict.fromkeys(pmcids):
        try:
            doc, text = jats_document(pid, request(API + pid + "/fullTextXML"))
            target = out / doc["text_file"]
            target.parent.mkdir(exist_ok=True)
            target.write_text(text + "\n")
            doc["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            docs.append(doc)
        except Exception as exc:
            errors.append(dict(id=pid, error=str(exc)))
    bundle = dict(schema_version=1, documents=docs, errors=errors,
                  search=json.loads(Path(search_file).read_text()) if search_file else None)
    dump(out / "registry.json", bundle)
    return dict(status="completed" if docs and not errors else "incomplete", documents=len(docs), errors=errors)

def import_document(input_path: Path, out: Path, doc_id, title, url, doi="", license_text="not supplied"):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", doc_id):
        raise ValueError("Invalid document id.")
    if out.exists():
        raise ValueError("Use a new source collection directory.")
    if input_path.suffix.lower() not in (".pdf", ".txt", ".md"):
        raise ValueError("Import accepts PDF or already extracted UTF-8 TXT/MD, not unparsed HTML or binary files.")
    if input_path.suffix.lower() == ".pdf":
        tool = shutil.which("pdftotext")
        if not tool:
            raise ValueError("PDF extraction unavailable. Convert with OpenDataLoader or provide page-marked UTF-8 text.")
        raw = subprocess.run([tool, "-layout", str(input_path.resolve()), "-"], capture_output=True, timeout=60, check=True).stdout.decode("utf-8")
        chunks = [(f"page {i}", p) for i, p in enumerate(raw.split("\f"), 1)]
    else:
        chunks = [("imported text", input_path.read_text())]
    lines = [f"{page}: {re.sub(chr(9), ' ', line).strip()}" for page, text in chunks for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty extraction; OCR or manual inspection required.")
    content = "\n".join(f"[L{i:04d}] {line}" for i, line in enumerate(lines, 1)) + "\n"
    rel = f"documents/{doc_id}.txt"; dest = out / rel
    dest.parent.mkdir(parents=True);dest.write_text(content)
    doc = dict(id=doc_id, title=title, doi=doi, url=url, access="user_supplied_full_text",
               license=license_text, retrieved=now(), role="unreviewed", text_file=rel,
               sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
               supplement_status="not reviewed", extraction="layout text; tables/equations require visual inspection")
    dump(out / "registry.json", dict(schema_version=1, documents=[doc], errors=[], search=None))
    return dict(status="completed", document=doc_id)


def merge_collections(bundles, out):
    from .workflow import source_index
    if out.exists():
        raise ValueError("Use a new merged collection directory.")
    documents, searches, ids = [], [], set()
    staged = []
    for bundle in bundles:
        doc_map, _ = source_index(bundle)
        registry = json.loads((bundle / 'registry.json').read_text())
        if registry.get('search'):
            searches.append(registry['search'])
        for doc in doc_map.values():
            if doc['id'] in ids:
                raise ValueError("Duplicate document id across collections: " + doc['id'])
            ids.add(doc['id'])
            new_doc = dict(doc, text_file=f"documents/{doc['id']}.txt")
            staged.append((bundle / safe_relative(doc['text_file']), new_doc['text_file']))
            documents.append(new_doc)
    out.mkdir(parents=True)
    for original, rel in staged:
        p = out / rel;p.parent.mkdir(exist_ok=True);shutil.copy2(original,p)
    dump(out / 'registry.json', dict(schema_version=1, documents=documents, errors=[], search=searches or None,
                                   coverage='Explicitly merged source collections, not an exhaustive literature review.'))
    return dict(status='completed', documents=len(documents))
