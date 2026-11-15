"""Rebuild the reviewed HTML and figures from included summaries, without raw data."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New complete bundle directory; must not already exist')
    args=parser.parse_args();bundle=Path(__file__).resolve().parent;output=args.output.resolve()
    if output.exists():parser.error('Output already exists; choose a new directory')
    if output.is_relative_to(bundle):parser.error('Output must be outside the source bundle')
    # Keep the report, documentation and source together so relative links survive.
    shutil.copytree(bundle,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    temporary=tempfile.TemporaryDirectory(prefix='comp3522-report-')
    stage=Path(temporary.name).resolve()
    # Validate the temporary cleanup boundary before entering its managed lifetime.
    if stage.parent!=Path(tempfile.gettempdir()).resolve():raise RuntimeError('Unexpected temporary directory boundary')
    try:
        analyses=stage/'geographical-research/analyses'
        for name in ['11_geographic_factors','12_geographic_deepening','13_hko_offset_reframing']:
            shutil.copytree(bundle/'source'/name,analyses/name)
        for name,source in [('11_geographic_factors',bundle/'report/results'),('12_geographic_deepening',bundle/'report/deepening/results'),('13_hko_offset_reframing',bundle/'report/deepening/results/hko_offset')]:
            shutil.copytree(source,analyses/name/'results')
        env=os.environ.copy();env['COMP3522_REPORT_ROOT']=str(output/'report');env['PYTHONIOENCODING']='utf-8'
        subprocess.run([sys.executable,str(analyses/'13_hko_offset_reframing/build_report.py')],env=env,check=True)
    finally:
        temporary.cleanup()
    subprocess.run([sys.executable,str(output/'verify_package.py')],check=True)
    # Record hashes of the rebuilt bundle rather than retaining the input manifest.
    manifest={'format':1,'scope':'rebuilt review package; raw observations and credentials excluded','files':{}}
    for path in sorted(output.rglob('*')):
        if path.is_file() and path!=output/'MANIFEST.json':
            data=path.read_bytes()
            manifest['files'][path.relative_to(output).as_posix()]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    (output/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Rebuilt report:',output/'report/deepening/index.html')

if __name__=='__main__':main()
