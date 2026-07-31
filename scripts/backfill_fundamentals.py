"""
backfill_fundamentals.py — 用新浪财务接口回填 total_share 历史到 2001 年

针对基本面 parquet 中 pub_date 仅从 2019 年开始的股票（约 510 只），
从新浪资产负债表获取完整季报 total_share，合并补充到已有 parquet。

数据说明：
  - 来源：ak.stock_financial_report_sina(stock, symbol='资产负债表')
  - 字段：报告日 → stat_date，公告日期 → pub_date，实收资本(或股本) → total_share
  - 单位：原始股数（与 baostock parquet 一致，无需转换）
  - 速度：~7s/只，4 线程并行 → 510只约 15分钟

用法：
    python3 scripts/backfill_fundamentals.py [--target-year 2016] [--threads 4]
"""

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from pathlib import Path

import pandas as pd

try:
    import akshare as ak
except ImportError:
    print("ERROR: akshare 未安装，请 pip install akshare")
    sys.exit(1)

import socket
socket.setdefaulttimeout(30)   # 全局 30s 超时，防止 Sina 请求永久挂起

PROJECT_DIR = Path(__file__).resolve().parent.parent
FUND_DIR    = PROJECT_DIR / "data" / "fundamentals"
UNI_DIR     = PROJECT_DIR / "data" / "universe"

SCHEMA_COLS = ["stock_code", "pub_date", "stat_date", "roe", "np_margin",
               "gp_margin", "net_profit", "eps_ttm", "revenue", "total_share", "float_share"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_DIR / "logs" / "backfill_fund.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("backfill_fund")


def _parquet_path(bs_code: str) -> Path:
    return FUND_DIR / (bs_code.lower().replace(".", "_") + ".parquet")


def _bs_to_sina(bs_code: str) -> str:
    """sh.600519 → sh600519"""
    return bs_code.replace(".", "")


def _load_existing(bs_code: str) -> pd.DataFrame | None:
    p = _parquet_path(bs_code)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["pub_date"] = pd.to_datetime(df["pub_date"])
    df["stat_date"] = pd.to_datetime(df["stat_date"])
    return df


def _fetch_sina_total_share(bs_code: str) -> pd.DataFrame | None:
    """从新浪获取 total_share 季报历史，返回符合 SCHEMA_COLS 的 DataFrame。

    akshare 内部用 requests.get() 不传 timeout，全局 socket.setdefaulttimeout()
    对连接阶段有效但读取阶段偶发不生效，见过整个进程卡死数小时的情况。这里用一次性
    子线程 + 硬超时兜底：超时就放弃这只股票继续下一只，卡住的线程直接丢弃(不等待)。
    """
    sina_code = _bs_to_sina(bs_code)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(ak.stock_financial_report_sina, stock=sina_code, symbol="资产负债表")
    try:
        df = future.result(timeout=25)
    except FutureTimeoutError:
        log.warning(f"  {bs_code}: sina 请求超时(25s)，跳过")
        executor.shutdown(wait=False)
        return None
    except Exception as e:
        log.warning(f"  {bs_code}: sina 请求失败 — {e}")
        executor.shutdown(wait=False)
        return None
    executor.shutdown(wait=False)

    if df is None or len(df) == 0:
        log.warning(f"  {bs_code}: sina 返回空数据")
        return None

    required_base = {"报告日", "公告日期"}
    if not required_base.issubset(df.columns):
        missing = required_base - set(df.columns)
        log.warning(f"  {bs_code}: 缺少基础列 {missing}")
        return None

    # 普通公司用"实收资本(或股本)"，银行/金融公司用"股本"
    share_col = None
    for candidate in ("实收资本(或股本)", "股本"):
        if candidate in df.columns:
            share_col = candidate
            break
    if share_col is None:
        log.warning(f"  {bs_code}: 找不到股本列（已检查: 实收资本(或股本), 股本）")
        return None

    out = pd.DataFrame()
    out["stat_date"] = pd.to_datetime(df["报告日"], format="%Y%m%d", errors="coerce").astype("datetime64[ns]")
    out["pub_date"]  = pd.to_datetime(df["公告日期"], format="%Y%m%d", errors="coerce").astype("datetime64[ns]")
    out["total_share"] = pd.to_numeric(df[share_col], errors="coerce")
    out["stock_code"] = bs_code

    # pub_date 缺失时用 stat_date + 4个月（保守的延迟）
    mask = out["pub_date"].isna()
    out.loc[mask, "pub_date"] = out.loc[mask, "stat_date"] + pd.DateOffset(months=4)

    # 补齐其他列为 NaN
    for col in SCHEMA_COLS:
        if col not in out.columns:
            out[col] = float("nan")

    out = out[SCHEMA_COLS].dropna(subset=["stat_date", "total_share"])
    out = out.sort_values("pub_date").reset_index(drop=True)
    return out


STALE_DAYS = 100  # latest pub_date older than this ⇒ 需要往前刷新最新一期


def backfill_one(bs_code: str, target_year: int) -> str:
    """处理一只股票，返回状态字符串。

    同时做两件事：往回补历史(到 target_year) + 往前刷新最新一期(避免财报
    停留在几个季度之前——旧逻辑只检查最早日期，已覆盖历史的股票永远不会
    再去看新浪有没有更新的季报，导致 total_share 长期滞后于实际披露进度)。
    """
    existing = _load_existing(bs_code)

    needs_backward = True
    needs_forward = True
    if existing is not None and len(existing) > 0:
        earliest = existing["pub_date"].min()
        latest = existing["pub_date"].max()
        needs_backward = earliest.year > target_year
        needs_forward = (pd.Timestamp.now() - latest).days > STALE_DAYS
        if not needs_backward and not needs_forward:
            return f"{bs_code}: SKIP (已有 {earliest.date()}~{latest.date()}，均满足)"

    sina_df = _fetch_sina_total_share(bs_code)
    if sina_df is None or len(sina_df) == 0:
        return f"{bs_code}: FAIL (sina 无数据)"

    if existing is not None and len(existing) > 0:
        # 往回(早于已有最早) + 往前(晚于已有最新) 两段都要
        new_rows = sina_df[
            (sina_df["pub_date"] < existing["pub_date"].min())
            | (sina_df["pub_date"] > existing["pub_date"].max())
        ]
    else:
        new_rows = sina_df
    new_rows = new_rows[new_rows["pub_date"] >= pd.Timestamp("2001-01-01")]

    if len(new_rows) == 0:
        return f"{bs_code}: SKIP (sina 数据无新增)"

    # 合并并去重（stat_date 为键）
    if existing is not None:
        combined = pd.concat([new_rows, existing], ignore_index=True)
    else:
        combined = new_rows.copy()

    combined = (combined
                .sort_values("pub_date")
                .drop_duplicates(subset=["stock_code", "stat_date"], keep="last")
                .reset_index(drop=True))

    combined.to_parquet(_parquet_path(bs_code), index=False)
    new_earliest = combined["pub_date"].min()
    return f"{bs_code}: OK +{len(new_rows)}行 earliest={new_earliest.date()}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-year", type=int, default=2016,
                        help="目标最早年份（默认 2016）")
    parser.add_argument("--threads", type=int, default=4,
                        help="并行线程数（默认 4）")
    parser.add_argument("--universe", default="csi1000,csi500",
                        help="目标宇宙")
    args = parser.parse_args()

    FUND_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "logs").mkdir(exist_ok=True)

    # 加载宇宙
    uni_names = [u.strip() for u in args.universe.split(",")]
    all_codes = set()
    for name in uni_names:
        for suffix in ["2020-01", "2017-01"]:
            p = UNI_DIR / f"{name}_{suffix}.txt"
            if p.exists():
                all_codes.update(p.read_text().split())
                break
    codes = sorted(all_codes)

    # 筛选需要回填的股票（历史不够早 或 最新一期已经滞后 STALE_DAYS 天）
    needs_backfill = []
    for code in codes:
        existing = _load_existing(code)
        if existing is None or len(existing) == 0:
            needs_backfill.append(code)
            continue
        earliest_stale = existing["pub_date"].min().year > args.target_year
        latest_stale = (pd.Timestamp.now() - existing["pub_date"].max()).days > STALE_DAYS
        if earliest_stale or latest_stale:
            needs_backfill.append(code)

    log.info("=" * 65)
    log.info(f"backfill_fundamentals  target_year≤{args.target_year}  threads={args.threads}")
    log.info(f"宇宙: {codes[:3]}... 共 {len(codes)} 只")
    log.info(f"需要回填: {len(needs_backfill)} 只  (其余 {len(codes)-len(needs_backfill)} 只已满足)")
    est = len(needs_backfill) * 7 / args.threads
    log.info(f"预计耗时: {est/60:.0f} 分钟")
    log.info("=" * 65)

    t_start = time.time()
    ok, fail, skip = 0, 0, 0

    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = {pool.submit(backfill_one, code, args.target_year): code
                   for code in needs_backfill}
        for i, fut in enumerate(as_completed(futures), 1):
            result = fut.result()
            if "OK" in result:
                ok += 1
            elif "FAIL" in result:
                fail += 1
            else:
                skip += 1
            if i % 20 == 0 or i <= 5:
                log.info(f"[{i}/{len(needs_backfill)}] {result}")
            else:
                log.debug(result)

    elapsed = time.time() - t_start
    log.info("=" * 65)
    log.info(f"完成: ok={ok}, skip={skip}, fail={fail}, 耗时={elapsed/60:.1f}min")


if __name__ == "__main__":
    main()
