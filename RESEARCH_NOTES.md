# QuantGPT A股因子挖掘研究笔记

## 阶段成果（2026-07-28）— 最新

### 环境
- 宇宙：csi1000（中证1000，1000只中小盘股）
- 回测区间：2020-01-01 ~ 2024-12-31（anti_overfit/rolling用2017起）
- 持仓周期：5日，分5组，行业+市值中性化
- 数据源：TickFlow batch API（100只/请求，~13s加载1000只；baostock兜底）

### 综合排行榜（含 anti_overfit）

| 排名 | 因子名 | 得分 | IC | IR | mono | anti_overfit | T½ |
|------|--------|------|----|----|------|--------------|----|
| 🥇 | vol15_amtrev | 70.6 B | 0.071 | 0.359 | 0.70 | **4/4 ✓** | 21d |
| 2 | vol15+ret20_rev | 66.0 B | 0.052 | 0.254 | 0.70 | **4/4 ✓** | 999d |
| 3 | vol15_baseline | 65.9 B | 0.078 | 0.361 | 0.80 | 3/4 ✗T½ | 1d ✗ |
| 4 | vol15x_park15 | 63.1 B | 0.070 | 0.323 | 0.80 | **4/4 ✓** | 119d |
| 5 | vol15+amt_shrink | 63.0 B | 0.066 | 0.338 | 0.30 | **4/4 ✓** | 999d |
| 6 | vol15+ret5_rev | 61.1 B | 0.053 | 0.258 | 0.40 | — | — |
| 7 | vol20_baseline | 61.0 B | 0.077 | 0.352 | 0.30 | — | — |
| 8 | vol15+ret10_rev | 60.2 B | 0.052 | 0.255 | 0.00 | — | — |
| 9 | hl_range15 | 59.6 C | 0.059 | 0.275 | 0.60 | — | — |
| 10 | vol_stability10 | 59.0 C | 0.048 | 0.248 | 0.70 | — | — |
| 11 | close_open_rev10 | 51.3 C | 0.040 | 0.206 | 0.00 | — | — |
| 12 | overnight_rev10 | 45.6 C | -0.040 | -0.190 | 0.40 | — | — |

---

### 🥇 最优因子：低波动 + 成交量萎缩（vol15_amtrev）

```
rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(volume/ts_mean(volume,20)))
```

**经济逻辑**：低波动（无人关注）× 成交量低于均值（资金未进入）= "安静股"被系统性低估。A股散户追涨杀跌，此类股定价洼地。

**anti_overfit 4/4 全通过**：
- IC稳定性：IC=0.052，2020~2024每年均正（0.060/0.051/0.059/0.050/0.039）
- 子样本压力：牛/熊/震荡/高低波动率 consistency=1.0
- 安慰剂检验：真实IC(0.052) >> 置换95th(0.017)，时移衰减正常
- 半衰期：**T½=21d**（适合5日持有期，信号不会在1天内消失）

**rolling_validation（2017-2024，12窗口）**：
- mean_testIC=0.057，mean_testIR=0.323，score=55.3
- win0~win9（2021~2023）：IC全正，Sharpe 1.3~3.1，稳健
- win10~win11（2023-07~2024-10）：IC仍正（0.036/0.047）但Sharpe转负（-0.07/-0.65）
- 注：2024年牛市beta行情，L/S对冲组合受损，但因子方向未失效

---

### vol15_baseline 半衰期不合格（3/4）

之前记录的 anti_overfit 4/4 是 bug 修复前的结果（中性化后因子值，IC 失真）。修复后重测：
- ✗ 半衰期估计：**T½=1d**，ics={'1': 0.049, '5': 0.010, '10': 0.004}
- 信号在1天内就衰减至噪声水平，但回测用5日持有期，存在持有期错配

这解释了 vol15_amtrev 在整体评分上反超 vol15_baseline 的原因。

---

## 技术改进（2026-07-28）

### TickFlow batch API 替换 baostock

**文件**：`quantgpt/market_data.py`

- 新增 `_fetch_tf_batch()`、`_fetch_remote_tf_batch()` 方法
- `fetch_stocks` 优先级：TickFlow(100只/请求) → baostock(逐只兜底) → rqdatac
- TickFlow 用 `requests` 库（`urllib` 在 QuantclassClient Python 沙盒中有网络限制）
- 下载全历史（count=10000）缓存到 parquet，后续运行无需重下载

**性能对比**：

| 数据源 | 1000只首次下载 |
|--------|---------------|
| baostock | ~15-25 分钟 |
| TickFlow | **~2 分钟** |

---

## Bug 修复记录

### 1. `backtest.py` — `_factor_df` 传的是中性化后因子值
**现象**：`run_anti_overfit` 和 `run_rolling_validation` 收到的 `factor_value` 是行业/市值中性化后的残差，IC≈0。

**修复**：
```python
# 修复前
"_factor_df": work[["trade_date", "stock_code", "factor_value", "daily_ret"]].copy(),
# 修复后
"_factor_df": work[["trade_date", "stock_code", "daily_ret"]].assign(
    factor_value=raw_factor_for_ic.reindex(work.index)
),
```

### 2. `db.py` — 空 `DATABASE_URL` 导致 SQLAlchemy 崩溃
```python
# 修复前
url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./quantgpt.db")
# 修复后
url = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./quantgpt.db"
```

### 3. Worker 进程日志丢失
`ProcessPoolExecutor` spawn 进程不继承 FileHandler，修复：`_setup_worker_logging()` 用绝对路径在 worker 内重建 FileHandler。

---

## 下一步方向

1. **csi2000 验证**：TickFlow 现已可快速下载，在 csi2000 上验证低波动效应是否更强
2. **组合因子精化**：vol15_amtrev（成交量版）与 vol15x_park15（Parkinson版）的组合
3. **接入真实 anti_overfit 分数**：`score_factor` 默认 anti_overfit=50，可自动跑后修正
4. **2024年Sharpe衰减研究**：win10/11 Sharpe转负，是否与市场结构变化有关
