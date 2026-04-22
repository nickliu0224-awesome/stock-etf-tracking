#!/usr/bin/env python3
"""
ETF 除息資料抓取腳本
- 來源：TWSE ETFortune dividendList（官方、免費、無限制）
- 使用 Playwright 渲染 JavaScript，攔截 TWSE 後端 API 回應
- 每日由 GitHub Actions 執行
- 輸出：data/dividends.json（累積式，新資料合併舊資料）
"""
import json
import os
import sys
import time
from datetime import datetime, date, timezone

# ── 設定 ──────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dividends.json")
TWSE_DIVIDEND_URL = "https://www.twse.com.tw/zh/ETFortune/dividendList"

# TWSE 尚未收錄時手動補充（每季更新一次）
KNOWN_DIVS = {
    "00888": [
        {"exDate": "2026-04-23", "payDate": "2026-05-20", "amount": 1.05},
        {"exDate": "2026-01-20", "payDate": "2026-02-11", "amount": 0.51},
    ],
}

# ── 工具函數 ──────────────────────────────────────────────
def roc_to_iso(s: str) -> str | None:
    """民國日期（115/04/23 或 115年04月23日）→ ISO（2026-04-23）"""
    s = s.strip().replace("年", "/").replace("月", "/").replace("日", "")
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        year = int(parts[0]) + 1911
        return f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    except ValueError:
        return None


def parse_amount(val) -> float | None:
    try:
        v = float(str(val).replace(",", "").strip())
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


# ── Playwright 抓取 ───────────────────────────────────────
def fetch_via_playwright() -> list[dict]:
    """
    用 headless Chromium 開啟 TWSE ETFortune 頁面，
    攔截後端 API 回應（JSON）或解析 HTML 表格。
    """
    from playwright.sync_api import sync_playwright

    captured = []

    def on_response(response):
        """攔截所有 XHR / fetch 回應，找 JSON 配息資料"""
        try:
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            if response.status != 200:
                return
            data = response.json()
            rows = data if isinstance(data, list) else data.get("data", [])
            if not rows or not isinstance(rows[0], dict):
                return
            # 判斷是否含有配息欄位
            keys = set(rows[0].keys())
            if any("除息" in k or "dividend" in k.lower() or "配息" in k for k in keys):
                captured.extend(rows)
                print(f"  [intercept] 攔截到 {len(rows)} 筆資料 from {response.url[:80]}")
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.on("response", on_response)

        print(f"  開啟 {TWSE_DIVIDEND_URL} ...")
        page.goto(TWSE_DIVIDEND_URL, wait_until="networkidle", timeout=60000)

        # 若攔截沒成功，改解析 HTML 表格
        if not captured:
            print("  API 攔截無資料，改解析 HTML 表格 ...")
            captured = parse_html_table(page)

        browser.close()

    return parse_records(captured)


def parse_html_table(page) -> list[dict]:
    """從渲染後的 HTML 表格解析資料"""
    rows = []
    try:
        # 等表格出現
        page.wait_for_selector("table tbody tr", timeout=15000)
        trs = page.query_selector_all("table tbody tr")
        for tr in trs:
            tds = tr.query_selector_all("td")
            if len(tds) >= 5:
                rows.append({
                    "証券代號": tds[0].inner_text().strip(),
                    "証券簡稱": tds[1].inner_text().strip(),
                    "除息交易日": tds[2].inner_text().strip(),
                    "收益分配發放日": tds[4].inner_text().strip(),
                    "收益分配金額": tds[5].inner_text().strip() if len(tds) > 5 else "",
                })
    except Exception as e:
        print(f"  [WARN] HTML 表格解析失敗: {e}")
    return rows


def parse_records(rows: list[dict]) -> list[dict]:
    """將原始 dict 陣列轉成標準格式"""
    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("証券代號") or row.get("stock_id") or "").strip()
        name = str(row.get("証券簡稱") or row.get("name") or "").strip()
        ex_raw = str(row.get("除息交易日") or row.get("ex_date") or "").strip()
        pay_raw = str(row.get("收益分配發放日") or row.get("pay_date") or "").strip()
        amt_raw = row.get("收益分配金額") or row.get("dividend") or 0

        ex_date = roc_to_iso(ex_raw)
        pay_date = roc_to_iso(pay_raw) if pay_raw else None
        amount = parse_amount(amt_raw)

        if code and ex_date and amount is not None:
            results.append({
                "code": code,
                "name": name,
                "exDate": ex_date,
                "payDate": pay_date,
                "amount": amount,
            })
    return results


# ── 資料合併 ─────────────────────────────────────────────
def load_existing() -> dict:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"etfs": {}}


def merge(etfs: dict, records: list[dict]) -> int:
    added = 0
    for rec in records:
        code = rec["code"]
        if code not in etfs:
            etfs[code] = {"name": rec["name"], "dividends": []}
        elif rec["name"]:
            etfs[code]["name"] = rec["name"]

        existing_dates = {d["exDate"] for d in etfs[code]["dividends"]}
        if rec["exDate"] not in existing_dates:
            etfs[code]["dividends"].append({
                "exDate": rec["exDate"],
                "payDate": rec["payDate"],
                "amount": rec["amount"],
            })
            added += 1
    return added


def apply_known_divs(etfs: dict):
    for code, divs in KNOWN_DIVS.items():
        if code not in etfs:
            etfs[code] = {"name": code, "dividends": []}
        existing_dates = {d["exDate"] for d in etfs[code]["dividends"]}
        for d in divs:
            if d["exDate"] not in existing_dates:
                etfs[code]["dividends"].append(d)


def sort_dividends(etfs: dict):
    for code in etfs:
        etfs[code]["dividends"].sort(key=lambda d: d["exDate"], reverse=True)


# ── 主程式 ───────────────────────────────────────────────
def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== 抓取 ETF 除息資料（TWSE ETFortune via Playwright）===")

    data = load_existing()
    etfs = data.get("etfs", {})

    records = fetch_via_playwright()
    print(f"  TWSE: 抓到 {len(records)} 筆有效記錄")

    added = merge(etfs, records)
    apply_known_divs(etfs)
    sort_dividends(etfs)

    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "etfs": etfs,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v["dividends"]) for v in etfs.values())
    print(f"✓ 共 {len(etfs)} 支 ETF，{total} 筆配息記錄（新增 {added} 筆）")
    print(f"✓ 寫入 {DATA_PATH}")


if __name__ == "__main__":
    main()
