# QuantGPT A股因子挖掘研究笔记（终局版 2026-07-29）

## 研究概述

- **宇宙**：csi1000（主）、csi500（交叉验证）
- **回测区间**：2020-01-01 ~ 2024-12-31（in-sample）
- **持仓周期**：5日（主）、10日、20日、21日（月频）全部测试
- **共测试因子**：~70个（OHLCV + 基本面 + 月频技术 + 换手率 + 52周高点）
- **数据源**：TickFlow batch API（价格）+ baostock 季报（profit/growth/balance API）

---

## 因子机制分类总纲（2026-07-30）

覆盖当前项目累计测试过的全部机制大类 + 已识别但未测试的空白区，作为后续挖掘的优先级参考。

| 类别 | 具体方向 | 状态 | 关键结果 | 预期价值 | 备注 |
|---|---|---|---|---|---|
| 量能/换手率 | volume/ts_mean(volume,60) + 换手率(volume/total_share) | ✅ 已验证=冠军 | score≈60-71, IC=0.084, WF 27/28(96%,含幸存者偏差) | — | `amtrev_x_turn_v2`，已饱和 |
| 量能衰减 | decay_linear(volume,20) 版本 | ✅ 已验证 | anti_overfit 4/4, WF 26/28(93%) | — | 与冠军逻辑重叠(G4塌陷)，不建议再叠加 |
| 量价相关性 | ts_corr(volume/amount, close, N) | ✅ 已验证=新正交因子 | score=82, IC=0.063, 与冠军相关性0.265, WF 2/2正 | — | 本轮最大收获，`ts_corr(volume,close,10)` |
| 价格位置(区间位置) | (close-low)/(high-low), sign(close-open) | ✅ 已测试=弱 | IC≈0.02, C/D级 | 低 | 单独用弱，可能只在champ+low_cs20组合里有价值 |
| 历史波动率 | ts_std(pct_change/ret,N), GK波动率 | ❌ 已关闭 | 相关性0.567(与冠军), 2024年IC衰减 | 低 | 本轮二次验证坐实了原有判断 |
| ts_rank百分位 | ts_rank(volume/amount, N) | ❌ 已测试=非正交 | score=80, 相关性0.658(与冠军) | 低 | 换手率逻辑的百分位变体 |
| 非线性变换(post-rank) | sign_power/tanh 套在外层rank() | ❌ 已证伪 | 数学上rank-invariant，3变体分数几乎相同 | 低 | 若要再试必须放进ts_mean内部才有意义 |
| 动量 | ret_20d/ret_60d | ❌ 已关闭 | A股月频动量IC为负(与美股相反) | 低 | — |
| 短期反转 | ret_1d/ret_5d | ❌ 已关闭 | 月频下IC为负 | 低 | — |
| 52周高点距离 | 距离年内高点比例 | ❌ 已关闭 | 方向不稳，C级 | 低 | — |
| 隔夜跳空 | overnight gap | ❌ 已关闭 | IC=0.026，太弱 | 低 | — |
| 基本面 | PE/PB/ROE/净利润增速 | ❌ 已关闭(且当前无数据) | IC≈0，季报滞后已被定价 | 低 | 缓存里也没有这些字段了 |
| **市值/规模** | rank(-1\*close\*total_share) | ✅ 已验证=新正交因子 | score=77(B), IC=0.081, anti_overfit 4/4, WF 1窗口正, 与冠军相关性-0.03 | — | 慢变量，半衰期999天，IC随周期变长增强 |
| 经典技术指标 | RSI/MACD/BOLL/ATR/OBV/EMA/WMA | ✅ 已扫描 | ATR最强(0.109)但与已关闭波动率方向相关0.575；**OBV正交(0.241)**；MACD/布林带mono差 | — | **OBV是新正交因子**，见下方汇总行 |
| **OBV** | rank(-1\*obv(close,20)) | ✅ 已验证=新正交因子 | score=71.7(B), IC=0.071, anti_overfit 4/4, WF 2/2正(decay为负), 与冠军/市值/ts_corr相关性均<0.27 | — | 第三个独立正交维度 |
| 流动性冲击(Amihud式) | rank(ts_mean(abs(pct_change)/amount, 10)) | ❌ 已测试=非正交 | score=80.8(A), IC=0.103, mono=1.0；但与市值因子相关性**0.588**、与冠军0.402 | 低 | 分数很高但被市值因子解释——illiquidity本质是size effect的另一种包装(学界常识)，非新维度 |
| 日历/季节效应 | rank(day)/weekday/month | ❌ 已证伪 | IC=0.0, mono=0.0（D级） | 低 | **数学上必然退化**：day/weekday/month对同一交易日所有股票是常数，横截面rank无意义；如需用日历效应必须做成regime条件(trade_when)而非独立rank因子 |
| **组合叠加** | 冠军 + ts_corr + 市值 + OBV | ✅ 已验证，**真实多头排名与理论多空排名不同** | 真实多头(hp=21)：**五合一**CAGR=24.6%/超额+13.0%/TopSharpe=1.16 **全场最优**；行业相对五合一CAGR=20.6%/超额+8.9%；四合一CAGR=21.6%/超额+9.9%。hp=5下冠军/ts_corr单独超额为负(跑输基准) | — | 用理论多空(`ls_returns`)数字时"行业相对五合一"看起来最强，但真实多头(`strategy_returns`)重验后**五合一才是真实最优**，anti_overfit 4/4 + WF(test_IC=0.1475,IR=1.00,decay=-0.21)三重确认。详见 [production-candidate-comparison.md](docs/knowledge/findings/production-candidate-comparison.md) |
| 行业相对排名 | group_rank/group_zscore | ✅ 已测试=非新维度 | score普遍B/A,anti_overfit 4/4,但与全市场母版本相关性0.88-0.89 | 低(作为新alpha) | 不是新正交信号，是已发现因子的行业相对改良实现（MaxDD更优，可用于生产） |
| 条件/regime因子 | trade_when(...) | ⬜ 从未测试 | — | 低 | 工程复杂度高，且没有明确的regime信号候选 |
| **跨宇宙验证** | csi1000(原生)/csi500/csi2000/hs300 | ✅ 已验证 | csi500/csi2000通过(csi2000 IC=0.111三宇宙最高)；**hs300真实失效**(anti_overfit 2/4 FAIL,安慰剂检验不通过) | — | 因子体系边界：仅适用中小盘，不适用大盘蓝筹。csi2000验证前先补了total_share全量回填(1918/1971成功) |

**当前状态（2026-07-31）**：总纲表里列出的全部方向均已测试或明确归类关闭，累计发现3个独立正交信号（ts_corr/市值/OBV）+ 三宇宙交叉验证通过 + 明确了大盘蓝筹边界(hs300失效)。**关键待办**：目前排行榜里的Sharpe/MaxDD大多数仍是理论多空(`ls_returns`)数字，A股不能做空，需要逐个换成真实多头(`strategy_returns`)重新验证，已发现两者差异巨大（多空版CAGR 45% vs 真实多头CAGR超额4.5%）。详见下方"研究现状 & TODO"。

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

## 研究现状 & TODO（截止 2026-07-31）

### 当前候选（2026-07-31更新：真实多头重验后排名已定）

| | amtrev_x_turn_v2(冠军) | 五合一（当前推荐） | 行业相对五合一(hp=21) |
|---|---|---|---|
| 表达式 | `(-1*rank(vol/ts_mean(vol,60)))+rank(-1*ts_mean(vol/total_share,60))` | 冠军+ts_corr+市值+OBV | 同左的group_rank行业相对版 |
| IC | 0.084 | 0.148 | 0.120 |
| mono | 0.90 | 1.0 | 1.0 |
| anti_overfit | 4/4 | 4/4(yearly IC 0.092~0.164) | 4/4 |
| WF | — | test_IC=0.1475,IR=1.00,decay=-0.21 | — |
| **真实多头CAGR超额(hp=21)** | +4.0% | **+13.0%(最优)** | +8.9% |
| Top组Sharpe(真实多头) | 0.82 | **1.16(最优)** | 0.99 |
| 跨宇宙 | hs300失效 | **待补测** | csi500/csi2000通过,hs300未测 |
| 推荐用途 | 已知基线 | **当前推荐生产候选** | 备选 |

**核心结论**：用真实多头(`strategy_returns`)重验后，**五合一（非行业相对版）才是真实表现最好的候选**，超过之前基于理论多空数字看起来更强的"行业相对五合一"。anti_overfit+WF+真实多头三重验证一致支持。跨宇宙验证(hs300/csi500/csi2000)仍待对五合一补测（此前只测过冠军和行业相对版）。

---

### TODO 优先级列表

#### 🔴 P0：收尾当前候选（可立即做，无需新数据）

- [x] **用真实多头(strategy_returns)重新验证四合一/五合一/行业相对五合一(hp=21)/ts_corr单独**——完成，排名反转：五合一才是真实最优（CAGR超额+13.0%），取代此前基于理论多空数字推荐的行业相对五合一（+8.9%）。冠军/ts_corr单独在hp=5下真实超额为负
- [ ] **用刷新后的total_share数据（覆盖到2026-04）重新跑WF滚动验证**——之前受限于旧数据只能测出1-2个窗口，现在应该能多测出至少一个窗口
- [ ] **五合一补充hs300/csi500/csi2000跨宇宙验证**——此前跨宇宙验证测的是冠军和行业相对五合一，真实排名第一的"五合一"本身还没在csi500/csi2000/hs300上单独测过

#### 🟡 P1：新方向（需要一定工程量）

- [ ] **trade_when/regime因子**：总纲表里唯一完全没测过的机制大类，工程复杂度较高，需要先想清楚用什么做regime信号（比如MA120牛熊切换）
- [ ] **Regime Overlay**：给现有候选叠加牛熊切换（熊市减仓/空仓），压缩最大回撤——旧笔记里提到MDD -40%~-43%过大，虽然新候选（行业相对五合一hp=5的Top组MaxDD已经只有-7.7%左右）情况好很多，但这理论数字也还没经过真实多头重新验证
- [ ] **半年报刷新**：8月31日semi-annual报告披露截止后，重新跑一次`backfill_fundamentals.py`往前刷新，拿到2026年中报数据

#### 🟢 P2：需要新数据源（探索性，本session未验证可行性）

- [ ] **baostock现金流API**：`query_cash_flow_data`，质量因子方向，尚未确认baostock在当前沙箱环境下是否可用（本session多次遇到baostock网络不通）
- [ ] **融资融券/北向资金数据（AkShare）**：需先确认历史数据长度和当前环境的抓取可行性（akshare本身是通的，见Sina财务接口测试，但具体这两个数据源未验证）
- [ ] **分钟线数据**：TickFlow是否支持分钟级批量下载尚未确认
- [ ] **WQ Brain提交**：`wq_brain_submit`等工具已可用但本session未使用，需要WorldQuant BRAIN账号配置

#### ✅ 本session（Phase 9-12,2026-07-30~31）已完成

- [x] 发现3个独立正交信号：ts_corr(量价相关)/市值(规模)/OBV(量能)
- [x] 组合叠加验证：四合一/五合一/行业相对五合一(hp=21及hp=5)
- [x] 跨宇宙验证：csi500/csi2000通过，hs300确认真实失效
- [x] 行业中性化压力测试：IC稳健，naive换手成本会侵蚀表面收益
- [x] 接入行业分类数据(stock_tracker来源)，group_rank/group_zscore首次真正可用
- [x] 方法论修正：评估真实收益改用strategy_returns(多头)而非ls_returns(多空)
- [x] 基础设施：6处bug修复(路径/日期参数/merge_asof/worker数/回填超时保护) + TickFlow key改环境变量并轮换
- [x] 数据回填：csi2000 total_share从0覆盖到1918/1971；csi1000+csi500 total_share从卡在2025Q1刷新到覆盖2026-04

#### ✅ 更早期已完成/已关闭（截止2026-07-29）

- [x] OHLCV 因子全扫（~40个）
- [x] 基本面因子（pb/pe/roe/yoy_ni/debt_ratio）→ 关闭（无数据/已被定价）
- [x] 月频测试（hp=21）+ 换手率参数优化
- [x] 五方向扩展（反转/收盘强度/GK波动/gap/交叉项）→ 大部分关闭
- [x] 52周高点 → 关闭（C级，方向不稳）
- [x] 非线性变换/日历效应/流动性冲击(Amihud) → 均证伪或被已知因子解释

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

---

## Phase 9：自治 Agent 首轮运行 + 正交信号发现（2026-07-30）

### 新发现：量价相关性正交信号

方向 A（ts_corr）第一批扫描即命中。`rank(-1*ts_corr(volume, close, 10))`：

- score=82.0（A级），IC=0.063，IR=0.75，mono=0.90
- anti_overfit 4/4 PASS（综合分100，yearly IC 2020-2024 全正）
- 与冠军 `amtrev_x_turn_v2` 截面相关性 0.265（<0.3 正交阈值）
- Walk-Forward：2/2 窗口 test_IC 为正（0.061/0.050），decay stable（几乎不衰减，三个候选里最稳）

同族候选 `rank(-1*ts_corr(amount, close, 20))`（score 81.6，相关性 0.263，decay stable）与 `rank(-1*ts_std(close/vwap, 20))`（score 83.6 最高，但相关性 0.416 超阈值、decay unstable）。详见 [docs/knowledge/findings/volume-price-corr-orthogonal.md](docs/knowledge/findings/volume-price-corr-orthogonal.md)。

`ts_corr(volume,close,N)` 符号随窗口长度反转：N=10/20 需要 `-1*`，N=40 原始方向已经是对的（加 `-1*` 反而错）。

### Bug 修复（本轮新增，均已验证生效）

| 问题 | 修复位置 | 说明 |
|------|----------|------|
| 硬编码 macOS 日志路径 | `task_executor.py:28`（`mcp_server.py` 之前已修） | worker 子进程 `os.makedirs("/Users/...")` 权限拒绝，改用 `Path(__file__)` 相对路径 |
| `compute_factor_values` 忽略 date 参数 | `mcp_server.py:934` | `get_universe(universe)` 没传 `date=start_dt`，永远按"今天"查成分股缓存，导致 csi1000 恒为空。已改为与其他工具一致的 `get_universe(universe, date=start_dt)` |
| worker 进程数偏保守 | `task_executor.py:95` | 默认 `min(4, cpu_count)` 改为 `max(1, cpu_count-1)`（本机6核→5 worker）；`.env` 里 `QUANTGPT_WORKER_PROCESSES` 同步从 4 改到 5 |
| **`run_rolling_validation` 假性"数据不足"** | `rolling_validator.py:130` | 窗口生成用 `test_end > max_date` 严格判断，任务固定参数 `end_date=2024-12-31` 卡在 5 年整边界，一个窗口都生成不出来。价格缓存实际到 2026-07，把调用时的 `end_date` 放宽到 2025-06-30 左右即可正常出 WF 结果（不是数据缺失，是调用参数问题，源码未改） |
| 冠军因子 `amtrev_x_turn_v2` 跑 `run_rolling_validation` 报错 "Not enough rebalance dates for backtest" | 待查 | 新候选因子（不依赖 total_share）不受影响，怀疑与 total_share 基本面数据在窗口切片后的对齐/dropna 有关，本轮未深入 |

### 安全问题：TickFlow API key 硬编码

`market_data.py:91` 和 `scripts/rebuild_price_cache.py:26` 曾各硬编码一个 TickFlow key，且已随 commit `8f4a05c`/`8020524` 推送到 `github.com/leslieluyu/QuantGPT`（origin/main）。已改为从环境变量读取（`TICKFLOW_API_KEY` / `TICKFLOW_PRO_API_KEY`，无 fallback），真实值移入本地 `.env`（已 gitignore），`.env.example` 补充占位说明。**Git 历史里这两个 commit 仍包含明文 key，如需彻底清除需要改写历史；建议尽快在 TickFlow 后台轮换这两个 key。**

### 方向 B/C/D 扫描结果（无新突破，均已归档）

- **方向B（价格位置）**：`ts_std(pct_change, N)`（N=10/15/20）全部 A 级（score 82+），但验证后与冠军相关性高达 0.567，且 2024 年 IC 明显衰减（0.055 vs 其他年份 0.09-0.12）——精确复现了已关闭方向"历史波动率"的失效模式，不是新信号。`(close-low)/(high-low)`、`sign(close-open)` 系列价格位置因子普遍偏弱（C/D级）。
- **方向C（ts_rank百分位）**：`ts_rank(volume/amount, 60)` 系列 A/B 级（最高 `ts_rank(amount,60)` score=80.0），但与冠军相关性 0.658，本质是冠军"量/60日均量"逻辑的百分位版本，非正交。20日窗口版本明显更弱（score降至62）。
- **方向D（非线性变换）**：验证了一个数学结论——`rank()` 外层套 `sign_power`/`tanh` 等单调变换对最终排序无影响（rank-invariant），3 个变体分数几乎位数级相同。非线性变换只有放进 `ts_mean` 等聚合内部才可能改变结果，但测试的 log 版本反而比线性基线弱。详见 [docs/knowledge/failures/nonlinear-post-rank-noop.md](docs/knowledge/failures/nonlinear-post-rank-noop.md)。

### 方法论澄清：csi1000 历史 universe 快照

`data/universe/` 下 csi1000 成分股快照实际只有 `2017-01`、`2020-01` 两个月份。Phase 7 的"28窗口/20年 WF"验证本身就是用 `2020-01` 静态快照套用到 2004-2024 全历史（笔记里已标注"含幸存者偏差"），并非真的逐月拿到历史成分股。本轮沙箱环境无法访问 baostock（DNS/连接超时，普通 HTTPS 出网正常），无法回补更多月份快照，因此新候选因子的 WF 验证目前只能生成 2 个窗口（用 anti_overfit 4/4 作为主要验证标准，WF 作为补充确认）。

---

## Phase 10：市值因子 + 组合叠加 + 技术指标扫描（2026-07-30）

### 全局分类总纲

新增"因子机制分类总纲"章节（见"研究概述"之后），汇总所有已测/已关闭/未测方向及预期价值，作为后续挖掘的优先级参考索引。

### 市值/规模因子（新发现，已验证）

`rank(-1*close*total_share)`：score=77.0(B), IC=0.081, turnover=0.008（极低）, anti_overfit 4/4 PASS(100)。**半衰期999天，IC随周期变长反而增强**——与所有量价类因子（半衰期50-110天，IC随周期衰减）动态特征相反，证明是完全不同的经济机制（慢变量）。与冠军相关性-0.030，与ts_corr新因子相关性0.053，双双正交。WF（1窗口）test_IC=0.055。详见 [docs/knowledge/findings/market-cap-factor-and-combo.md](docs/knowledge/findings/market-cap-factor-and-combo.md)。

### 方向E：组合叠加测试

用等权求和验证正交因子叠加是否真的提升组合质量：

| 组合 | score | IC | IR | Sharpe | anti_overfit | WF test_IC/IR/decay |
|---|---|---|---|---|---|---|
| 冠军+ts_corr | 84.7 A | 0.107 | 0.86 | 1.51 | — | — |
| 冠军+市值 | 86.2 A | 0.139 | 0.91 | 1.91 | 4/4(100) | 0.105/0.59/0.047 |
| 冠军+ts_corr+市值（四合一） | 87.5 A | 0.137 | **1.03** | **2.04** | 4/4(100) | 0.139/**1.06**/**-0.19（样本外更强）** |
| 冠军+ts_corr+市值+OBV（五合一） | 87.0 A | **0.148** | 0.96 | 2.01 | 4/4(100) | — |

三/四/五个正交分量两两相关性都很低，叠加带来真实的分散化收益，不是重复计数。**四合一或五合一均可作为生产候选**，前者IR更优，后者IC绝对值和回撤更优。

### 技术指标家族扫描（RSI/MACD/OBV/ATR/布林带，此前从未测试过）

| 指标 | score | IC | 与冠军相关性 | 结论 |
|---|---|---|---|---|
| ATR(20) | 79.8 B | 0.109 | 0.424 | 与已关闭的"历史波动率"方向相关性0.575，本质同一信号，非新发现 |
| **OBV(close,20)** | 71.7 B | 0.071 | **0.241** | **新正交信号**：与市值因子0.127、与ts_corr新因子几乎为零(-0.0002)、与低波动因子0.270，全部<0.3 |
| RSI(14) | 66.4 B | 0.047 | 0.349(临界) | 弱正交，分数较低，暂不优先 |
| MACD(20) | 43-46 C | ±0.028 | — | mono仅0.1，分组不单调，不推荐 |
| 布林带位置/偏离 | 62-65 B | -0.06~0.05 | — | mono 0.4-0.7，一般 |

OBV：anti_overfit 4/4 PASS(100)，yearly IC全正(0.019-0.089)，半衰期999天(同市值因子的"慢变量"特征)，WF 2/2窗口正且**decay为负（样本外更强）**。详见 [docs/knowledge/findings/obv-orthogonal-and-five-way-combo.md](docs/knowledge/findings/obv-orthogonal-and-five-way-combo.md)。

### 累计正交信号清单（与冠军 amtrev_x_turn_v2 相关性均<0.3）

1. `ts_corr(volume, close, 10)` — 量价短期相关性
2. `close*total_share`（市值） — 慢变量，近乎不衰减
3. `obv(close, 20)` — OBV动量，同样是慢变量特征

三者两两相关性也都很低，是真正独立的三个维度。

---

## Phase 11：接入行业分类数据 + 行业中性化压力测试（2026-07-30）

### 行业数据接入

从 `stock_tracker/data/research/sw_industry.csv`（5533只股票，5203只有有效行业标注，与QuantGPT代码格式`sh./sz.`兼容）转换写入 `QuantGPT/data/industry/industry_2026-07.parquet`，对接现成的 `get_industry_data()`（`quantgpt/neutralize.py:133`，此前因无数据源一直返回None，`neutralize_industry`参数和`group_rank`/`group_zscore`算子实际上是空转的）。同时给 `get_industry_data()` 加了一个小改进：当前月份缓存不存在时回退到最近一个可用月份文件（行业分类变化很慢，没必要每月手动重新生成）。csi1000覆盖率92.9%。

**至此 `neutralize_industry=true`、`group_rank(col, industry)`、`group_zscore(col, industry)` 全部首次真正可用。**

### 行业中性化压力测试：IC稳健，但naive换手成本会吃掉大部分表面收益

用 `neutralize_industry=true` 重新测本session发现的全部因子，出现一个"评分从B/A暴跌到C(59.9)"的现象——排查后确认**不是bug**，是 `iteration.py:100-107` 的评分保护机制（quantstats算出的真实多空组合Sharpe或CAGR为负时，评分强制封顶59.9/C），是故意设计防止"IC好看但实际组合亏钱"误导人。

**但触发这个封顶的背后原因很重要**：

| 因子 | neutralize_industry=false | neutralize_industry=true（score_factor,cost_rate=0.3%）| neutralize_industry=true（anti_overfit,cost_rate=0）|
|---|---|---|---|
| 冠军 | Sharpe=1.26, turnover=0.075 | Sharpe=**+0.076**(勉强为正,未封顶), turnover=0.075(**不变**) | IC=0.083(vs原始0.084,**几乎不变**), 4/4 PASS |
| 市值因子 | Sharpe未测,turnover=**0.008** | Sharpe=**-0.45**(封顶), turnover=**0.074(暴涨9倍!)** | IC=0.080(vs原始0.081,**几乎不变**), 4/4 PASS |
| OBV | turnover=**0.005** | Sharpe=**-0.06**(封顶), turnover=**0.072(暴涨14倍!)** | IC=0.062(vs原始0.071,小幅下降), 4/4 PASS |
| ts_corr | turnover=0.069 | Sharpe=**-0.27**(封顶), turnover=0.075 | IC=0.055(vs原始0.063,小幅下降), 4/4 PASS |
| 五合一组合 | Sharpe=2.01 | Sharpe=**-0.68**(封顶) | IC=**0.125**(vs原始0.148,仍很强), 4/4 PASS,yearly IC全正(0.075~0.164) |

**结论**：
- 用**无成本的纯IC视角**（`anti_overfit`）检验，所有因子的统计edge在行业中性化后**几乎完好无损地保留**——说明这些因子的选股能力是真实的股票特异性alpha，不是靠押注特定行业。
- 用**含0.3%成本的naive回测**（`score_factor`）检验，市值因子和OBV这类原本换手率极低（0.005-0.008）的慢变量因子，一旦每期都按行业均值重新中性化，换手率暴涨9-14倍，叠加交易成本后表面Sharpe转负——**这是简单粗暴的"每期全量行业中性化"实现方式带来的换手成本问题，不是alpha消失了**。
- 冠军因子比较特殊：换手率没变但Sharpe仍大幅下降（1.26→0.076），IC却几乎不变——说明其真实多空组合层面的收益有相当一部分依赖于"行业集中度暴露"这个维度本身（而非换手成本），是这几个因子里唯一一个"IC稳但组合收益不稳"的。

**实操建议**：若要实盘应用市值/OBV/ts_corr这些因子并叠加行业中性化，不应该用"每期全量重算行业中性排名"这种粗暴方式，而应该用换手率约束的组合优化（如目标行业暴露带宽内的最小换手调仓），才能同时保住IC和低成本的优势。

### group_rank/group_zscore 首次真正可用后的测试结果

修复过程中发现 `market_data.py` 的 `fetch_stocks()` 从未把 industry 列合并进参与**表达式求值**的 market_df（`neutralize_industry` 的行业数据合并只发生在因子值算出来之后的中性化后处理里，是两条独立数据流）。导致此前所有 `group_rank(col, industry)`/`group_zscore(col, industry)` 表达式在找不到 `industry` 列时静默退化成普通按日期rank——测出来的5个"行业内相对排名"因子数值和全市场版本一模一样（可精确到十几位小数），才发现这个问题。已在 `fetch_stocks()` 里把 industry 合并进基础 market_df（`market_data.py:713-726`），重启验证后 `group_rank`/`group_zscore` 结果确实变了。

修复后测试5个行业内相对版本，score普遍B/A级、anti_overfit 4/4 PASS，部分风险指标（MaxDD）比全市场版本更优（如 `-1*group_rank(ts_corr(volume,close,10),industry)` MaxDD=-8.4% vs 全市场版-10.8%）。但正交性检验显示：**行业内版本与其全市场母版本相关性高达0.88-0.89**，本质是同一信号的行业相对改写，不是新的独立机制。

**结论**：`group_rank`/`group_zscore` 这条路径不产生新的正交alpha维度，但可以作为已发现因子（尤其市值/OBV/ts_corr）的**更稳健生产实现**——行业相对构造天然降低了行业集中度风险，同时保留了大部分股票特异性edge，回撤表现通常更好。

### 生产候选定案

把冠军、四合一、五合一、行业相对五合一四个候选做了完整对比（详见 [docs/knowledge/findings/production-candidate-comparison.md](docs/knowledge/findings/production-candidate-comparison.md)）。**行业相对五合一**（四个正交因子的 group_rank/group_zscore 行业相对版等权叠加）风险调整后指标全场最优：IR=1.30、Sharpe=2.60、MaxDD=-7.1%（均为本轮最佳），anti_overfit 4/4 PASS 且 yearly IC 最稳定（0.090~0.116，positive_rate=86.7%全场最高）。IC绝对值(0.120)略低于五合一(0.148)，但综合风险调整后质量更优，推荐作为生产候选：

```
(-1*group_rank(volume/ts_mean(volume,60), industry))
+ (-1*group_zscore(volume/total_share, industry))
+ (-1*group_rank(ts_corr(volume,close,10), industry))
+ (-1*group_rank(close*total_share, industry))
+ (-1*group_rank(obv(close,20), industry))
```

### 跨宇宙验证：csi500通过，hs300真实失效

- **csi500**：冠军和生产候选IC都能穿越（0.068~0.070），生产候选依然优于冠军单独使用，anti_overfit 4/4 PASS。冠军单独在csi500上明显比csi1000弱（Sharpe 1.26→0.16），组合更稳健。
- **csi2000**：total_share原本完全缺失（该宇宙从未被历史回填过），跑完全量回填（1918/1971成功，94.2min）后验证——生产候选 score=83.2(A), IC=0.111（三宇宙最高）, anti_overfit 4/4 PASS；冠军单独 mono仅0.4(不单调)。三个中小盘宇宙(csi1000/csi500/csi2000)全部验证通过。
- **hs300**：生产候选和冠军**真实失效**（MaxDD分别-49.5%/-95.3%，mono仅0.2-0.3），anti_overfit仅2/4 PASS，安慰剂检验FAIL（真实IC低于随机排列95分位数），2020年IC为负出现reversal。**这不是300只股票分组样本量小的噪音，是统计上确认的真实失效**——这套"缩量低换手+正交扩展"逻辑仅适用于中小盘（csi1000/csi500），不适用于沪深300等大盘蓝筹宇宙。详见 [docs/knowledge/findings/production-candidate-comparison.md](docs/knowledge/findings/production-candidate-comparison.md)。

### Bug修复：hs300专属的merge_asof日期类型不一致

测hs300时触发了`fundamental_data.py`里`_align_quarterly_to_daily`的`merge_asof`报错（`datetime64[us]` vs `datetime64[ns]`），是Phase8修过的同类bug在新场景下的复现——`_load_cache`会把`pub_date`/`stat_date`统一转成ns，但`market_df["trade_date"]`本身是us精度存的parquet，csi1000/csi500因为有独立的预计算factor cache绕开了这条merge_asof路径，hs300没有对应缓存所以直接走原始路径暴露了这个问题。已在merge前显式统一两侧为`datetime64[ns]`（`fundamental_data.py:359-363`），修复具有普适性，不限于hs300。

### 方法论提醒：评估真实收益要用多头(strategy_returns)，不是多空(ls_returns)

A股不能做空，`run_factor_backtest`返回的`ls_returns`（Top组-Bottom组）只是理论参考指标，不代表真实可交易收益。用生产候选(hp=5)跑2016-2024逐年收益时，一开始用`ls_returns`算出"9年全正、CAGR 45%"这种明显不现实的数字，改用`strategy_returns`（代码里就是Top组纯多头，注释写明"long-only, A-share"）对比等权持有全宇宙基准后，得到年化超额≈4.47%、Top组Sharpe=0.44、并非每年跑赢（2020/2022跑输）的合理结果。**以后评估任何因子的真实可交易表现，一律用`strategy_returns`/`top_group_sharpe`，`ls_returns`/`long_short_sharpe`只做统计显著性参考，不能当成预期收益。** 详见 [docs/knowledge/findings/production-candidate-comparison.md](docs/knowledge/findings/production-candidate-comparison.md)。

### 日频(hp=5)验证：本轮全场最强结果

之前全部验证都在hp=21（月频）。把生产候选（行业相对五合一）换成hp=5重新测试：**score=87.5(A), IC=0.090, IR=0.999, Sharpe=3.75(全场最高), MaxDD=-7.7%**，anti_overfit 4/4 PASS且yearly IC**逐年单调递增**(2020:0.068→2024:0.092)，WF(1窗口) test_IC=0.094/IR=0.95/decay=-0.22(样本外更强)。三种验证方法完全一致确认，是本session里最强的组合表现，代价是换手率更高(0.178 vs 月频0.055)。详见 [docs/knowledge/findings/production-candidate-comparison.md](docs/knowledge/findings/production-candidate-comparison.md)。
