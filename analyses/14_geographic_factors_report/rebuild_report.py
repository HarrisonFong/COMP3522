"""Rebuild the reviewed HTML and figures from included summaries, without raw data."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys,tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New output directory; must not already exist')
    args=parser.parse_args();bundle=Path(__file__).resolve().parent;output=args.output.resolve()
    if output.exists():parser.error('Output already exists; choose a new directory')
    shutil.copytree(bundle/'report',output)
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
        env=os.environ.copy();env['COMP3522_REPORT_ROOT']=str(output);env['PYTHONIOENCODING']='utf-8'
        subprocess.run([sys.executable,str(analyses/'13_hko_offset_reframing/build_report.py')],env=env,check=True)
    finally:
        temporary.cleanup()
    print('Rebuilt report:',output/'deepening/index.html')

if __name__=='__main__':main()
