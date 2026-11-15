"""Research narrative: elevation -> coast -> HKO offsets -> residual geography."""
from pathlib import Path
import base64,html,json,shutil,re,os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent;R=HERE/'results';PREV=HERE.parent/'12_geographic_deepening/results'
MAIN=Path(os.environ['COMP3522_REPORT_ROOT']);DEST=MAIN/'deepening'
FIG=DEST/'figures';FIG.mkdir(parents=True,exist_ok=True)
if Path('C:/Windows/Fonts/msjh.ttc').exists():font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc')
report_fonts=[f for f in ['Microsoft JhengHei','Noto Sans CJK TC','DejaVu Sans'] if f in {item.name for item in font_manager.fontManager.ttflist}]
plt.rcParams.update({'font.family':report_fonts,'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
read=lambda n:pd.read_csv(R/(n+'.csv'))
S=read('station_definitions');B=read('benefits');C=read('coast_contrasts');A=read('adjusted_geo_regressions')
O=pd.read_csv(PREV/'station_outcomes.csv');G=pd.read_csv(PREV/'group_means.csv');P=pd.read_csv(PREV/'outcome_correlations.csv');OLDCOAST=pd.read_csv(PREV/'matched_contrasts.csv')
assert json.loads((R/'verification.json').read_text(encoding='utf-8'))['passed']
def table(d):return '<div class="scroll">'+d.to_html(index=False,border=0,float_format=lambda x:f'{x:.3f}',escape=True)+'</div>'
def figsave(n):plt.savefig(FIG/(n+'.png'),dpi=170,bbox_inches='tight');plt.close()
def fig(n,cap):return '<figure><img src="data:image/png;base64,'+base64.b64encode((FIG/(n+'.png')).read_bytes()).decode()+'" alt="'+html.escape({'13_01_altitude':'海拔與逐站預報誤差散點圖','13_02_lowland':'低海拔三組的預報誤差比較','13_03_raw_coast':'移除高站前後的原始海岸差異','13_04_offset_effect':'地方校正前後的平均絕對誤差','13_05_adjusted_coast':'地方校正前後的海岸差異','13_06_geo_after_offset':'多因素分析的關聯係數比較'}.get(n,'研究結果圖表'))+'"><figcaption>'+cap+'</figcaption></figure>'
def b(target,cohort='low29',lead='D1-D9'):return B[B.target.eq(target)&B.cohort.eq(cohort)&B.lead.eq(lead)].iloc[0]
def c(target,version,cohort='low29'):return C[C.target.eq(target)&C.cohort.eq(cohort)&C.lead.eq(3)&C.version.eq(version)].iloc[0]
def interval(r):return f'{r.difference:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}]'

# Replot source data so all altitude labels consistently use the new 200 m cutoff.
f,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for i,t in enumerate(['Tmax','Tmin']):
 for j,cohort in enumerate(['all','lowland']):
  q=O[O.target.eq(t)].merge(S,on='station_code');q=q if cohort=='all' else q[q.elevation_m.lt(200)];ax=axes[i,j]
  im=ax.scatter(q.elevation_m,q.loss,c=q.coast_distance_m/1000,cmap='viridis',vmin=0,vmax=S.coast_distance_m.max()/1000,s=45,edgecolors='white')
  for row in q.itertuples():
   if row.elevation_m>=200 or row.station_code=='TWN':ax.annotate(row.station_code,(row.elevation_m,row.loss),xytext=(3,5),textcoords='offset points',fontsize=8)
  r=P[P.target.eq(t)&P.cohort.eq(cohort)&P.urban_definition.eq('restricted')&P.feature.eq('elevation_m')].iloc[0]
  ax.set_title(f'{t} · '+('全部 32 站' if j==0 else '0–<200 m：29 站')+f'\nr={r.pearson:.3f}；ρ={r.spearman:.3f}');ax.set_xlabel('站址海拔（m）');ax.set_ylabel('逐站 D3 MAE（°C）');ax.grid(alpha=.15)
f.colorbar(im,ax=axes,shrink=.75,label='海岸距離（km）');figsave('13_01_altitude')
f,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for ax,t in zip(axes,['Tmax','Tmin']):
 q=G[G.target.eq(t)&G.cohort.eq('lowland')&G.scheme.eq('elev_detail')].set_index('group').loc[['lt20','20to50','50to300']]
 ax.bar(range(3),q.loss,color=['#32638a','#248573','#cf983b']);ax.set_xticks(range(3),['<20 m\nn=11','20–<50 m\nn=9','50–<200 m\nn=9']);ax.set_title(t);ax.set_ylim(0,2.1);ax.set_ylabel('D3 MAE（°C）')
 for i,v in enumerate(q.loss):ax.text(i,v+.03,f'{v:.3f}',ha='center')
figsave('13_02_lowland')
f,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
for ax,t in zip(axes,['Tmax','Tmin']):
 q=OLDCOAST[OLDCOAST.target.eq(t)&OLDCOAST.scheme.eq('coast_group')].set_index('cohort').loc[['all','lowland']]
 ax.errorbar(q.difference,range(2),xerr=[q.difference-q.ci_low,q.ci_high-q.difference],fmt='o',capsize=4,color='#32638a');ax.set_yticks(range(2),['全部 32 站','低海拔 29 站']);ax.set_ylim(1.45,-.45);ax.axvline(0,color='#888');ax.set_xlabel('內陸 − 近海 MAE（°C）');ax.set_title(t)
figsave('13_03_raw_coast')
f,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
for ax,t in zip(axes,['Tmax','Tmin']):
 q=B[B.target.eq(t)&B.lead.eq('D1-D9')].set_index('cohort').loc[['all32','low29']];x=np.arange(2)
 ax.bar(x-.18,q.raw_mae,width=.36,label='原始公共預報',color='#a5b5c4');ax.bar(x+.18,q.offset_mae,width=.36,label='HKO offset',color='#248573')
 for off,col in [(-.18,'raw_mae'),(.18,'offset_mae')]:
  for i,v in enumerate(q[col]):ax.text(i+off,v+.025,f'{v:.3f}',ha='center',fontsize=8)
 ax.set_xticks(x,['全部 32 站','低海拔 29 站']);ax.set_ylabel('D1–D9 MAE（°C）');ax.set_title(t);ax.set_ylim(0,2.35);ax.legend(fontsize=8)
figsave('13_04_offset_effect')
f,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
for ax,t in zip(axes,['Tmax','Tmin']):
 for off,v,color,label in [(-.1,'raw','#32638a','校正前'),(.1,'offset','#248573','HKO offset 後')]:
  q=C[C.target.eq(t)&C.lead.eq(3)&C.version.eq(v)].set_index('cohort').loc[['all32','low29']]
  ax.errorbar(q.difference,np.arange(2)+off,xerr=[q.difference-q.ci_low,q.ci_high-q.difference],fmt='o',capsize=3,color=color,label=label)
 ax.set_yticks(range(2),['全部 32 站','低海拔 29 站']);ax.set_ylim(1.45,-.45);ax.axvline(0,color='#888');ax.set_title(t);ax.set_xlabel('內陸 − 近海 MAE（°C）');ax.legend(fontsize=8)
figsave('13_05_adjusted_coast')
f,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
features=['elevation_m','log_coast_km','restricted_fraction_500m']
for ax,t in zip(axes,['Tmax','Tmin']):
 for off,v,region,color,label in [(-.18,'raw',False,'#a5b5c4','原始：六特徵'),(0,'offset',False,'#248573','offset 後：六特徵'),(.18,'offset',True,'#cf983b','offset 後：加四大區')]:
  q=A[A.target.eq(t)&A.cohort.eq('low29')&A.version.eq(v)&A.region_adjustment.eq(region)].set_index('feature').loc[features]
  ax.errorbar(q.coefficient,np.arange(3)+off,xerr=[q.coefficient-q.ci_low,q.ci_high-q.coefficient],fmt='o',capsize=3,color=color,label=label)
 ax.set_yticks(range(3),['海拔','log(1+海岸距離 km)','較窄開發比例']);ax.invert_yaxis();ax.axvline(0,color='#888');ax.set_title(t);ax.set_xlabel('每增加 1 個站間 SD 的 MAE 關聯（°C）');ax.legend(fontsize=8)
figsave('13_06_geo_after_offset')

mount=S[S.elevation_m.ge(200)][['station_code','name_zh','elevation_m','coast_group']].rename(columns={'station_code':'代碼','name_zh':'站名','elevation_m':'海拔 m','coast_group':'海陸組'})
alt=[]
for t in ['Tmax','Tmin']:
 q=O[O.target.eq(t)].merge(S[['station_code','elevation_m']],on='station_code');q['分組']=pd.cut(q.elevation_m,[0,200,700,np.inf],right=False,labels=['0–<200 m','200–<700 m','≥700 m'])
 for label,a in q.groupby('分組',observed=True):alt.append({'變量':t,'分組':label,'站數':len(a),'MAE °C':a.loss.mean(),'Bias °C':a.bias.mean()})
benefit=B[B.lead.eq('D1-D9')].copy();benefit['站群']=benefit.cohort.map({'all32':'全部 32 站','old30':'原研究 30 站（仍含昂坪）','low29':'低海拔 29 站'});benefit['改善的95%區間']=benefit.apply(lambda r:f'[{r.ci_low:.3f}, {r.ci_high:.3f}]',axis=1)
benefit=benefit[['target','站群','raw_mae','offset_mae','improvement','percent','改善的95%區間','improved_stations','worsened_stations']].rename(columns={'target':'變量','raw_mae':'原始 MAE','offset_mae':'校正後 MAE','improvement':'改善 °C','percent':'改善 %','improved_stations':'改善站數','worsened_stations':'變差站數'})
coastrows=[]
for t in ['Tmax','Tmin']:
 coastrows.append({'變量':t,'2022–25 原始／29站':interval(OLDCOAST[OLDCOAST.target.eq(t)&OLDCOAST.cohort.eq('lowland')&OLDCOAST.scheme.eq('coast_group')].iloc[0]),'2025 原始／29站':interval(c(t,'raw')),'2025 offset後／29站':interval(c(t,'offset'))})

# Narrative template keeps the report prose separate from chart generation.
H=read('hko_same_date_reference')
counts={t:int((q.raw_gap>0).sum()) for t,q in H.groupby('target')}
hko_check=f'<p>結果顯示，32 站中有 <strong>{counts["Tmax"]} 站的最高溫 MAE，以及 {counts["Tmin"]} 站的最低溫 MAE 高於 HKO</strong>；每站與 HKO 的比較使用 {H.n_dates.min()}–{H.n_dates.max()} 個共同有效日。換言之，這份公共預報在大多數站點的誤差，比它在 HKO 本身更大。<a href="results/hko_offset/hko_same_date_reference.csv">逐站配對結果</a></p>'
alt_table=pd.DataFrame(alt).pivot(index=['分組','站數'],columns='變量',values='MAE °C').reindex(['0–<200 m','200–<700 m','≥700 m'],level='分組').reset_index().rename(columns={'Tmax':'最高溫 MAE（°C）','Tmin':'最低溫 MAE（°C）'})
alt_table.columns.name=None
simple_benefit=[];simple_coast=[]
for target,label in [('Tmax','最高溫'),('Tmin','最低溫')]:
 for cohort,cohort_label in [('all32','全部 32 站'),('low29','低海拔 29 站')]:
  row=b(target,cohort);simple_benefit.append({'站群':cohort_label,'變量':label,'校正前 MAE（°C）':row.raw_mae,'校正後 MAE（°C）':row.offset_mae,'改善幅度':f'{row.percent:.1f}%'})
 simple_coast.append({'變量':label,'校正前差距（°C）':c(target,'raw').difference,'校正後差距（°C）':c(target,'offset').difference})
def validation_table(cohorts):
 frames=[]
 for cohort,label in cohorts:
  v=read('validation_selection').query('cohort == @cohort').pivot(index='method',columns='target',values='validation_mae').reindex(['raw','annual_mean','monthly_mean','monthly_median']).reset_index()
  v.insert(0,'站群',label);v['method']=v.method.map({'raw':'不校正','annual_mean':'全年平均溫差','monthly_mean':'月別平均溫差','monthly_median':'月別中位溫差'});frames.append(v)
 v=pd.concat(frames,ignore_index=True).rename(columns={'method':'校正方法','Tmax':'最高溫驗證 MAE（°C）','Tmin':'最低溫驗證 MAE（°C）'});v.columns.name=None
 return table(v)
content={
 'VALIDATION_TABLE':validation_table([('all32','全部 32 站'),('low29','低海拔 29 站')]),
 'LEGACY_VALIDATION_TABLE':validation_table([('old30','原研究 30 站（仍含昂坪）')]),
 'LEGACY_BENEFITS':table(benefit[benefit['站群'].str.contains('30 站')]),
 'ALTITUDE_TABLE':table(alt_table),
 'OFFSET_TABLE':table(pd.DataFrame(simple_benefit)),
 'COAST_TABLE':table(pd.DataFrame(simple_coast)),
 'HKO_CHECK':hko_check,
 'DETAILED_BENEFITS':table(benefit[~benefit['站群'].str.contains('30 站')]),
 'FIG1':fig('13_01_altitude','圖 1｜2022–2025 年提前三天（D3）的逐站 MAE。每點是一個站，越高代表誤差越大；顏色表示海岸距離。左邊含全部 32 站，右邊放大低海拔 29 站，橫軸尺度不同。高站的誤差明顯較大，但低海拔內沒有一致上升趨勢。圖中的 r 和 ρ 分別描述線性及排序關聯；各站使用自身有效日期。'),
 'FIG2':fig('13_02_lowland','圖 2｜2022–2025 年 D3，29 個低海拔站分成三個高度組，各有 11／9／9 站。柱高是先逐站計算、再對站等權平均的 MAE。兩種氣溫的誤差都沒有隨高度組別一致上升，因此不能把高站的結果直接套用到低地。'),
 'FIG3':fig('13_03_raw_coast','圖 3｜2022–2025 年 D3，比較全部 32 站與低海拔 29 站的內陸減近海 MAE 差；大於零表示內陸誤差較大。點表示估計值，橫線為 95% 日期重抽樣區間。低海拔子集已移除大老山、昂坪和大帽山，差距縮小但仍為正。各站對使用自身共同有效日。'),
 'FIG4':fig('13_04_offset_effect','圖 4｜2025 年 D1–D9，全部 32 站與低海拔 29 站的原始及 HKO 地方溫差校正後 MAE。柱越低越好；同一站群內，兩柱使用相同案例，並對站點及提前天數等權平均。低海拔仍有改善，顯示校正效果不只來自三個高站。'),
 'FIG5':fig('13_05_adjusted_coast','圖 5｜2025 年 D3，分別在全部 32 站與低海拔 29 站內，比較校正前後的內陸減近海 MAE 差。每個範圍的站群與站對共同日期保持一致；點越接近零，兩組差距越小，橫線為 95% 日期重抽樣區間。低海拔的 40 個站對各有 214–328 個共同日。校正後差距縮小，但沒有消失。'),
 'FIG6':fig('13_06_geo_after_offset','圖 6｜2025 年 D3、低海拔 29 站，同時考慮多個地理因素後的結果。點在零的右邊表示正向關聯，左邊表示負向；橫線跨過零，表示方向仍不明確。三種顏色分別為原始結果、校正後結果，以及校正後再加入四大區。各特徵統一尺度後比較，圖中展示三項，其餘地形因素同時納入；這些是關聯而非因果效果。')
}
from report_extensions import build as build_extensions
content.update(build_extensions(HERE,DEST,fig,table))
body=(HERE/'report_body.html').read_text(encoding='utf-8')
body=body.replace('@@REFERENCE_FIRST_SECTIONS@@',(HERE/'reference_first_sections.html').read_text(encoding='utf-8'))
for key,value in content.items():body=body.replace('@@'+key+'@@',value)
assert '@@' not in body
figure_order=iter(range(1,len(re.findall('<figcaption>',body))+1))
body=re.sub(r'(<figcaption>)圖 \d+｜',lambda m:m.group(1)+'圖 '+str(next(figure_order))+'｜',body)
css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2f5f7;color:#193247;font-family:"Microsoft JhengHei",sans-serif;line-height:1.85;font-size:16px}header,main,nav,footer{max-width:1160px;margin:auto}header{padding:64px 38px 42px}h1{font-size:44px;line-height:1.35;letter-spacing:-1px;margin:16px 0}h2{font-size:28px;line-height:1.5;margin:8px 0 22px}h3{font-size:19px;margin-top:28px;color:#146a62}.kicker{font-size:13px;letter-spacing:2px;text-transform:uppercase;color:#52778d}.lead{max-width:840px;font-size:20px;color:#496575}.tag{display:inline-block;padding:8px 14px;background:#dfece8;border-radius:8px;font-size:14px}nav{display:flex;gap:10px;flex-wrap:wrap;padding:12px 24px;border-top:1px solid #cddae0;border-bottom:1px solid #cddae0}a{color:#176d80;text-underline-offset:4px}nav a{padding:6px 10px;text-decoration:none}main{padding:28px 24px}section{background:white;padding:36px;margin:24px 0;border-radius:14px;box-shadow:0 5px 24px #17334706;scroll-margin-top:20px}aside,.callout{border-left:4px solid #248573;background:#e5f0ec;padding:22px 26px;border-radius:5px}figure{margin:28px 0;background:#fff;border:1px solid #e2e8ec;border-radius:8px;padding:12px}figure img{width:100%;height:auto;display:block}figcaption{font-size:14px;color:#4f6574;line-height:1.8;padding:12px 8px 4px}.scroll{width:100%;overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px 14px;border-bottom:1px solid #e1e7eb;text-align:left;min-width:90px}th{background:#edf3f6;white-space:nowrap}td{vertical-align:top}p,li{overflow-wrap:anywhere}li{margin:10px 0}.formula{padding:22px;background:#eef3f6;border-radius:8px;font-size:19px;line-height:2}summary{cursor:pointer;font-weight:bold;color:#176d80}details{padding:20px;border:1px solid #d8e3e8;border-radius:8px}footer{padding:20px 38px 50px;color:#6f8593;font-size:13px}@media(max-width:650px){header{padding:30px 22px}h1{font-size:30px}h2{font-size:24px}main{padding:12px}section{padding:22px 18px}nav{padding:10px 12px;font-size:14px}.lead{font-size:18px}figure{padding:4px}aside{padding:18px}td,th{padding:10px}body{font-size:15px}}@media print{nav{display:none}section{box-shadow:none;break-inside:auto}figure{break-inside:avoid}body{background:white}}'''
css+='details{margin:14px 0}section p{margin:18px 0}caption{color:#526978}.downloads{font-size:14px}@media print{header{padding:25px}section{padding:20px 0;margin:0;border-radius:0}details{break-inside:auto}}'
page='<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HKO 參考點、地方校正與地理差異｜COMP3522</title><style>'+css+'</style>'+body+'</html>'
index=DEST/'index.html';appendix=DEST/'technical_appendix.html'
notes=DEST/'evidence_notes.html'
if index.exists() and not notes.exists():shutil.copy2(index,notes)
if not appendix.exists() and index.exists():shutil.copy2(index,appendix)
# Scientific prose throughout the retained appendix and main parent report.
replacements={'是組員提出、研究採用的操作門檻':'是研究採用的操作門檻','沿用組員研究門檻':'沿用研究門檻','與你和組員之前的研究有何不同':'與既有研究的差異','你本機':'本地既有分析','按組員要求不加季節':'本輪不加入季節','組員 RQ7':'RQ7','如何接上組員的最新結果':'與既有結果的銜接'}
for path in [appendix,MAIN/'index.html',HERE.parent/'12_geographic_deepening/build_report.py',HERE.parent/'11_geographic_factors/build_report.py',HERE.parent/'10_geographical_methods/build_report.py']:
 if path.exists():
  text=path.read_text(encoding='utf-8')
  for old,new in replacements.items():text=text.replace(old,new)
  if path==appendix and 'id="current-version"' not in text:
   text=text.replace('<body>','<body><aside id="current-version" style="padding:20px;background:#e5f0ec">技術附錄保留前一版 2022–2025 原始地理分析及 300 m 門檻。<a href="index.html">最新主報告：200 m 定義、HKO offset 與 2025 校正前後比較</a>。兩個高度門檻在本樣本站群相同。</aside>')
  if path==MAIN/'index.html':text=text.replace('低海拔 29 站細分、保留／剔除山站、四種城市化定義、行政分區、多因素相關及與 GitHub 舊結果對賬。','低海拔 29 站細分、保留／移除高站、HKO 參考點 offset、校正前後海岸差異及多因素關聯。')
  path.write_text(text,encoding='utf-8')
index.write_text(page,encoding='utf-8')
destresults=DEST/'results/hko_offset';shutil.copytree(R,destresults,dirs_exist_ok=True)
for name in ['run_analysis.py','verify_analysis.py','build_report.py','qa_report.cjs','README.md','report_body.html','reference_first_sections.html','report_extensions.py','analyze_continuous_coast.py','compare_existing_ml.py']:
 target=DEST/'code/hko_offset'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE/name,target)
sources=[dict(url='https://www.info.gov.hk/gia/general/201202/22/P201202220231.htm',date='2012-02-22',supports='Government answer: HQ data historically used as indicator for weather reports and forecasts; not exclusive model input'),dict(url='https://my.weather.gov.hk/tc/index.html',accessed='2026-11-14',supports='Current-day max/min icon values at HKO; not full historical D1-D9 field documentation')]
(DEST/'sources/hko_reference_sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
print(index)
