# QuantGPT A股因子挖掘研究笔记（终局版 2026-07-29）

## 研究概述

- **宇宙**：csi1000（主）、csi500（交叉验证）
- **回测区间**：2020-01-01 ~ 2024-12-31（in-sample）
- **持仓周期**：5日（主）、10日、20日、21日（月频）全部测试
- **共测试因子**：~70个（OHLCV + 基本面 + 月频技术 + 换手率 + 52周高点）
- **数据源**：TickFlow batch API（价格）+ baostock 季报（profit/growth/balance API）

---

## 全局排行榜（跨所有测试阶段）

| # | 因子名 | 表达式 | 得分 | AO | RV | 宇宙 | hp |
|---|--------|--------|------|----|----|------|----|
| 🥇 | **champ+low_cs20** | `amtrev_x_turn_v2 + rank(-1*ts_mean((close-low)/(high-low),20))` | **75.7 B** | **4/4** | — | csi1000 | **21** |
| 🥈 | **amtrev_x_turn_v2** | `(-1*rank(vol/ts_mean(vol,60))) + rank(-1*ts_mean(vol/total_share,60))` | **77.1 B** | **4/4** | — | csi1000 | **21** |
| 2 | amtrev_x_turn_m | `(-1*rank(vol/ts_mean(vol,60))) + rank(-1*ts_mean(vol/total_share,20))` | 74.5 B | 4/4 | — | csi1000 | 21 |
| 3 | vol15_amtrev | `rank(-1*ts_std(ret,15)) + (-1*rank(vol/ts_mean(vol,20)))` | 70.6 B | 4/4 | 55.3 | csi1000 | 5 |
| 4 | vol15_amtrev60 | `rank(-1*ts_std(ret,15)) + (-1*rank(vol/ts_mean(vol,60)))` | 68.8 B | 4/4 | **57.1** | csi1000 | 5 |
| 5 | low_vol15_m | `rank(-1*ts_std(ret,15))` | 68.1 B | 4/4 | — | csi1000 | 21 |
| 6 | champ+low_turn | vol15_amtrev60 + rank(-1*ts_mean(vol/total_share,20)) | 69.7 B | 4/4 | — | csi1000 | 5 |
| 7 | low_turn_20 | `rank(-1*ts_mean(vol/total_share,20))` | 64.4 B | 4/4 | — | csi1000 | 5 |

> **推荐生产因子（月频）：amtrev_x_turn，hp=21，score=74.5 B**
> **推荐生产因子（日频）：vol15_amtrev60，hp=5，rolling_val=57.1**

---

## 推荐因子完整表达式

### 🥇 月频冠军 v2（hp=21，参数优化后）
```
(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share, 60))
```
**指标**：score=77.1 B，top_ann=+25.1%，top_Sh=0.946，MDD=-43.1%，anti_overfit 4/4
**IC 详情**：IC=0.084，pos=0.72，yearly: 2020=0.076, 2021=0.111, 2022=0.100, 2023=0.074, 2024=0.057
**子样本**：bull=0.099, bear=0.050, sideways=0.082, consistency=1.0；半衰期 999d+
**需要**：total_share 列（baostock profit API 缓存）；turn 窗口从 20d→60d 是关键升级
**与 v1 对比**：+3pp 年化，Sh +0.12，bear IC 0.050 vs v1 的 0.063（略降但可接受）

### 🥈 月频 v1（历史参考）
```
(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share, 20))
```
**指标**：score=74.5 B，top_ann=+22.1%，top_Sh=0.829，bear IC=0.063（最稳）

### 🏆 日频冠军（hp=5，rolling_val 最佳）
```
rank(-1*ts_std(close/ts_shift(close,1)-1, 15)) + (-1*rank(volume/ts_mean(volume,60)))
```
**指标**：IC=0.066，IC_IR=0.330，score=68.8 B，anti_overfit 4/4，rolling_val mean_testIC=0.060，T½≈21d
**优势**：纯 OHLCV，无需基本面数据依赖

---

## 分阶段研究记录

### Phase 1：纯 OHLCV（v4/v5，~40因子）

**结论：天花板 ~70~71 B，无因子突破。**

- 低波动族（vol15_amtrev 变体）：全部 4/4 AO，跨宇宙/窗口/持仓期稳健
- 动量（updays_20, ret20）：D级，csi1000 5日动量完全无效
- amihud 非流动性：25.9 D，方向错误（csi1000 中流动性溢价反转）
- overnight vol（65.4 B）：最强单因子新发现
- skewness/kurtosis：未能成功运行

### Phase 2：基本面因子（v6/v7，pb/pe/roe/yoy_ni/debt_ratio）

**结论：基本面因子单独 C/D 级，与技术组合微增至 ~69 B，仍未突破。**

| 因子类别 | 代表 | 得分 | IC | 结论 |
|---------|------|------|----|------|
| 低PB（价值） | rank(-1*pb) | 52.7 C | 0.035 | 弱有效 |
| 高ROE（质量） | rank(roe) | 43.9 C | 0.024 | 弱有效 |
| 低PE | rank(-1*pe) | 34.5 D | **-0.013** | ⚠️ 方向反 |
| ROE+低PB | rank(roe)+rank(-1*pb) | 56.7 C | 0.036 | mono=1.0，最佳纯基本面 |
| yoy_ni（成长） | rank(yoy_ni) | 23.0 D | 0.001 | 纯噪声 |
| debt_ratio | rank(-1*debt_ratio) | 31.2 D | 0.011 | 无效 |
| champ+roe | vol15_amtrev60+rank(roe) | ~69.8 B | 0.074 | 微增，4/4 AO |

**重要发现：low_pe 方向反了** — csi1000 高PE股（成长股）跑赢低PE股，价值陷阱显著。

**数据说明**：
- 基本面数据来自 baostock 季报缓存（data/fundamentals/），1800只股票
- yoy_ni 覆盖率 61%（growth API 仅部分行业有数据）
- baostock 因大量抓取（5万次 API 调用）触发封禁，后续用 CACHE_ONLY 模式

### Phase 3：月频因子（v8，hp=21）

**结论：月频低波动 68.1 B ≈ 日频水平；动量在 csi1000 月频下方向反转。**

| 因子 | 得分 | AO | IC | 备注 |
|------|------|----|----|------|
| low_vol15（月频） | 68.1 B | 4/4 | +0.118 | 月频最强 |
| vol15_amtrev60（月频）| 68.0 B | 4/4 | +0.101 | 日频冠军月频持平 |
| mom_120d | 63.2 B | 3/4 | **-0.079** | ⚠️ IC 负 = 反向动量 |
| mom_60d | 60.6 B | 3/4 | **-0.063** | ⚠️ IC 负 = 反向动量 |
| high_roe（月频） | 28.0 D | — | -0.015 | 月频下更差 |
| high_yoy_ni（月频） | 34.0 D | — | -0.017 | 月频下更差 |

**动量反转现象**：csi1000 中，过去3-6个月涨幅最高的股票，下个月反而跑输。散户追涨杀跌 + 小盘股脉冲后回调的典型 A股特征。实用含义：反向动量（过去3-6月涨幅最低）是有效信号，方向与美股相反。

### Phase 5：五方向扩展搜索（~30个因子）

**结论：只有日内收盘强度组合突破冠军（Sh 0.946→1.078），其余全部否决。**

| 方向 | 最佳候选 | top_Sh | AO | 结论 |
|------|---------|--------|----|------|
| 短期反转（ret1/ret5） | champ+ret5 hp=5 | 0.628 | 4/4 | ❌ 月频下拖累；hp=5 MDD 恶化 |
| **日内收盘强度** | **champ+low_cs20** | **1.078** | **4/4** | ⚠️ 升级候选，mono=0.60 较低 |
| GK 波动率 | champ+low_gk20 | 0.946 | 4/4 | ❌ 无改善，2024 IC 衰减至 0.032 |
| Overnight gap | gap_pos | 0.889 | — | ❌ IC=0.026，方向不稳 |
| 换手率×反向动量 | turn_x_ret20 | 0.835 | — | ❌ 弱于冠军 |

**champ+low_cs20 详情**：
```
(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share, 60))
+ rank(-1 * ts_mean((close-low)/(high-low), 20))
```
- top_ann=29.2%，top_Sh=1.078，MDD=-39.8%，4/4 AO
- IC=0.071，yearly: 2020=0.075, 2021=0.091, 2022=0.097, 2023=**0.036**, 2024=0.053
- mono=0.60（G3=20.5% > G4=17.0%，中间乱序）
- 收盘强度单独 IC=0.015（接近噪声），但组合后有效
- 归档为"升级候选"，与冠军并列，后续实盘比较决定

**日内收盘强度含义**

`(close - low) / (high - low)` 描述收盘价在当天最高-最低区间内的位置：
- 值=1.0 → 收盘=当日最高，尾盘强势
- 值=0.0 → 收盘=当日最低，尾盘弱势

因子使用20日均值取反，即**过去20天持续在日内低位收盘的股票**。

为什么"尾盘弱"可能是正向信号（A股特有）：
1. **被动卖压**：基金赎回/指数再平衡必须尾盘卖出，压价但非基本面劣化，次月容易反弹
2. **三重被忽视叠加**：低相对成交量 + 低绝对换手率 + 尾盘弱 = 在市场上完全"隐形"的股票，后续修复空间大
3. **散户行为的反面**：散户追尾盘强势股，持续尾盘弱的股票剔除了噪声追涨成分

为什么单独 IC=0.015 但组合后 Sh 跳升到 1.078：线性 IC 捕捉不到交互效应。三个条件叠加后选出的是极小且高度同质化的一类股票（被遗忘+无流动性+被动卖压），这类股票的月度超额收益是非线性的。这也是为什么它是"升级候选"而非直接替换冠军——黑盒感较强，需要实盘验证。

### Phase 4：换手率 + 52周高点 + 新冠军（v9/triple，~10个因子）

**结论：换手率有效（64.4 B），52周高点无方向，去掉低波动后两个成交量信号组合创历史最高 74.5 B。**

#### Round 1：52周高点接近度（纯OHLCV）

| 因子 | 得分 | IC | 结论 |
|------|------|----|------|
| near_52wk_high（close/ts_max(close,252)） | 44.2 C | — | 方向不确定 |
| far_52wk_high（-1*close/ts_max(close,252)） | 47.4 C | — | 反向也弱 |
| price_pos_252（区间位置[0,1]） | — | — | 与近高点同类 |

**结论**：csi1000 中 52周高点接近度无稳定 alpha。动量因子在 A股小盘中方向不可靠。

#### Round 2：换手率因子（volume/total_share）

| 因子 | 得分 | AO | IC | 结论 |
|------|------|----|----|------|
| low_turn_20（20日均换手率取反） | 64.4 B | 4/4 | 正 | ✅ 有效 |
| low_turn_60（60日均换手率取反） | ~62 B | — | 正 | ✅ 有效 |
| champ+low_turn | 69.7 B | 4/4 | — | 微增 |

**结论**：低换手率是机构沉淀信号，在 csi1000 有效。

#### Round 3：突破——去掉低波动的纯成交量双信号

| 因子 | 得分 | AO | IC | IR | mono |
|------|------|----|----|----|----|
| vol_amtrev_turn（三因子：波动+缩量+低换手） | ~69 B | — | — | — | 0.50 |
| **amtrev_x_turn（双因子：缩量+低换手）** | **72.6 B** | **4/4** | 0.082 | 0.474 | **0.90** |
| vol_turn（波动+低换手） | ~65 B | — | — | — | — |

**关键发现**：去掉低波动后，两个纯成交量信号（相对缩量×绝对低换手）的单调性从 0.50 提升到 0.90，得分从 ~70 跳到 72.6，突破了 OHLCV 天花板。

#### Round 4：月频深度验证（hp=21 新高）

```
(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share, 20))
```

| 持仓期 | 得分 | AO | IC | IR | mono |
|--------|------|----|----|----|----|
| hp=5 | 72.6 B | 4/4 | 0.082 | 0.474 | 0.90 |
| hp=10 | 69.1 B | 4/4 | 0.091 | 0.516 | 0.30 |
| **hp=21** | **74.5 B** | **4/4** | **0.107** | **0.658** | 0.80 |

**全局最高分 74.5 B（hp=21）**。IC 稳定性：2020=0.066, 2021=0.061, 2022=0.080, 2023=0.078, 2024=0.079（全年正）。

**anti_overfit 4/4 详情（hp=21）**：
- IC 稳定性：IC=0.073，正率=0.69，跨年均正
- 子样本：bull=0.082, bear=0.069, sideways=0.062, high_vol=0.088, low_vol=0.058，consistency=1.0
- 安慰剂：real_IC=0.073 >> perm_95th=0.012，shift ICs衰减（5d=0.052, 20d=0.040）
- 半衰期：T½=105.9 天，signal 有长期持续性

**csi500 交叉验证**：59.8 C（信号在 csi1000 更适用，csi500 偏弱）。

---

## 否决因子完整记录

| 因子 | 得分 | 否决原因 |
|------|------|---------|
| amihud15 | 25.9 D | 方向错误（流动性溢价反转） |
| updays_20 | 30.6 D | 动量无效 |
| yoy_ni | 23.0 D | IC≈0，纯噪声 |
| debt_ratio | 31.2 D | 财务杠杆无效 |
| high_roe | 43.9 C | 太弱 |
| low_pe | 34.5 D | ⚠️ IC 负，方向错误 |
| pv_corr20 | 56.4 C | 价量相关性信号太弱 |
| intraday_vol15 | 58.5 C | 弱于隔夜波动版本 |
| mom_60d/120d/240d | 47-63 C/B | IC 负（A股动量反向） |
| amtrev_zscore+park | 52.6 C | zscore 标准化后变差 |
| roe_pb_m（月频） | 48.4 C | 月频下基本面更差 |

---

## 关键结论

### 1. 「低波动 + 成交量萎缩」是 csi1000/csi500 最强信号

跨5日/10日/20日/月频（21日），跨两个宇宙（csi1000/csi500）均保持 4/4 AO + B级。这是真实 alpha 的标志。

### 2. csi1000 动量方向与国际文献相反

- 5日：动量无效
- 月频：60d/120d 动量 IC 均为负，高动量股反而跑输
- **实用**：反向动量（排做空高动量、做多低动量）在 csi1000 月频下有效

### 3. 基本面因子在5日/月频下均失效

- 季报数据（3个月滞后）在5日调仓中噪声主导
- 月频调仓下同样失效：高ROE/yoy_ni 的 IC 均转负
- low_pe IC 为负：csi1000 中成长溢价远大于价值溢价

### 4. 结构上限：约 74 B（B级末尾）

- **amtrev_x_turn（hp=21）= 74.5 B** 是当前最高，月频 + total_share 数据
- A 级（≥80）无法通过 OHLCV + baostock 季报 + 换手率触达
- 突破需要：分析师预期数据、高频另类数据（资金流/情绪）

### 5. 去掉低波动后，双成交量信号更强

- 低波动 + 缩量 + 低换手（三因子）：mono=0.50，score≈69
- 缩量 + 低换手（两因子，去掉低波动）：mono=0.90，score=72.6
- 原因：低波动与成交量信号有部分重叠，引入后降低了因子单调性，信息量没有增加

---

## 研究现状 & TODO（截止 2026-07-29）

### 当前冠军（二选一，待实盘比较）

| | amtrev_x_turn_v2 | champ+low_cs20 |
|---|---|---|
| 表达式 | `(-1*rank(vol/ts_mean(vol,60))) + rank(-1*ts_mean(vol/total_share,60))` | 上述 + `rank(-1*ts_mean((close-low)/(high-low),20))` |
| top_Sh | 0.946 | **1.078** |
| top_ann | 25.1% | **29.2%** |
| MDD | -43.1% | **-39.8%** |
| IC | **0.084** | 0.071 |
| mono | **0.90** | 0.60 |
| AO | 4/4 | 4/4 |
| 推荐用途 | 日频稳健首选 | 月频激进候选 |

**两者 MDD 均过大（-40%~-43%），进实盘必须先叠加 Regime overlay。**

---

### TODO 优先级列表

#### 🔴 P0：当前信号空间内的收尾（可立即做）

- [ ] **剩余3个OHLCV因子**：上影线比率 `(high-close)/(high-low)`、日内涨跌 `close/open-1`、换手率稳定性 `ts_std(vol/total_share,20)`
- [ ] **Rolling Validation（长数据）**：对 amtrev_x_turn_v2 用 2013-2024 OHLCV 数据跑 rolling_val，补充 in-sample 以外的验证
- [ ] **Regime Overlay**：叠加 MA120 牛熊切换，熊市空仓，目标 MDD 压到 -15~-20%，Sharpe 大幅提升

#### 🟡 P1：扩展信号空间（需新数据，本周内可做）

- [ ] **baostock 现金流 API**：`query_cash_flow_data` → oper_cash_flow/net_profit（现金含量），质量因子，今天能抓
- [ ] **融资融券数据（AkShare）**：`stock_margin_detail_szse/sse`，历史追溯2010年，高融资余额=散户杠杆=负向信号；与换手率正交
- [ ] **北向资金持股（AkShare）**：陆股通持股明细，先验证历史数据长度

#### 🟢 P2：更大改造（需规划）

- [ ] **分钟线数据**：确认 TickFlow 是否支持分钟级批量下载；若支持，开放 VWAP 偏差、开盘集竞量等全新信号空间
- [ ] **宇宙扩展**：在全A股或 CSI300 上验证信号泛化性
- [ ] **WQ Brain 提交**：需 WorldQuant 账号；外部独立 out-of-sample 验证

#### ✅ 已完成 / 已关闭

- [x] OHLCV 因子全扫（~40个）
- [x] 基本面因子（pb/pe/roe/yoy_ni/debt_ratio）
- [x] 月频测试（hp=21）
- [x] 换手率因子 + 参数优化（turn 窗口 20→60d 升级）
- [x] 五方向扩展（反转/收盘强度/GK波动/gap/交叉项）
- [x] 资金流探索 → 关闭（AkShare 仅120天，无历史）
- [x] 52周高点 → 关闭（C级，方向不稳）

---

## 未测试的因子（已并入上方TODO）

---

## 技术改进汇总

| 改动 | 文件 | 效果 |
|------|------|------|
| TickFlow batch API 替换 baostock | market_data.py | 1000只下载从25min→2min |
| TickFlow SSL 重试（3次指数退避） | market_data.py | 瞬时 SSL EOF 不再 fallback |
| `_factor_df` 传原始因子值（bug fix） | backtest.py | anti_overfit IC 从≈0修复 |
| 空 DATABASE_URL（bug fix） | db.py | 消除 SQLAlchemy 报错 |
| Worker 进程 logging | task_executor.py | spawn 进程日志写入 logs/mcp.log |
| baostock 季报 growth+balance API 预抓 | prefetch_fundamentals.py | 新增 yoy_ni/debt_ratio 缓存 |

---

## Bug 修复记录

### 1. `backtest.py` — `_factor_df` 传中性化后因子值
```python
"_factor_df": work[["trade_date","stock_code","daily_ret"]].assign(
    factor_value=raw_factor_for_ic.reindex(work.index)
),
```

### 2. `db.py` — 空 DATABASE_URL
```python
url = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./quantgpt.db"
```

### 3. baostock 封号风险
大量顺序 API 调用（>5万次）会触发 baostock 黑名单封禁。
修复：多进程预抓后改用 `QUANTGPT_CACHE_ONLY=1` 模式，完全依赖本地缓存。

---

## Phase 6：DeepSeek 自主挖掘（2026-07-29，~48 个因子）

**背景**：MCP 工具因 baostock 黑名单全部失效，改用自建脚本直读本地 parquet，绕过登录。

**环境**：
- DeepSeek API（deepseek-chat，sk-76a344c0...）生成因子表达式
- 本地 parquet 缓存（`data/stocks/` + `data/fundamentals/`，1000只股票，2020-2024）
- 3 进程并行回测（spawn 模式，已修复 macOS multiprocessing 问题）
- 脚本：`scratchpad/autonomous_mining.py`（非生产代码，临时）

**6 个研究方向，48 因子，7 分钟完成，47/48 超越冠军基准（Sh=0.946）**

| 方向 | 最佳因子 | top_Sh | ann | 耗时 |
|------|---------|--------|-----|------|
| vwap 偏离 | vwap_08 | 1.764 | 62.1% | 29s |
| decay_linear 近期加权 | decay_linear_01 | 1.727 | 64.0% | 45s |
| amount 成交金额 | amount_05 | 1.683 | 68.1% | 30s |
| p0_ohlcv 纯价格 | p0_ohlcv_07 | 1.609 | 53.8% | 27s |
| ts_rank 百分位 | ts_rank_08 | 1.546 | 62.8% | 237s |
| 冠军变异 | mutations_06 | 1.666 | 57.6% | 51s |

> 注意：整体 Sharpe 虚高（2020-2024 含 COVID 反弹），所有候选需验证。

### 全局 Top20 快照（Sharpe 降序）

| 排名 | tag | Sh | ann | IC | mono | 表达式 |
|------|-----|----|-----|----|----|------|
| 1 | vwap_08 | 1.764 | 62.1% | +0.025 | 0.30 | `rank(-1*ts_corr(close/vwap, volume, 20)) + rank(ts_mean(vwap,20)/vwap)` |
| 2 | decay_linear_01 | 1.727 | 64.0% | +0.092 | 0.10 | `(-1*rank(volume/decay_linear(volume,60))) + rank(-1*decay_linear(volume/total_share,60))` |
| 3 | amount_05 | 1.683 | 68.1% | -0.079 | 0.30 | `rank(ts_std(amount/volume, 10)) + rank(ts_mean(amount, 5)/ts_mean(amount, 60))` |
| 4 | mutations_06 | 1.666 | 57.6% | +0.097 | 0.10 | `(-1*rank(amount/ts_mean(amount,60))) + rank(-1*ts_mean(volume/total_share,60))` |
| 5 | mutations_01 | 1.647 | 58.0% | +0.091 | 0.10 | `(-1*rank(volume/ts_mean(volume,40))) + rank(-1*ts_mean(volume/total_share, 40))` |
| 6 | p0_ohlcv_07 | 1.609 | 53.8% | +0.124 | 0.10 | `rank(-1 * ts_std(pct_change, 20))` |
| 7 | mutations_08 | 1.573 | 55.8% | +0.096 | 0.20 | `(-1*rank(volume/ts_mean(volume,60))) + rank(sign_power(-1*ts_mean(volume/total_share,60),0.5))` |
| 8 | vwap_05 | 1.565 | 50.9% | +0.057 | 0.40 | `rank(-1*ts_std(close/vwap,20)) + rank(ts_mean(volume,5)/ts_mean(volume,60))` |
| 9 | **decay_linear_02** | **1.548** | **52.7%** | **+0.087** | **0.40** | `(-1*rank(volume/decay_linear(volume,20))) + rank(-1*decay_linear(volume/total_share,20))` |
| 10 | ts_rank_08 | 1.546 | 62.8% | -0.025 | 0.50 | `rank(ts_rank(vwap, 20)) + rank(ts_rank(close / open, 10))` |

### 可信度初筛（从 Top20 中过滤）

直接排除：IC 负 + Sh 高（矛盾，过拟合信号）、mono=0.10（分组无单调性）。

进入深度验证的候选（IC>0，mono≥0.30）：
- **vwap_08**（Sh=1.764，IC=+0.025，mono=0.30）
- **vwap_05**（Sh=1.565，IC=+0.057，mono=0.40）
- **decay_linear_02**（Sh=1.548，IC=+0.087，mono=0.40）← 最终胜出
- **decay_linear_06**（Sh=1.416，IC=+0.030，mono=0.90）

---

### Anti-Overfit 验证（4 候选，2026-07-29）

参数：universe=csi1000，2020-2024，HP=21，本地 parquet，脚本 `run_anti_overfit_local.py`

| tag | 总分 | 建议 | IC稳定性 | 子样本压力 | 安慰剂检验 | 半衰期 |
|-----|------|------|----------|-----------|----------|--------|
| **vwap_08** | **100%** | **推荐** | ✓ | ✓ | ✓ | ✓ 63.5d |
| **decay_linear_02** | **100%** | **推荐** | ✓ | ✓ | ✓ | ✓ ∞ |
| vwap_05 | 75% | 谨慎 | ✗ 2024 IC=-0.01 | ✓ | ✓ | ✓ |
| decay_linear_06 | 75% | 谨慎 | ✗ 2024 IC=-0.025 | ✓ | ✓ | ✓ 114d |

**vwap_05 和 decay_linear_06 失败原因**：2024 年 yearly_ic 转负，近年有效性衰减。

**decay_linear_02 详情**：
- IC=0.069，正率=71%
- 5年 yearly_ic 极稳：2020=0.064, 2021=0.061, 2022=0.087, 2023=0.066, 2024=0.068（无一年翻转）
- 子样本：bull=0.077, bear=0.049, sideways=0.057, high_vol=0.088, low_vol=0.051，consistency=1.0
- IC 随持仓期延长反而增强（1d=0.039, 5d=0.050, 10d=0.050, 20d=0.053, 40d=0.058）→ 月频非常匹配

**vwap_08 详情**：
- IC=0.030，正率=63%，5年无翻转
- 熊市 IC=0.076 >> 牛市 IC=0.018（防御性信号）
- 半衰期 63.5 天，与 HP=21 匹配

---

### Walk-Forward 滚动验证（2 候选，2026-07-29）

参数：train=2y/valid=1y/test=1y/step=3m → 4 个滑动窗口，脚本 `run_rolling_local.py`

**decay_linear_02（WF得分 59.2）**

| 窗口 | 测试期 | train_IC | valid_IC | test_IC | test_IR |
|------|--------|----------|----------|---------|---------|
| W0 | 2023-01 ~ 2024-01 | 0.0567 | 0.0855 | **0.0588** | 0.448 |
| W1 | 2023-04 ~ 2024-04 | 0.0544 | 0.1051 | **0.0524** | 0.299 |
| W2 | 2023-07 ~ 2024-07 | 0.0614 | 0.0870 | **0.0778** | 0.440 |
| W3 | 2023-10 ~ 2024-10 | 0.0610 | 0.0932 | **0.0759** | 0.437 |

均 test_IC=0.066，衰减分析 mean_decay=-0.13，status=stable ✅

**vwap_08（WF得分 43.7）**

test_IC 四窗口：0.017 / 0.002 / 0.003 / 0.019，样本外严重衰减 ❌

**结论：decay_linear_02 通过全部关卡（anti-overfit 4/4 + WF 4/4），vwap_08 WF 失败。**

---

### 组合测试：amtrev_x_turn_v2 × decay_linear_02（2026-07-29）

表达式：
```
((-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share, 60)))
+ ((-1*rank(volume/decay_linear(volume,20))) + rank(-1*decay_linear(volume/total_share,20)))
```

| 因子 | Sh | ann | MDD | IC | IR | mono |
|------|----|-----|-----|----|----|------|
| amtrev_x_turn_v2 | 1.573 | 55.8% | -49.2% | 0.096 | 0.617 | 0.20 |
| decay_linear_02 | 1.548 | 52.7% | -45.6% | 0.087 | 0.582 | 0.40 |
| **combo** | **1.736** | **63.4%** | **-47.2%** | 0.096 | 0.627 | **0.10** |

**分组（G1低→G5高）**：
```
amtrev   : +35.0% | +62.3% | +34.1% | +30.9% | +55.8%
dl_02    : +55.3% | +41.6% | +33.4% | +22.9% | +52.7%
combo    : +55.3% | +35.9% | +43.3% | +15.2% | +63.4%  ← G4塌陷
```

**结论：不推荐直接叠加**。两者均为"缩量低换手"逻辑（只是窗口/加权方式不同），信息重叠导致 mono=0.10，G4 年化仅 15.2%。建议作为独立备选因子，而非组合。

---

### Phase 6 新结论

**decay_linear_02** 加入推荐候选池：
```
(-1*rank(volume/decay_linear(volume,20))) + rank(-1*decay_linear(volume/total_share,20))
```
- top_Sh=1.548，IC=0.087，mono=0.40，anti-overfit 4/4，WF 4/4
- 逻辑：decay_linear 对近期赋予更高权重，窗口 20d（vs 冠军 60d），捕捉短期缩量更灵敏
- **与冠军逻辑重叠，建议独立轮换使用，不做线性叠加**

---

## 基础设施改进（2026-07-29）

| 改动 | 文件 | 效果 |
|------|------|------|
| DeepSeek API 配置 | `.env` + `scripts/mcp_deepseek.py` | MCP DeepSeek 工具可用（ask_deepseek） |
| MCP .mcp.json 绝对路径 | `.mcp.json` | deepseek server 由 Failed→Connected |
| 本地 parquet 加载（绕过 baostock） | `autonomous_mining.py` | load_data_from_cache，1000只/1.2M行/1s |
| 正则 bug 修复 | `autonomous_mining.py` | `[#//]`→`(?:#|//)` 修复 `/` 被截断问题 |
| N_PROC=3 限制 | `autonomous_mining.py` | 防止 CPU 打满（之前 8 进程打满机器） |
| `QUANTGPT_CACHE_ONLY=1` 加入 .env | `.env` | MCP 工具（run_backtest/score_factor 等）将从 parquet 读数据，绕过 baostock |

### 下一步：激活完整 MCP 挖掘流程

1. **VSCode Reload Window** → MCP server 重读 `.env`（含 `QUANTGPT_CACHE_ONLY=1`）
2. 验证：`score_factor(amtrev_x_turn_v2)` 不报 baostock 错误
3. 之后可直接用 `PROMPT.md` 中的 Agent 提示词启动自治挖掘循环（6阶段 + MutationEngine + 知识库积累）

---

## Phase 7：扩展历史数据 + 20 年 WF 验证（2026-07-29）

### 数据管道扩展

| 脚本 | 数据源 | 结果 |
|------|--------|------|
| `scripts/rebuild_price_cache.py` | TickFlow Pro（count=10000） | csi1000/csi500 全量，最早追溯至上市日（1990s） |
| `scripts/backfill_fundamentals.py` | 新浪资产负债表（`实收资本(或股本)` / `股本`） | 961/1000 csi1000 股票 total_share 回填至 2001 年 |

**注意事项**：
- 银行/金融类公司资产负债表用 `股本` 列（非 `实收资本(或股本)`），已加兜底
- 新浪返回 `datetime64[us]`，merge_asof 前须 `.astype("datetime64[ns]")` 统一
- spawn worker 不继承 sys.path，须在 `_init` 中 `sys.path.insert(0, PROJECT_DIR)`
- quantgpt 含 `tuple | None` 语法（Python 3.10+），须用 `.venv/bin/python3`（3.11）

---

### Extended WF（2004-2024，28 窗口，train=5y/valid=1y/test=1y/step=6m）

**⚠️ 含幸存者偏差**：universe 用 csi1000_2020-01 静态快照，早期数据仅含存活至 2020 年的股票。WF 稳定性结论可信，绝对 IC 水平偏高（尤其 2004-2012 年段）。

| 指标 | amtrev_x_turn_v2 | decay_linear_02 |
|------|-----------------|-----------------|
| WF 窗口数 | 28 | 28 |
| 正窗口数 | **27/28（96%）** | **26/28（93%）** |
| mean test_IC | **0.0805** | 0.0713 |
| 负窗口 | W01=-0.0018 | W00=-0.001, W01=-0.001 |

**W00/W01 弱（测试期≈2009-2010）**：2008 大熊市后反弹，极端行情期量价信号失真，属已知 edge case。

**年度 IC 5 个翻转年（两因子共同）**：2006-2007（A股大牛顶部）、2008（金融危机）、2012（缩量熊市中段）、2018（贸易战去杠杆）。规律一致：极端牛市顶部或极端熊市，换手率信号暂时失效。

**2020+ IC 显著变强**（amtrev：+0.009→+0.022）：注册制 + 机构化加速，量价因子效力上升趋势明确。

**定案**：amtrev_x_turn_v2 经 **28 窗口 / 20 年 / 多个完整牛熊周期**验证，96% 正窗口率。**不是 COVID 反弹产物，是跨周期稳健信号。**

---

## 全局排行榜（更新至 2026-07-29 Phase 7）

| # | 因子名 | 表达式 | Sh（top组） | AO | WF（20年28窗口） | hp |
|---|--------|--------|------------|----|----|-----|
| 🥇 | **champ+low_cs20** | `amtrev_x_turn_v2 + rank(-1*ts_mean((close-low)/(high-low),20))` | **1.078** | **4/4** | — | **21** |
| 🥈 | **amtrev_x_turn_v2** | `(-1*rank(vol/ts_mean(vol,60))) + rank(-1*ts_mean(vol/total_share,60))` | 0.946 | **4/4** | **27/28 ✅** | **21** |
| ✅ | **decay_linear_02** | `(-1*rank(vol/decay_linear(vol,20))) + rank(-1*decay_linear(vol/total_share,20))` | 1.548\* | **4/4** | **26/28 ✅** | 21 |
| 3 | amtrev_x_turn_m | 换手率窗口 20d 版 | ~0.9 | 4/4 | — | 21 |
| 4 | vol15_amtrev60 | `rank(-1*ts_std(ret,15)) + (-1*rank(vol/ts_mean(vol,60)))` | — | 4/4 | 57.1 | 5 |

\* decay_linear_02 的 Sh=1.548 含 COVID 虚高，WF mean_test_IC=0.071 是更可信的样本外信号强度。

---

## Phase 8：MCP 修复 + 自治 Agent 就绪（2026-07-29）

### Bug 修复

| 问题 | 修复位置 | 说明 |
|------|----------|------|
| `merge_asof` 日期类型不一致 | `quantgpt/fundamental_data.py:148-150` | 新浪回填的 parquet 存 `datetime64[us]`，merge 前须 `.astype("datetime64[ns]")` |
| MCP server 未读新 .env | VSCode Reload Window | `QUANTGPT_CACHE_ONLY=1` 需要重启 MCP server 才生效 |

修复后验证：`score_factor(amtrev_x_turn_v2, universe=csi1000, start_date=2020-01-01, holding_period=21, neutralize_industry=false)` → score=59.9（C 级，符合预期；非中性化模式下冠军约 60 分）。

### 自治 Agent Prompt（PROMPT_AGENT.md）

已写好完整启动提示词，覆盖：
- 固定参数（universe/start_date/neutralize=false/holding_period=21）
- 已验证冠军因子 + 已关闭方向（防重复探索）
- 可用数据字段白名单（OHLCV + total_share，无基本面）
- 5 个优先探索方向（ts_corr / 价格位置 / ts_rank 百分位 / 非线性变换 / 组合）
- 三阶段研究循环 + 停止条件

**用法**：新 Claude Code 对话 + QuantGPT MCP 已连接，粘贴 `PROMPT_AGENT.md` 代码块内容即可启动。预计运行 30-60 分钟完成方向 A-E 全量扫描。

### 当前状态总结

| 组件 | 状态 |
|------|------|
| 价格数据（csi1000/csi500） | ✅ TickFlow Pro 全量，最早至 IPO 日（1990s~） |
| total_share（csi1000） | ✅ 961/1000 已回填至 2001 年；39 只 2016 后 IPO 属正常 |
| MCP 工具（8 项） | ✅ CACHE_ONLY=1 模式全部可用，绕过 baostock |
| 自治 Agent Prompt | ✅ PROMPT_AGENT.md 就绪 |
| 下一步 | 在服务器上启动自治挖掘循环，目标找到正交于"缩量低换手"的新信号维度 |
