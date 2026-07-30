"""
rebuild_price_cache.py — 用 TickFlow Pro 批量重建股票价格 parquet 缓存

覆盖 csi1000 + csi500，全量历史（count=10000，从上市至今）。
速度：100只/请求，2s间隔 → ~1500只约 30秒。

用法：
    python3 scripts/rebuild_price_cache.py [--universe csi1000,csi500,all_a]
"""

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
STOCK_DIR   = PROJECT_DIR / "data" / "stocks"
UNI_DIR     = PROJECT_DIR / "data" / "universe"

TF_PRO_KEY   = os.environ.get("TICKFLOW_PRO_API_KEY", "")
TF_BATCH_URL = "https://api.tickflow.org/v1/klines/batch"
TF_BATCH_SIZE = 100
TF_BATCH_SLEEP = 2.0   # 30 batch calls/min → 2s 间隔

N_THREADS = 3          # 并行批次数（受 API 速率约束，不宜超过 3）

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_DIR / "logs" / "rebuild_price.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("rebuild_price")


def _bs_to_tf(bs_code: str) -> str:
    """sh.600519 → 600519.SH"""
    prefix, num = bs_code.split(".", 1)
    return f"{num}.{prefix.upper()}"


def _tf_to_bs(tf_code: str) -> str:
    """600519.SH → sh.600519"""
    num, suffix = tf_code.rsplit(".", 1)
    return f"{suffix.lower()}.{num}"


def _parquet_path(bs_code: str) -> Path:
    return STOCK_DIR / (bs_code.lower().replace(".", "_") + ".parquet")


def _fetch_batch(tf_symbols: list, count: int = 10000, retries: int = 3) -> dict:
    """返回 {tf_symbol: DataFrame(date_index)}，失败返回 {}"""
    syms_str = ",".join(tf_symbols)
    url = f"{TF_BATCH_URL}?symbols={syms_str}&period=1d&count={count}&adjust=forward"
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"x-api-key": TF_PRO_KEY}, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            break
        except Exception as e:
            last_exc = e
            wait = 2 ** attempt
            log.warning(f"  batch attempt {attempt+1}/{retries} failed: {e}, retry in {wait}s")
            time.sleep(wait)
    else:
        log.error(f"  batch FAILED after {retries} retries: {last_exc}")
        return {}

    result = {}
    for sym, vals in raw.get("data", {}).items():
        ts = vals.get("timestamp")
        if not ts:
            continue
        df = pd.DataFrame({
            "trade_date": pd.to_datetime([t // 1000 for t in ts], unit="s").normalize(),
            "open":       vals["open"],
            "high":       vals["high"],
            "low":        vals["low"],
            "close":      vals["close"],
            "volume":     [v * 100 for v in vals["volume"]],   # 手→股
            "amount":     vals["amount"],
        })
        result[sym] = df
    return result


def load_universe(names: list) -> list:
    """加载宇宙，合并去重，返回 baostock 格式 code 列表"""
    all_codes = set()
    for name in names:
        # 优先用 2020-01 版本，其次 2017-01
        for suffix in ["2020-01", "2017-01"]:
            p = UNI_DIR / f"{name}_{suffix}.txt"
            if p.exists():
                codes = p.read_text().split()
                all_codes.update(codes)
                log.info(f"  {name} ({suffix}): {len(codes)} 只")
                break
        else:
            log.warning(f"  找不到 {name} 宇宙文件")
    return sorted(all_codes)


def process_batch(batch_bs: list) -> tuple:
    """处理一个批次，返回 (ok_count, fail_count)"""
    tf_map = {_bs_to_tf(c): c for c in batch_bs}
    raw = _fetch_batch(list(tf_map.keys()))
    ok, fail = 0, 0
    for tf_sym, df in raw.items():
        bs_code = tf_map.get(tf_sym)
        if bs_code is None:
            continue
        df["stock_code"] = bs_code
        df["pct_change"] = df["close"].pct_change() * 100
        out_df = df[["trade_date", "stock_code", "open", "high", "low",
                     "close", "volume", "amount", "pct_change"]].copy()
        out_df = out_df.dropna(subset=["close"]).sort_values("trade_date").reset_index(drop=True)
        out_df.to_parquet(_parquet_path(bs_code), index=False)
        ok += 1
    fail = len(batch_bs) - len(raw)
    return ok, fail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="csi1000,csi500",
                        help="逗号分隔的宇宙名称，如 csi1000,csi500,all_a")
    args = parser.parse_args()

    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "logs").mkdir(exist_ok=True)

    uni_names = [u.strip() for u in args.universe.split(",")]
    log.info("=" * 65)
    log.info(f"rebuild_price_cache  universe={uni_names}")
    log.info(f"TickFlow Pro Key: {TF_PRO_KEY[:12]}...  batch_size={TF_BATCH_SIZE}")
    log.info("=" * 65)

    codes = load_universe(uni_names)
    log.info(f"总计 {len(codes)} 只股票")

    batches = [codes[i:i+TF_BATCH_SIZE] for i in range(0, len(codes), TF_BATCH_SIZE)]
    log.info(f"共 {len(batches)} 个批次，预计 {len(batches) * TF_BATCH_SLEEP:.0f}s")

    t_start = time.time()
    total_ok, total_fail = 0, 0

    # 顺序执行（批量接口已是多股并行，受速率限制不宜并发请求）
    for bi, batch in enumerate(batches):
        t0 = time.time()
        ok, fail = process_batch(batch)
        total_ok += ok
        total_fail += fail
        elapsed = time.time() - t0
        log.info(
            f"[{bi+1:3d}/{len(batches)}] ok={ok}/{len(batch)} fail={fail} "
            f"耗时={elapsed:.1f}s  累计ok={total_ok}"
        )
        if bi < len(batches) - 1:
            time.sleep(TF_BATCH_SLEEP)

    total_time = time.time() - t_start
    log.info("=" * 65)
    log.info(f"完成: ok={total_ok}, fail={total_fail}, 总耗时={total_time:.1f}s ({total_time/60:.1f}min)")
    log.info(f"parquet 文件位于: {STOCK_DIR}")


if __name__ == "__main__":
    main()
