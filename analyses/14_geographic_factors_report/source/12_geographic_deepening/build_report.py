from pathlib import Path
import json,re,base64,shutil,html,zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];R=HERE/'results';PREV=HERE.parent/'11_geographic_factors/results'
MAIN=Path('Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors');DEST=MAIN/'deepening';DEST.mkdir(exist_ok=True)
FIG=DEST/'figures';FIG.mkdir(exist_ok=True)
font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams.update({'font.family':['Microsoft JhengHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white'})
def read(n):return pd.read_csv(R/(n+'.csv'))
S=read('station_definitions');O=read('station_outcomes');G=read('group_means');C=read('matched_contrasts');F=read('factor_correlations');A=read('date_adjusted_regressions');P=read('outcome_correlations')
COHORT={'all':'保留全部山站','old30':'只剔除 TC／TMS','lowland':'剔除全部 ≥300 m 站'}
URBAN={'urban_restricted':'較窄土地用途','urban_broad':'較廣土地用途','urban_footprint':'建築覆蓋率','urban_height':'建築高度強度'}
REG={'HKI':'港島','KL':'九龍','NT':'新界（不含離島區）','Islands':'離島區'}
LAB={'elevation_m':'海拔','log_coast_km':'海岸距離 log','restricted_fraction_500m':'較窄開發比例','slope_deg':'坡度','tpi_z_500m':'TPI z','relief_500m':'局部高差','developed_fraction_500m':'較廣開發比例','building_cover_500m':'建築覆蓋率','log_height_intensity':'高度強度 log'}
def table(df,digits=3):return '<div class="tablewrap">'+df.to_html(index=False,border=0,escape=True,float_format=lambda x:f'{x:.{digits}f}',na_rep='—')+'</div>'
def savefig(n):plt.savefig(FIG/(n+'.png'),dpi=180,bbox_inches='tight');plt.close()
def fig(n,cap):return '<figure><img src="data:image/png;base64,'+base64.b64encode((FIG/(n+'.png')).read_bytes()).decode()+'" alt="'+html.escape(cap)+'"><figcaption>'+cap+'</figcaption></figure>'
def interval(r):return f'{r.difference:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]'

# 1: Different x ranges explicitly labelled, avoiding a mountain-driven linear claim.
fig1,axs=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
for i,target in enumerate(['Tmax','Tmin']):
 for j,cohort in enumerate(['all','lowland']):
  q=O[O.target.eq(target)].merge(S,on='station_code');q=q if cohort=='all' else q[q.elevation_m.lt(300)];ax=axs[i,j]
  sc=ax.scatter(q.elevation_m,q.loss,c=q.coast_distance_m/1000,cmap='viridis',vmin=0,vmax=S.coast_distance_m.max()/1000,s=40,edgecolors='white')
  for r in q.itertuples():
   if cohort=='all' and r.elevation_m>=300 or cohort=='lowland' and (r.elevation_m>100 or r.loss>2):ax.annotate(r.station_code,(r.elevation_m,r.loss),xytext=(4,-12 if r.station_code=='NGP' and target=='Tmin' else 4),textcoords='offset points',fontsize=8)
  row=P[P.target.eq(target)&P.cohort.eq(cohort)&P.urban_definition.eq('restricted')&P.feature.eq('elevation_m')].iloc[0]
  ax.set_title(f'{target} · '+('全部 32 站' if cohort=='all' else '低海拔 29 站')+f'\nPearson r={row.pearson:.3f}；Spearman ρ={row.spearman:.3f}');ax.set_xlabel('站點地面海拔（m）');ax.set_ylabel('逐站 D3 MAE（°C）');ax.grid(alpha=.15)
fig1.colorbar(sc,ax=axs,shrink=.7,label='海岸距離（km）');savefig('01_elevation_scatter')
# 2: Lowland means.
fig2,axs=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
for ax,target in zip(axs,['Tmax','Tmin']):
 q=G[G.target.eq(target)&G.cohort.eq('lowland')&G.scheme.eq('elev_detail')].set_index('group').loc[['lt20','20to50','50to300']]
 ax.bar(range(3),q.loss,color=['#23679b','#108979','#dd9531']);ax.set_xticks(range(3),['<20 m\nn=11','20–<50 m\nn=9','50–<300 m\nn=9']);ax.set_ylabel('D3 MAE（°C）');ax.set_title(target)
 for i,v in enumerate(q.loss):ax.text(i,v+.025,f'{v:.3f}',ha='center')
 ax.set_ylim(0,2.1);ax.grid(axis='y',alpha=.15)
savefig('02_lowland_bins')
# 3: Repeated cohort comparison, same estimator, same source snapshot.
fig3,axs=plt.subplots(1,2,figsize=(11,4.3),constrained_layout=True)
for ax,target in zip(axs,['Tmax','Tmin']):
 q=C[C.target.eq(target)&C.scheme.eq('coast_group')].set_index('cohort').loc[['all','old30','lowland']]
 ax.errorbar(q.difference,range(3),xerr=np.vstack([q.difference-q.ci_low,q.ci_high-q.difference]),fmt='o',capsize=4,color='#108979');ax.set_yticks(range(3),['全部 32 站','排除 TC／TMS：30 站','全部 <300 m：29 站']);ax.invert_yaxis();ax.axvline(0,color='#777',lw=1);ax.set_title(target);ax.set_xlabel('內陸 − 近海：D3 MAE 差（°C）');ax.grid(axis='x',alpha=.15)
savefig('03_mountain_coast')
# 4: Definition sensitivity, identical lowland parent population.
fig4,axs=plt.subplots(1,2,figsize=(12,4.4),constrained_layout=True)
for ax,target in zip(axs,['Tmax','Tmin']):
 q=C[C.target.eq(target)&C.cohort.eq('lowland')&C.scheme.isin(URBAN)].set_index('scheme').loc[list(URBAN)]
 ax.errorbar(q.difference,range(4),xerr=np.vstack([q.difference-q.ci_low,q.ci_high-q.difference]),fmt='o',capsize=4,color='#23679b');ax.axvline(0,color='#777',lw=1);ax.set_yticks(range(4),list(URBAN.values()));ax.invert_yaxis();ax.set_title(target);ax.set_xlabel('低城市化組 − 高城市化組：MAE 差（°C）');ax.grid(axis='x',alpha=.15)
savefig('04_urban_definition')
# 5: Correlations between geographic variables, one station per row.
fig5,axs=plt.subplots(1,2,figsize=(15,7),constrained_layout=True)
cols=list(LAB)
for ax,cohort in zip(axs,['all','lowland']):
 q=F[F.cohort.eq(cohort)&F.method.eq('spearman')].pivot(index='feature_a',columns='feature_b',values='correlation').loc[cols,cols]
 im=ax.imshow(q,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(9),list(LAB.values()),rotation=55,ha='right',fontsize=8);ax.set_yticks(range(9),list(LAB.values()),fontsize=8);ax.set_title('全部 32 站' if cohort=='all' else '低海拔 29 站')
 for i in range(9):
  for j in range(9):ax.text(j,i,f'{q.iloc[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if abs(q.iloc[i,j])>.65 else '#152d43')
fig5.colorbar(im,ax=axs,shrink=.7,label='Spearman ρ');savefig('05_factor_correlations')
# 6: Regression sensitivity; one SD in same 29 sites for both variants.
fig6,axs=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
features=['elevation_m','log_coast_km','restricted_fraction_500m']
for ax,target in zip(axs,['Tmax','Tmin']):
 for off,region,color,label in [(-.13,False,'#23679b','六個地理特徵'),(.13,True,'#dd9531','再控制四大區')]:
  q=A[A.target.eq(target)&A.cohort.eq('lowland')&A.urban_definition.eq('restricted')&A.region_adjustment.eq(region)].set_index('feature').loc[features]
  ax.errorbar(q.coefficient,np.arange(3)+off,xerr=np.vstack([q.coefficient-q.ci_low,q.ci_high-q.coefficient]),fmt='o',capsize=4,color=color,label=label)
 ax.set_yticks(range(3),[LAB[f] for f in features]);ax.invert_yaxis();ax.set_title(target+'・低海拔 29 站');ax.axvline(0,color='#777',lw=1);ax.set_xlabel('特徵增加 1 個站點 SD 的條件 MAE 變化（°C）');ax.grid(axis='x',alpha=.15)
axs[0].legend(fontsize=8,loc='lower left');savefig('06_joint_region')

old=read('old_coast_reconciliation');bridge=[]
for target in ['Tmax','Tmin']:
 qq=old[old.target.eq(target)].set_index('group');bridge.append({'變量':target,'比較':'舊 30 站：各站全部有效日均值之差','內陸−近海 MAE 差 °C':qq.loc['inland','old_mae']-qq.loc['near','old_mae']})
 for cohort in ['old30','all','lowland']:
  rr=C[C.target.eq(target)&C.cohort.eq(cohort)&C.scheme.eq('coast_group')].iloc[0];bridge.append({'變量':target,'比較':COHORT[cohort]+'：同日站對差','內陸−近海 MAE 差 °C':rr.difference})
mount=S[S.elevation_m.ge(300)][['station_code','name_zh','elevation_m','rain_candidate']].rename(columns={'station_code':'站碼','name_zh':'站名','elevation_m':'地面海拔 m','rain_candidate':'具本輪雨量資料'})
mount['具本輪雨量資料']=mount['具本輪雨量資料'].map({True:'有',False:'無'})
lowcounts=[]
for scheme in ['elev_detail','elev_fine','elev_tertiles']:
 q=S[S.elevation_m.lt(300)]
 for label,d in q.groupby(scheme):lowcounts.append({'方案':scheme,'組別':label,'站數':len(d),'站點':'; '.join(d.station_code)})
ut=[]
for scheme in URBAN:
 for cohort,condition in [('all',S.elevation_m.ge(0)),('lowland',S.elevation_m.lt(300))]:
  q=S[condition];counts=q[scheme].value_counts();ut.append({'定義':URBAN[scheme],'站群':COHORT[cohort],'低':counts.get('low',0),'混合':counts.get('mixed',0),'高':counts.get('high',0)})
lowcon=C[C.cohort.eq('lowland')&C.scheme.eq('elev_detail')].copy();lowcon['差值 [95% 區間]']=lowcon.apply(interval,axis=1)
rain=C[C.target.str.startswith('rain')&C.scheme.eq('coast_group')&C.cohort.isin(['all','lowland'])].copy();rain['差值 [95% 區間]']=rain.apply(interval,axis=1);rain['站群']=rain.cohort.map(COHORT)
reggroups=G[G.scheme.eq('region4_group')&G.target.isin(['Tmax','Tmin'])&G.cohort.isin(['all','lowland'])].copy();reggroups['區域']=reggroups.group.map(REG);reggroups['站群']=reggroups.cohort.map(COHORT)
pc=P[P.urban_definition.eq('restricted')&P.cohort.isin(['all','lowland'])&P.target.isin(['Tmax','Tmin'])&P.feature.isin(['elevation_m','log_coast_km','restricted_fraction_500m'])].copy();pc['因素']=pc.feature.map(LAB);pc['站群']=pc.cohort.map(COHORT)

body='''<header><div class="eyebrow">COMP3522 · 深化分析 · 2026-11-14</div><h1>低海拔、城市化定義與多因素關聯</h1><p class="lead">把山站保留／剔除並排比較，說清楚地理因素怎樣定義，以及這次與既有 GitHub 研究的分別。</p><div class="badges"><span>32 → 30 → 29 氣溫站</span><span>4 種城市化定義</span><span>四大區＋18 區</span><span>相關＋偏相關＋同日回歸</span></div></header><nav><a href="../index.html">原始完整報告</a><a href="#altitude">A 海拔深化</a><a href="#mountains">保留／剔除山站</a><a href="#urban">城市化與分區</a><a href="#joint">因素合併分析</a><a href="#previous">與過往研究比較</a><a href="#sources">來源與證據</a></nav><main>
<section><div class="eyebrow">這次的新結論</div><h2>「山站不同」不等於「低海拔內越高越不準」。</h2><div class="cards"><article><h3>低海拔沒有同樣的單調趨勢</h3><p>全部 32 站的海拔與 Tmax MAE Pearson r 為 0.928；只看 29 個低海拔站變成 −0.151。低海拔三組的 MAE 並非隨高度一路上升。</p></article><article><h3>海岸差異不是全由山站造成</h3><p>同日配對的 Tmax 內陸−近海差，由全部站 +1.779°C，降至只刪 TC/TMS 的 +1.033°C，再降至全部低海拔的 +0.715°C，仍大於零。</p></article><article><h3>城市化結論對定義敏感</h3><p>較窄土地用途、較廣土地用途、建築覆蓋、樓高強度會把不同站分到不同組。部分結果反向；控制行政分區後，Tmax 的條件關聯也會反向。</p></article></div><p class="callout">本輪沿用同一份公共預報。氣溫是 2022–2025 D3 的地方吻合程度；雨量是 2025 D3 的研究 PSR 映射基準。沒有把同一公共預報改稱為各站自己的預報，也沒有把相關性當作因果。</p></section>
<section id="altitude"><div class="eyebrow">A / 海拔深化</div><h2>先說清楚高度，再分析低海拔內部。</h2><h3>1，定義與結論</h3><p>本研究的海拔是<strong>站址地面高於平均海平面的高度</strong>，不是風速計高度、測溫儀離地高度或建築物高度。<a href="https://my.weather.gov.hk/en/cis/stn.htm">HKO 站點表</a>提供這個欄位。原本 &lt;300／300–&lt;700／≥700 m 是研究採用的操作門檻；不是本研究查證到的 HKO 官方氣候分區。</p><p>只有三個中高海拔站具本次完整期氣溫資格；因此不能把 2 個中海拔站和 1 個高海拔站，當成兩個具代表性的母群。</p>'''+table(mount)+'''<p>低海拔 29 站的高度實際為 4–142 m；其中 100–&lt;300 m 只有荃灣 TWN 一站。若直接分 &lt;100／100–&lt;200／200–&lt;300 m，會出現單站組及空組，無法得到穩健的三組比較。</p><h3>2，用了什麼數據和計算</h3><p>這次另採容易解釋的 &lt;20／20–&lt;50／50–&lt;300 m，分別 11／9／9 站。門檻是探索性研究選擇，不是看誤差後最佳化。另保留四細組的覆蓋檢查，以及只按高度排序的三等分（切點 15.33、38.67 m）作敏感度；連續高度仍保留，不只依賴分組。</p>'''+fig('01_elevation_scatter','圖 1｜每點一個 AWS，縱軸為 2022–2025 D3 的逐站 MAE；右欄放大低海拔範圍，兩欄橫軸尺度不同。顏色由近海到內陸漸變，只作辨識，未作額外調整。Pearson 衡量線性關聯、Spearman 衡量排序關聯。全部站的高 Pearson 主要受三個山站拉動；各站日期不同，因此相關是描述性，非因果估計。')+fig('02_lowland_bins','圖 2｜29 個低海拔站按高度分三組，先算逐站 MAE 再組內等權。最高溫三組為 1.769、1.471、1.520°C；最低溫為 1.489、1.374、1.364°C。柱圖使用各站有效日，未假裝所有站共享日期；下表另列同日站對差及區塊區間。')+'''<h3>3，為什麼可以得到這個結論</h3><p>最低高度組的誤差反而較大，最高溫在中間組較小；所以全站的「海拔越高、誤差越大」不能直接外推到低海拔內。對同日站對比較，20–&lt;50 m 減 &lt;20 m 的 Tmax 差為 −0.297°C，50–&lt;300 m 減 &lt;20 m 為 −0.252°C。但兩組也有不同海岸、城市化與區域組成，這些差不能單獨歸因於海拔。</p>
<details><summary>低海拔配對結果：氣溫與降雨，以及全部分組站名</summary>'''+table(lowcon[['target','contrast','差值 [95% 區間]','n_a','n_b','min_common_dates','max_common_dates','period']])+table(pd.DataFrame(lowcounts))+'''<p>lt20=&lt;20 m；20to50=20–&lt;50 m；50to300=50–&lt;300 m。Tmax／Tmin 單位 °C；rain_event 為 Brier 差；rain_amount 為研究毫米量 MAE 差。雨量低海拔為 18 站，三組 7／5／6；其差值區間沒有支持同樣清楚的高度排序。</p></details><p class="note">不能據此證明低海拔「沒有海拔效應」。多因素回歸中加入行政分區會改變高度係數，說明低海拔內的關聯對控制方式敏感。第 D 節完整呈現這項結果。</p></section>'''
body+='''<section id="mountains"><div class="eyebrow">B / 保留山站與 REMOVE 的比較</div><h2>三種站群，固定相同比較方法。</h2><p>① 全部 32 站；② 舊版只移除 TC、TMS，剩 30 站，<strong>仍有昂坪 NGP 593 m</strong>；③ 再移除 NGP，才是全部 &lt;300 m 的 29 站。雨量因沒有 NGP，對應為 20／18／18 站。</p><p><b>結論：</b>山站放大了內陸與近海的氣溫差距，但不是差距的全部來源。<b>方法：</b>對每個跨組站對，取共同有效日期的 D3 絕對誤差差，再對站對等權平均；同一天的所有站共同抽樣，14 日區塊、2,000 次。</p>'''+fig('03_mountain_coast','圖 3｜三種站群使用同一資料快照、同一 D3 定義與同一站對估計量。正值＝內陸 MAE 較大；線為固定站點的 95% 時間區塊區間。刪站改變研究站群與站對支持日期，不是將同一群站的天氣重新生成，也不是海拔因果效應的分解。')+'''<p><b>推論邏輯：</b>低海拔 Tmax 差 +0.715°C（0.602–0.821），Tmin +0.642°C（0.514–0.767），區間仍高於零。因此「內陸較不吻合」在這批低海拔站仍有證據。不能把 1.779−0.715 直接稱為海拔的獨立貢獻比例。</p>
<h3>降雨同樣保留／剔除，但結論較弱</h3>'''+table(rain[['target','站群','差值 [95% 區間]','n_a','n_b']])+'''<p>rain_event 是用既有訓練期 PSR 分類事件頻率預測地方 ≥10 mm；rain_amount 是 PSR 分類中位數預測地方毫米量。這裡只改評估站群，<strong>基準模型保持原擬合版本</strong>。低海拔的事件及毫米量差區間均跨零，不能沿用氣溫的強度作雨量結論。</p>
<details><summary>區分「改評估站群」與「刪山站後重新訓練」</summary><p>前一輪已另外做低海拔模型重訓，並與保留山站的模型在<strong>相同低海拔 2025 測試 cases</strong>評分。這回答訓練時是否保留山站，與上面改變地理站群的描述問題不同。</p>__REFIT__<p>loss 是低海拔重訓模型；primary_on_same_cases 是全站訓練模型在相同低海拔測試個案的分數；difference=前者−後者。氣溫／毫米量為 MAE，事件為 Brier。參數沿用原設定，這是敏感度，不是新一輪測試集選模。</p></details></section>'''
refit=pd.read_csv(PREV/'geographic_model_sensitivity.csv');refit=refit[refit.variant.eq('lowland')&refit.method.isin(['linear_full','hgb_full'])];body=body.replace('__REFIT__',table(refit[['target','method','loss','primary_on_same_cases','difference','ci_low','ci_high']],4))
body+='''<section id="urban"><div class="eyebrow">C / 城市化定義與行政分區</div><h2>城市化不是只有一個量度方式。</h2><p>所有主定義均用站址周圍 500 m。有效陸地分母排除海／未分類、水塘、河道、魚塘及機場；因此不是完整圓形面積。土地用途來自 2023 raster；建築資料為 2026 快照。這是靜態代理，不是每年真實城市化變化。</p>
<div class="tablewrap"><table><thead><tr><th>定義</th><th>怎樣計算</th><th>分組門檻與意義</th></tr></thead><tbody><tr><td>較窄土地用途</td><td>住宅、商業、工業／倉儲、政府社區設施、道路鐵路港口、公用設施及墳場等指定代碼的面積 ÷ 有效陸地</td><td>&lt;20%、20–&lt;50%、≥50%；沿用研究門檻。不是官方的「高城市化」認證，也不是純不透水率。</td></tr><tr><td>較廣土地用途</td><td>上述再加入代碼 32 空地／康樂、53 空置／施工用地、54 其他</td><td>使用同一 20／50% 門檻，檢查對 numerator 定義的敏感度；公園和開放土地會令數值提高。</td></tr><tr><td>永久建築覆蓋率</td><td>Tower／Podium 建築足跡合併後，裁切至有效陸地面積 ÷ 有效陸地；重疊不重複計</td><td>沿用原站群經驗三分位：≤5.7477%、&gt;5.7477–≤13.6522%、&gt;13.6522%。刪山站後不重新切門檻。</td></tr><tr><td>建築高度強度</td><td>2 m 格點的最大已知建築高度（Top−Base）× 面積總和 ÷ 有效陸地</td><td>≤0.6512、&gt;0.6512–≤2.5700、&gt;2.5700 m；表示面積加權的幾何強度，不是平均樓高、人口或真正容積率。</td></tr></tbody></table></div>
<p>數值分類邊界用未四捨五入值；完整代碼及 building thresholds 隨證據包附上。規劃署明確把土地用途資料定位為概括描述，並非精密量算用途，因此 500 m 比例只作探索性代理。<a href="https://data.gov.hk/en-data/dataset/hk-pland-pland1-land-utilization-in-hong-kong-raster-grid/resource/b3e81da8-585b-4afc-b167-d696bd1774d9">官方資料說明</a></p>'''+table(pd.DataFrame(ut))+'''<h3>1，結論：定義會改變分組，甚至改變方向</h3><p>低海拔樣本採較廣定義時，「低開發」只剩坪洲 PEN、橫瀾島 WGL 兩站，高開發達 24 站。這時低組已高度帶有小島／近海特性，不能說它是一般低城市化地區的代表。</p><h3>2，數據與計算</h3><p>固定同一批低海拔站；只更換城市化標籤，對各定義的低組−高組計同日站對 MAE 差。另用連續比例替換多因素回歸中的 urban 欄位，避免只靠任意分組。</p>'''+fig('04_urban_definition','圖 4｜相同低海拔母站群、四種城市化定義，差值＝低組−高組。線為 14 日區塊 95% 區間；不同定義使站點組成和配對日期改變，不能把它視為同一估計量的四次獨立驗證。較廣土地用途的低組只有 PEN／WGL；Tmin 方向與其餘三種定義相反。')+'''<h3>3，為什麼支持這個結論</h3><p>Tmin 低−高差：較窄土地用途 +0.317°C、較廣 −0.341°C、建築覆蓋 +0.496°C、高度強度 +0.398°C。因此「城市化越高越準」過於簡化；合理結論是<strong>不同城市化構面和站群組成，與地方預報誤差的關聯不同</strong>。較窄土地用途與建築覆蓋的低海拔 Spearman ρ=0.798，與較廣土地用途只有 0.317，亦證明四種代理不能當作同一欄資料。</p>
<h3>行政分區：已新增，但不把分區當城市化</h3><p>按既有站址行政區對應，分港島、九龍、新界（扣除離島區）、離島區；另列 18 區。離島指行政離島區，並非所有地理島嶼：例如青衣仍在新界。大老山 TC 的既有站址落在黃大仙區，因此全站版九龍組包括山站；這本身正說明「九龍＝城市低地」不成立。</p>'''+table(reggroups[['target','站群','區域','n_stations','loss']].rename(columns={'target':'變量','n_stations':'站數','loss':'D3 MAE °C'}))+'''<p>低海拔港島／九龍／新界／離島為 5／5／16／3 站；18 區中多區只有一站。適合描述覆蓋及檢查地域混雜，不適合當成具代表性的 18 區天氣能力排行榜。完整同日區域對比和交叉站數見資料表。</p><details><summary>18 區低海拔氣溫明細</summary>__DISTRICTS__</details></section>'''
dd=G[G.cohort.eq('lowland')&G.scheme.eq('district_zh')&G.target.isin(['Tmax','Tmin'])][['target','group','n_stations','loss','stations']];body=body.replace('__DISTRICTS__',table(dd.rename(columns={'target':'變量','group':'行政區','n_stations':'站數','loss':'MAE °C','stations':'站碼'})))
body+='''<section id="joint"><div class="eyebrow">D / 把 FACTORS 合在一起</div><h2>分三層問：互相相關？與誤差相關？控制其他因素後呢？</h2><ol><li><b>因素對因素：</b>每站一行，算 Pearson 及 Spearman；不把重複站日當成獨立地理樣本。</li><li><b>因素對結果：</b>每站的平均 D3 損失，算單因素相關；再以 rank residual 計 partial Spearman，控制其餘五個連續特徵。逐站剔除範圍是影響敏感度，不是信賴區間。</li><li><b>同日多因素回歸：</b>同一天先扣除當日平均損失及平均特徵，等同日期固定效應。每一天等權，同日有效站等權，再同時放海拔、log 海岸距離、urban proxy、坡度、TPI、局部高差。另加入四大區作控制敏感度。</li></ol>'''+fig('05_factor_correlations','圖 5｜地理欄位的 Spearman 相關矩陣；左 32 站、右 29 個低海拔站。紅為同方向，藍為反方向，對角線為 1。每站只算一次；例如海拔與 TPI、坡度有重疊，而兩種土地用途定義並不等同。相關不代表其中一個因素可完全取代另一個，更不是因果。')+'''<details><summary>與氣溫誤差的單因素相關、偏相關和逐站剔除敏感度</summary>'''+table(pc[['target','站群','因素','pearson','spearman','partial_spearman','leave_one_min','leave_one_max']])+'''<p>偏相關控制其餘五個 predictor 的排序；使用逐站各自可用日均值，日期不同仍會影響結果。leave_one_min/max 是逐個移除站後的偏相關範圍，不是 95% 區間。</p></details>
<h3>同日回歸的具體模型</h3><p class="callout">Loss<sub>s,t</sub> = 當日共同項 α<sub>t</sub> + β₁海拔 + β₂log(1+海岸 km) + β₃城市化代理 + β₄坡度 + β₅TPI z + β₆局部高差 + ε<sub>s,t</sub></p><p>這是<strong>解釋誤差的關聯模型</strong>，不是預報未來天氣的測試。沒有放 station fixed effects，因為它會把所有不隨時間改變的地理因素一起吸收。係數的區間用整天共同抽樣的 14 日區塊 bootstrap；固定站群，沒有修正多重比較。日期固定效應可扣除當日共同變動，但不能消除未測量站址差異或非隨機缺失。</p>'''+fig('06_joint_region','圖 6｜只用低海拔 29 站，同時控制六個連續地理特徵；藍色未額外加行政區、橙色加入四大區。係數表示同一批低海拔站中 predictor 增加 1 個站點標準差時的條件 MAE 變化。正值＝誤差較大；線為 95% 時間區塊區間。加入區域後 Tmax 的城市化係數由負轉正，顯示結論對控制設計敏感。')+'''<h3>可以怎樣寫結論</h3><p><b>海岸：</b>低海拔 Tmax 的偏 Spearman ρ=0.520；同日回歸的海岸係數在加入區域前後都保持正值，約 +0.201／+0.183°C 每 1 SD。這比只看分組均值更支持海岸距離在這批站中仍有條件關聯。</p><p><b>海拔：</b>低海拔 Tmax 的單純 Pearson r=−0.151，六特徵回歸的高度係數為 +0.004°C／SD、區間跨零；加區域後變為 +0.072°C／SD。不能下「低海拔無影響」或「越高一定越差」的確定結論。</p><p><b>城市化：</b>低海拔 Tmax 的較窄開發比例係數，六特徵模型為 −0.059°C／SD；加四區後為 +0.028°C／SD。Tmin 則均為負值，但幅度由 −0.171 縮至 −0.060。這些結果應寫成模型條件下的關聯，而不是普遍城市化規律。</p><p>主要六特徵的 VIF 在全站約 1.31–3.44，低海拔約 1.14–4.21；代表有資訊重疊。VIF 不是因果識別證明，也不是低於某門檻就能消除混雜。完整 44 個回歸（含降雨、四種 urban 替換、站群及分區敏感度）全部保留。</p><details><summary>全部同日多因素係數</summary>__REGRESSIONS__</details><p class="note">氣溫使用 2022–2025，降雨用 2025 基準損失；單位不同，不可比較係數大小來說哪一種天氣更受地理影響。全站 Tmax within-date R² 約 0.431，低海拔六特徵模型約 0.058；這是樣本內空間誤差解釋比例，絕不是未來預報準確度。</p></section>'''
aq=A.copy();aq['feature']=aq.feature.map(lambda x:LAB.get(x,REG.get(x,x)));body=body.replace('__REGRESSIONS__',table(aq[['target','cohort','urban_definition','region_adjustment','feature','coefficient','ci_low','ci_high','n_stations']],4))
body+='''<section id="previous"><div class="eyebrow">E / 與既有研究的差異</div><h2>是延伸與重新對齊，不是推翻或冒充全新發現。</h2><div class="tablewrap"><table><thead><tr><th>既有研究</th><th>原本做了什麼</th><th>這次差別／保留什麼</th></tr></thead><tbody>
<tr><td><a href="https://github.com/JJChand/COMP3522/blob/main/analyses/09_geographic_temperature/results/findings.md">GitHub 09：全站海岸／四區</a></td><td>30 AWS，排除 TC/TMS、保留 NGP；2022–2025 D1–D9，原始公共預報。全有效日描述＋24 全站共同日敏感度。</td><td>先精確重現 30 站 D3 結果，再比較 32／30／29 站和同日站對估計量。近海較小的方向延續；新內容是山站影響、低海拔內部及多因素控制。</td></tr>
<tr><td><a href="https://github.com/JJChand/COMP3522/blob/main/analyses/09_geographic_temperature_v2/general_forecast/README.md">GitHub general forecast</a></td><td>30 站，2025，有修訂事件；同一事件的舊／新 MAE、修訂有用性 U、地理差距變化 C。Tmax 新預報內陸−近海約 1.035°C。</td><td>本次主分析是全部有效 D3 預報日，不限有修訂事件，也沒有用 U/C 取代 MAE。1.035 與本次 1.033 數字接近是不同估計量，不能當作精確重現。</td></tr>
<tr><td>本地既有分析 9 站／782 共同日</td><td>每組三站，排除 TC/TMS 後的共同日期；近海 WGL/SKW/KSC、過渡 SSP/SHA/HKS、內陸 SSH/TKL/YLP。Tmax 內陸−近海約 0.801°C。</td><td>本次保留全部合資格站，低海拔 29 站；站對各用交集而非九站共同集，不能沿用 0.801 當全站效果。</td></tr>
<tr><td>本地既有分析 10/multifactor</td><td>30 站，9 因素組／17 欄，含海拔海岸、建築、用地、座標、季節及發布時天氣文字；Ridge/boosting、drop-group、32 個地理組合與 Shapley。</td><td>「多因素」本來已有做。本輪新增 DTM 坡度／TPI／高差和雨量，本輪不加入季節；這次深化再聚焦低海拔、urban 定義及 date-fixed-effect 關聯，沒有宣稱首次做多因素。</td></tr>
<tr><td><a href="https://github.com/JJChand/COMP3522/blob/main/analyses/08_rq7_error_factors/results/findings.md">RQ7：天氣情況因素</a></td><td>降雨日、實測溫度變化、固定八站溫差、季節與文字情況，解釋 HKO 氣溫誤差／修訂；含分層、OLS、線性 SHAP。</td><td>它問「什麼天氣下誤差較大」，我們問「哪些地理環境的地方吻合不同」。實況雨量等為事後條件，不能直接當發布時可用 predictor；兩套 factor 意義不同，但可以互相補充。</td></tr></tbody></table></div>
<h3>數值對賬：先只改一件事</h3><p>從本次原始配對重新取舊 30 站，近海／過渡／內陸的兩種氣溫共 <strong>6 個 D3 MAE 均與舊結果一致</strong>（浮點差最大約 4.4×10⁻¹⁶°C）。因此差異不是基本 MAE 算錯；接著分開改「估計方法」和「站群」。</p>'''+table(pd.DataFrame(bridge))+'''<p>舊版各站全有效日均值之差：Tmax 1.050°C；同樣 30 站改成同日站對：1.033°C。再加回 TC/TMS：1.779°C；再限制全部 &lt;300 m：0.715°C。這條比較鏈可以在 PPT 解釋為何不同報告的海岸數字不同。</p><p class="note">GitHub 檔案已在本輪重新讀取並保存 blob SHA；不按檔案路徑猜誰是作者。兩個主研究及 RQ7 的來源快照隨包附上。原始 CSV 仍沿用此前版本，沒有假稱重新取得最新資料庫。</p></section>'''
body+='''<section id="sources"><div class="eyebrow">F / 相關資料、可再補強什麼</div><h2>已有資料先用好；新增資料要對應新的問題。</h2><div class="tablewrap"><table><thead><tr><th>相關因素／資料</th><th>目前狀態</th><th>能補什麼、仍要做什麼</th></tr></thead><tbody>
<tr><td>土地用途＋永久建築足跡／高度</td><td>已使用，且四種城市化定義已比較</td><td>分清「開發用途」、「實際建築覆蓋」、「垂直建築強度」；不能推算人口或直接量測城市熱島。</td></tr>
<tr><td><a href="https://essd.copernicus.org/articles/14/3835/2022/">Local Climate Zones 原始研究</a>／<a href="https://doi.org/10.5281/zenodo.6364594">公開 LCZ 資料</a></td><td>已找到來源，未加入本輪計算</td><td>約 100 m 全球地圖、名義年份 2018，結合建築形態與地表覆蓋。可抽取站點／500 m 類別比例，先檢查香港覆蓋及分類信心；不能直接把研究中的低／高開發組當成 LCZ。</td></tr>
<tr><td><a href="https://data.gov.hk/en-data/dataset/hk-censtatd-census_geo-2021-population-census-by-ssg">2021 人口普查小合併組</a></td><td>已找到 2,342 小區統計及分界；未作站點人口推算</td><td>可建立人口密度代理；500 m 圓與小區不重合，需說明面積／建築加權分配假設，不能拿行政區平均直接當站址人口。</td></tr>
<tr><td>植被比例、天空可視率、坡向／迎風程度</td><td>本輪未計算</td><td>植被可由已有土地用途代碼另外定義；天空可視率需建築／地形幾何；迎風程度需坡向與同時段風資料。不能因資料可能可取得，就當作已有證據。</td></tr></tbody></table></div>
<h3>檢查與重現</h3><p>已獨立核對 556 個分組摘要、116 個同日對比、288 個相關結果、44 個回歸的逐列加權最小平方法與每個模型 2,000 次區塊區間，以及 6 個舊海岸均值。驗證計算不等於驗證因果或站群代表性。</p><p><a class="button" href="../../COMP3522_Geographic_Deepening_Evidence.zip">下載本次深化證據包</a><a class="button secondary" href="code/README.md">方法／檔案索引</a><a class="button secondary" href="results/verification.json">獨立驗證</a></p><details><summary>全部結果 CSV 與定義</summary><ul>__FILES__</ul></details><p class="note">沒有修改原始資料或資料庫。HTML 圖片已內嵌，可單獨閱讀；CSV／程式連結需保留資料夾。大型來源及逐筆記錄留在原工作區，不放入分享包。本次所有結果仍屬探索性，區間固定現有站，未涵蓋新站抽樣、歷史地理變化及多重比較。</p></section></main><footer>COMP3522 · 地理因素深化 · 2026-11-14</footer>'''

body=body.replace('代碼 32 空地／康樂','代碼 32 休憩用地／康樂')
body=body.replace('<p class="note">不能據此證明低海拔', '<p>改用高度三等分時，Tmax 上組−下組仍為 −0.246°C（−0.319 至 −0.164）；但 Tmin 上組−下組為 −0.028°C（−0.096 至 0.039），區間跨零。這顯示低海拔細分也有門檻敏感度，尤其不能把 Tmin 的固定三組排序當成穩定規律。</p><p class="note">不能據此證明低海拔')
for folder in ['results','code','sources']:(DEST/folder).mkdir(exist_ok=True)
for p in R.iterdir():
 if p.suffix in ['.csv','.json']:shutil.copy2(p,DEST/'results'/p.name)
for p in HERE.iterdir():
 if p.suffix in ['.py','.md','.cjs']:shutil.copy2(p,DEST/'code'/p.name)
for p in (HERE/'sources').iterdir():shutil.copy2(p,DEST/'sources'/p.name)
for name in ['geography_specification.json','building_region_specification.json']:shutil.copy2(ROOT/'analysis/geographic-representativeness/results'/name,DEST/'results'/name)
shutil.copy2(PREV/'geographic_model_sensitivity.csv',DEST/'results/previous_model_sensitivity.csv')
links=''.join('<li><a href="results/'+p.name+'">'+p.name+'</a></li>' for p in sorted((DEST/'results').iterdir()));body=body.replace('__FILES__',links)
original=(MAIN/'index.html').read_text(encoding='utf-8');css=re.search(r'<style>(.*?)</style>',original,re.S).group(1)
(DEST/'index.html').write_text('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>COMP3522｜低海拔與多因素深化</title><style>'+css+'</style></head><body>'+body+'</body></html>',encoding='utf-8')
notice='<aside id="deepening-link" class="callout"><b>新增深化分析：</b>低海拔 29 站細分、保留／剔除山站、四種城市化定義、行政分區、多因素相關及與 GitHub 舊結果對賬。<a href="deepening/index.html">閱讀深化報告</a></aside>'
if 'id="deepening-link"' not in original:
 shutil.copy2(MAIN/'index.html',MAIN/'index_before_deepening.html')
 original=original.replace('<section id="factors">','<section id="factors">'+notice)
 (MAIN/'index.html').write_text(original,encoding='utf-8')
archive=MAIN.parent/'COMP3522_Geographic_Deepening_Evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(MAIN.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(MAIN.parent)))
print(json.dumps({'html':str(DEST/'index.html'),'zip':str(archive),'figures':len(list(FIG.glob('*.png')))},ensure_ascii=False))
