"""Produce the corrected Task 2b report and scientific figures, temperature only."""
import csv,hashlib,json,os
from datetime import date
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(HERE.parents[1]/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
COLORS={'hko':'#1764A0','nearest':'#C56315','bilinear':'#008575'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.axisbelow':True})


def read(name):
    with (HERE/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def n(x,d=3):return f'{float(x):.{d}f}'
def interval(r,prefix='ci7'):return f"[{n(r[prefix+'_low'])}, {n(r[prefix+'_high'])}]"
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])


def save(fig,name,note):
    fig.text(.025,.014,note,fontsize=8);fig.tight_layout(rect=(0,.075,1,.93));fig.savefig(HERE/name,dpi=160);plt.close(fig)


def main():
    meta=json.loads((HERE/'run_metadata.json').read_text());valid=json.loads((HERE/'validation.json').read_text())
    if not valid['passed'] or meta['gfs_runs']!=371:raise ValueError('Full corrected analysis must pass before publication')
    a=read('scores.csv');c=read('spatial_contrasts.csv');u=read('revision_summary.csv');v=read('revision_contrasts.csv');t=read('temporal_diagnostics.csv');cases=read('cases.csv')
    def score(var,p,lead=0):return next(r for r in a if r['variable']==var and r['product']==p and int(r['lead_days'])==lead)
    def contrast(var,kind,lead=0):return next(r for r in c if r['variable']==var and r['contrast']==kind and int(r['lead_days'])==lead)
    def update(var,p):return next(r for r in u if r['variable']==var and r['product']==p and r['new_lead']=='0')
    def temporal(var,p):return next(r for r in t if r['variable']==var and r['product']==p and r['lead_days']=='0')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
    for ax,var in zip(axes,('tmax','tmin')):
        for p,label,marker,ls in [('hko','HKO public forecast','o','-'),('nearest','GFS nearest grid','s','-'),('bilinear','GFS bilinear to HQ','^','--')]:
            ax.plot(range(1,8),[float(score(var,p,d)['mae']) for d in range(1,8)],marker=marker,ls=ls,color=COLORS[p],label=label)
        ax.set(title=var.upper(),xlabel='Calendar lead (days)',ylabel='MAE (degrees C)',xticks=range(1,8),ylim=(0,None));ax.grid(axis='y',alpha=.2);ax.legend(frameon=False,fontsize=8)
    fig.suptitle('2025 temperature: identical HKT midnight-to-midnight target windows')
    save(fig,'accuracy_by_lead.png','Retrospective 00 UTC GFS / 14:00 HKT HKO selection; GFS values are full-window linear-trajectory proxies, not exact native daily extrema.')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
    for ax,var in zip(axes,('tmax','tmin')):
        rows=[contrast(var,'bilinear_minus_nearest_ae',lead) for lead in range(1,8)]
        for lead,r in enumerate(rows,1):
            ax.vlines(lead,float(r['ci7_low']),float(r['ci7_high']),color=COLORS['bilinear'],lw=2)
            ax.scatter([lead],[float(r['delta_mae'])],color=COLORS['bilinear'],marker='D',zorder=3)
        ax.axhline(0,color='#222222',lw=1);ax.set(title=var.upper(),xlabel='Calendar lead (days)',ylabel='Bilinear AE minus nearest AE (degrees C)',xticks=range(1,8));ax.grid(axis='y',alpha=.2)
    fig.suptitle('Spatial alignment comparison: negative differences favor bilinear')
    save(fig,'bilinear_minus_nearest.png','Same raw four-cell inputs, run, target date, truth and full HKT window; 95% paired seven-calendar-day block bootstrap intervals.')
    fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True)
    for ax,var in zip(axes,('tmax','tmin')):
        rows=sorted((r for r in cases if r['variable']==var and r['lead_days']=='1'),key=lambda r:r['valid_date']);days=[date.fromisoformat(r['valid_date']) for r in rows]
        ax.plot(days,[float(r['observed']) for r in rows],color='#222222',lw=1.5,label='HQ observed')
        for p,ls in [('hko','--'),('nearest','-'),('bilinear',':')]:ax.plot(days,[float(r[p]) for r in rows],color=COLORS[p],ls=ls,lw=1,label=p.upper())
        ax.set(title=var.upper(),ylabel='Temperature (degrees C)');ax.grid(axis='y',alpha=.2);ax.legend(ncol=4,frameon=False,fontsize=9)
    axes[-1].set_xlim(date(2025,1,1),date(2025,12,31));axes[-1].xaxis.set_major_locator(mdates.MonthLocator());axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    fig.suptitle('2025 daily Tmax/Tmin: the next full HKT day')
    save(fig,'daily_D1.png','Every target window is [00:00, next 00:00) HKT. Nearest and bilinear use the same time reconstruction. Historical availability unverified.')
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
    for ax,var in zip(axes,('tmax','tmin')):
        for i,p in enumerate(('hko','nearest','bilinear')):
            row=update(var,p);ax.bar(i,float(row['mean_revision_gain_c']),color=COLORS[p],width=.55)
            ax.vlines(i,float(row['ci7_low']),float(row['ci7_high']),color='#222222',lw=2)
            ax.scatter([i],[float(row['mean_revision_gain_c'])],color='#222222',s=20)
        ax.axhline(0,color='#444444',lw=1);ax.set(title=var.upper(),ylabel='Mean RevisionGain (degrees C / opportunity)',xticks=[0,1,2],xticklabels=['HKO','Nearest','Bilinear']);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Daily revisions: positive gain means the new forecast reduced error')
    save(fig,'revision_gain.png','Same target date, D7 to D1; no-change opportunities included. Whiskers are 95% seven-day block CIs; proxy and availability limits remain.')
    accuracy_table=table(['变量','HKO MAE','Nearest MAE','Bilinear MAE','Bilinear−HKO（95% CI）'],[
        [var.upper(),n(score(var,'hko')['mae']),n(score(var,'nearest')['mae']),n(score(var,'bilinear')['mae']),
         n(contrast(var,'bilinear_minus_hko_ae')['delta_mae'])+' '+interval(contrast(var,'bilinear_minus_hko_ae'))] for var in ('tmax','tmin')])
    spatial_table=table(['变量','Bilinear−nearest MAE','95% CI（7 天块）','95% CI（14 天块）'],[
        [var.upper(),n(contrast(var,'bilinear_minus_nearest_ae')['delta_mae']),interval(contrast(var,'bilinear_minus_nearest_ae')),interval(contrast(var,'bilinear_minus_nearest_ae'),'ci14')] for var in ('tmax','tmin')])
    lead_table=table(['变量','提前天数','日期数','HKO MAE','Nearest MAE','Bilinear MAE','空间差值 95% CI'],[
        [var.upper(),lead,score(var,'hko',lead)['n_dates'],n(score(var,'hko',lead)['mae']),n(score(var,'nearest',lead)['mae']),n(score(var,'bilinear',lead)['mae']),interval(contrast(var,'bilinear_minus_nearest_ae',lead))] for var in ('tmax','tmin') for lead in range(1,8)])
    revision_table=table(['变量','产品','原始数值修订率','≥1°C 修订率','改动后改善占比¹','平均 RevisionGain（95% CI）'],[
        [var.upper(),p,n(update(var,p)['revision_rate_pct'],2)+'%',n(update(var,p)['material_revision_rate_pct'],1)+'%',
         n(update(var,p)['useful_changed_pct'],1)+'%',n(update(var,p)['mean_revision_gain_c'])+' '+interval(update(var,p))]
        for var in ('tmax','tmin') for p in ('hko','nearest','bilinear')])
    gain_table=table(['变量','收益差值（前者−后者）','平均差值','95% CI'],[
        [r['variable'].upper(),r['contrast'],n(r['delta_gain_c']),interval(r)] for r in v if r['new_lead']=='0'])
    temporal_table=table(['变量','方法','完整日轨迹 MAE','仅日内原生采样 MAE','午夜处理平均改变量（°C）'],[
        [r['variable'].upper(),r['product'],n(r['full_hkt_window_proxy_mae']),n(r['native_sample_only_mae']),n(r['mean_abs_midnight_effect'])] for r in t if r['lead_days']=='0'])
    native_table=table(['变量','Nearest 轨迹近似 MAE','Nearest 原生区间条件性 MAE 包络²'],[
        [var.upper(),n(score(var,'nearest')['mae']),n(temporal(var,'nearest')['native_interval_conditional_mae_lower'])+'–'+n(temporal(var,'nearest')['native_interval_conditional_mae_upper'])] for var in ('tmax','tmin')])
    slide=[]
    quoted={('tmax',1,'hko'):1.039,('tmax',7,'hko'):1.509,('tmin',1,'hko'):.764,('tmin',7,'hko'):1.107,
            ('tmax',1,'bilinear'):2.716,('tmax',7,'bilinear'):2.997,('tmin',1,'bilinear'):.857,('tmin',7,'bilinear'):1.299}
    for (var,lead,p),old in quoted.items():
        new=float(score(var,p,lead)['mae']);slide.append(dict(variable=var,lead_days=lead,product=p,canva_unverified_quote_mae=old,
            recomputed_mae=new,difference=new-old,rounding_matches=abs(new-old)<.0005,
            qualification='Different auditable selection/temporal pipeline; original slide inputs unavailable. Do not force-fit.'))
    with (HERE/'slide_number_reconciliation.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(slide[0]),lineterminator='\n');writer.writeheader();writer.writerows(slide)
    spatial_answers=[]
    for var in ('tmax','tmin'):
        row=contrast(var,'bilinear_minus_nearest_ae');low=float(row['ci7_low']);high=float(row['ci7_high'])
        finding='bilinear 的平均误差较低' if high<0 else 'nearest 的平均误差较低' if low>0 else '两种方法的平均误差差异尚不明确'
        spatial_answers.append(var.upper()+'：'+finding+'（空间差值 '+n(row['delta_mae'])+'°C，95% CI '+interval(row)+'）。')
    note=f'''# Task 2b：按 HKT 00:00–次日 00:00 重做温度比较

2026-11-16 HKT。只修正温度分析；已有 rainfall 研究保留原样。

## 先说明这次比较的含义

**每一个目标日都从香港时间 00:00 开始，到次日 00:00 结束。**
这次 {len(cases):,} 个温度案例都保存了相同定义的开始／结束时间，预报与 HQ 观测对应同一个香港自然日。
Nearest 与 bilinear 使用真实四邻点数据、同一批日期、同一个 GFS run、同一时间重建和同一条观测。

在下述可核实的回顾性选版及温度轨迹近似下，全年 D1–D7 的结果为：

{accuracy_table}

**空间方法的直接结论：** {' '.join(spatial_answers)}
这个差值只改变空间对齐方式，比把不同日期、不同起报或不同日界线的结果放在一起更能回答 nearest 与 bilinear 的差异。

**严格基准仍有两项证据缺口：**三小时输出不能唯一恢复原生日极值；HKO 的 2026 年补抓时间及 GFS 的初始化时间也不能证明 2025 年实际可用性。
所以这里报告完整香港日的、明确标记的温度轨迹近似比较，**不宣称已经得到原生精确日极值或经历史可用性验证的全年产品优越性。**

## 00:00 窗口与选版时间分开记录

控制定义来自 Canva 实际第7页 “Task 2a — Benchmark Definition”，原文写明：
`HKO Headquarters observations`、`1 Jan–31 Dec 2025`、`HKT day: [00:00, next 00:00)`。
[定义摘录及对应关系](benchmark_source.json) 保留这次读取结果。

下表以 2025-01-01、提前一天为例。**14:00 只来自温度页的选版描述，绝不是温度统计日的起点。**

| 项目 | HKT | UTC |
| --- | --- | --- |
| 目标日开始 | 2025-01-01 00:00 | 2024-12-31 16:00 |
| 目标日结束，不含该时刻 | 2025-01-02 00:00 | 2025-01-01 16:00 |
| GFS 初始化 | 2024-12-31 08:00 | 2024-12-31 00:00 |
| HKO 选版情景截止 | 2024-12-31 14:00 | 2024-12-31 06:00 |

本次仅把第8页的 `GFS 00 UTC / HKO 14:00 HKT` 作为**单独标记的复现情景**。
HKO 选择截止前公告时间和 RSS 发布时间均有效的最新预报；不把补抓时间当起报时间。
两者预报年龄不同，不能把它解释成相同信息年龄的核心模型实验。
第7页的自然日要求始终控制预报／观测的有效窗口。

## Nearest 与 bilinear 怎样计算

HQ 坐标为 22.30194444°N、114.17416667°E。四格按 SW、SE、NW、NE 顺序为
22.25/114.00、22.25/114.25、22.50/114.00、22.50/114.25。Nearest 使用 SE，距离 HQ 约 9.71 km。
固定 bilinear 权重为 **{', '.join(f'{w:.8f}' for w in meta['bilinear_weights'])}**，均为非负，合计为1。

每个三小时时刻先把四格的 **2 m 瞬时温度**对齐至 HQ。随后连接成同一条分段线性时间轨迹，
在精确的 HKT 日界线裁切，再取该日轨迹的最高／最低值。两个午夜均由左右原生输出夹住，禁止外推。
对于连续轨迹，在不含次日午夜的窗口内使用午夜前的单侧极限；没有加入次日内部的极值。

没有把四格各自的日最高温／最低温直接加权后冒充“总部温度轨迹的极值”。两种运算一般不交换。
这种错误次序与本次 bilinear 结果的平均绝对差为 Tmax **{n(temporal('tmax','bilinear')['mean_abs_interpolation_order_effect'])}°C**、
Tmin **{n(temporal('tmin','bilinear')['mean_abs_interpolation_order_effect'])}°C**，仅作运算次序诊断。

{spatial_table}

差值 = bilinear 绝对误差 − nearest 绝对误差；负值倾向 bilinear，正值倾向 nearest。
置信区间来自配对日历区块 bootstrap，2,000 次、seed 3522；同一天所有 lead 和产品一起抽样。
区间反映本年天气日变异，没有消除时间重建、空间代表性及历史可用性的限制；分组比较未做多重检验校正。

![温度误差随提前天数变化](accuracy_by_lead.png)

![两种空间方法的配对差值](bilinear_minus_nearest.png)

{lead_table}

![全年逐日的提前一天温度](daily_D1.png)

## 更新得是否有效

保持目标日、变量、空间方法及选版规则不变，每天比较前后预报：D7→D6，一直至 D2→D1。
每个变量有 **2,190 个共同机会**。RevisionGain = 旧绝对误差 − 新绝对误差；正值表示改善。
平均收益的分母包括没有改变数值的机会，不只挑选改对的更新。

{revision_table}

¹ “改动后改善占比”只以该产品发生数值变化的机会为分母，三个产品的条件子样本不同。
HKO 是整数温度，GFS 保留小数，所以同时报告 ≥1°C 的改动率；[完整表](revision_summary.csv) 还包含共同整数精度下的修订率。
“经常变化”“变化幅度大”“更接近最终观测”分别衡量不同性质，不能互相替代。

{gain_table}

收益差值 CI 跨零时，不能判定平均改善谁较多。即使某项近似下的差值不跨零，仍只适用于同一重建及选版情景。
收益较大也可能来自起点误差较大，不意味着最终预报更准；验证程序另外核对了整条链的首尾误差差是否等于累计收益。

![日更新的平均误差改善](revision_gain.png)

## 完整窗口与原生极值不是同一件事

这次窗口长度严格为24小时，但 GFS 在输出之间的温度并未直接观测。
我们统一使用三小时采样的连续线性轨迹作为可重复的近似；并不把它称为原生精确 Tmax/Tmin。
官方 GFS 输出在前120小时可逐小时、之后逐三小时，因此也不能假定七天都能取得逐小时原生输出。
[NOAA GFS 输出说明](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/gfs.php)

{temporal_table}

此外，复用数据库已有的 nearest 原生 TMAX/TMIN 区间作时间诊断：日内完全包含的区间联合覆盖21小时，
相交区间覆盖24小时，但跨日极值无法精确分到午夜两侧。沿用已披露的 max(0.02°C, 量化步长) 余量得到：

{native_table}

² 原生区间包络是带语义和编码余量假设的保守范围，不是统计 CI、不是认证编码误差界限，
也没有证明所有区间来自同一连续温度路径。这里只作为 nearest 的时间敏感性检查；没有由一个格点捏造 bilinear 原生区间。
由此不能把 GFS 与 HKO 的全部误差差距都归因于预报能力。

## 缺失、可用性与结论边界

| 检查 | 本次结果 | 可支持的解读 |
| --- | --- | --- |
| 全年 HQ 数值观测 | Tmax/Tmin 各365天，完整性 C | 同一站点、同一年真值 |
| 数值配对 | 每变量2,555；两方法相同交集 | 数值缺失率 {n(meta['forecast_pair_missingness_pct']['tmax'],1)}%／{n(meta['forecast_pair_missingness_pct']['tmin'],1)}%，低于30%门槛 |
| GFS 四邻点 | 371 runs，21,518 原始 TMP 来源 | 空间方法使用真实四格，不由单点推造 |
| Nearest 对旧导入值 | 21,518 次独立控制，差异 {meta['nearest_control_mismatches']} | 新提取与已有温度数据一致 |
| HKO 截止前捕获证据 | 0／2,555 个窗口 | 2026 补抓不能证明2025实际可用性 |
| GFS 历史 available time | 未建立 | 初始化时间不能充当实际发布时间 |
| 共同操作可用性已证实案例 | 0 | 不给出无条件的全年产品优越性结论 |

数值完整不等于历史可用性证据完整。严格的 archive-confirmed 结果目前不能从现有资料生成；
不能把 2026 抓取时间改写成 2025，也不能把公告时间自动称为实测接收日志。
HKO 源字段、截止点及选择结果均保留在 [逐条选版记录](vintage_selection.csv) 和 [温度案例](cases.csv)。
GFS 在 2 m 高度；HQ 站海拔记录为 {meta['station']['elevation_m']} m，观测传感器具体高度尚未建立。
未做高度校正或海陆代表性校正；bilinear 不会自动消除这些差异。

Canva 现有温度表的数字没有附原始选版与重建输入。本次不拿它们当真值强行拟合。
[逐项对照](slide_number_reconciliation.csv) 区分讲义旧引用与本次可复核情景；两者不一致时，应使用带来源和规则的新结果，
或者取得旧表的原始捕获证据后再解释差异。

## 核对与复现

数据库仅只读访问；没有写入或修改中央数据库。原始全球 GRIB 只在内存使用，缓存只保留四点和来源。
雨量目录的文件指纹逐一核对保持不变。

```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s benchmark/temperature_task2b_2025 -p test_methods.py -v
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/read_hko.py
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/acquire_four_cells.py --workers 16
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/run_analysis.py
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/verify_results.py --live --online-controls
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/build_report.py
```

只从已提交输入与案例核对，无需数据库或下载：

```powershell
.\\.venv\\Scripts\\python.exe benchmark/temperature_task2b_2025/verify_results.py
```

| 文件 | 用途 |
| --- | --- |
| [PLAN.md](PLAN.md)、[benchmark_source.json](benchmark_source.json) | 第7页定义与第8页选版情景分开记录 |
| [source_points.csv](source_points.csv)、[window_knots.csv](window_knots.csv) | 真实四点、原始字节来源及完整日轨迹节点 |
| [native_interval_inputs.csv](native_interval_inputs.csv) | 已导入 nearest 原生极值，供单独时间诊断 |
| [cases.csv](cases.csv)、[scores.csv](scores.csv)、[spatial_contrasts.csv](spatial_contrasts.csv) | 5,110 案例、MAE/RMSE/bias 和配对 CI |
| [revision_pairs.csv](revision_pairs.csv)、[revision_summary.csv](revision_summary.csv)、[revision_contrasts.csv](revision_contrasts.csv) | 修订前后值、幅度、收益及差值 |
| [run_metadata.json](run_metadata.json)、[validation.json](validation.json) | 输入／输出 hashes、门槛与独立核对结果 |

验证包含 {valid['checks']:,} 项检查，全部香港日边界与四点计算、HKO 选版与真值、原始 nearest 控制、误差与修订算术、
配对区块 CI，并对12个月原始 NOAA 文件做独立的四格数组索引解码。
这些检查不认证原生完整日极值或历史可用性。旧 [20:00／单点温度实验](../temperature_2025/README.md)
只保留为不同规则下的历史实验，不能替代本次 Task 2b 的空间对齐比较。
'''
    (HERE/'README.md').write_text(note,encoding='utf-8',newline='\n')
    manifest=dict(scope='Corrected Task 2b temperature publication; all raw/global files and caches excluded',
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='publication_manifest.json'})
    (HERE/'publication_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Corrected temperature report and four figures built.')


if __name__=='__main__':main()
