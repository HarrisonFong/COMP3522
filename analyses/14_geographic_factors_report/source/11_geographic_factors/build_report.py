"""Build a portable Chinese research report from verified aggregate results."""
from pathlib import Path
import base64,json,html,shutil,zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; R=HERE/'results'
DEST=Path('Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors')
DEST.mkdir(parents=True,exist_ok=True); FIG=DEST/'figures';FIG.mkdir(exist_ok=True)
font=Path('C:/Windows/Fonts/msjh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=[font_manager.FontProperties(fname=str(font)).get_name(),'DejaVu Sans']
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'axes.unicode_minus':False,'figure.facecolor':'#ffffff','axes.facecolor':'#ffffff','savefig.facecolor':'#ffffff'})
def read(n):return pd.read_csv(R/(n+'.csv'))
M=read('method_metrics');G=read('geographic_means');S=read('station_factors');D=read('factor_drop_comparisons');L=read('lowland_matched_contrasts_D3');C=read('geographic_matched_contrasts_D3')
NAMES={'raw':'原始公共預報','global_mean':'全體平均校正／平均值','station_mean':'逐站平均','station_median':'逐站中位數','category_mean':'PSR 分類平均','category_median':'PSR 分類中位數','zero':'固定零雨量','linear_base':'線性／Logistic（無地理）','linear_full':'線性／Logistic＋地理','hgb_base':'Boosting（無地理）','hgb_full':'Boosting＋地理（80 輪）','hgb_long_full':'Boosting L1（500 輪）','hgb_squared_full':'Boosting L2（80 輪）','mean_elevation':'海拔分組平均','mean_coast':'海岸分組平均','mean_urban':'城市化分組平均','mean_terrain':'地形分組平均'}
FAC={'elevation':'海拔','coast':'海陸位置','urban':'城市化','terrain':'地形'}
LABEL={'elevation':{'low':'低海拔','mid':'中海拔','high':'高海拔'},'coast':{'near':'近海','transition':'過渡帶','inland':'內陸'},'urban':{'low':'低開發','mixed':'混合','high':'高開發'},'terrain':{'plain':'平坦／緩坡','valley':'谷地／凹地','slope':'山坡','ridge':'脊頂／凸地'}}
ORDER={'elevation':['low','mid','high'],'coast':['near','transition','inland'],'urban':['high','mixed','low'],'terrain':['plain','valley','slope','ridge']}
def savefig(name):
 plt.savefig(FIG/(name+'.png'),dpi=180,bbox_inches='tight');plt.close()
def figure(name,caption):
 b=base64.b64encode((FIG/(name+'.png')).read_bytes()).decode()
 return f'<figure><img src="data:image/png;base64,{b}" alt="{html.escape(caption)}"><figcaption>{caption}</figcaption></figure>'
def table(df):return '<div class="tablewrap">'+df.to_html(index=False,border=0,escape=True,float_format=lambda x:f'{x:.4f}',na_rep='—')+'</div>'
def modeltable(target,methods):
 q=M[(M.target==target)&M.method.isin(methods)].copy();q['method']=pd.Categorical(q.method,methods,ordered=True);q=q.sort_values(['design','method'])
 cols=['design','method']+(['brier','log_loss'] if target=='rain_event' else ['mae','rmse','bias'])
 q=q[cols];q['design']=q.design.map({'temporal':'已知站・2025','spatial':'未見地區・2025'});q['method']=q.method.astype(str).map(NAMES)
 return table(q.rename(columns={'design':'測試','method':'方法','mae':'MAE','rmse':'RMSE','bias':'Bias','brier':'Brier','log_loss':'Log loss'}))

# Figure 1: actual coordinates, no invented map/boundaries.
fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
sc=axs[0].scatter(S.longitude,S.latitude,c=S.elevation_m,cmap='viridis',s=65,edgecolors='white');fig.colorbar(sc,ax=axs[0],label='海拔 m')
colors={'plain':'#2563a6','valley':'#955fb3','slope':'#dc8e21','ridge':'#108979'}
for g in ORDER['terrain']:
 q=S[S.terrain_group==g];axs[1].scatter(q.longitude,q.latitude,s=65,color=colors[g],label=f'{LABEL["terrain"][g]} ({len(q)})')
for ax in axs:
 for r in S.itertuples():ax.annotate(r.station_code,(r.longitude,r.latitude),xytext=(3,4),textcoords='offset points',fontsize=6)
 ax.set_xlabel('經度');ax.set_ylabel('緯度');ax.set_aspect(1/np.cos(np.radians(22.3)));ax.grid(alpha=.15)
axs[0].set_title('32 個氣溫 AWS：站址與海拔');axs[1].set_title('同一批站址：500 m 地形代理分組');axs[1].legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.16),ncol=2)
savefig('01_station_factors')
# Figure 2 raw group means, explicitly descriptive available cases.
fig,axs=plt.subplots(1,4,figsize=(14,4.4),sharey=True,constrained_layout=True)
for ax,(factor,order) in zip(axs,ORDER.items()):
 for offset,target,color in [(-.18,'Tmax','#23679b'),(.18,'Tmin','#e39b32')]:
  q=G[(G.target==target)&G.factor.eq(factor)&G.lead.eq(3)].set_index('group').loc[order];x=np.arange(len(order))
  ax.bar(x+offset,q.mae,width=.34,label=target,color=color)
 counts=S[factor+'_group'].value_counts();ax.set_xticks(x,[LABEL[factor][g]+f'\nn={counts[g]}' for g in order],fontsize=8);ax.set_title(FAC[factor]);ax.grid(axis='y',alpha=.18)
axs[0].set_ylabel('原始公共預報 MAE（°C）');axs[0].legend();savefig('02_raw_groups')
# Figure 3 matched coastal differences all vs lowland.
fig,ax=plt.subplots(figsize=(9,3.8),constrained_layout=True)
for i,target in enumerate(['Tmax','Tmin']):
 for offset,df,label,color in [(-.13,C,'全部 32 站','#2563a6'),(.13,L,'低海拔 29 站','#108979')]:
  q=df[(df.target==target)&df.factor.eq('coast')&df.contrast.eq('near minus inland')].iloc[0];y=i+offset
  ax.errorbar(q.difference,y,xerr=[[q.difference-q.ci_low],[q.ci_high-q.difference]],fmt='o',capsize=4,color=color,label=label if i==0 else None)
ax.axvline(0,color='#777',lw=1);ax.set_yticks([0,1],['最高溫 Tmax','最低溫 Tmin']);ax.set_xlabel('近海 − 內陸：同日 D3 絕對誤差差（°C）；負值＝近海較小');ax.legend();ax.grid(axis='x',alpha=.15);savefig('03_coast_matched')
# Figure 4 model generalization.
fig,axs=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
methods=['raw','station_mean','station_median','linear_full','hgb_full'];short=['原始預報','逐站平均','逐站中位數','Ridge＋地理','Boosting＋地理']
for ax,target in zip(axs,['Tmax','Tmin']):
 for off,design,color,name in [(-.18,'temporal','#23679b','已知站'),(.18,'spatial','#e39b32','未見地區')]:
  q=M[M.target.eq(target)&M.design.eq(design)].set_index('method').loc[methods];ax.bar(np.arange(5)+off,q.mae,.34,label=name,color=color)
 ax.set_xticks(np.arange(5),short,rotation=25,ha='right');ax.set_title(target+'・2025');ax.set_ylabel('MAE（°C）');ax.grid(axis='y',alpha=.15)
axs[0].legend();savefig('04_temperature_models')
# Figure 5 multiobjective amount comparison.
fig,axs=plt.subplots(1,3,figsize=(13,5),constrained_layout=True)
methods=['zero','category_mean','category_median','station_median','hgb_full','hgb_long_full','hgb_squared_full'];labels=['固定零','PSR 平均','PSR 中位數','逐站中位數','Boosting L1 / 80','Boosting L1 / 500','Boosting L2 / 80']
q=M[M.target.eq('rain_amount')&M.design.eq('temporal')].set_index('method').loc[methods]
for ax,col in zip(axs,['mae','rmse','bias']):
 ax.barh(np.arange(len(q)),q[col],color=['#b7c1cc','#23679b','#108979','#108979','#c37e21','#e5af56','#7957a0']);ax.set_yticks(np.arange(len(q)),labels if col=='mae' else []);ax.invert_yaxis();ax.set_title(col.upper()+'（mm）');ax.axvline(0,color='#777',lw=.8);ax.grid(axis='x',alpha=.15)
savefig('05_rain_amount')
# Figure 6 drop factor; effects in each model, no causal interpretation.
fig,axs=plt.subplots(1,2,figsize=(12,4.4),constrained_layout=True)
for ax,target in zip(axs,['Tmax','Tmin']):
 for off,method,color,label in [(-.12,'linear_full','#23679b','Ridge'),(.12,'hgb_full','#108979','Boosting')]:
  q=D[D.target.eq(target)&D.method.eq(method)&D.block_days.eq(14)].set_index('factor').loc[list(FAC)]
  ax.errorbar(q.loss_increase_without_factor,np.arange(4)+off,xerr=np.vstack([q.loss_increase_without_factor-q.ci_low,q.ci_high-q.loss_increase_without_factor]),fmt='o',capsize=3,label=label,color=color)
 ax.set_yticks(np.arange(4),list(FAC.values()));ax.axvline(0,color='#777',lw=1);ax.set_title(target);ax.set_xlabel('移除該因素後 MAE 增量（°C）');ax.grid(axis='x',alpha=.15)
axs[0].legend();savefig('06_factor_increment')
# Figure 7 event precision-sensitive view; include uncertainty with no rank claim.
fig,axs=plt.subplots(1,2,figsize=(12,4.2),constrained_layout=True)
I=read('method_intervals');methods=['category_mean','station_mean','linear_full','hgb_full']
for ax,design,title in zip(axs,['temporal','spatial'],['已知站・2025','未見地區・2025']):
 q=I[I.target.eq('rain_event')&I.design.eq(design)&I.block_days.eq(14)].set_index('method').loc[methods]
 ax.errorbar(q.loss,np.arange(4),xerr=np.vstack([q.loss-q.ci_low,q.ci_high-q.loss]),fmt='o',capsize=4,color='#108979');ax.set_yticks(np.arange(4),[NAMES[m] for m in methods],fontsize=9);ax.invert_yaxis();ax.set_title(title);ax.set_xlabel('Brier score（越小越好）');ax.grid(axis='x',alpha=.15)
savefig('07_rain_event')

counts=read('group_station_counts');counts=counts[counts.target.isin(['Tmax','rain_event'])].copy();counts['target']=counts.target.map({'Tmax':'氣溫','rain_event':'降雨'});counts['類別']=counts.apply(lambda r:LABEL[r.factor][r.group],axis=1);counts['factor']=counts.factor.map(FAC)
ct=counts.pivot_table(index=['factor','類別'],columns='target',values='n_stations',aggfunc='first').reset_index();ct.columns.name=None
ev=read('rain_event_threshold_metrics');ev=ev[ev.design.eq('temporal')&ev.method.isin(['category_mean','hgb_full'])].copy();ev['method']=ev.method.map(NAMES)
evt=table(ev[['method','threshold','hit_rate','false_alarm_ratio','miss_rate','accuracy']].rename(columns={'method':'方法','threshold':'判雨門檻 p','hit_rate':'命中率 POD','false_alarm_ratio':'誤報比例 FAR','miss_rate':'漏報率','accuracy':'Accuracy'}))
low=L[L.factor.eq('coast')&L.contrast.eq('near minus inland')][['target','difference','ci_low','ci_high']]
fimgs=[
figure('01_station_factors','圖 1｜32 個氣溫 AWS 的實際經緯度分佈；其中 20 站可做降雨分析。左圖顏色是站點海拔，右圖是由 DTM 計算的地形代理。這是站址散點圖，未繪製行政區或海岸邊界；地形分組不等於行政區。'),
figure('02_raw_groups','圖 2｜2022–2025、D3 的原始公共氣溫預報 MAE。先算逐站 MAE，再在組內等權平均；柱越低表示與該組站點實測越接近。各站可用日期不同，因此這是描述性總覽，不能單憑柱高判定因素效應。圖 3 另用同日配對處理日期差異。n 是站數。'),
figure('03_coast_matched','圖 3｜近海與內陸站，每一對站只比較共同有效日期的 D3 絕對誤差，再對站對等權平均。點是差值，線是 14 日時間區塊 bootstrap 的 95% 區間。剔除中高海拔站後差距縮小但仍低於零，支持這批低海拔站也存在近海／內陸差異；不能證明海岸距離造成差異。'),
figure('04_temperature_models','圖 4｜2025 年 D1–D9：每個站 × lead 先計 MAE，再等權平均。藍色為已知站跨年測試；橙色為五個地理群逐群留出的未見地區測試。橙色「逐站」方法因沒有該站訓練歷史而退回訓練站的 lead 平均，並非真正逐站校正。所有方法在同一 target、同一設計使用相同測試記錄。'),
figure('05_rain_amount','圖 5｜PSR → 地方每日毫米量的研究模型，已知站 2025 測試。左：MAE；中：RMSE；右：預測 − 實測的 Bias。L1 是絕對誤差訓練，L2 是平方誤差訓練。L1 boosting 的 MAE 低於平均法，但低估雨量、RMSE 較大；加入中位數基準後，不能說 ML 整體勝出。這些不是天文台原生毫米量預報的誤差。'),
figure('06_factor_increment','圖 6｜每次移除一組地理特徵後重新訓練，其他設定固定，計算 2025 MAE 增量及 14 日區塊 95% 區間。正值表示該因素對此模型具有額外預測資訊；跨零表示證據未清楚。因素相互相關，增量不可相加成 100%，也不能解讀為因果貢獻。'),
figure('07_rain_event','圖 7｜地方日雨量 ≥10 mm 的研究事件模型，Brier score 及 14 日區塊 95% 區間。方法的點估計相近。應使用配對差值區間比較兩方法，不能只憑各自區間重疊與否判定差異。PSR 分類平均是訓練期分類／lead 的地方事件頻率，不把 PSR 文字硬編成官方地方機率。')]

body='''<header><div class="eyebrow">COMP3522 · PART 1 · 地理因素與方法比較</div><h1>哪些地區與公共預報更接近？<br>地理因素能否改善地方預測？</h1><p class="lead">Temperature × Rainfall｜海拔、海陸位置、城市化、地形<br>2022–2025 既有資料重分析 · 2026-11-14 完成</p><div class="badges"><span>32 氣溫站</span><span>20 降雨站</span><span>4 地理因素</span><span>簡單統計＋ML</span><span>跨年＋未見地區測試</span></div></header>
<nav><a href="#conclusion">結論</a><a href="#factors">四個因素</a><a href="#methods">數據與方法</a><a href="#models">方法比較</a><a href="#explore">互動結果</a><a href="#limits">假設與限制</a><a href="#evidence">證據與下載</a></nav>
<main><section id="conclusion"><div class="eyebrow">01 / 結論</div><h2>可以回答地區差異；但要區分「適用程度」與「模型能力」。</h2>
<p class="callout">現有主要預報是<strong>同一份 HKO 公共預報</strong>配對各站實測。因此，原始分析回答的是「這份預報在哪些站較接近實況」。加入地理資訊後的線性／ML 模型，則是本研究另外建立的地方校正或事件／雨量映射。</p>
<div class="cards"><article><h3>氣溫：地區差異有證據</h3><p>高海拔站的原始誤差較大。近海站在配對日期比較中較接近公共預報；只看低海拔站，最高／最低溫 MAE 差仍約為 −0.72／−0.64°C。</p></article><article><h3>城市化、地形：需要條件式結論</h3><p>分組平均存在差異，但剔除中高海拔站後部分排序改變。地形已有可計算的代理資料；不能把它當作已驗證的地貌分類，亦不能把組間差異直接稱為因果。</p></article><article><h3>ML：沒有全面勝出</h3><p>已知站的逐站平均／中位數校正已有效。Boosting 的額外氣溫改善不明確；未見地區的 Ridge 點估計較好。降雨需同時看事件機率及毫米量，不能只憑 MAE 排名。</p></article></div>
<h3>可放入 PPT 的總結</h3><blockquote>在相同有效日期與預報 lead 的配對比較中，氣溫預報與實測的一致程度存在地理差異。海拔及海陸位置有較明確的關聯證據；城市化與地形的解讀受因素重疊、站數及分類尺度影響。簡單逐站校正已能改善已知站氣溫，複雜 ML 並未顯示全面優勢。降雨分析目前支持建立地方事件／雨量的研究映射，未足以宣稱某一地理類別的官方降雨預報普遍較準。</blockquote></section>'''
body+='<section id="factors"><div class="eyebrow">02 / 四個因素：結論 → 數據與計算 → 推論邏輯</div><h2>四個因素都已計算；證據強度不同。</h2>'+fimgs[0]
body+='''<div class="tablewrap"><table><thead><tr><th>因素</th><th>分組與資料</th><th>本次完成／仍有限制</th></tr></thead><tbody>
<tr><td>海拔</td><td>&lt;300 m／300–&lt;700 m／≥700 m；站點 metadata</td><td>已完成分組、平均、配對比較、ML 及低海拔敏感度。氣溫中高組只有 2／1 站，不能泛化成全港高山結論。</td></tr>
<tr><td>海陸位置</td><td>≤0.5 km／&gt;0.5–2 km／&gt;2 km；站址至海洋水域邊界</td><td>已完成同日比較、剔除山站、逐站剔除及連續距離特徵。使用 2026 海岸快照，不是逐年海岸。</td></tr>
<tr><td>城市化</td><td>500 m 有效陸地開發比例：&lt;20%／20–&lt;50%／≥50%；2023 土地用途</td><td>已完成 250／500／1000 m、較廣開發代碼與低海拔敏感度。它是土地用途代理，不是人口密度或城市熱島的直接量測。</td></tr>
<tr><td>地形</td><td>5 m DTM → 坡度、標準化 TPI、局部高差 → 平坦／谷地／山坡／脊頂代理</td><td>已補做計算、分組、尺度與門檻敏感度、ML。仍需實地或獨立地貌資料驗證分類；谷地僅 2 氣溫站／1 雨量站。</td></tr></tbody></table></div>'''+table(ct.rename(columns={'factor':'因素','氣溫':'氣溫站數','降雨':'降雨站數'}))+fimgs[1]
body+='''<article class="finding"><h3>A. 海拔：原始公共預報在高山站偏差較大</h3><p><b>1，結論：</b>D3 最高溫的組內等站權 MAE，低／中／高海拔約 1.60／3.93／6.21°C；高海拔組只有大帽山一站。</p><p><b>2，數據及計算：</b>32 個 AWS、2022–2025、相同 D3 定義；計算逐站 |預報−實測| 的平均，再按海拔組平均。另計同日站對差值，並在模型中加入連續海拔。</p><p><b>3，為何支持：</b>描述性差距大，Ridge 移除海拔後 Tmax MAE 增加 0.133°C（95% 區間 0.119–0.146）。兩種方法支持海拔與預測偏差有關，但不是「海拔造成全部誤差」；高山小樣本仍是主要限制。</p></article>
<article class="finding"><h3>B. 海陸位置：近海較接近公共氣溫預報，低海拔分析仍成立</h3><p><b>1，結論：</b>全部站的近海−內陸 Tmax 差約 −1.78°C；限制為 29 個低海拔站後縮至 −0.72°C，說明原始差距有一部分與山站分佈重疊。</p><p><b>2，數據及計算：</b>站對在共同有效日期比較 D3 絕對誤差；每個跨組站對等權平均，再以 14 日時間區塊重抽樣 2,000 次。</p><p><b>3，為何支持：</b>低海拔 Tmax 區間 −0.82 至 −0.60°C、Tmin −0.77 至 −0.51°C 均低於零，支持這批站的差異仍存在。站對可用日期範圍不同，且城市化等因素尚未完全控制，因此不能作因果宣稱。</p></article>'''+fimgs[2]
body+='''<article class="finding"><h3>C. 城市化：有關聯，但不是簡單的「越城市越準」</h3><p><b>1，結論：</b>全部站的低開發組 Tmax MAE 較高；但只看低海拔站，低開發−高開發差為 −0.047°C，95% 區間 −0.106 至 0.014，差異已不明確。Tmin 的同一低海拔對比仍為 +0.317°C（0.285–0.352）。</p><p><b>2，數據及計算：</b>2023 土地用途 restricted 開發代碼佔 500 m 有效陸地比例，排除水域、無圖徵及機場；按門檻分組，再做與上面相同的站對比較。另以連續比例加入 Ridge／boosting。</p><p><b>3，為何支持：</b>限制海拔後 Tmax 結論改變，顯示簡單分組混合了其他地理差異。Tmin 的 Ridge 移除城市化後 MAE 增加 0.013°C（0.010–0.016），但 boosting 並非同樣清楚，因此只支持依 target 與模型而異的關聯。</p></article>
<article class="finding"><h3>D. 地形：已補齊代理資料，但排序不宜當普遍規律</h3><p><b>1，結論：</b>四組已有數據和模型結果。全部站 Tmax 的脊頂組平均誤差高於平坦組；剔除中高海拔站後，脊頂−平坦的同日差約 −0.223°C，方向改變。</p><p><b>2，數據及計算：</b>中心 25 m 內陸地格點高度中位數；50 m 平面擬合得坡度；25–500 m 環帶得鄰域平均、標準差及 P95−P05 高差。TPI z≤−1 為谷／凹地，&gt;1 為脊／凸地，其餘按坡度 &lt;5° 分平坦／山坡。</p><p><b>3，為何支持：</b>這套規則可重現地形描述，但 10/32 站會隨 250／500／1000 m 尺度改組，8 站接近分類門檻；只有 2 個谷地氣溫站。Ridge Tmax 移除地形的增量約 0.009°C，Tmin 不清楚。因此「有額外資訊」比「某地形一定更準」更符合證據。</p></article>
<p class="note">以上分組是規則分類，不是從誤差學出來的 clustering。未見地區測試才使用站址座標的 KMeans 分群。這裡的 factor analysis 指地理因素比較，並非潛在變數的探索性因子分析（EFA）。</p></section>'''
body+='''<section id="methods"><div class="eyebrow">03 / 每個步驟做了什麼、為什麼</div><h2>先確定比較單位，再分開描述與預測。</h2>
<ol class="steps"><li><b>固定來源與站點。</b>沿用 GitHub／本機研究的 forecast、observation、series、station CSV 及地理欄位；使用符合既有候選規則的全部 32 氣溫站、20 雨量站，包括 TC／TMS。沒有按預報誤差挑站，也沒有用平均值補缺失。</li>
<li><b>對齊預報與實測。</b>HKT 日曆日期；同一發布日、目標日保留最後一個存檔 bulletin；lead 為 D1–D9。實測只用完整度 C。氣溫為每日最高／最低溫，降雨為每日毫米量／≥10 mm 事件。Trace 在事件定義為未達門檻，毫米量不代入零；本次候選 AWS 的兩種雨量樣本數相同。</li>
<li><b>先做原始地理比較。</b>逐站平均、各組 MAE／RMSE／Bias；主文以 D3 示範，完整 CSV 包含 D1–D9。同日同 lead 站對比較能減少日期不一致；全 32 站嚴格共同 D3 日期僅 24 日，因此另列敏感度，不把 24 日當四年代表。</li>
<li><b>做跨年預測比較。</b>2022–2023 訓練、2024 選參數；再用 2022–2024 重訓，測試發布及有效日期都在 2025 的記錄。訓練有效日早於驗證／測試發布日，避免跨年目標洩漏。各方法使用完全相同測試樣本。</li>
<li><b>再做未見地區測試。</b>依經緯度 KMeans 分 5 組；每次把一組的站從訓練及 2024 選參數都排除，再預測其 2025 資料。座標只用來分組，未作預測輸入。沒有訓練歷史的逐站方法明確使用 fallback。</li>
<li><b>用不同方法及敏感度互相檢查。</b>分組平均、逐站平均／中位數、Ridge／Logistic、histogram boosting；有／無地理特徵、逐一移除因素、250／1000 m 半徑、低海拔子集、逐站剔除海岸對比，以及 7／14／28 日區塊區間。</li></ol>
<div class="tablewrap"><table><thead><tr><th>Target</th><th>2022–2025 配對記錄</th><th>2025 測試記錄</th><th>主指標</th></tr></thead><tbody><tr><td>Tmax</td><td>358,013</td><td>92,025</td><td>MAE（°C）</td></tr><tr><td>Tmin</td><td>358,031</td><td>92,025</td><td>MAE（°C）</td></tr><tr><td>地方降雨 ≥10 mm</td><td>260,044</td><td>64,593</td><td>Brier score</td></tr><tr><td>地方每日雨量</td><td>260,044</td><td>64,593</td><td>MAE，並列 RMSE／Bias（mm）</td></tr></tbody></table></div>
<p>上述是「站 × 目標日 × lead」記錄，不是獨立天數；同一觀測可能被多個 lead 配對。各 target 的 2025 測試均涵蓋 364 個目標日，但各站日期不完全相同。</p>
<h3>計算方式與模型規格</h3><p>先對每個站 × lead 計平均損失，再等權平均，避免資料較多的站主導分數。MAE = 平均 |預測−實測|；RMSE = √平均 (預測−實測)²；Bias = 平均 (預測−實測)；Brier = 平均 (p−事件 0/1)²。RMSE 先平均平方誤差再開根號。模型訓練使用相應站 × lead 權重；中位數基準按指定分組直接計算樣本中位數。</p>
<p>氣溫模型預測「實測−公共預報」殘差，再加回原始預報；降雨模型使用 PSR 五類 one-hot 及 lead，推估地方事件機率或毫米量。地理特徵共六個：海拔、log(1+海岸公里距離)、開發比例、坡度、TPI z、局部高差。沒有使用未來實測天氣或季節 predictor。</p>
<p>Ridge α ∈ {1,100,10000}；Logistic C ∈ {0.1,1,10}。Boosting 使用 7／15 葉、learning rate 0.07、min leaf 150、L2=1、關閉 early stopping，主版本 80 輪；氣溫／毫米量主版本為 absolute-error loss。每個設計／留出組按 2024 分數選參數。隨機種子 3522。</p>
<p>區間以同一天所有站及 lead 一起做環形時間區塊 bootstrap，2,000 次；主文 14 日，另供 7／28 日結果。重抽樣時模型固定，只表示現有站和已擬合模型的時間不確定性，不涵蓋重新訓練、新站母體及所有地理標註誤差。多重比較未校正，分析屬探索性。</p></section>'''
body+='<section id="models"><div class="eyebrow">04 / 不同方法得出什麼</div><h2>簡單方法是必要基準。</h2><h3>氣溫：校正有效，額外 ML 優勢有限</h3>'+fimgs[3]
body+='<details><summary>查看 Tmax／Tmin 的 MAE、RMSE、Bias</summary><h4>Tmax（°C）</h4>'+modeltable('Tmax',['raw','station_mean','station_median','linear_full','hgb_full'])+'<h4>Tmin（°C）</h4>'+modeltable('Tmin',['raw','station_mean','station_median','linear_full','hgb_full'])+'</details>'
body+='''<p><b>結論：</b>已知站 Tmax 原始 MAE 1.960°C，逐站平均 1.543°C，boosting 1.509°C；Tmin 為 1.983、1.129、1.124°C。但 boosting−逐站平均的配對差，Tmax −0.034°C（−0.072 至 0.003），Tmin −0.006°C（−0.034 至 0.022），均跨零。這不證明兩者完全等效，而是額外改善的證據不足。</p>
<p><b>為何不能只選最低分：</b>未見地區時 Ridge Tmax／Tmin 為 1.641／1.216°C，boosting 為 1.698／1.265°C；點估計排序改變。2024 驗證選出的已知站氣溫方法是 boosting，但實務選擇仍需看簡單性、是否有該站歷史，以及配對不確定性。</p>'''+fimgs[5]
body+='<h3>降雨事件：四個因素已有結果，但改善幅度很小</h3>'+fimgs[6]+modeltable('rain_event',['category_mean','station_mean','linear_full','hgb_full'])
body+='''<p><b>結論：</b>已知站 boosting Brier 0.077487，PSR 分類平均 0.077924；配對差 −0.000437（−0.001136 至 0.000098）跨零，不能宣稱明確優於這個簡單基準。與逐站平均相比有很小的改善證據，仍須考慮效果量及多重比較。Logistic 移除海岸距離的 Brier 增量約 0.000107，其他因素與模型的證據不一致。</p>
<p><b>數據及邏輯：</b>目標是「該站當日雨量 ≥10 mm」，從訓練期 PSR／lead 與站點觀測估計 p；比較同一批 2025 事件。不同地理組的事件頻率或平均雨量差，代表實況分佈差異，不能直接當作預報準確率差異。以下固定門檻表顯示命中與誤報的取捨。</p>
<details><summary>事件門檻敏感度：POD、FAR、漏報、Accuracy</summary>'''+evt+'''<p>POD=TP/(TP+FN)，FAR=FP/(TP+FP)，漏報率=FN/(TP+FN)。此表為 pooled 記錄計數，與主 Brier 的站 × lead 等權不同；事件只佔 7,902/64,593≈12.23%，所以高 Accuracy 本身不代表擅長預測降雨。門檻 0.2／0.35／0.5 為展示取捨，沒有用測試集選最佳門檻。</p></details>
<h3>降雨毫米量：MAE 改善可能只是更接近中位數</h3>'''+fimgs[4]+modeltable('rain_amount',['zero','category_mean','category_median','station_median','hgb_full','hgb_long_full','hgb_squared_full'])
body+='''<p><b>結論：</b>已知站 PSR 分類平均 MAE 8.119 mm，L1 boosting 6.504 mm，看似改善；但分類中位數已達 6.142 mm，逐站中位數 6.130 mm。L1 boosting Bias 約 −6.22 mm、RMSE 25.71 mm，平均法約 −0.01／22.47 mm。因此不能用 MAE 一項宣稱 ML 對降雨較準。</p><p><b>計算與推論：</b>增加 500 輪 L1 boosting 幾乎不改變結果；改用 L2 的 boosting，其 MAE／RMSE／Bias 約 8.057／22.352／−0.017 mm。這支持損失函數與雨量分佈是比較結果的重要部分。中位數、固定零、500 輪及 L2 模型是在首輪診斷後補加，已記錄；其參數仍由 2024 選擇，不能稱為事前完全固定的確認性實驗。</p></section>'''
body+='''<section id="explore"><div class="eyebrow">05 / 查閱完整分組結果</div><h2>選擇 target、方法與因素。</h2><p>以下為 2025 測試集，D1–D9 站 × lead 等權彙總；各方法在相同 target／設計使用同一批測試記錄。不同地理組的日期組成仍可不同，分組差異不是單獨因素的因果效應。</p><div class="controls"><label>變量<select id="target"><option value="Tmax">最高溫 Tmax</option><option value="Tmin">最低溫 Tmin</option><option value="rain_event">降雨事件 ≥10 mm</option><option value="rain_amount">降雨毫米量</option></select></label><label>測試<select id="design"><option value="temporal">已知站跨年</option><option value="spatial">未見地區</option></select></label><label>方法<select id="method"></select></label><label>因素<select id="factor"><option value="elevation">海拔</option><option value="coast">海陸位置</option><option value="urban">城市化</option><option value="terrain">地形</option></select></label></div><div id="group-results" aria-live="polite"></div><p id="metric-note" class="note"></p></section>'''
body+='''<section id="limits"><div class="eyebrow">06 / 額外假設與尚需補強的證據</div><h2>完成了計算，不等於消除了研究限制。</h2><ul>
<li><b>預報空間含義：</b>同一公共預報與不同 AWS 配對，衡量地區適用程度。若要聲稱某個模型在某地真正較準，仍需同地、同變量、同時效的原生站點或網格預報。</li>
<li><b>靜態地理假設：</b>2023 土地用途、2026 海岸用於 2022–2025；未重建逐年填海、用地變遷。開發比例分母排除水、無圖徵及機場，不能解讀為整個圓形面積的開發率。</li>
<li><b>DTM 與地形代理：</b>本次下載的是官方命名的 5 m DTM 歷史產品，並非宣稱最新 CSDI raster；資料可能包含植被及地上物。海岸／島嶼只用有效陸地，不把海面補成零；橫瀾島 500 m 鄰域陸地支持約 8.9%，需保守解讀。<a href="https://www.landsd.gov.hk/en/spatial-data/open-data/kf_dtm.html">地政總署產品說明</a></li>
<li><b>站數與因素重疊：</b>32／20 站才是地理樣本規模，百萬筆站日 lead 記錄不能當作百萬個獨立地點。高海拔僅 1 站、降雨谷地僅 1 站；地形／海拔／海岸／開發比例相互相關。</li>
<li><b>缺失與代表性：</b>未補值；主模型共同測試 cases 保證方法公平，但不能排除缺失與惡劣天氣相關。全站共同日期太少，站對日期亦不完全一樣。沒有以本研究證明季節無影響；只是按需求未加入季節因子。</li>
<li><b>研究設計：</b>這是已看過部分 2025 結果後的回顧探索，不是全新盲測。五群留出只代表現有站網內的空間轉移；時間區間未反映新站抽樣、重訓及多重測試不確定性。</li>
<li><b>後續優先補強：</b>若要提升為普遍地區結論，優先取得更多中高海拔／谷地站、獨立地貌標註、歷史地理版本，以及真正地方預報；再用新增年份作預先固定方案的外部驗證。這些是新增證據需求，不是本輪遺漏的分析。</li></ul></section>'''
body+='''<section id="evidence"><div class="eyebrow">07 / 可追溯證據</div><h2>原始來源、計算結果與驗證記錄。</h2><p>本報告以既有研究作為起點，新增完整四因素、地形代理、32／20 站統一分析、方法與空間驗證。舊版 9 站、30 站或不同日期的數值不能直接拼接到本輪結論。沒有修改原始 CSV／資料庫，也沒有把研究結果上傳 GitHub。</p>
<ul><li><a href="https://github.com/JJChand/COMP3522">COMP3522 GitHub</a>：本機研究 checkout 042ce8931f7eda185e034c730521b834bf90e600；查閱的 main 為 435396e6cd870f70ea5e73026f2acf7c023f13d7。原始 CSV 的 SHA256 見 <a href="results/model_metadata.json">model_metadata.json</a>，不把本機快照說成最新資料庫。</li>
<li><a href="https://www.hko.gov.hk/en/cis/stn.htm">HKO 站點資料</a>；<a href="https://www.hko.gov.hk/tc/wxinfo/currwx/fnd.htm">九天天氣預報／PSR</a>；<a href="https://portal.csdi.gov.hk/csdi-webpage/dataset/pland_rcd_1696577406166_85973">規劃署 2023 土地用途</a>。地理代碼及來源快照見 <a href="results/geography_specification.json">geography_specification.json</a>。</li>
<li><a href="https://www.landsd.gov.hk/en/spatial-data/open-data/kf_dtm.html">地政總署 5 m DTM</a>；<a href="https://www.jennessent.com/downloads/Land_Facet_Tools_A4.pdf#page=55">TPI／坡度分類參考</a>。本研究採用自己的四組操作規則，並非原文方法的完整複製；下載版本、雜湊及公式見 <a href="results/terrain_provenance.json">terrain_provenance.json</a>。</li></ul>
<div class="cards"><article><h3>來源與重算核對通過</h3><p>1,236,132 個配對記錄檢查；140 次獨立模型重擬合；102 個指標摘要核對。</p><a href="results/independent_verification.json">檢查明細</a></article><article><h3>地形核對通過</h3><p>32 站 × 3 半徑共 96 次檢查，2 個已知坡面測試；原始 ASC 與 TIFF 站點取樣一致。</p><a href="results/terrain_verification.json">地形驗證</a></article><article><h3>彙總核對通過</h3><p>262 方法欄位、1,326 分組欄位、60 地理對比、65 敏感度列及 66 門檻列重新核對。</p><a href="results/summary_verification.json">彙總驗證</a></article></div>
<p><a class="button" href="../COMP3522_Geographic_Factors_Evidence.zip">下載報告＋圖表＋數據＋程式 ZIP</a> <a class="button secondary" href="code/README.md">重現步驟與檔案索引</a></p>
<details><summary>全部結果檔（含未放入主文的結果）</summary><ul>__FILES__</ul></details><p class="note">HTML 圖片及互動數據已內嵌，可單獨開啟；CSV、程式及下載連結需保留整個資料夾。ZIP 不包含原始觀測、模型逐筆預測或大型 GIS raster；重現全流程需原工作區的來源快照。</p></section></main><footer>COMP3522 · 地理因素研究 · 數值以隨附 CSV 為準 · 2026-11-14</footer>'''

css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font:17px/1.8 "Microsoft JhengHei",system-ui,sans-serif;color:#223347;background:#f4f6f8}header{background:#123149;color:white;padding:65px max(24px,calc((100vw - 1160px)/2)) 55px}h1{font-size:clamp(30px,4vw,49px);line-height:1.35;margin:16px 0}h2{font-size:28px;line-height:1.45;color:#153a53}h3{font-size:21px;line-height:1.5}h4{margin-bottom:8px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:2px;color:#168a7a}header .eyebrow{color:#8bdbc9}.lead{font-size:20px;color:#d0e2eb}.badges{display:flex;gap:10px;flex-wrap:wrap}.badges span{border:1px solid #547080;border-radius:20px;padding:4px 13px;font-size:13px}nav{display:flex;gap:24px;flex-wrap:wrap;background:white;border-bottom:1px solid #dfe5eb;padding:14px max(24px,calc((100vw - 1160px)/2));font-size:14px}a{color:#126c91;text-underline-offset:3px;overflow-wrap:anywhere}main{max-width:1208px;padding:0 24px;margin:auto}section{padding:50px 0;border-bottom:1px solid #d6dfe6;scroll-margin-top:20px}p{margin:16px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:25px 0}.cards article{background:white;padding:24px;border:1px solid #dce5e9;border-radius:10px}.cards h3{margin-top:0}.callout,blockquote{margin:24px 0;padding:20px 25px;border-left:4px solid #168a7a;background:#e7f3ef}.finding{padding:16px 25px;margin:22px 0;background:white;border:1px solid #e1e7eb;border-radius:8px}.finding b{color:#126d67}figure{margin:30px 0;background:white;padding:18px;border:1px solid #dce5e9;border-radius:9px}figure img{width:100%;height:auto;display:block}figcaption{font-size:14px;line-height:1.7;color:#506477;padding:16px 7px 0}.tablewrap{overflow-x:auto;max-width:100%;background:white;margin:20px 0;border:1px solid #dce5e9;border-radius:7px}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th{text-align:left;background:#e8eff3;white-space:nowrap;color:#244b63}th,td{padding:11px 14px;border-bottom:1px solid #e6ecf0}td{vertical-align:top}tbody tr:nth-child(even){background:#f8fafb}.steps li,section>ul>li{margin:16px 0;padding-left:6px}.note{font-size:14px;color:#5d6d7b}details{background:#eef2f5;padding:17px 20px;border-radius:8px;margin:20px 0}summary{cursor:pointer;font-weight:600}.controls{display:grid;grid-template-columns:1fr 1fr 2fr 1fr;gap:14px}.controls label{font-size:14px;font-weight:600}select{width:100%;padding:11px 9px;font:inherit;margin-top:5px;border:1px solid #a8bdcb;border-radius:5px;background:white;color:#223347}.button{display:inline-block;padding:11px 17px;background:#126f69;color:white;text-decoration:none;border-radius:6px;margin:5px 10px 5px 0;font-size:15px}.secondary{background:#dde9ee;color:#23445a}footer{padding:35px 24px;text-align:center;color:#6a7d8c;font-size:13px}@media(max-width:760px){body{font-size:16px}.cards{grid-template-columns:1fr}.controls{grid-template-columns:1fr 1fr}header{padding:35px 22px}.lead{font-size:17px}nav{gap:10px 20px;padding:13px 22px}main{padding:0 16px}section{padding:32px 0}h2{font-size:24px}.finding{padding:12px 17px}figure{padding:8px}figcaption{font-size:13px}}@media print{nav,.controls,.button{display:none}body{background:white;font-size:11pt}header{padding:20px;background:white;color:#123149}header .lead{color:#223347}main{padding:0}figure{break-inside:avoid}section{padding:20px 0}.cards{grid-template-columns:repeat(3,1fr)}details{display:block}a{color:inherit}}'''
css+='body{overflow-wrap:anywhere}.controls>*{min-width:0}'
records=json.loads(read('method_by_geographic_group').to_json(orient='records'))
sub=read('method_by_geographic_group');rainrows=[]
for factor,order in ORDER.items():
 for group in order:
  q=sub[sub.design.eq('temporal')&sub.factor.eq(factor)&sub.group.eq(group)]
  evbase=q[q.target.eq('rain_event')&q.method.eq('category_mean')].iloc[0]
  evfull=q[q.target.eq('rain_event')&q.method.eq('hgb_full')].iloc[0]
  ambase=q[q.target.eq('rain_amount')&q.method.eq('category_median')].iloc[0]
  amfull=q[q.target.eq('rain_amount')&q.method.eq('hgb_full')].iloc[0]
  rainrows.append({'因素':FAC[factor],'分組':LABEL[factor][group],'站數':int(evbase.n_stations),'分類平均 Brier':evbase.brier,'ML − 分類平均 Brier':evfull.brier-evbase.brier,'分類中位數 MAE mm':ambase.mae,'ML − 分類中位數 MAE mm':amfull.mae-ambase.mae})
rainframe=pd.DataFrame(rainrows)
rainsection='<h3>四個因素的降雨結果：同組、同 cases 比較方法</h3><p>下表均為已知站 2025 測試。事件基準為 PSR 分類平均機率，毫米量基準為 PSR 分類中位數，ML 為 80 輪 boosting＋四因素。Δ 為 ML 減基準，負值表示 ML 的損失較小。表內是點估計，不是各組差異的顯著性檢驗。</p>'+table(rainframe)+'<p>海拔、海陸位置、城市化、地形均已有對應的事件與毫米量結果。比較模型應看同一組內的 Δ；不同組的 Brier／MAE 還會受到事件頻率、雨量幅度及可用日期影響，不能把最低分的一組直接稱為「官方降雨預報最準的地區」。中高海拔及谷地雨量站特別少，結論以探索性描述為限。</p>'
body=body.replace('<h3>降雨毫米量：',rainsection+'<h3>降雨毫米量：')
js='''const data=__DATA__,names=__NAMES__,labels=__LABELS__;const $=id=>document.getElementById(id);function draw(reset){const target=$('target').value,design=$('design').value,factor=$('factor').value;let rows=data.filter(r=>r.target===target&&r.design===design);const methods=[...new Set(rows.map(r=>r.method))];if(reset||!methods.includes($('method').value)){const old=$('method').value;$('method').replaceChildren(...methods.map(m=>{let o=document.createElement('option');o.value=m;o.textContent=names[m]||m;return o}));if(methods.includes(old))$('method').value=old}rows=rows.filter(r=>r.method===$('method').value&&r.factor===factor);const rain=target==='rain_event',cols=rain?['brier','log_loss']:['mae','rmse','bias'];let h='<div class="tablewrap"><table><thead><tr><th>分組</th><th>站數</th><th>記錄數</th><th>日期聯集</th>'+cols.map(c=>'<th>'+c.toUpperCase()+'</th>').join('')+'</tr></thead><tbody>';for(const r of rows)h+='<tr><td>'+labels[factor][r.group]+'</td><td>'+r.n_stations+'</td><td>'+r.n_cases.toLocaleString()+'</td><td>'+r.n_dates+'</td>'+cols.map(c=>'<td>'+(r[c]===null?'—':r[c].toFixed(rain?6:3))+'</td>').join('')+'</tr>';$('group-results').innerHTML=h+'</tbody></table></div>';$('metric-note').textContent=rain?'事件是地方日雨量 ≥10 mm；Brier 越低越好。這是研究映射，不是官方地方機率。':target==='rain_amount'?'單位 mm；Bias = 預測 − 實測。PSR 轉毫米量為研究模型，務必同看 MAE、RMSE 及 Bias。':'單位 °C；MAE、RMSE 越低越好，Bias 正值表示預報偏高。未見地區的逐站方法使用訓練站 fallback。'}for(const id of ['target','design','method','factor'])$(id).addEventListener('change',()=>draw(id==='target'||id==='design'));draw(true);'''.replace('__DATA__',json.dumps(records,ensure_ascii=False)).replace('__NAMES__',json.dumps(NAMES,ensure_ascii=False)).replace('__LABELS__',json.dumps(LABEL,ensure_ascii=False))

# Preserve all result tables; publish source without input data or virtual environments.
(DEST/'results').mkdir(exist_ok=True);(DEST/'code').mkdir(exist_ok=True)
shutil.copy2(ROOT/'analysis/geographic-representativeness/results/geography_specification.json',R/'geography_specification.json')
for p in R.iterdir():
 if p.suffix in ['.csv','.json']:shutil.copy2(p,DEST/'results'/p.name)
for p in HERE.iterdir():
 if p.suffix in ['.py','.md','.txt','.cjs']:shutil.copy2(p,DEST/'code'/p.name)
links=''.join(f'<li><a href="results/{p.name}">{p.name}</a></li>' for p in sorted((DEST/'results').iterdir()))
body=body.replace('__FILES__',links)
# Captions follow the narrative order: geography, temperature, attribution, event, amount.
body=body.replace('圖 5｜PSR','圖 7｜PSR').replace('圖 6｜每次','圖 5｜每次').replace('圖 7｜地方','圖 6｜地方')
(DEST/'index.html').write_text('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>COMP3522｜四個地理因素與方法比較</title><style>'+css+'</style></head><body>'+body+'<script>'+js+'</script></body></html>',encoding='utf-8')
archive=DEST.parent/'COMP3522_Geographic_Factors_Evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(DEST.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(DEST.parent)))
print(json.dumps({'html':str(DEST/'index.html'),'zip':str(archive),'figures':len(list(FIG.glob('*.png'))),'bytes':(DEST/'index.html').stat().st_size},ensure_ascii=False))
