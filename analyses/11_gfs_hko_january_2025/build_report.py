"""Build the repository's research figures and Traditional-Chinese findings."""
import csv,json,os
from datetime import date
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
os.environ.setdefault('MPLCONFIGDIR',str(HERE.parents[1]/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.axisbelow':True})
COLORS={'hko':'#2369A1','gfs':'#B66D18','gfs_sampled':'#777777'}


def read(name):return list(csv.DictReader((OUT/name).open(encoding='utf-8')))
def f(row,key):return float(row[key])
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])
def save(fig,name,note):
    fig.text(.04,.018,note,fontsize=9)
    fig.tight_layout(rect=(0,.07,1,.94));fig.savefig(OUT/name,dpi=160);plt.close(fig)


def main():
    scores=read('temperature_scores.csv');contrasts=read('paired_contrasts.csv')
    revisions=read('revision_summary.csv');cases=read('paired_cases.csv');rh=read('hko_rh_scores.csv')
    baseline=read('baseline_skill.csv');meta=json.loads((OUT/'run_metadata.json').read_text(encoding='utf-8'))
    verification=json.loads((OUT/'verification.json').read_text())
    base='20HKT_lag6'
    def score(variable,product,lead=0):return next(r for r in scores if r['scenario']==base and r['variable']==variable and r['product']==product and int(r['lead_days'])==lead)
    def contrast(variable,scenario=base,lead=0):return next(r for r in contrasts if r['scenario']==scenario and r['variable']==variable and int(r['lead_days'])==lead)
    def revision(variable,product):return next(r for r in revisions if r['variable']==variable and r['product']==product and r['later_lead']=='0')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8),sharey=True)
    for ax,var in zip(axes,('tmax','tmin')):
        for product,label,style,marker in [('hko','HKO','-','o'),('gfs','GFS interval midpoint','-','s'),('gfs_sampled','GFS sampled extrema',':','^')]:
            ax.plot(range(1,8),[f(score(var,product,d),'mae') for d in range(1,8)],
                    color=COLORS[product],label=label,linestyle=style,marker=marker)
        ax.set(title=var.upper(),xlabel='Common decision lead (days)',xticks=range(1,8),ylim=(0,2.7))
        ax.grid(axis='y',alpha=.25);ax.legend(frameon=False,fontsize=9)
    axes[0].set_ylabel('MAE (degrees C)')
    fig.suptitle('January 2025: temperature error by lead')
    save(fig,'accuracy_by_lead.png','31 paired target dates per lead; 20:00 HKT cutoff; assumed GFS release delay = 6 h. HQ nearest-point comparison.')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8),sharey=True)
    for ax,var in zip(axes,('tmax','tmin')):
        rows=[contrast(var,lead=d) for d in range(1,8)]
        y=np.array([f(r,'delta_mae') for r in rows])
        err=np.array([y-np.array([f(r,'ci7_low') for r in rows]),np.array([f(r,'ci7_high') for r in rows])-y])
        ax.errorbar(range(1,8),y,yerr=err,fmt='o-',color=COLORS['gfs'],capsize=4)
        ax.axhline(0,color='#333333',linewidth=1);ax.grid(axis='y',alpha=.25)
        ax.set(title=var.upper(),xlabel='Common decision lead (days)',xticks=range(1,8),ylim=(-.65,1.65))
    axes[0].set_ylabel('GFS MAE minus HKO MAE (degrees C)')
    fig.suptitle('Positive differences favor HKO; intervals crossing zero are inconclusive')
    save(fig,'paired_difference.png','95% exploratory 7-day block-bootstrap intervals; all leads/products move with each target date. Multiple leads are unadjusted.')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8),sharey=True)
    for ax,key,title in zip(axes,('revision_rate_pct','material_revision_rate_pct'),('Any numerical change','Change of at least 1 degree C')):
        for offset,product,label in [(-.18,'hko','HKO'),(.18,'gfs','GFS midpoint')]:
            bars=ax.bar(np.arange(2)+offset,[f(revision(v,product),key) for v in ('tmax','tmin')],width=.34,color=COLORS[product],label=label)
            ax.bar_label(bars,fmt='%.1f%%',padding=3)
        ax.set(title=title,xticks=[0,1],xticklabels=['Tmax','Tmin'],ylim=(0,111));ax.grid(axis='y',alpha=.25)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.91),ncol=2,frameon=False)
    axes[0].set_ylabel('Percentage of paired daily revisions')
    fig.suptitle('Revision rates depend strongly on numerical precision')
    save(fig,'revision_precision.png','186 daily revision pairs per product/variable. A high change rate alone does not establish poor accuracy or useless revisions.')
    fig,axes=plt.subplots(2,1,figsize=(12.5,7.8),sharex=True,sharey=True)
    for ax,var in zip(axes,('tmax','tmin')):
        rows=sorted([r for r in cases if r['scenario']==base and r['variable']==var and r['lead_days']=='1'],key=lambda r:r['valid_date'])
        x=np.arange(1,32)
        ax.plot(x,[f(r,'observed') for r in rows],color='#222222',linewidth=2,label='HQ observed')
        for product,label,marker in [('hko','HKO','o'),('gfs','GFS midpoint','s')]:
            ax.plot(x,[f(r,product) for r in rows],color=COLORS[product],label=label,marker=marker,markersize=3)
        ax.fill_between(x,[f(r,'gfs_lower') for r in rows],[f(r,'gfs_upper') for r in rows],color=COLORS['gfs'],alpha=.2,label='Temporal reconstruction range')
        ax.set(title=var.upper(),ylabel='Temperature (degrees C)',ylim=(8,25));ax.grid(axis='y',alpha=.25)
        ax.legend(frameon=False,ncol=2,fontsize=9)
    axes[-1].set(xlabel='January 2025 target day',xticks=[1,5,10,15,20,25,31])
    fig.suptitle('Day-1 forecasts and observations at Headquarters')
    save(fig,'daily_day1.png','The orange band is a conditional reconstruction range, not forecast uncertainty or a statistical confidence interval.')
    scenarios=list(meta['scenarios'])
    fig,axes=plt.subplots(1,2,figsize=(12.5,5.2),sharex=True,sharey=True)
    for ax,var in zip(axes,('tmax','tmin')):
        rows=[contrast(var,s) for s in scenarios]
        x=np.array([f(r,'delta_mae') for r in rows]);y=np.arange(len(rows))
        err=np.array([x-np.array([f(r,'ci7_low') for r in rows]),np.array([f(r,'ci7_high') for r in rows])-x])
        ax.errorbar(x,y,xerr=err,fmt='o',capsize=4,color=COLORS['gfs'])
        ax.axvline(0,color='#333333',linewidth=1);ax.set(title=var.upper(),yticks=y,yticklabels=scenarios,xlabel='GFS MAE minus HKO MAE (degrees C)')
        ax.grid(axis='x',alpha=.25)
    axes[0].invert_yaxis();fig.suptitle('Cutoff and assumed publication-delay sensitivity')
    save(fig,'timing_sensitivity.png','Each point pools leads 1-7 on the same 31 target dates. Intervals are exploratory 7-day bootstrap intervals, not release-time evidence.')
    mainrows=[]
    for var in ('tmax','tmin'):
        for product,label in [('hko','HKO'),('gfs','GFS midpoint proxy')]:
            r=score(var,product);mainrows.append([var.upper(),label,*[f'{f(r,k):.3f}' for k in ('mae','rmse','bias')],r['n']])
    leadrows=[]
    for d in range(1,8):leadrows.append([d,*[f'{f(score(v,p,d),"mae"):.3f}' for v in ('tmax','tmin') for p in ('hko','gfs')]])
    revrows=[]
    for v in ('tmax','tmin'):
        for p,label in [('hko','HKO'),('gfs','GFS')]:
            r=revision(v,p);revrows.append([v.upper(),label,r['n_pairs'],f'{f(r,"revision_rate_pct"):.1f}%',
                f'{f(r,"material_revision_rate_pct"):.1f}%',f'{f(r,"mean_absolute_revision"):.3f}',
                f'{f(r,"usefulness_changed_pct"):.1f}%',f'{f(r,"mean_error_reduction_all"):.3f}',
                f'[{f(r,"mean_error_reduction_all_ci7_low"):.3f}, {f(r,"mean_error_reduction_all_ci7_high"):.3f}]'])
    sensrows=[[s,*[f'{f(contrast(v,s),"delta_mae"):.3f} [{f(contrast(v,s),"ci7_low"):.3f}, {f(contrast(v,s),"ci7_high"):.3f}]' for v in ('tmax','tmin')]] for s in scenarios]
    rhrows=[[r['variable'],*[f'{f(r,k):.3f}' for k in ('mae','rmse','bias')],r['n']] for r in rh if r['lead_days']=='0']
    baseline_rows=[[r['variable'].upper(),r['product'],r['reference'],f'{f(r,"mae_skill"):.3f}'] for r in baseline if r['lead_days']=='0']
    cmax,cmin=contrast('tmax'),contrast('tmin')
    selected=read('vintage_selection.csv');sel=[r for r in selected if r['scenario']==base]
    age=float(np.median([f(r,'hko_age_hours') for r in sel]))
    rain=meta['rainfall']
    report=f'''# 一月試行：Tmax 支持 HKO 較準，Tmin 暫無清楚高下

本輪已完成 2025 年 1 月 **溫度的 GFS–HKO 條件式比較**，以及 RH／rainfall
的可比性審計和 HKO 側診斷。GFS RH／rainfall 尚未匯入，這兩類沒有跨產品排名。
數據庫全程唯讀；月份指 **target dates**，包括較早發布的預報。

## 1. 先說能夠得出的結論

- Tmax：HKO MAE **0.943°C**，GFS midpoint proxy **1.705°C**，HKO 平均少
  **{f(cmax,'delta_mae'):.3f}°C** 絕對誤差。配對差的 exploratory 95% interval
  是 **[{f(cmax,'ci7_low'):.3f}, {f(cmax,'ci7_high'):.3f}]°C**，支持本設計下 HKO 較接近 HQ 觀測。
- Tmin：HKO MAE **0.820°C**，GFS **0.824°C**。差距僅 **{f(cmin,'delta_mae'):.3f}°C**，
  interval **[{f(cmin,'ci7_low'):.3f}, {f(cmin,'ci7_high'):.3f}]°C** 包含 0；沒有充分證據判誰較準。
- Tmax 的方向在六個 timing scenarios 和 temporal sensitivity envelope 中保持一致；
  Tmin 的小幅點估計則可換方向，因此不作優勝宣稱。
- GFS native revision rate 是 100%，但只計 ≥1°C 的變動時反而低於 HKO。
  **數值精度必須加入比較規則，不能用「變得較頻密」推斷較不可靠。**

以上只適用於一月、HQ、nearest-grid extraction 和已披露的 reconstruction／availability
假設；不是全年、全港或核心數值模型的整體排名。

## 2. 哪些資料實際可比

| 變量 | HKO 及觀測 | 現有 GFS | 本輪處理 |
| --- | --- | --- | --- |
| Tmax / Tmin | 公開日預報及 31 個完整 HQ 日觀測 | 2m TMP、interval TMAX/TMIN | 以披露的日重建 approximation 配對比較 |
| RHmin / RHmax | 公開預報及 31 份 HQ daily JSON reports | 這次 payload 沒有 RH | 只計 HKO MAE／修訂，不作 GFS–HKO 比較 |
| Rainfall | HKO PSR category、HQ daily amount、22 站 proxy | 這次 payload 沒有 rainfall/probability | 只做 HKO proxy 診斷；PSR 不能直接與 mm 相減 |

缺少匯入變量，並不等於 GFS 模型沒有提供它。Rainfall 即使補到 mm，也仍須處理
probability/event/spatial-definition 的不同；不能直接把 GFS rainfall amount 當成 HKO PSR。
RH daily-report values 是 provisional，沒有 CSV-style completeness flag；日期、範圍與數值檢查通過
不代表已取得 finalized climatological quality certification。

## 3. 本輪採用的比較規則

31 個 target dates × D1–D7 × Tmax/Tmin，共 **434 個 paired cases**，每個變量
217 cases；每個 lead 31 天，並非 217 個獨立天氣日。六個 scenarios 均沒有排除個案。

- 主 cutoff：每日 **20:00 HKT**。HKO 選 bulletin/RSS timestamp 均在截止前的最新版本。
- GFS：主假設 run+6h 才可用，所以選到 06 UTC run；歷史 availability **未核實**。
  HKO timestamp 也只是已知 publication proxy，不是當年的實測接收日誌。
- 主設計 GFS run age 為 6 小時；HKO 公告的中位 age 為 **{age*60:.1f} 分鐘**。
  這回答使用者在同一決策時刻可選哪個產品的條件式問題，不代表兩者資訊年齡相同。
- 地點：HQ 22.301944°N, 114.174167°E；GFS point 22.25°N, 114.25°E，距離 **9.708 km**。
  其他 0.25°產品不一定同樣距離；網格起點、掩膜與定義仍須逐項檢查。
- 只有一個已存檔點，無法從它推回四鄰點，所以這次沒有實作全月 bilinear sensitivity。
  HQ elevation 為 32m，model orography 未驗證，沒有套用事後海拔／bias correction。
- GFS interval 完全 contained 的 union 覆蓋 21h，overlapping union 覆蓋 24h。
  各 endpoint envelope 的 midpoint 作單值；不是 Tmin/Tmax 的平均。
  平均 envelope width：Tmax {f(cmax,'mean_envelope_width'):.3f}°C，Tmin {f(cmin,'mean_envelope_width'):.3f}°C。
  這是處理方法的敏感度範圍，依賴 interval consistency／packing 假設，並非保證界限或 CI。

完整方法及事前固定規則見 [PLAN.md](../PLAN.md)，來源查詢見 [source_queries.sql](../source_queries.sql)。

## 4. 溫度誤差：先分開最高／最低溫

單位 °C；bias=forecast−observed，正數偏高、負數偏低。

{table(['變量','產品','MAE','RMSE','Bias','Cases'],mainrows)}

GFS Tmax 在這個月的最近格點有約 −1.562°C 平均 bias。這是觀察到的模式，不能直接歸因於
海岸、地形或模型本身。沒有以一月觀測估 offset 再回頭評同一月，避免訓練／測試混用。

![各 lead 溫度 MAE](accuracy_by_lead.png)

{table(['Lead','Tmax HKO','Tmax GFS','Tmin HKO','Tmin GFS'],leadrows)}

D1 的 Tmin 點估計是 GFS 較低；D7 則是 HKO 較低。完整配對 intervals 如下，
不把單一 lead 的點估計或 31 天結果當穩定排名。
HKO Tmax 的 D1→D7 MAE 由 0.839 升至 1.123°C；GFS 則由 1.661 至 1.677°C，
中間亦有升跌。本月不支持「兩產品每增加一個 lead 都一定更差」的單調描述。

![配對誤差差及區間](paired_difference.png)

如果只取八個 instantaneous samples 的極值，GFS Tmax MAE 是 **2.227°C**，
而 interval-midpoint 是 **1.705°C**。僅資料處理就改變約 **0.521°C**，顯示 inconsistency
的處理確實影響比較。instantaneous sampled Tmax 不能直接冒充完整日 Tmax。

主設計下，GFS 誤差相對 HKO 的 temporal sensitivity envelope 是 Tmax
**[{f(cmax,'temporal_delta_lower'):.3f}, {f(cmax,'temporal_delta_upper'):.3f}]°C**、Tmin
**[{f(cmin,'temporal_delta_lower'):.3f}, {f(cmin,'temporal_delta_upper'):.3f}]°C**。
它不是抽樣 CI；甚至讓每個 case 選有利 endpoint，Tmax 平均方向仍支持 HKO。
這只是 conditional conservative envelope，不宣稱所有 case endpoint 能由同一模型路徑同時實現。

![Day-1 預報及觀測](daily_day1.png)

## 5. Timing 與 baseline 敏感度

每格為 GFS MAE−HKO MAE 和 7-day exploratory 95% interval，單位 °C。

{table(['Scenario','Tmax ΔMAE [CI]','Tmin ΔMAE [CI]'],sensrows)}

4h／6h 假設選到相同 cycle；8h／12h 亦選到相同 cycle，兩兩相同並非四份獨立證據。
三日 block sensitivity 也保留在 CSV；月份只有 31 日，對 7-day blocks 的有效資訊量很有限。

![Timing sensitivity](timing_sensitivity.png)

baseline 延續 Task 1 的 frozen 1991–2020 ±2-calendar-day mean，以及 decision date−2
的 retrospective persistence。MAE skill=1−forecast MAE/baseline MAE，正數較 baseline 準。

{table(['Variable','Product','Baseline','MAE skill'],baseline_rows)}

GFS Tmax 本月沒有勝過所選 climatology baseline；這不代表全年都沒有 skill。

## 6. Revision rate、幅度及 usefulness

同一 target date 相鄰 decision day，兩產品每天各選一次，D(k+1)→Dk，k=1–6。
每產品／變量 186 pairs，只有 31 個 target dates。Native change threshold=1e−10
僅去除浮點噪聲；另以 ≥1°C 呈現共同的 material threshold。

{table(['Variable','Product','Pairs','Any change','≥1°C','MAR °C','Changed-only improved','Mean U all °C','U 95% interval'],revrows)}

U=舊絕對誤差−新絕對誤差，正數表示改善。changed-only improved 的分母只包含 changed cases；
Mean U all 則包含所有 186 pairs，不可把兩者混成同一指標。
Tmin 的兩產品 mean U intervals 均支持正方向；Tmax 的 intervals 均跨 0。
GFS Tmax 平均改善約 0.003°C，不能形容為已證明修訂有明顯幫助。

![Revision precision](revision_precision.png)

HKO 公開溫度以整數為主，GFS 保留更細精度。因此 native 100% change rate 本身不是
穩定性優劣的充分判據。MAR、FFI 和 ≥1°C change rate 必須一同閱讀。
FFI 公式沿用 Task 1，Tmax HKO/GFS 約 0.090/0.236°C，Tmin 約 0.052/0.180°C；
它描述軌跡折返程度，不表示修訂是否準確，也沒有消除 reporting-precision 差異。

## 7. RH 與 rainfall：完成可比性審計，保留 HKO 側結果

RH errors 用 percentage points（pp），不是相對百分比。

{table(['HKO variable','MAE pp','RMSE pp','Bias pp','Cases'],rhrows)}

HKO RH 的 daily revision rate：約 RHmin 30.1%、RHmax 31.2%；changed-only improved 約
64.3%／56.9%。完整 lead／revision 表見 CSV。因 GFS RH 未匯入，以上不是模型間比較。

Rainfall 的 22-station proxy 在 **31 個可用日中沒有 ≥10mm event**，HQ point 也沒有。
217 個選中 HKO PSR 全是 Low，186 次 daily revisions 的 category change rate 是 0%。
以 Low midpoint=0.15 編碼的 Brier score 是 **{rain['midpoint_brier']:.4f}**；相容 band-score
bounds 是 **[{rain['brier_lower']:.3f}, {rain['brier_upper']:.3f}]**，不是 CI。
全為 non-events 時，always-no-event baseline 的 Brier score 就是 0；所以不能用小 Brier score
或零修訂率宣稱 PSR 完美／已證明校準，也無法估計 event hit rate。

HQ numeric rainfall sum=4.2mm；5 個 Trace 值保留 [0,0.05)mm，因此研究用總量區間為
[4.2,4.45)mm，而非把 Trace 靜默變成 0。這與官方公布 4.2mm 的 reporting convention 不矛盾。

## 8. 樣本涵蓋及最終可說的話

[HKO 一月天氣摘要](https://www.hko.gov.hk/en/wxinfo/pastwx/mws2025/mws202501.htm)
記錄本月以乾燥東北季候風為主、雨量 4.2mm，並有冷空氣過程；南海及西北太平洋沒有熱帶氣旋。
所以「一月沒有颱風／大雨測試樣本」屬月份本身的範圍限制，不是這次漏掉那些日期。

**可以說：**這個月、HQ、指定 timing／nearest-grid／daily-proxy 下，Tmax 支持 HKO 較準，
Tmin 沒有清楚優勝者。配對流程、lead errors 和 daily revision 指標已跑通。

**仍不能說：**HKO 全年一定較準；GFS 在所有地點都偏低；已控制核心模型能力或地形因果；
RH/rain 已完成 GFS–HKO 比較；或本研究已驗證颱風／暴雨情況。

擴展全年前，優先補上：GFS RH/rain 的相應資料與共同事件定義、若要 bilinear 則重取鄰點、
以及維持歷史 availability 的情景限制。[ESMF 方法說明](https://earthsystemmodeling.org/regrid/)
指出 bilinear 是局部線性插值、conservative regridding 保留場的面積積分；兩者用途不同，
不能當成可互換的通用修正，也不會自動恢復高度／海陸差異。

## 9. 核對與重現

{verification['checks']:,} 項獨立檢查通過：重算全部 case／score／revision 算術、
{verification['reconstructed_cases_checked']:,} 個 daily reconstructions，以及主 paired interval。
另一套 live SQL 對 {verification['selection_rows_verified_live_sql']:,} 個 vintage selections 全數核對，錯配 0。
同一 ending time 的 instantaneous／min／max 經各自 packing padding 後，一致性警示為
{verification['native_crossfield_warnings_after_padding']}。這些核對不會把 conditional envelope 變成保證界限。

來源與 hash 見 [run_metadata.json](run_metadata.json)，檢查範圍見 [verification.json](verification.json)。
原始唯讀 snapshot 留在被 Git 忽略的 cache/；結果 CSV 是研究派生配對／彙總，沒有 credentials。
因沒有資料庫修改，本輪不需要刷新 schema snapshot。
'''
    (OUT/'findings.md').write_text(report,encoding='utf-8')
    print('Wrote findings.md and five research figures.')


if __name__=='__main__':main()
