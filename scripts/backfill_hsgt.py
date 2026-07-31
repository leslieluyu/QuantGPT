"""
backfill_hsgt.py — 用 AkShare(东财) 抓取北向资金(陆股通)个股持股历史

按股票抓取(而非按日期)：每次调用返回该股票全部历史的北向持股明细。
单只约28秒(比融资融券的按日期查询慢很多)，全宇宙预计8-12小时，单线程
+ 硬超时兜底跑，避免网络问题拖死整个进程。

数据说明：
  - 来源：ak.stock_hsgt_individual_em(symbol)，symbol为6位数字代码(无sh/sz前缀)
  - 字段：持股日期/当日收盘价/当日涨跌幅/持股数量/持股市值/持股数量占A股百分比/
    今日增持股数/今日增持资金/今日持股市值变化
  - 存储：按股票分片parquet，data/hsgt/{sh|sz}_{code}.parquet，支持断点续跑

用法：
    python3 scripts/backfill_hsgt.py [--universe csi1000,csi500]
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
HSGT_DIR = PROJECT_DIR / "data" / "hsgt"
UNI_DIR = PROJECT_DIR / "data" / "universe"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_DIR / "logs" / "backfill_hsgt.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("backfill_hsgt")

STALE_TIMEOUT = 45  # 这个接口本身就慢(~28s)，超时阈值放宽一些


def _call_with_timeout(fn, *args, **kwargs):
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


def _cache_path(bs_code: str) -> Path:
    return HSGT_DIR / (bs_code.lower().replace(".", "_") + ".parquet")


def backfill_one(bs_code: str) -> str:
    path = _cache_path(bs_code)
    if path.exists():
        return f"{bs_code}: SKIP (已缓存)"

    symbol = bs_code.split(".")[1]
    df, err = _call_with_timeout(ak.stock_hsgt_individual_em, symbol=symbol)
    if err:
        return f"{bs_code}: FAIL ({err})"
    if df is None or len(df) == 0:
        return f"{bs_code}: EMPTY"

    df = df.copy()
    df["stock_code"] = bs_code
    df.to_parquet(path, index=False)
    return f"{bs_code}: OK +{len(df)}行"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="csi1000,csi500")
    args = parser.parse_args()

    HSGT_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "logs").mkdir(exist_ok=True)

    uni_names = [u.strip() for u in args.universe.split(",")]
    all_codes = set()
    for name in uni_names:
        for suffix in ["2020-01", "2017-01"]:
            p = UNI_DIR / f"{name}_{suffix}.txt"
            if p.exists():
                all_codes.update(p.read_text().split())
                break
    codes = sorted(all_codes)

    needs = [c for c in codes if not _cache_path(c).exists()]

    log.info("=" * 65)
    log.info(f"backfill_hsgt  宇宙={uni_names}  共{len(codes)}只  需要抓取={len(needs)}只")
    log.info(f"预计耗时: {len(needs)*28/60:.0f} 分钟")
    log.info("=" * 65)

    t0 = time.time()
    ok, empty, fail, skip = 0, 0, 0, 0
    for i, code in enumerate(needs, 1):
        result = backfill_one(code)
        if "OK" in result:
            ok += 1
        elif "FAIL" in result:
            fail += 1
        elif "EMPTY" in result:
            empty += 1
        else:
            skip += 1
        if i % 20 == 0 or i <= 5:
            log.info(f"[{i}/{len(needs)}] {result}")
        else:
            log.debug(result)

    log.info("=" * 65)
    log.info(f"完成: ok={ok}, empty={empty}, fail={fail}, skip={skip}, 耗时={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
