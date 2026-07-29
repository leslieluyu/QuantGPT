"""
extended_wf.py — 在扩展历史数据（2004-2024）上验证冠军因子

universe: csi1000 (2020-01 快照，注意含幸存者偏差)
factors : amtrev_x_turn_v2, decay_linear_02
WF      : train=5y / valid=1y / test=1y / step=6m → ~28 个窗口
"""
import os, sys, time, json, logging, multiprocessing as mp, pathlib
import pandas as pd

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
PROJECT_DIR = pathlib.Path(".").resolve()
STOCK_DIR   = PROJECT_DIR / "data/stocks"
FUND_DIR    = PROJECT_DIR / "data/fundamentals"
UNI_DIR     = PROJECT_DIR / "data/universe"

START = "2004-01-01"
END   = "2024-12-31"
HP    = 21

FACTORS = {
    "amtrev_x_turn_v2": "(-1*rank(volume/ts_mean(volume,60))) + rank(-1*ts_mean(volume/total_share,60))",
    "decay_linear_02":  "(-1*rank(volume/decay_linear(volume,20))) + rank(-1*decay_linear(volume/total_share,20))",
}

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(PROJECT_DIR/"logs/extended_wf.log", mode="w", encoding="utf-8")])
log = logging.getLogger("ext_wf")

# ── 数据加载 ──────────────────────────────────────────────────────────
def load_data(codes, start, end):
    stock_dfs, fund_dfs = [], []
    for code in codes:
        key = code.lower().replace(".", "_")
        sp = STOCK_DIR / f"{key}.parquet"
        fp = FUND_DIR  / f"{key}.parquet"
        if not sp.exists(): continue
        df = pd.read_parquet(sp)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df[(df["trade_date"] >= start) & (df["trade_date"] <= end)]
        if len(df) == 0: continue
        stock_dfs.append(df)
        if fp.exists():
            dff = pd.read_parquet(fp)[["stock_code","pub_date","total_share"]].copy()
            dff["pub_date"] = pd.to_datetime(dff["pub_date"])
            dff.rename(columns={"pub_date":"trade_date"}, inplace=True)
            fund_dfs.append(dff)

    df_s = pd.concat(stock_dfs, ignore_index=True)
    df_f = pd.concat(fund_dfs,  ignore_index=True)
    # 统一 datetime 精度（baostock=ns，sina 回填=us，merge_asof 要求一致）
    df_s["trade_date"] = df_s["trade_date"].astype("datetime64[ns]")
    df_f["trade_date"] = df_f["trade_date"].astype("datetime64[ns]")
    df = pd.merge_asof(df_s.sort_values("trade_date"),
                       df_f.sort_values("trade_date"),
                       on="trade_date", by="stock_code", direction="backward")
    df["vwap"] = df["amount"] / df["volume"].replace(0, float("nan"))
    return df.sort_values(["stock_code","trade_date"]).reset_index(drop=True)

# ── Worker ────────────────────────────────────────────────────────────
_df_global = None
def _init(df):
    global _df_global; _df_global = df
    import sys, os
    sys.path.insert(0, str(PROJECT_DIR))
    os.chdir(str(PROJECT_DIR))
    logging.getLogger().setLevel(logging.ERROR)

def _worker(args):
    name, expr = args
    try:
        from quantgpt.backtest import enable_api_context
        from quantgpt.expression_parser import parse_expression
        from quantgpt.rolling_validator import RollingValidator
        enable_api_context()
        df = _df_global.copy()
        fn = parse_expression(expr)
        df["factor_value"] = fn(df)
        df["daily_ret"] = df.groupby("stock_code")["close"].pct_change()
        fdf = df[["trade_date","stock_code","factor_value","daily_ret"]].copy()
        fdf = fdf.dropna(subset=["factor_value","daily_ret"])

        # 年度 IC（方便看稳定性）
        fdf["year"] = fdf["trade_date"].dt.year
        yearly = {}
        for yr, grp in fdf.groupby("year"):
            ic = grp["factor_value"].corr(grp["daily_ret"].shift(-HP), method="spearman")
            yearly[int(yr)] = round(float(ic), 4) if pd.notna(ic) else None

        # WF: train=5y / valid=1y / test=1y / step=6m
        rv = RollingValidator(fdf, holding_period=HP,
                              train_years=5, valid_years=1, test_years=1, step_months=6)
        wf_res = rv.run()

        # RollingResult 是 dataclass，用属性访问
        windows  = wf_res.windows
        test_ics = [w.test_ic for w in windows]
        pos_rate = sum(1 for x in test_ics if x > 0) / len(test_ics) if test_ics else 0

        return {
            "name": name,
            "n_rows": len(fdf),
            "yearly_ic": yearly,
            "wf_n_windows": len(windows),
            "wf_test_ic_mean": round(float(pd.Series(test_ics).mean()), 4) if test_ics else None,
            "wf_test_ic_pos_rate": round(pos_rate, 3),
            "wf_test_ics": [round(x,4) for x in test_ics],
            "wf_score": wf_res.score,
        }
    except Exception as e:
        import traceback
        return {"name": name, "error": str(e), "tb": traceback.format_exc()[-600:]}


if __name__ == "__main__":
    log.info("=" * 65)
    log.info(f"extended_wf  {START}~{END}  HP={HP}  universe=csi1000")
    log.info("=" * 65)

    codes = (UNI_DIR/"csi1000_2020-01.txt").read_text().split()
    log.info(f"加载 {len(codes)} 只股票数据 ...")
    t0 = time.time()
    df_all = load_data(codes, START, END)
    # 统计各年有效股票数（total_share 不为 NaN）
    df_all["has_ts"] = df_all["total_share"].notna()
    coverage = df_all.groupby(df_all["trade_date"].dt.year)["has_ts"].mean().round(2)
    log.info(f"数据加载完成: {len(df_all):,} 行  耗时 {time.time()-t0:.1f}s")
    log.info("各年 total_share 覆盖率(有值占比):")
    for yr, cov in coverage.items():
        bar = "#" * int(cov * 20)
        log.info(f"  {yr}: {cov:.0%}  {bar}")

    ctx = mp.get_context("spawn")
    with ctx.Pool(2, initializer=_init, initargs=(df_all,)) as pool:
        results = pool.map(_worker, list(FACTORS.items()))

    log.info("")
    for r in results:
        if "error" in r:
            log.error(f"{r['name']}: {r['error']}\n{r.get('tb','')}")
            continue
        log.info("=" * 65)
        log.info(f"【{r['name']}】  WF={r['wf_n_windows']}窗口  "
                 f"mean_test_IC={r['wf_test_ic_mean']}  pos_rate={r['wf_test_ic_pos_rate']:.0%}")
        log.info(f"  WF score={r['wf_score']}  total_rows={r['n_rows']:,}")
        log.info(f"  年度 IC:")
        for yr, ic in sorted(r["yearly_ic"].items()):
            tag = "✓" if ic and ic > 0 else "✗"
            log.info(f"    {yr}: {ic:+.4f}  {tag}")
        log.info(f"  WF test_IC 各窗口:")
        for i, ic in enumerate(r["wf_test_ics"]):
            tag = "✓" if ic > 0 else "✗"
            log.info(f"    W{i:02d}: {ic:+.4f}  {tag}")

    out = PROJECT_DIR / "logs/extended_wf_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"\n结果已保存: {out}")
    log.info(f"总耗时: {(time.time()-t0)/60:.1f}min")
