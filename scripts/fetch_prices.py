#!/usr/bin/env python3
"""
抓 TWSE 全市場前一交易日收盤價，存成 data/stock_prices.json
"""
import json
import os
import sys
import urllib.request
import ssl
from datetime import datetime, timezone

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stock_prices.json")
TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"


def fetch_json(url, ctx):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    ctx = ssl.create_default_context()
    if os.environ.get("VERIFY_SSL", "1") == "0":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    stocks = {}

    print(f"抓取上市 {TWSE_URL} ...")
    twse = fetch_json(TWSE_URL, ctx)
    for s in twse:
        code = s.get("Code", "").strip()
        try:
            close = float(s.get("ClosingPrice", ""))
            change = float(str(s.get("Change", "")).strip() or 0)
        except ValueError:
            continue
        stocks[code] = {"name": s.get("Name", "").strip(), "close": close, "change": change}
    print(f"  上市 {len(twse)} 支")

    print(f"抓取上櫃 {TPEX_URL} ...")
    tpex = fetch_json(TPEX_URL, ctx)
    tpex_count = 0
    for s in tpex:
        code = s.get("SecuritiesCompanyCode", "").strip()
        try:
            close = float(s.get("Close", ""))
            change = float(str(s.get("Change", "")).strip() or 0)
        except ValueError:
            continue
        stocks[code] = {"name": s.get("CompanyName", "").strip(), "close": close, "change": change}
        tpex_count += 1
    print(f"  上櫃 {tpex_count} 支")

    trade_date = (twse[0].get("Date") if twse else "") or (tpex[0].get("Date") if tpex else "")
    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tradeDate": trade_date,
        "stocks": stocks,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ 共 {len(stocks)} 支股票，寫入 {DATA_PATH}")


if __name__ == "__main__":
    main()
