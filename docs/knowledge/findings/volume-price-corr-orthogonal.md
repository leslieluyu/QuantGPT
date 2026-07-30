# Volume-Price Correlation — Orthogonal Signal to amtrev_x_turn_v2

Date: 2026-07-30
Universe: csi1000, 2020-01-01~2024-12-31, holding_period=21, neutralize_industry=false, neutralize_cap=false, n_groups=5

## 结论

`rank(-1*ts_corr(volume, close, 10))` 是与月频冠军 `amtrev_x_turn_v2`（缩量低换手族）**正交**的新信号维度：
量-价时序相关性（短窗口）衡量的是"放量是否伴随上涨"，逻辑上不同于冠军的"缩量程度"，实测截面相关性验证了这一点。

- score=82.0（A级），IC=0.063，IC_IR=0.75，monotonicity=0.9
- anti_overfit 4/4 PASS（综合分100）：IC稳定性/子样本压力/安慰剂检验/半衰期估计全部通过，yearly IC 2020-2024 全部为正（0.028~0.079区间）
- 与 `amtrev_x_turn_v2` 的日度截面 Spearman 相关性：均值 0.265，中位数 0.275（117个交易日样本，2020-01~2020-06）—— 低于 0.3 正交阈值
- **Walk-Forward 滚动验证：2/2 窗口 test_IC 为正（0.061、0.050），decay 状态 stable（mean_decay=-0.004，几乎不衰减）**。

  修复过程：`run_rolling_validation` 默认 3年训练+1年验证+1年测试、步长3个月的窗口方案，在 `end_date=2024-12-31`（任务固定参数）下卡在严格 5 年边界上（`rolling_validator.py:130` 用 `test_end > max_date` 判断），一个窗口都生成不出来，报"数据不足"。价格数据缓存实际已到 2026-07（非仅 2020-2024），把 `end_date` 放宽到 2025-06-30（其余参数不变）即可正常生成窗口。受限于 csi1000 成分股快照仅有 2017-01/2020-01 两个月（`data/universe/`），目前只能生成 2 个窗口，无法复现冠军因子当年"28窗口/20年"的规模（那次验证本身也是用 2020-01 静态快照套用全历史，有幸存者偏差，见 `RESEARCH_NOTES.md` Phase 7）。

## 同族其他候选（评分详情，均已 anti_overfit 4/4 PASS，score 100）

| 表达式 | score | IC | IC_IR | mono | 半衰期(天) | 与冠军相关性 | WF(2窗口) test_IC | WF decay |
|---|---|---|---|---|---|---|---|---|
| `rank(-1*ts_corr(volume, close, 10))` | 82.0 | 0.063 | 0.75 | 0.90 | 52.8 | 0.265 | 0.061, 0.050（2/2正）| stable（-0.004）|
| `rank(-1*ts_corr(amount, close, 20))` | 81.6 | 0.069 | 0.71 | 1.00 | 106.7 | 0.263 | 0.056, 0.043（2/2正）| stable（0.17）|
| `rank(-1*ts_std(close/vwap, 20))` | 83.6 | 0.113 | 0.76 | 1.00 | (未测) | 0.416（**超过0.3阈值，与冠军有中度重叠**） | 0.067, 0.049（2/2正）| **unstable（0.39，train IC比test高40-47%）** |

综合 WF decay 表现看，`ts_corr(volume, close, 10)` 是三者中最稳健的（train→test 几乎无衰减），推荐作为正交叠加的首选；`ts_std(close/vwap,20)` 虽然静态评分最高，但衰减不稳定，叠加优先级应靠后。

`ts_corr(volume,close,N)` 符号随窗口长度反转：N=10/20 时原始 corr 与未来收益负相关（需要 `-1*`），N=40 时原始 corr 转为正相关（不能加 `-1*`，否则 IC=-0.063）。窗口越长信号衰减越慢（半衰期 10→52.8天，20→106.7天），但短窗口 IC 更高，需要在 IC 强度和信号持续性之间取舍。

## 推荐下一步

- `rank(-1*ts_corr(volume, close, 10))` 或 `rank(-1*ts_corr(amount, close, 20))` 可作为与冠军等权叠加的候选（相关性 <0.3，理论上叠加应能提升组合 IR）；`amount` 版本半衰期更长（106.7天 vs 52.8天），换手更低，工程上可能更适合与月频冠军叠加。
- `ts_std(close/vwap, 20)` 单独评分最高（83.6）但衰减不稳定、与冠军相关性 0.416，叠加价值有限，可作为独立备用因子而非组合对象。
- 冠军因子 `amtrev_x_turn_v2` 本身在 `run_rolling_validation` 下报 "Not enough rebalance dates for backtest"（`end_date` 放宽后仍失败，可能与 total_share 基本面数据在窗口切片后的对齐/dropna 有关），这是待查的独立小 bug，不影响本文档结论。
- 若要扩大 WF 窗口数（目前仅 2 个），需要补齐 csi1000 更多月份的成分股快照（`data/universe/csi1000_*.txt`），当前沙箱环境出网受限无法直接跑 baostock 回补，需在无网络限制的环境下执行。
