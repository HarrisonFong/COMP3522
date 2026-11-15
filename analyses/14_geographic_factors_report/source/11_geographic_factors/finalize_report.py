"""Completion audit and final evidence archive, after browser verification."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
import pandas as pd
HERE=Path(__file__).resolve().parent;R=HERE/'results'
DEST=Path('Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors')
required=['independent_verification','summary_verification','terrain_verification','lowland_verification']
checks={k:json.loads((R/(k+'.json')).read_text())['passed'] for k in required}
checks['browser']=json.loads((DEST/'qa/browser_verification.json').read_text())['passed']
m=pd.read_csv(R/'method_metrics.csv');s=pd.read_csv(R/'station_factors.csv');d=pd.read_csv(R/'factor_drop_comparisons.csv');g=pd.read_csv(R/'geographic_means.csv')
targets={'Tmax','Tmin','rain_event','rain_amount'};factors={'elevation','coast','urban','terrain'}
checks['four_targets_two_designs']=set(m.target)==targets and all(set(q.design)=={'temporal','spatial'} for _,q in m.groupby('target'))
checks['all_four_factors']=all(s[f+'_group'].notna().all() for f in factors) and all(set(q.factor)==factors for _,q in d.groupby('target'))
checks['all_leads']=all(set(q.lead)==set(range(1,10)) for _,q in g.groupby(['target','factor']))
checks['simple_and_ml']=all({'station_mean','linear_full','hgb_full'}.issubset(set(q.method)) for _,q in m.groupby(['target','design']))
checks['sample_sizes']=len(s)==32 and int(s.rain_candidate.sum())==20
checks['uncertainty_and_sensitivity']=all((R/n).stat().st_size>100 for n in ['paired_method_differences.csv','method_intervals.csv','geographic_model_sensitivity.csv','geographic_label_sensitivity_D3.csv','coast_leave_one_station_out.csv','lowland_matched_contrasts_D3.csv'])
text=(DEST/'index.html').read_text(encoding='utf-8')
checks['captions_in_order']=re.findall(r'<figcaption>圖 (\d+)｜',text)==[str(x) for x in range(1,8)]
checks['format_and_assumptions']=all(x in text for x in ['1，結論','2，數據及計算','3，為何支持','額外假設','研究映射','同一份 HKO 公共預報'])
assert all(checks.values()),checks
for p in HERE.iterdir():
 if p.suffix in ['.py','.md','.cjs']:shutil.copy2(p,DEST/'code'/p.name)
for p in R.iterdir():
 if p.suffix in ['.csv','.json']:shutil.copy2(p,DEST/'results'/p.name)
hashes={str(p.relative_to(DEST)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='completion_audit.json'}
audit={'passed':True,'checks':checks,'scope':'All four prescribed geographic factors, both variables, simple means/medians and statistical/ML comparisons, temporal and spatial evaluation, interpretation and limitations, illustrated HTML and reproducibility evidence. Scientific uncertainty is explicitly retained.','html_sha256':hashlib.sha256((DEST/'index.html').read_bytes()).hexdigest(),'files_sha256':hashes}
(DEST/'qa/completion_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
archive=DEST.parent/'COMP3522_Geographic_Factors_Evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(DEST.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(DEST.parent)))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert json.loads(z.read('COMP3522_Geographic_Factors/qa/browser_verification.json'))['passed']
 assert hashlib.sha256(z.read('COMP3522_Geographic_Factors/index.html')).hexdigest()==audit['html_sha256']
print(json.dumps({'passed':True,'checks':checks,'files':len(hashes)+1,'zip_bytes':archive.stat().st_size,'html':str(DEST/'index.html')},ensure_ascii=False))
