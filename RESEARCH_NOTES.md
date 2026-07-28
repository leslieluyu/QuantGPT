# QuantGPT A股因子挖掘研究笔记（终局版 2026-07-28）

## 研究概述

- **宇宙**：csi1000（中证1000）+ csi500（中证500）
- **回测区间**：2020-01-01 ~ 2024-12-31（in-sample）；2017-01-01 ~ 2024-12-31（rolling_val）
- **持仓周期**：5日为主，同时测试 hp=10/20
- **共测试因子**：~40个（含跨宇宙、跨持仓期变体）

---

## 终局排行榜（全量，含 anti_overfit）

| # | 因子名 | 得分 | AO | RV | 宇宙 | hp | IC | IR | mono |
|---|--------|------|----|----|------|----|----|----|------|
| 🥇 | **vol15_amtrev** | **70.6 B** | **4/4** | 55.3 | csi1000 | 5 | 0.071 | 0.359 | 0.70 |
| 2 | csi500_amtrev | 70.1 B | 4/4 | 50.1 | csi500 | 5 | 0.067 | 0.288 | 0.90 |
| 3 | vol15_amtrev_hp10 | 69.2 B | 4/4 | 52.2 | csi1000 | 10 | 0.066 | 0.288 | 0.90 |
| 4 | **vol15_amtrev60** | **68.8 B** | **4/4** | **57.1** | csi1000 | 5 | 0.066 | 0.330 | 0.70 |
| 5 | vol15_amtrank20 | 68.7 B | 3/4 | — | csi1000 | 5 | 0.066 | 0.330 | 0.70 |
| 6 | csi500_vol15 | 67.2 B | 4/4 | — | csi500 | 5 | 0.065 | 0.261 | 0.90 |
| 7 | amtrev+park | 66.9 B | 4/4 | — | csi1000 | 5 | 0.078 | 0.388 | 0.90 |
| 8 | vol20_amtrev | 66.1 B | 4/4 | — | csi1000 | 5 | 0.074 | 0.370 | 0.70 |
| 9 | overnight_vol15 | 65.4 B | 4/4 | — | csi1000 | 5 | 0.077 | 0.355 | 0.50 |
| 10 | amtrev+ret20 | 65.4 B | — | — | csi1000 | 5 | 0.052 | 0.270 | 0.70 |

> v4 冠军 vol15_amtrev（70.6）微领，但 vol15_amtrev60 的 rolling_val 分最高（57.1 vs 55.3）。

---

## 双冠军因子

### 🥇 in-sample 冠军：vol15_amtrev（csi1000, hp=5）
```
rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(volume/ts_mean(volume,20)))
```
- **得分**：70.6 B，anti_overfit 4/4，T½=21d
- **rolling_val**：12窗口，mean_testIC=0.057，IR=0.323，2021~2023 Sharpe 1.3~3.1

### 🏆 rolling 冠军：vol15_amtrev60（csi1000, hp=5）
```
rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(volume/ts_mean(volume,60)))
```
- **得分**：68.8 B，anti_overfit 4/4
- **rolling_val score=57.1**（全部因子最高），mean_testIC=0.060，IR=0.330
- decay=0.030（近乎零衰减），12窗口 IC 全正，仅 win10/11 Sharpe 轻微转负（-0.15/-0.68）

**推荐用 vol15_amtrev60**：60日成交量基准更稳定（不被单月异常成交扰动），rolling 样本外表现更佳。

---

## 关键结论

### 1. 「低波动 + 成交量萎缩」是 A股 csi1000/csi500 最强纯技术因子族

共测出 5 个 4/4 anti_overfit + score≥65 的同族变体，跨宇宙（csi1000/csi500）、跨窗口（15/20d）、跨持仓期（5/10d）均成立——这是真实信号的标志。

| 维度 | 结果 |
|------|------|
| 宇宙 | csi1000 ≈ csi500（70.6 vs 70.1），信号普适 |
| 成交量基准 | 60d 略优于 20d（rolling 57.1 vs 55.3） |
| 持仓期 | hp=5 最优（70.6）；hp=10 降至 69.2；hp=20 降至 64.3 |
| 组合因子 | 加 Parkinson +0.9分但不抵成本；三/四因子组合均拖分 |

### 2. OHLCV 因子天花板约 70~71 B

- 全部 ~40 个因子无一突破 71
- amihud 非流动性（D级 25.9）、价量相关（C级 56.4）、skewness/kurtosis（未见）等经典因子在 csi1000 5日持仓下无效
- overnight vol（65.4 B）是唯一意外惊喜的新单因子

### 3. 2024年 L/S Sharpe 普遍转负

所有因子在 2023-07~2024-10 窗口 Sharpe 转负，但 IC 保持正值：
- 因子方向（选股能力）未失效
- L/S 组合受 2024年牛市 beta 行情拖累（多头小盘股未跑赢空头）
- **含义**：单边做多低波动股仍有效，对冲策略在 2024 受损

### 4. 突破 B→A（≥80）需要基本面数据

当前组合：IC~0.07, IR~0.35, mono~0.70, ls_sharpe~0.9
- IC_IR 分项：0.35 得 ~8/15（需 IR≥1.0 才满分）
- group_backtest 分项：sharpe~0.9 得 ~10/15（需 sharpe>1.5+mono=1.0）
- **结构上限**：纯 OHLCV 在 csi1000/5日持仓下，自然 IR 上限约 0.4

要达到 A 级需引入：
1. 基本面质量因子（ROE、净利润增速稳定性）
2. 分析师预期修正
3. 另类数据（舆情、资金流）

---

## 否决因子记录

| 因子 | 得分 | 否决原因 |
|------|------|---------|
| amihud15 | 25.9 D | 方向错误（csi1000 流动性溢价反转）|
| updays_20 | 30.6 D | 动量在 csi1000 完全无效 |
| pv_corr20 | 56.4 C | 价量相关性信号太弱 |
| intraday_vol15 | 58.5 C | 弱于隔夜波动版本 |
| amtrev_zscore+park | 52.6 C | zscore 标准化后组合反而变差 |
| vol15+pb_value | 失败 | pb 基本面字段在直接脚本中不可用 |
| amihud_ts_abs | 失败 | ts_abs 不在算子注册表（应用 abs） |

---

## 技术改进汇总

| 改动 | 文件 | 效果 |
|------|------|------|
| TickFlow batch API 替换 baostock | market_data.py | 1000只下载从25min→2min |
| TickFlow SSL 重试（3次指数退避） | market_data.py | 瞬时 SSL EOF 不再 fallback baostock |
| `_factor_df` 传原始因子值（bug fix） | backtest.py | anti_overfit IC 从≈0修复到真实值 |
| 空 DATABASE_URL（bug fix） | db.py | 消除日志里持续的 SQLAlchemy 报错 |
| Worker 进程 logging | task_executor.py | spawn 进程日志写入 logs/mcp.log |

---

## Bug 修复记录

### 1. `backtest.py` — `_factor_df` 传中性化后因子值
```python
# 修复后
"_factor_df": work[["trade_date","stock_code","daily_ret"]].assign(
    factor_value=raw_factor_for_ic.reindex(work.index)
),
```

### 2. `db.py` — 空 DATABASE_URL
```python
url = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./quantgpt.db"
```

### 3. Worker 进程 logging 丢失
`task_executor.py` 的 `_run_backtest_in_process` 添加 `_setup_worker_logging()`。
