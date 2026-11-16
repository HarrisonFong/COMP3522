# 2025 年 1 月 GFS–HKO 試行：分析前固定的方法

本輪沿用 repository 的研究資料夾／Markdown findings 格式，延伸現有 GFS
fairness pilot；不改寫原 pilot、不修改資料庫。目標日期為 2025-01-01 至
2025-01-31，包含較早發布的預報，避免月初長 lead 左截尾。

## 比較規則

- 比較的是 HKO 公開預報和經指定方法處理的 GFS raw output；不把差異全歸因於核心模型。
- 共同參考是 HQ 站；不宣稱公開預報的官方空間定義就是 HQ。
- 主設計每日 20:00 HKT、D1–D7。選擇 bulletin time 和 RSS publication time
  均不晚於截止點的最新 HKO 版本。沒有同日版本時可保留真正最新的舊版本並記錄 age。
- GFS 以 run + 固定 6 小時 delay 作**假設可用時間**；不是歷史發布證據。
  4/8/12 小時及 12:00/16:00 HKT 截止點為敏感度。絕不使用目前下載時間判定歷史可用性。
- GFS 主空間方法維持已存檔 nearest point；0.25°本身不保證 9.71 km 距離。
  只有一個點，不能重造 bilinear interpolation。高度資訊不足時不套任意 lapse rate。
- 日界線採 HKT 00:00–24:00，UTC 前日 16:00 至當日 16:00。
- 每一個 Tmax/Tmin endpoint 分別構造 contained/overlapping interval sensitivity envelope，
  padding=max(0.02°C, 該 GRIB field 的 inspected quantization step)，取**該 endpoint
  envelope 的 midpoint**作 deterministic approximation。另評估八個 instantaneous samples
  的 extrema。這些範圍不是置信區間、機率區間或保證的真實日極值界限。

## 變量和指標

- 溫度：與同一天 C 且 numeric 的 HQ Tmax/Tmin 分別計 MAE、RMSE、bias，
  paired ΔAE=|GFS−O|−|HKO−O|。負數支持 GFS、正數支持 HKO。
- baseline：Task 1 同一個 1991–2020、leap-calendar ±2 日 climatology mean；
  persistence 用 decision date−2 的實測，僅為回顧性 comparator。
- Revision：同一 target date 相鄰 decision day，即 D(k+1)→Dk，k=1–6；
  兩產品都每天只選一次。Task 1 的 change rate、MAR、usefulness U 和 FFI 公式保留，
  不拿本次 daily-cutoff 樣本冒充原 Task 1 consecutive-bulletin ≤24h 主樣本。
- 原始 changed threshold=1e−10 僅排浮點噪聲；另外同時計算 ≥1°C 的 material
  revision rate，防止 GFS 較細小數位與 HKO 公布精度主導 change-rate 比較。
- mean U=|F_old−O|−|F_new−O|。changed-only 和 all-pairs 分母分開。
- paired mean ΔAE 的 95% exploratory intervals：2,000 次 circular calendar-day
  block bootstrap，7 日主、3 日敏感度；同一日全部 leads/products 一起抽。
  31 個天氣日不是 217 個獨立日；多 lead 區間未作多重比較校正。
- RH 和 rainfall 先審計現有 GFS payload。缺少相應產品時只做 HKO 側診斷，
  並明列不能跨產品比較；不從 temperature 捏造 RH、rain 或 probabilities。
- HKO PSR 維持 Task 1 已同意的 22 站面積加權日雨量 ≥10 mm proxy；它不是官方
  territorial label。HQ-point ≥10 mm 僅另外呈現，不混合事件定義。

## 可以形成的結論

完整配對可支持這個月、地點、版本規則和 approximation 下的條件式比較。
對發布延遲或 temporal envelope 改變敏感時，結論標記 method-dependent。
資料缺失與該月本來沒有颱風／大雨必須分開，不能把季節範圍當資料遺失。
一月冬季結果不外推全年、其他站點、RH/rain 或整個機構。
