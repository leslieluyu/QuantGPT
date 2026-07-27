# QuantGPT A股因子挖掘研究笔记

## 阶段成果（2026-07-27）

### 环境
- 宇宙：csi1000（中证1000，1000只中小盘股）
- 回测区间：2020-01-01 ~ 2024-12-31
- 持仓周期：5日，分5组，行业+市值中性化

### 因子排行榜

| 排名 | 因子表达式 | 得分 | IC | IC_IR | 单调性 | anti_overfit |
|------|-----------|------|-----|-------|--------|-------------|
| 🥇 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 15))` | 75.1 B | 0.088 | 0.591 | 0.60 | **100/100 ✓✓✓✓** |
| 2 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 20))` | 74.9 B | 0.086 | 0.564 | 0.90 | — |
| 3 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) * rank(-1*ts_mean((high-low)/close, 15))` | 73.8 B | 0.091 | 0.571 | **1.00** | — |
| 4 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + rank(-1*ts_mean((high-low)/close, 15))` | 72.8 B | 0.090 | 0.562 | 0.90 | — |
| 5 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(ts_mean(close/vwap-1, 5)))` | 71.0 B | 0.077 | 0.546 | 0.80 | — |
| 6 | `rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(volume/ts_mean(volume,20)))` | 66.4 B | 0.082 | 0.697 | 0.10 | — |
| 7 | `rank(-1*ts_mean((high-low)/close, 15))` | 68.5 B | 0.087 | 0.534 | 0.60 | — |
| — | VWAP反转、开盘跳空反转 | 43~47 C | — | — | — | — |

> hs300 同样因子只有 B(62.2)；csi1000 小盘市场效率低，低波动溢价更强。

### 最优因子：15日低波动（low-volatility）

```
rank(-1 * ts_std(close / ts_shift(close, 1) - 1, 15))
```

**经济逻辑**：A股散户主导，追涨高波动股票，造成高波动股定价偏高；低波动股被低估，长期超额。中证1000小盘尤其明显。

**anti_overfit 4/4 全通过**：
- IC稳定性：年均IC=0.076，2020~2024每年均正（0.067 / 0.075 / 0.082 / 0.081 / 0.077）
- 子样本压力：牛/熊/震荡/高低波动率子样本方向100%一致
- 安慰剂检验：真实IC(0.076) >> 随机置换95th(0.003)，时移信号正常衰减
- 半衰期：信号持续时间≥5天

**真实总分估算**：75.1（score_factor）+ anti_overfit修正 +7.5 = **~82.6 → A级**

---

## Bug 修复记录

### 1. `backtest.py` — `_factor_df` 传的是中性化后因子值
**现象**：`run_anti_overfit` 和 `run_rolling_validation` 收到的 `factor_value` 是行业/市值中性化后的残差，IC≈0，与 `score_factor` 的 IC 相差约30倍。

**根因**：`_factor_df` 从 `work` 取 `factor_value`（已被 `neutralize_factor` 覆盖），而 IC 计算用的是中性化前的 `raw_factor_for_ic`。

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
**现象**：日志持续输出 `Could not parse SQLAlchemy URL from given URL string`。

**根因**：`.env` 里 `DATABASE_URL=`（空字符串），`os.environ.get("DATABASE_URL", default)` 当 key 存在但值为空时不走 default。

**修复**：
```python
# 修复前
url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./quantgpt.db")
# 修复后
url = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./quantgpt.db"
```

### 3. Worker 进程日志丢失
**现象**：`ProcessPoolExecutor` spawn 的 worker 进程是全新 Python 进程，不继承父进程的 `FileHandler`，backtest 步骤日志全部丢失。

**修复**：在 `task_executor.py` 的 `_run_backtest_in_process` 里添加 `_setup_worker_logging()`，用绝对路径追加写入同一个 `logs/mcp.log`。

---

## 下一步方向

1. **接入真实 anti_overfit 分数**：在 `score_factor` 里自动运行 `run_anti_overfit` 并将得分注入 `compute_factor_score`（而不是固定 50）
2. **继续探索**：在低波动×Parkinson 乘积基础上加基本面质量因子（需 `_enrich_with_fundamentals`）
3. **扩展宇宙**：在 csi2000 上验证低波动效应是否更强
4. **滚动验证**：对最优因子跑 `run_rolling_validation`（2017-2024，8年），确认样本外稳健性
