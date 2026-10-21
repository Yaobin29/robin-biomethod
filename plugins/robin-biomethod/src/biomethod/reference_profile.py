"""Optional dated Europe PMC metadata; influence is never a replication score."""
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import json
from pathlib import Path
from .workflow import read
from robinharness.runtime import dump


def refresh_references(source,out):
    profiles=[]
    for doc in read(Path(source)/'registry.json').get('documents',[]):
        query='DOI:"'+doc['doi']+'"' if doc.get('doi') else 'EXT_ID:'+doc['id']
        url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urlencode(dict(query=query,format='json',resultType='core',pageSize=5))
        row=dict(id=doc['id'],provider='Europe PMC',query_url=url,retrieved_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),status='unavailable',citation_count=None,journal=None,year=None,independent_replication='not assessed')
        try:
            with urlopen(Request(url,headers={'User-Agent':'RobinBioMethod/0.3 report metadata'}),timeout=25) as response:body=json.load(response)
            matches=body.get('resultList',{}).get('result',[])
            if doc.get('doi'):
                matches=[r for r in matches if r.get('doi','').lower()==doc['doi'].lower() and (not doc['id'].startswith('PMC') or not r.get('pmcid') or r.get('pmcid')==doc['id'])]
            else:
                matches=[r for r in matches if r.get('pmcid')==doc['id']]
            if len(matches)!=1:raise ValueError('No unique exact source match.')
            record=matches[0];count=record.get('citedByCount')
            if count is not None and (type(count) is not int or count<0):raise ValueError('Invalid citation count.')
            row.update(status='retrieved',citation_count=count,journal=record.get('journalInfo',{}).get('journal',{}).get('title'),year=record.get('pubYear'),doi=record.get('doi'),article_type=record.get('pubTypeList',{}).get('pubType',[]))
        except (OSError,ValueError,KeyError,TypeError) as exc:row['error']=str(exc)
        profiles.append(row)
    result=dict(schema_version=1,scope='Bibliographic metadata only. Citation count is not independent replication or method validity.',documents=profiles)
    dump(Path(out),result);return result
