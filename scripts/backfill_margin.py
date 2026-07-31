"""
backfill_margin.py — 用 AkShare(新浪/东财) 抓取沪深两市融资融券每日明细

按交易日抓取(而非按股票)：每次调用返回当天全市场所有标的的融资融券数据，
沪深各一次。存成按日期分片的 parquet，方便断点续跑。

数据说明：
  - 来源：ak.stock_margin_detail_sse / ak.stock_margin_detail_szse
  - 沪深字段不完全一致，只取两边都有的核心字段并统一 schema：
    stock_code, trade_date, margin_balance(融资余额),
    margin_buy(融资买入额), short_balance(融券余量), short_sell(融券卖出量)
  - 速度：~9s/交易日(沪+深)，单线程跑2020-2024全部约1200个交易日预计3小时左右

用法：
    python3 scripts/backfill_margin.py [--start 2020-01-01] [--end 2024-12-31]
"""

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

import pandas as pd

try:
    import akshare as ak
except ImportError:
    print("ERROR: akshare 未安装，请 pip install akshare")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent
MARGIN_DIR = PROJECT_DIR / "data" / "margin"
STOCK_DIR = PROJECT_DIR / "data" / "stocks"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_DIR / "logs" / "backfill_margin.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("backfill_margin")

STALE_TIMEOUT = 25


def _call_with_timeout(fn, *args, **kwargs):
    """一次性子线程 + 硬超时，卡住的请求直接放弃(不等待)。"""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args, **kwargs)
    try:
        result = future.result(timeout=STALE_TIMEOUT)
    except FutureTimeoutError:
        executor.shutdown(wait=False)
        return None, "timeout"
    except Exception as e:
        executor.shutdown(wait=False)
        return None, str(e)
    executor.shutdown(wait=False)
    return result, None


def _to_bs_code(raw_code: str, exchange: str) -> str:
    code = str(raw_code).strip().split(".")[0].zfill(6)
    prefix = "sh" if exchange == "sse" else "sz"
    return f"{prefix}.{code}"


def _fetch_one_date(date_str: str) -> pd.DataFrame | None:
    """date_str: YYYYMMDD"""
    frames = []

    sse_df, err = _call_with_timeout(ak.stock_margin_detail_sse, date=date_str)
    if err:
        log.warning(f"  {date_str} SSE 失败/超时: {err}")
    elif sse_df is not None and len(sse_df) > 0:
        out = pd.DataFrame()
        out["stock_code"] = sse_df["标的证券代码"].apply(lambda c: _to_bs_code(c, "sse"))
        out["margin_balance"] = pd.to_numeric(sse_df["融资余额"], errors="coerce")
        out["margin_buy"] = pd.to_numeric(sse_df["融资买入额"], errors="coerce")
        out["short_balance"] = pd.to_numeric(sse_df["融券余量"], errors="coerce")
        out["short_sell"] = pd.to_numeric(sse_df["融券卖出量"], errors="coerce")
        frames.append(out)

    szse_df, err = _call_with_timeout(ak.stock_margin_detail_szse, date=date_str)
    if err:
        log.warning(f"  {date_str} SZSE 失败/超时: {err}")
    elif szse_df is not None and len(szse_df) > 0:
        out = pd.DataFrame()
        out["stock_code"] = szse_df["证券代码"].apply(lambda c: _to_bs_code(c, "szse"))
        out["margin_balance"] = pd.to_numeric(szse_df["融资余额"], errors="coerce")
        out["margin_buy"] = pd.to_numeric(szse_df["融资买入额"], errors="coerce")
        out["short_balance"] = pd.to_numeric(szse_df["融券余量"], errors="coerce")
        out["short_sell"] = pd.to_numeric(szse_df["融券卖出量"], errors="coerce")
        frames.append(out)

    if not frames:
        return None
    result = pd.concat(frames, ignore_index=True)
    result["trade_date"] = pd.Timestamp(date_str)
    return result


def _trading_days(start: str, end: str) -> list[str]:
    """从本地已缓存的价格数据里取交易日历，避免额外调用日历接口。

    部分个股缓存文件混入过极少数周末脏数据，这里显式过滤掉周六/周日兜底，
    避免因为samples到脏文件而对着非交易日发请求浪费时间。
    """
    sample = next(STOCK_DIR.glob("sh_600*.parquet"))
    df = pd.read_parquet(sample, columns=["trade_date"])
    dates = sorted(d for d in df["trade_date"].unique()
                    if pd.Timestamp(start) <= d <= pd.Timestamp(end) and pd.Timestamp(d).dayofweek < 5)
    return [pd.Timestamp(d).strftime("%Y%m%d") for d in dates]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    args = parser.parse_args()

    MARGIN_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "logs").mkdir(exist_ok=True)

    all_days = _trading_days(args.start, args.end)
    needs = [d for d in all_days if not (MARGIN_DIR / f"{d}.parquet").exists()]

    log.info("=" * 65)
    log.info(f"backfill_margin  {args.start}~{args.end}  共{len(all_days)}个交易日")
    log.info(f"需要抓取: {len(needs)} 天  (其余 {len(all_days)-len(needs)} 天已缓存)")
    log.info(f"预计耗时: {len(needs)*9/60:.0f} 分钟")
    log.info("=" * 65)

    t0 = time.time()
    ok, empty, fail = 0, 0, 0
    for i, d in enumerate(needs, 1):
        df = _fetch_one_date(d)
        if df is None:
            fail += 1
            status = "FAIL"
        elif len(df) == 0:
            empty += 1
            status = "EMPTY"
        else:
            df.to_parquet(MARGIN_DIR / f"{d}.parquet", index=False)
            ok += 1
            status = f"OK +{len(df)}行"
        if i % 20 == 0 or i <= 5:
            log.info(f"[{i}/{len(needs)}] {d}: {status}")

    log.info("=" * 65)
    log.info(f"完成: ok={ok}, empty={empty}, fail={fail}, 耗时={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
