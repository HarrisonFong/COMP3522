from pathlib import Path
import json,hashlib,shutil,zipfile,re
import pandas as pd
HERE=Path(__file__).resolve().parent;R=HERE/'results'
MAIN=Path('Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors');DEST=MAIN/'deepening'
verify=json.loads((R/'verification.json').read_text(encoding='utf-8'));browser=json.loads((DEST/'qa/browser_verification.json').read_text(encoding='utf-8'));assert verify['passed'] and browser['passed']
metadata=json.loads((R/'metadata.json').read_text());metadata['current_script_sha256']=hashlib.sha256((HERE/'run_deepening.py').read_bytes()).hexdigest();metadata['post_run_code_change']='Only moved D3 audit outputs outside Git; numerical calculations unchanged. Original executed script hash retained in script_sha256.'
(R/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
for p in HERE.iterdir():
 if p.suffix in ['.py','.md','.cjs']:shutil.copy2(p,DEST/'code'/p.name)
for p in R.iterdir():
 if p.suffix in ['.csv','.json']:shutil.copy2(p,DEST/'results'/p.name)
text=(DEST/'index.html').read_text(encoding='utf-8');assert re.findall(r'<figcaption>圖 (\d+)｜',text)==list('123456')
groups=pd.read_csv(R/'group_means.csv');reg=pd.read_csv(R/'date_adjusted_regressions.csv')
checks={'numerical_verification':verify['passed'],'browser':browser['passed'],'cohorts':set(groups.cohort)=={'all','old30','lowland'},'four_targets':set(groups.target)=={'Tmax','Tmin','rain_event','rain_amount'},'four_urban_definitions':set(reg.urban_definition)=={'restricted','broad','footprint','height'},'region_and_district':{'region4_group','district_zh'}.issubset(set(groups.scheme)),'github_reconciliation':len(pd.read_csv(R/'old_coast_reconciliation.csv'))==6,'no_case_data_in_package':not list(DEST.rglob('*_D3_audit*'))}
assert all(checks.values()),checks
hashes={str(p.relative_to(DEST)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file() and p.name!='completion_audit.json'}
audit={'passed':True,'checks':checks,'files_sha256':hashes,'original_report_update':'Added one navigation callout only; previous original is index_before_deepening.html. Earlier original-report completion hashes refer to that version.','main_report_sha256':hashlib.sha256((MAIN/'index.html').read_bytes()).hexdigest()}
(DEST/'qa/completion_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
archive=MAIN.parent/'COMP3522_Geographic_Deepening_Evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(MAIN.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(MAIN.parent)))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert json.loads(z.read('COMP3522_Geographic_Factors/deepening/qa/browser_verification.json'))['passed']
print(json.dumps({'passed':True,'checks':checks,'zip_bytes':archive.stat().st_size,'html':str(DEST/'index.html')},ensure_ascii=False))
