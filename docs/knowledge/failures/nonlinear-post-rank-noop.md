# 非线性变换（direction D）：outer rank() 前的逐元素非线性变换是无效操作

Date: 2026-07-30
Universe: csi1000, 2020-01-01~2024-12-31, holding_period=21, neutralize_industry=false, neutralize_cap=false, n_groups=5

## 结论

对已有信号在**外层 rank() 之前**套 `sign_power`/`tanh` 等单调非线性变换，对最终截面排序没有任何影响——`rank()` 对其参数的任何单调变换都不变（数学上必然如此）。实测验证：

| 表达式 | score | IC |
|---|---|---|
| `rank(-1*volume/ts_mean(volume,60))`（基线，方向A中已测） | 71.4* | -0.063* |
| `rank(sign_power(-1*volume/ts_mean(volume,60), 0.5))` | 80.3 | 0.0625 |
| `rank(sign_power(-1*volume/ts_mean(volume,60), 2))` | 80.3 | 0.0625（与0.5次幂完全一致） |
| `rank(tanh(-3*(volume/ts_mean(volume,60)-1)))` | 80.3 | 0.0625（与上面几乎完全一致） |
| `rank(-1*ts_corr(volume,close,10))`（基线，方向A） | 82.0 | 0.063 |
| `rank(sign_power(-1*ts_corr(volume,close,10), 0.5))` | 82.0 | 0.0628（与基线一致） |

（*注：这里的基线用了未加`-1*`的版本，符号相反仅作对比说明单调不变性，非直接分数对比）

`sign_power(x, 0.5)`、`sign_power(x, 2)`、`tanh(-3x)` 三种不同强度/形状的非线性变换，评分和 IC 几乎位数级相同 —— 证实了 rank-invariance。

**唯一可能产生差异的情形**：把非线性变换放在时间序列聚合（`ts_mean`/`ts_sum`等）**内部**，改变聚合前每个样本点的权重分布。测试了 `rank(-1*ts_mean(log(volume+1),20) / log(ts_mean(volume,60)+1))`（对数在聚合内部），score=76.7（B），IC=0.055 —— 比线性版本（冠军本身，IC≈0.084）更弱，没有带来提升。

## 建议

- 后续再探索"非线性变换"方向时，必须确保变换发生在 **rank() 之前的聚合运算内部**（比如 `ts_mean(f(x), N)` 而非 `f(ts_mean(x,N))`外面单独包一层 `rank(f(...))`），否则测试是无意义的重复工作。
- 目前测试的"聚合内部log变换"（D1）没有超过线性基线，此方向在当前数据/字段范围内暂无突破空间，可关闭。
