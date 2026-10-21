"""Source-bound report translations. No implicit model calls or network translation."""
from collections import Counter
import hashlib
import json
import re
import unicodedata

# Identifiers, formulae and original quotations are not paraphrased by localization.
PRESERVE={'quote','url','doi','id','route_id','document','locator','material','method_ids','uncertainty_ids','expression'}


def report_payload(goal,data,literature):
    return dict(goal=goal,data=data,literature={k:literature.get(k,[]) for k in ('literature_review','source_gaps')})


def content_hash(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def required_strings(payload):
    result=set()
    def walk(value,key=''):
        if key in PRESERVE:return
        if isinstance(value,dict):
            for k,v in value.items():walk(v,k)
        elif isinstance(value,list):
            for v in value:walk(v,key)
        elif isinstance(value,str):result.add(value)
    walk(payload)
    return sorted(result)


def numbers(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'(?<=[A-Za-z])-(?=\d)', ' ', text)
    return Counter(re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',text))


def validate_localization(pack,payload):
    if not isinstance(pack,dict) or pack.get('source_hash')!=content_hash(payload):
        raise ValueError('Report translation is missing or stale: source hash differs.')
    strings=pack.get('zh',{})
    missing=[x for x in required_strings(payload) if not isinstance(strings.get(x),str)]
    if missing:raise ValueError(f'Chinese translation incomplete: {len(missing)} strings missing.')
    for source in required_strings(payload):
        target=strings[source]
        if source and not target.strip():raise ValueError('Empty Chinese translation.')
        if numbers(source)!=numbers(target):raise ValueError('Translation changed numeric tokens: '+source[:90])
        if re.search(r'[A-Za-z]{3,}(?:[ ,.;:]+[A-Za-z]{3,}){6}',target) and not 'sum(' in target:
            raise ValueError('Untranslated English prose remains in Chinese edition: '+source[:90])
        # English identifiers/units/formulae may remain; prose may not silently pass through.
        if len(source)>45 and source==target and not re.search(r'[\u3400-\u9fff]',source) and not ('sum(' in source or source.startswith(('http','/'))):
            raise ValueError('English prose left untranslated: '+source[:90])
    for source in required_strings(payload):
        if re.search(r'[\u3400-\u9fff]',source):
            en=pack.get('en',{}).get(source)
            if not isinstance(en,str) or re.search(r'[\u3400-\u9fff]',en):
                raise ValueError('English translation missing for Chinese source prose.')
            if numbers(source)!=numbers(en):raise ValueError('English translation changed numeric tokens.')
    return strings
