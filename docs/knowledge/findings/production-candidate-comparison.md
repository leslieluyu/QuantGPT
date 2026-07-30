# 生产候选对比 — 行业相对五合一是本轮最优风险调整后组合

Date: 2026-07-30
Universe: csi1000, 2020-01-01~2024-12-31, holding_period=21, neutralize_industry=false, neutralize_cap=false, n_groups=5

## 对比表

| 候选 | 表达式 | score | IC | IR | Sharpe | MaxDD | Turnover | anti_overfit |
|---|---|---|---|---|---|---|---|---|
| 冠军（基线） | `(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share,60))` | 77-81 B/A | 0.084 | ~0.74 | 1.26 | -17.6% | 0.075 | 4/4 |
| 四合一 | 冠军 + `rank(-1*ts_corr(volume,close,10))` + `rank(-1*close*total_share)` | 87.5 A | 0.137 | 1.03 | 2.04 | -15.2% | ~0.07 | 4/4（WF 2/2正，decay为负） |
| 五合一 | 四合一 + `rank(-1*obv(close,20))` | 87.0 A | 0.148（IC最高） | 0.96 | 2.01 | -12.9% | ~0.05 | 4/4（yearly IC 0.092~0.164） |
| **行业相对五合一** | 见下方表达式 | 87.5 A | 0.120 | **1.30**（IR最高） | **2.60**（Sharpe最高） | **-7.1%**（回撤最低） | 0.055 | 4/4（yearly IC 0.090~0.116，全场最一致；positive_rate=86.7%全场最高） |

## 推荐表达式（行业相对五合一）

```
(-1*group_rank(volume/ts_mean(volume,60), industry))
+ (-1*group_zscore(volume/total_share, industry))
+ (-1*group_rank(ts_corr(volume,close,10), industry))
+ (-1*group_rank(close*total_share, industry))
+ (-1*group_rank(obv(close,20), industry))
```

anti_overfit 4/4 PASS（综合分100）：
- yearly IC：2020=0.090, 2021=0.107, 2022=0.107, 2023=0.116, 2024=0.094（全场波动最小的一组）
- 子样本压力（牛/熊/震荡/高波动/低波动）：0.099~0.107，consistency=1.0
- 半衰期999天（近乎不衰减）

## 结论

四个候选的IC绝对值排序是：五合一(0.148) > 四合一(0.137) > 行业相对五合一(0.120) > 冠军(0.084)。但**风险调整后质量排序是：行业相对五合一 > 四合一 ≈ 五合一 > 冠军**——行业相对版本用较低的IC换来了显著更低的回撤（-7.1% vs -12.9%~-17.6%）和更高的IR/Sharpe，且yearly IC最稳定、positive_rate最高。

结合 Phase11 的发现（冠军因子的部分收益依赖行业集中度暴露，行业中性化后Sharpe从1.26暴跌至0.076），行业相对构造从机制上更彻底地剥离了行业风险，是实盘落地的更优选择。若追求绝对IC最大化可选五合一，若追求风险调整后收益/更低回撤可选行业相对五合一。

## 跨宇宙验证（csi500）

同一表达式在 csi500（此前全部测试均只在csi1000上做）上重新验证：

| 因子 | csi1000 | csi500 |
|---|---|---|
| 冠军 | IC=0.084, Sharpe=1.26, MaxDD=-17.6% | IC=0.070, Sharpe=**0.16**(接近于0), MaxDD=**-28.0%**(更差) |
| 行业相对五合一 | IC=0.120, Sharpe=2.60, MaxDD=-7.1% | IC=0.068, Sharpe=0.76, MaxDD=-20.3% |

两者IC都能穿越到csi500（绝对水平走弱符合预期——因子是在csi1000上挖出来的），但**行业相对五合一组合在csi500上依然明显优于冠军**（Sharpe 0.76 vs 0.16，MaxDD -20.3% vs -28.0%），anti_overfit 在csi500上同样4/4 PASS（yearly IC 2020-2024全正：0.020~0.089，子样本一致性1.0）。冠军单独在csi500上的表现明显比在csi1000上弱得多（Sharpe从1.26掉到0.16），说明冠军本身对csi1000这个特定宇宙有一定程度的过拟合/适配性，而叠加了正交因子的组合更稳健，跨宇宙迁移能力更好。
