"""Evidence-grounded design entry with explicit lower-level research tools."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
from robinharness.runtime import dump, state_root
from robinharness import cli as core
from . import __version__
from .research import search, collect, import_document, merge_collections
from .workflow import prepare, read, validate_task_source, PLUGIN
from .validation import assess
from .reporting import render, compare
from .pipeline import run_design, settings, configure, job_status
from .execution import export_execution


def main(argv=None):
    p=argparse.ArgumentParser(prog='biomethod')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('setup');sub.add_parser('doctor')
    config=sub.add_parser('configure')
    design=sub.add_parser('design')
    design.add_argument('--goal',type=Path,required=True)
    design.add_argument('--query',action='append',default=[])
    design.add_argument('--bundle',type=Path)
    design.add_argument('--prepared-from',type=Path)
    design.add_argument('--run-dir',type=Path)
    design.add_argument('--dry-run',action='store_true')
    for command in (config,design):
        command.add_argument('--session-limit',type=int)
        command.add_argument('--minutes',type=float)
        command.add_argument('--k',type=int)
        command.add_argument('--model')
    resume=sub.add_parser('resume-final');resume.add_argument('job',type=Path);resume.add_argument('--minutes',type=float,required=True);resume.add_argument('--extra-minutes',type=float,default=0);resume.add_argument('--reuse-partial',action='store_true')
    repair=sub.add_parser('repair-delivery');repair.add_argument('job',type=Path)
    html=sub.add_parser('html-report',help='Render saved results as offline HTML; zero model calls');html.add_argument('job',type=Path)
    status=sub.add_parser('status');status.add_argument('job',type=Path)
    evidence=sub.add_parser('evidence');evidence.add_argument('run_dir',type=Path)
    s=sub.add_parser('search');s.add_argument('--query',required=True);s.add_argument('--provider',choices=['europepmc','pubmed'],default='europepmc');s.add_argument('--limit',type=int,default=8);s.add_argument('--out',type=Path,required=True)
    c=sub.add_parser('collect');c.add_argument('--pmcid',nargs='+',required=True);c.add_argument('--search',type=Path);c.add_argument('--out',type=Path,required=True)
    i=sub.add_parser('import');i.add_argument('--input',type=Path,required=True);i.add_argument('--id',required=True);i.add_argument('--title',required=True);i.add_argument('--url',required=True);i.add_argument('--doi',default='');i.add_argument('--license',default='not supplied');i.add_argument('--out',type=Path,required=True)
    m=sub.add_parser('merge');m.add_argument('--bundle',type=Path,action='append',required=True);m.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('prepare')
    for flag in ('goal','bundle','methods','out'):q.add_argument('--'+flag,type=Path,required=True)
    q.add_argument('--profile',type=Path)
    a=sub.add_parser('assess');a.add_argument('--task',type=Path,required=True);a.add_argument('--artifact',type=Path,required=True)
    a=sub.add_parser('render');a.add_argument('--task',type=Path,required=True);a.add_argument('--artifact',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    c=sub.add_parser('compare');c.add_argument('--task',type=Path,required=True);c.add_argument('--artifact',action='append',type=Path,required=True);c.add_argument('--out',type=Path,required=True)
    d=sub.add_parser('demo');d.add_argument('--out',type=Path,required=True)
    r=sub.add_parser('run');r.add_argument('--task',required=True);r.add_argument('--holdout',action='append',default=[]);r.add_argument('--learning-task');r.add_argument('--library-dir');r.add_argument('--model');r.add_argument('--k',type=int,default=1);r.add_argument('--mode',choices=['parallel','sequential'],default='parallel');r.add_argument('--session-limit',type=int,default=16);r.add_argument('--minutes',type=int,default=45);r.add_argument('--run-dir')
    a=sub.add_parser('report');a.add_argument('run_dir',type=Path)
    args=p.parse_args(argv)
    try:
        if args.command=='setup':
            out=core.setup();out['settings']=settings();out['next']='For a material design request, load biomethod-design and invoke design --goal after clarifying the target. Setup alone is not completion.'
        elif args.command=='configure':
            out=configure(dict(session_limit=args.session_limit,minutes=args.minutes,k=args.k,model=args.model))
        elif args.command=='design':
            out=run_design(args.goal,queries=args.query,bundle=args.bundle,run_dir=args.run_dir,dry_run=args.dry_run,prepared_from=args.prepared_from,
                           overrides=dict(session_limit=args.session_limit,minutes=args.minutes,k=args.k,model=args.model))
        elif args.command=='resume-final':
            from .resume import resume_final
            out=resume_final(args.job,minutes=args.minutes,extra_minutes=args.extra_minutes,reuse_partial=args.reuse_partial)
        elif args.command=='repair-delivery':
            from .repair import repair_delivery
            out=repair_delivery(args.job)
        elif args.command=='html-report':
            from .html_report import render_job_report
            report=render_job_report(args.job)
            out=dict(status='rendered',html_report=str(report),model_calls=0)
        elif args.command=='status':out=job_status(args.job)
        elif args.command=='evidence':out=export_execution(args.run_dir)
        elif args.command=='doctor':
            out=core.doctor();out.update(pdf_extractors={'pdftotext':bool(shutil.which('pdftotext')),'opendataloader-pdf':bool(shutil.which('opendataloader-pdf'))},product='RobinBioMethod',state=str(state_root()),model_calls=0)
        elif args.command=='search':
            if args.out.exists():raise ValueError('Search output already exists; use a new file.')
            out=search(args.query,args.limit,args.provider);dump(args.out,out)
        elif args.command=='collect':out=collect(args.pmcid,args.out,args.search)
        elif args.command=='import':out=import_document(args.input,args.out,args.id,args.title,args.url,args.doi,args.license)
        elif args.command=='merge':out=merge_collections(args.bundle,args.out)
        elif args.command=='prepare':out=prepare(args.goal,args.bundle,args.methods,args.out,args.profile)
        elif args.command in ('assess','render','compare'):
            task=read(args.task)
            source=args.task.parent / task['source_dir']
            if args.command=='assess':out=assess(source,args.artifact)
            elif args.command=='render':out=render(source,args.artifact,args.out)
            else:out=compare(source,[(str(i),a) for i,a in enumerate(args.artifact)],args.out)
        elif args.command=='demo':
            if args.out.exists():raise ValueError('Demo requires a new directory.')
            example=PLUGIN/'examples/gelma'
            args.out.mkdir(parents=True)
            shutil.copytree(example/'task/source',args.out/'source')
            shutil.copy2(example/'curated-method.json',args.out/'curated-method.json')
            out=render(args.out/'source',args.out/'curated-method.json',args.out/'method.md')
            render(args.out/'source',args.out/'curated-method.json',args.out/'method.html')
            dump(args.out/'assessment.json',out)
            out=dict(status='completed' if out['valid'] else 'incomplete',model_calls=0,workflow_complete=False,harness2_executed=False,
                     artifact=str(args.out/'method.html'),markdown=str(args.out/'method.md'),origin='host-curated public literature example; NOT a model-generated optimization')
        elif args.command=='report':
            raw=core.read_report(args.run_dir);proof=export_execution(args.run_dir)
            out=dict(raw,core_report_status=raw.get('status'),status=proof['status'],harness2_executed=proof['core_executed'],verified=proof['verified'])
        elif args.command=='run':
            if read(Path(args.task)).get('evaluator')!='biomethod-v1':raise ValueError('RobinBioMethod requires a biomethod-v1 task.')
            report,run=core.optimize(args)
            proof=export_execution(run)
            out=dict(status=proof['status'],harness2_executed=proof['core_executed'],report=str(run/'report.json'),
                     execution_evidence=str(run/'execution-evidence.json'),recommended=False,
                     scientific_performance='not experimentally tested',errors=report['errors'])
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 1 if out.get('status')=='incomplete' or out.get('valid') is False or out.get('ok') is False else 0
    except Exception as exc:
        print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=False),file=sys.stderr)
        return 1
