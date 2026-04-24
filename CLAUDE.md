# ETF 配息追蹤器

## 專案目的
追蹤台灣季配息 ETF 的除息日與配息金額，可記錄持有股數計算可領股利。
部署在 GitHub Pages，手機也能看，資料每天自動更新。

## 目前狀態
✅ 正常運作中

- GitHub Pages：https://nickliu0224-awesome.github.io/stock-etf-tracking/
- 每天早上 9 點（台灣時間）GitHub Actions 自動抓 TWSE 資料並更新 `data/dividends.json`
- 下方搜尋區：顯示「除息日已公布且還沒到」的季配 ETF，目前 Q3 未公告所以為空

## 主要檔案

| 檔案 | 說明 |
|------|------|
| `index.html` | 前端主頁，所有 UI + 邏輯都在這裡，無外部框架 |
| `data/dividends.json` | 所有 ETF 配息資料，由 GitHub Actions 每日更新 |
| `scripts/fetch.py` | 用 Playwright 爬 TWSE ETFortune，合併寫入 dividends.json |
| `.github/workflows/update.yml` | GitHub Actions 排程設定 |

## 如何執行（本地開發）

```bash
cd C:\Users\nickliu\Desktop\AI\etf-tracking-v2
python -m http.server 8766
# 開啟 http://localhost:8766/
```

> 不可直接雙擊 index.html 開啟，fetch() 會因 file:// 協議被瀏覽器封鎖

## TODO
- [ ] 等 Q3 除息日公告後確認搜尋區正常顯示
- [ ] 00888 名稱目前顯示為 "00888"（TWSE 未收錄，從 KNOWN_DIVS 補）
- [ ] 未來考慮加入 FinMind 付費 API 做回測功能

## 踩過的坑

- **TWSE ETFortune 是 SPA**：不能用 requests 直接抓，要用 Playwright 等 networkidle
- **file:// 協議**：fetch() 無法讀本地 JSON，一定要跑 HTTP server
- **GitHub Actions IP 被 GoodInfo 封鎖**：GoodInfo 不能當自動化資料來源
- **merge conflict**：Actions 自動 commit dividends.json 與本地衝突時，用 `git pull --rebase`
- **upcoming 判斷**：用 `exDate > todayStr`（嚴格大於），當天除息日已來不及買
- **localStorage**：key 用 `etf_tracker_v4`，開新 server port 或換網域時舊資料會消失

## 資料結構（dividends.json）

```json
{
  "lastUpdated": "2026-04-24T01:00:00Z",
  "etfs": {
    "0056": {
      "name": "元大高股息",
      "dividends": [
        { "exDate": "2026-04-23", "payDate": "2026-05-14", "amount": 1.0 }
      ]
    }
  }
}
```

## 最後更新
2026-04-24
