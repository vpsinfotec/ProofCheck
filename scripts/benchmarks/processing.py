"""Reproducible comparison with the supplied archive baseline (requires git history).

Run: python scripts/benchmarks/processing.py --output docs/benchmark-results.json
Numbers are synthetic local measurements, not production latency guarantees.
"""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from proofcheck import document, pipeline
from proofcheck.matcher import PreparedMatcher
from proofcheck.models import RunConfig
from openpyxl import Workbook
from reportlab.pdfgen import canvas

BASELINE = '9c9502c'


def old_module(name, file):
    code = subprocess.check_output(['git', 'show', f'{BASELINE}:{file}'], cwd=ROOT, text=True)
    module = types.ModuleType('proofcheck.' + name)
    module.__package__ = 'proofcheck'
    sys.modules[module.__name__] = module
    exec(compile(code, file, 'exec'), module.__dict__)
    return module


def measure(fn, repeats=3):
    times=[]
    for _ in range(repeats):
        start=perf_counter(); result=fn(); times.append(perf_counter()-start)
    return statistics.median(times), result, times


def verdicts(results):
    return [(r.expected, r.status.value, r.page, r.score) for r in results]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default='docs/benchmark-results.json')
    args=parser.parse_args()
    baseline_matcher=old_module('_baseline_matcher','proofcheck/matcher.py')
    baseline_pdf=old_module('_baseline_pdf','proofcheck/pdf.py')
    baseline_pipeline=old_module('_baseline_pipeline','proofcheck/pipeline.py')
    baseline_pipeline.match_value=baseline_matcher.match_value
    pages={p+1:'\n'.join(f'Delegate {p*30+i:04d} Conference City {p:02d}' for i in range(30)) for p in range(20)}
    workloads={
        'exact_unique': [f'Delegate {i:04d}' for i in range(300)],
        'exact_repeated': [f'Delegate {i%30:04d}' for i in range(600)],
        'fuzzy_and_missing': [f'Dellegate {i:04d}' for i in range(50)]+[f'ZZQX unknown {i:04d}' for i in range(30)],
    }
    report={'baseline_commit':BASELINE,'python':sys.version.split()[0], 'repeats':3,
            'dependencies':{p:importlib.metadata.version(p) for p in ['rapidfuzz','pdfplumber','pypdfium2','fastapi','starlette']},'workloads':[]}
    for name,values in workloads.items():
        old_time,old,old_samples=measure(lambda:[baseline_matcher.match_value(v,pages) for v in values])
        def current():
            m=PreparedMatcher(pages)
            return [m.match(v) for v in values]
        new_time,new,new_samples=measure(current)
        assert verdicts(old)==verdicts(new), name
        report['workloads'].append({'name':name,'values':len(values),'pages':len(pages),'baseline_seconds':old_time,'updated_seconds':new_time,'speedup':old_time/new_time,'baseline_samples':old_samples,'updated_samples':new_samples,'verdict_parity':True})
        print(name, round(old_time,4), round(new_time,4), round(old_time/new_time,1), flush=True)
    with tempfile.TemporaryDirectory() as temp:
        xlsx=Path(temp)/'delegates.xlsx'; pdf=Path(temp)/'document.pdf'
        wb=Workbook(); wb.active.append(['Name'])
        for i in range(600): wb.active.append([f'Delegate {i:04d}'])
        wb.save(xlsx)
        c=canvas.Canvas(str(pdf))
        for page in pages.values():
            y=800
            for line in page.splitlines(): c.drawString(40,y,line); y-=22
            c.showPage()
        c.save()
        config=RunConfig(str(xlsx),str(pdf),columns=['Name'])
        original_extract=document.extract
        try:
            document.extract=baseline_pdf.extract
            old_time,old,old_samples=measure(lambda:baseline_pipeline.run(config))
        finally: document.extract=original_extract
        new_time,new,new_samples=measure(lambda:pipeline.run(config))
        assert verdicts(old.columns[0].results)==verdicts(new.columns[0].results)
        report['workloads'].append({'name':'pipeline_text_pdf','values':600,'pages':20,'baseline_seconds':old_time,'updated_seconds':new_time,'speedup':old_time/new_time,'baseline_samples':old_samples,'updated_samples':new_samples,'verdict_parity':True,'updated_stage_seconds':new.timings})
        print('pipeline_text_pdf',round(old_time,4),round(new_time,4),round(old_time/new_time,1),flush=True)
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
