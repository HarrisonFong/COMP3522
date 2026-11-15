"""Readable figures and narrative for continuous coast, correlation, urban and ML."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def build(here,dest,fig,table):
 r=here/'results';p=here.parent/'12_geographic_deepening/results';m=here.parent/'11_geographic_factors/results';out=dest/'figures'
 read=lambda base,n:pd.read_csv(base/(n+'.csv'))
 s=read(r,'station_definitions').set_index('station_code');low=s[s.elevation_m.lt(200)]
 def save(name):plt.savefig(out/(name+'.png'),dpi=180,bbox_inches='tight');plt.close()
 cs=read(r,'continuous_coast_site_regressions');cp=read(r,'continuous_coast_station_points');cd=read(r,'continuous_coast_date_regressions')
 f,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
 for i,t in enumerate(['Tmax','Tmin']):
  for j,cohort in enumerate(['all32','low29']):
   ax=axes[i,j];parts=[]
   for v,color,label,marker in [('raw','#32638a','校正前','o'),('offset','#248573','HKO offset 後','^')]:
    q=cp[cp.target.eq(t)&cp.cohort.eq(cohort)&cp.version.eq(v)];reg=cs[cs.target.eq(t)&cs.cohort.eq(cohort)&cs.version.eq(v)].iloc[0]
    ax.scatter(q.coast_km,q.mae,color=color,label=label,marker=marker,s=30,alpha=.8)
    x=np.linspace(q.coast_km.min(),q.coast_km.max(),100);ax.plot(x,reg.intercept+reg.slope_per_km*x,color=color,lw=1.6)
    parts.append(f'{label} r={reg.pearson:.2f}')
    if v=='raw':
     for row in q.itertuples():
      if row.elevation_m>=200 or (j==1 and row.coast_km>2):ax.annotate(row.station_code,(row.coast_km,row.mae),xytext=(3,5),textcoords='offset points',fontsize=8)
   ax.set_title(t+' · '+('全部 32 站' if j==0 else '低海拔 29 站')+'\n'+'；'.join(parts),fontsize=11);ax.set_xlabel('距海岸最短距離（km）');ax.set_ylabel('逐站 D3 MAE（°C）');ax.set_ylim(bottom=0);ax.grid(alpha=.15);ax.legend(fontsize=8)
 save('14_coast_linear')
 rows=[]
 for cohort,label in [('all32','全部 32 站'),('low29','低海拔 29 站')]:
  for t in ['Tmax','Tmin']:
   row={'站群':label,'變量':t}
   for v,title in [('raw','原始'),('offset','offset 後')]:
    a=cd[cd.target.eq(t)&cd.cohort.eq(cohort)&cd.version.eq(v)&cd.model.eq('coast_only')&cd.feature.eq('coast_km')].iloc[0]
    row[title+' °C/km']=f'{a.slope_per_km:.3f} [{a.slope_ci_low:.3f}, {a.slope_ci_high:.3f}]'
   rows.append(row)
 coast='''<section id="continuous"><div class="kicker">07 / 不分組，再看連續距離</div><h2>離海岸越遠，誤差是否逐漸增加？</h2>
 <p>近海、過渡帶和內陸的比較容易閱讀，但分組會把同一組內的距離差異合併。為了檢查結果是否只依賴 0.5 km 和 2 km 的門檻，這一步直接使用每個站到海岸的實際公里距離，觀察距離與 MAE 的連續關係。</p>
 <div class="formula">逐站平均誤差 MAE = a + b × 海岸距離（km）</div>
 <p>a 是直線的起點，b 是斜率：b 為正表示較內陸的站平均誤差較大；例如 b = 0.07，表示沿這條擬合直線，每增加 1 km 對應約 0.07°C 的 MAE 增加。這是現有站群的平均趨勢，不是每個站必然遵守的規則。</p>'''
 coast+=fig('14_coast_linear','圖 0｜2025 年 D3，每點為一站的平均絕對誤差，藍色為原始、綠色為 HKO offset 後，直線為站點等權線性擬合。左欄全部 32 站、右欄低海拔 29 站；縱軸範圍不同。r 為 Pearson 相關係數。各站使用自身有效日期，因此圖線是描述性結果；下表再控制同日比較。距離範圍約 0–7.23 km，線條不作範圍外推算。')
 coast+='''<p>兩種氣溫在移除高站後仍有正向趨勢，offset 後的斜率則較小。相關係數與斜率的意思不同：例如低海拔 Tmin 校正後的 r 約為 0.70，高於原始的 0.52，但誤差及斜率都較小；r 較大只是表示點更接近線性關係，並不代表預報更差。</p><p>各站可用日期不同，散點圖不能單獨排除缺測影響。若要求所有站完全共用日期，全部 32 站只剩 13 天，低海拔 29 站只剩 32 天，因此不宜把這個小樣本當成全年結果。</p>
 <p>下表改以同一天有資料的站點作比較，控制當天共同的誤差高低，並對日期等權。數值仍以每公里的 MAE 變化表示；方括號是 95% 日期區塊估計區間。</p>'''+table(pd.DataFrame(rows))
 coast+='''<p>低海拔站經校正後，每增加 1 km 的 MAE 關聯約為最高溫 <strong>+0.068°C</strong>、最低溫 <strong>+0.071°C</strong>。再同時考慮海拔、城市化、地形及四大區後，仍約為 +0.060 和 +0.057°C/km。這支持海岸關係不只出現在分組比較中；既有多因素分析使用 log(1+距離)，本次則特別改用直接公里距離，讓斜率容易閱讀。</p>
 <p>但結果不代表海岸距離與誤差之間已證實為嚴格直線。低海拔只有四個站超過 2 km，遠端站點對斜率有較大影響。逐一移除一站後，校正後同日斜率仍為正，但最高溫會在約 0.052–0.089、最低溫在 0.056–0.083°C/km 之間變動。因此保留「存在正向平均關聯」的結論，避免推論每公里的因果效果或香港以外的距離。</p>
 <p><a href="results/hko_offset/continuous_coast_site_regressions.csv">散點圖擬合與相關係數</a> · <a href="results/hko_offset/continuous_coast_date_regressions.csv">同日及多因素斜率</a> · <a href="results/hko_offset/continuous_coast_leave_one_station_out.csv">逐站移除檢查</a></p></section>'''

 # Urban counts and same-date outcome contrasts distinguish the four definitions.
 schemes=['urban_restricted','urban_broad','urban_footprint','urban_height'];labels=['較窄土地用途','較廣土地用途','建築覆蓋率','建築高度強度']
 f,ax=plt.subplots(figsize=(11,3.6),layout='constrained');left=np.zeros(4)
 for group,label,color in [('low','低','#b8dace'),('mixed','混合／中','#e4cb86'),('high','高','#32638a')]:
  counts=np.array([(low[sc]==group).sum() for sc in schemes]);ax.barh(range(4),counts,left=left,color=color,label=label,height=.6)
  for i,n in enumerate(counts):ax.text(left[i]+n/2,i,str(n),ha='center',va='center',color='white' if group=='high' else '#193247')
  left+=counts
 ax.set_yticks(range(4),labels);ax.invert_yaxis();ax.set_xlim(0,29);ax.set_xlabel('站數（每列都是相同的 29 個低海拔站）');ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,1.2));save('14_urban_counts')
 urban_counts=fig('14_urban_counts','圖 0｜相同 29 個低海拔站，使用四種城市化定義後的分組人數。每條總數均為 29；數字是站數，不是土地比例。較廣土地用途將更多站列入高開發組，表示比較對象會隨定義改變，不能把不同列的高組視為相同站群。')
 uc=read(p,'matched_contrasts');f,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
 for ax,t in zip(axes,['Tmax','Tmin']):
  q=uc[uc.target.eq(t)&uc.cohort.eq('lowland')&uc.scheme.isin(schemes)].set_index('scheme').loc[schemes]
  ax.errorbar(q.difference,range(4),xerr=[q.difference-q.ci_low,q.ci_high-q.difference],fmt='o',color='#248573',capsize=4)
  for i,row in enumerate(q.itertuples()):ax.annotate(f'{row.difference:+.3f}',(row.difference,i),xytext=(0,-16),textcoords='offset points',ha='center',fontsize=9)
  ax.set_yticks(range(4),labels);ax.set_ylim(3.55,-.6);ax.axvline(0,color='#666');ax.set_title(t);ax.set_xlabel('低組 − 高組 MAE（°C）\n左：低組誤差較小　｜　右：高組誤差較小');ax.grid(axis='x',alpha=.15)
 save('14_urban_contrasts')
 urban_effect=fig('14_urban_contrasts','圖 0｜2022–2025 年 D3、低海拔 29 站的原始公共預報。每個定義各自比較低組與高組，使用站對共同日期；點為 MAE 差，橫線為 95% 日期區塊區間。正值表示高組較準，負值表示低組較準，跨零表示差異不明確。不同定義的站群不同；本圖尚未套用 HKO offset。')

 # Six-factor correlation matrix, independently recomputed from station metadata.
 cols=['elevation_m','log_coast_km','restricted_fraction_500m','slope_deg','tpi_z_500m','relief_500m'];names=['海拔','海岸距離','開發比例','坡度','相對地形位置','局部高差']
 fc=read(p,'factor_correlations');f,axes=plt.subplots(1,2,figsize=(13,6.5),layout='constrained')
 for ax,cohort,codes,title in [(axes[0],'all',s.index,'全部 32 站'),(axes[1],'lowland',low.index,'低海拔 29 站')]:
  z=s.loc[codes,cols].corr(method='spearman');original=fc[fc.cohort.eq(cohort)&fc.method.eq('spearman')].pivot(index='feature_a',columns='feature_b',values='correlation').loc[cols,cols]
  assert np.allclose(z,original,atol=1e-12)
  im=ax.imshow(z,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(6),names,rotation=40,ha='right');ax.set_yticks(range(6),names);ax.set_title(title)
  for i in range(6):
   for j in range(6):ax.text(j,i,f'{z.iloc[i,j]:.2f}',ha='center',va='center',color='white' if abs(z.iloc[i,j])>.65 else '#193247')
 f.colorbar(im,ax=axes,shrink=.8,label='Spearman 相關係數（−1 至 +1）');save('14_factor_correlation')
 corr='''<div id="correlation"><h3>Correlation：哪些地理特徵會一起出現？</h3><p>相關係數用來檢查特徵之間是否有重疊。這裡每個站只算一筆資料：接近 +1 表示兩個特徵的高低排序相近，接近 −1 表示排序相反，接近 0 則表示沒有明顯的排序關係。它與前面的「海岸距離對 MAE」相關不同；此處比較的是地理特徵彼此。</p>'''
 corr+=fig('14_factor_correlation','圖 0｜六個地理特徵的 Spearman 相關矩陣，左邊全部 32 站、右邊低海拔 29 站。每格比較一對特徵；紅色為正、藍色為負，對角線永遠為 1。城市化使用較窄土地用途比例；海岸距離的 log 轉換不改變其排序相關。每個站只計一次，沒有把同一站的多天資料當成多個地理樣本。')
 corr+='''<p>以低海拔站為例，海拔與坡度的排序相關約為 +0.68，與相對地形位置約為 +0.69，顯示幾項地形特徵存在重疊，不能把每個因素當成完全獨立的解釋。保留與移除高站後的矩陣也不同。相關圖本身不能告訴我們哪個因素造成誤差，但可以說明為什麼需要一起納入模型，以及為什麼單獨分組與多因素結果可能不同。</p></div>'''

 # Existing verified temperature prediction experiments, including lowland refits.
 metrics=read(m,'method_metrics');sens=read(m,'geographic_model_sensitivity');benefits=read(r,'benefits')
 methods=['raw','hko_offset','station_mean','station_median','linear_full','hgb_full'];lab=['原始公共預報','HKO 實測溫差 offset','逐站平均殘差','逐站中位殘差','Ridge＋地理','Boosting＋地理'];mlrows=[]
 f,axes=plt.subplots(2,2,figsize=(12.5,8.7),layout='constrained')
 for i,cohort in enumerate(['all32','low29']):
  for j,t in enumerate(['Tmax','Tmin']):
   values=[];b=benefits[benefits.target.eq(t)&benefits.cohort.eq(cohort)&benefits.lead.eq('D1-D9')].iloc[0]
   for method in methods:
    if method=='raw':v=b.raw_mae
    elif method=='hko_offset':v=b.offset_mae
    elif cohort=='all32':v=metrics[metrics.target.eq(t)&metrics.design.eq('temporal')&metrics.method.eq(method)].mae.item()
    else:v=sens[sens.target.eq(t)&sens.variant.eq('lowland')&sens.method.eq(method)].loss.item()
    values.append(v);mlrows.append(dict(target=t,cohort=cohort,method=method,mae=v))
   ax=axes[i,j];ax.barh(range(6),values,color=['#bcc8d2','#248573','#d9c29c','#cfa76d','#32638a','#5c8cb2']);ax.set_yticks(range(6),lab);ax.invert_yaxis();ax.set_xlim(0,2.3);ax.set_xlabel('2025 D1–D9 MAE（°C），越低越好');ax.set_title(t+' · '+('全部 32 站' if i==0 else '低海拔 29 站'))
   for k,v in enumerate(values):ax.text(v+.025,k,f'{v:.3f}',va='center',fontsize=9)
 save('14_ml_methods');pd.DataFrame(mlrows).to_csv(r/'restored_ml_display_scores.csv',index=False,encoding='utf-8-sig')
 drop=read(m,'factor_drop_comparisons');f,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained');factors=['elevation','coast','urban','terrain']
 for ax,t in zip(axes,['Tmax','Tmin']):
  for off,method,color,label in [(-.12,'linear_full','#32638a','Ridge'),(.12,'hgb_full','#248573','Boosting')]:
   q=drop[drop.target.eq(t)&drop.method.eq(method)&drop.block_days.eq(14)].set_index('factor').loc[factors]
   ax.errorbar(q.loss_increase_without_factor,np.arange(4)+off,xerr=[q.loss_increase_without_factor-q.ci_low,q.ci_high-q.loss_increase_without_factor],fmt='o',capsize=3,color=color,label=label)
  ax.set_yticks(range(4),['海拔','海岸','城市化','地形']);ax.invert_yaxis();ax.axvline(0,color='#777');ax.set_title(t);ax.set_xlabel('移除因素後的 MAE 增量（°C）');ax.legend()
 save('14_ml_factor_drop')
 ml='''<section id="ml"><div class="kicker">09 / 從解釋走向預測</div><h2>ML 嘗試：地理資料能否帶來額外的預報改善？</h2>
 <p>前面的相關和線性分析解釋「誤差與什麼有關」，ML 實驗則進一步檢查「把這些資料放進模型，能否改善下一年的預報」。這兩種問題需要分開：相關較強，不代表加入模型後一定帶來更多改善。</p>
 <p>這裡恢復既有已完成的氣溫模型實驗，並與 HKO offset 放在同一批 2025 年案例比較。ML 學習的是地方實測減公共預報的殘差，與前面使用地方實測減 HKO 實測的 offset 不同。兩者都加回原始預報，但所學的差值不同：</p>
 <div class="formula">殘差 r = 地方實測 O − 公共預報 F<br>ML 地方預報 F̂ = F + f(X)</div>
 <p>X 包含原始預報、提前天數，以及六個地理特徵：海拔、log(1+海岸距離)、較窄開發比例、坡度、相對地形位置和局部高差。既有模型沒有使用目標日實測天氣或季節作輸入，也沒有把前面的 HKO offset 當成 ML 的額外輸入。海岸的直接公里線性分析是本次補充；既有 ML 仍保留原本 log 距離設定。</p>
 <div class="scroll"><table><thead><tr><th>方法</th><th>怎樣計算／學習</th><th>要檢查什麼</th></tr></thead><tbody>
 <tr><td>逐站平均／中位殘差</td><td>F̂ = F + mean(r站,lead) 或 median(r站,lead)</td><td>簡單歷史修正是否已足夠；按站點及提前天數分開估計。</td></tr>
 <tr><td>Ridge 線性模型</td><td>f(X) = β₀ + ΣβⱼXⱼ；最小化 Σwᵢ[rᵢ−f(Xᵢ)]² + αΣβⱼ²</td><td>各項資訊以線性組合校正；α 限制係數過大，特徵先統一尺度。</td></tr>
 <tr><td>Histogram Gradient Boosting</td><td>f(X) = c + ηΣhₘ(X)</td><td>逐步加入小型決策樹，學習較複雜的關係和交互作用；氣溫版本以絕對誤差訓練。</td></tr>
 </tbody></table></div>
 <p>公式中的 β 是模型給每個特徵的權重，w 用來平衡站點及提前天數的訓練資料；Boosting 的 c 是起始值、η 是每次修正的步長，hₘ 是第 m 棵小型決策樹。Ridge 以一個線性組合修正預報，Boosting 則逐步累加多棵樹的修正。</p>
 <p>模型先用 2022–2023 年訓練，在 2024 年選參數，再用 2022–2024 年重訓並評估 2025。Ridge 比較 α = 1、100、10000；Boosting 比較每棵樹 7 或 15 葉，主版本 80 輪、學習率 0.07。另有不加地理特徵，以及每次移除一組因素後重新訓練的比較，用來檢查地理資料提供多少額外資訊。</p>'''
 ml+=fig('14_ml_methods','圖 0｜已知站點的 2025 D1–D9 氣溫預報 MAE。上排全部 32 站，下排低海拔 29 站；每個面板各方法使用相同案例、站點及 lead 等權。低海拔 ML 已在低海拔訓練資料重新擬合，沿用原驗證參數，沒有按 2025 成績重新調參。HKO offset 學實測站間溫差，其餘校正學預報殘差，因此標籤分開。')
 ml+='''<p>全部 32 站中，Boosting 的最高溫 MAE 約為 1.509°C、最低溫為 1.124°C，看起來比原始預報低很多；但 HKO offset、逐站平均和中位殘差已經有相當效果。因此不能只把 ML 與原始預報比較，就認為複雜模型必然更好。</p>
 <p>新增的同案例檢查顯示，Boosting 相對 HKO offset 的 MAE 差，在全部 32 站為最高溫 −0.026°C、最低溫 −0.005°C；低海拔 29 站則為 −0.032°C、+0.001°C。四個 95% 日期區塊區間都跨過零，現有證據不足以說明 Boosting 穩定優於這個簡單校正。</p>'''
 ml+=fig('14_ml_factor_drop','圖 0｜既有全部 32 站、2025 D1–D9 實驗：每次移除一組地理特徵並重新訓練，其餘設定固定。正值表示移除後誤差增加，該因素對此模型有額外預測資訊；跨零表示證據不清楚。橫線為 95% 日期區塊區間。這是模型增量，不是因果貢獻或可相加的百分比；本圖的移除因素實驗只涵蓋全部站。')
 ml+='''<p>Ridge 對海拔和海岸資料較敏感，Boosting 的額外增量通常較小。這不代表某因素對天氣沒有影響，而可能是其他相關特徵已提供相近資訊。既有未見地區測試亦顯示，Ridge 的最高／最低溫 MAE 約為 1.641／1.216°C，Boosting 為 1.698／1.265°C，與已知站點的排名不同；這是另一種使用情境，不能混作同一個模型排名。</p>
 <p>因此，ML 實驗支持地理資料有預測用途，但沒有證據顯示複雜方法在所有比較下都勝出。對已有歷史實測的站，簡單地方校正應保留為基準；如果要把方法用到沒有歷史實測的新站，還需要另外驗證空間推廣能力。</p>
 <p><a href="results/hko_offset/restored_ml_display_scores.csv">本圖模型分數</a> · <a href="results/hko_offset/restored_ml_vs_hko.csv">ML 對 HKO offset 的配對區間</a> · <a href="../index.html#models">既有 Temperature／Rainfall 模型完整結果</a></p></section>'''
 return {'CONTINUOUS_SECTION':coast,'URBAN_COUNTS':urban_counts,'URBAN_CONTRASTS':urban_effect,'CORRELATION_BLOCK':corr,'ML_SECTION':ml}
