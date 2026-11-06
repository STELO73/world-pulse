# WORLD PULSE 2.0 — STELO73

繁體中文、手機優先的世界新聞／熱門搜尋／股票圖表網站。**不需要付費 API 或信用卡**。網站本身不含虛構新聞。

## 重要：摘要的真實能力

- 新聞來自 Google News RSS，顯示**真實標題、來源、時間與連結**。若 RSS description 有足夠非重複內容，才顯示來源摘要；否則明確標示未取得內文。**不會冒充 AI 閱讀全文的新聞分析**。
- 熱搜來自 Google Trends RSS（如可用），可顯示相關報道標題；Reddit 公開熱門帖 JSON 只作可用時的補充。**不是 Threads 官方熱搜排行**；不會虛構網民立場。
- 股票使用 TradingView 第三方嵌入圖表。行情可能延遲或因供應商限制而不可用；預設股票**不是即時熱門排名**。
- 不提供 AI 自動生成深度摘要、全文翻譯、可靠的「股價升跌原因」歸因。此類功能在零成本、無受保障資料權限下不可保證。

## 部署到 GitHub Pages（新 Repository）

1. 建立 **Public** Repository：`world-pulse`（不要覆蓋其他遊戲 Repository）。
2. 把本 ZIP **解壓後的全部檔案及資料夾**上傳到 Repository 根目錄（`index.html`, `scripts/`, `data/`, `.github/workflows/` 等）。注意 GitHub 網頁上傳時隱藏的 `.github` 目錄也要存在。
3. Repository → **Settings → Actions → General**，確認 Actions 可執行；Workflow permissions 設為 **Read and write permissions**（若可設定）。如組織策略限制推送，請檢查權限。
4. **Actions → Update public news and trends → Run workflow**。首次更新後，檢查 `data/pulse.json` 的 `generated_at`、`status`、`regions`。若全數來源不可用，會顯示 unavailable 而非假新聞。
5. **Settings → Pages → Build and deployment → Deploy from a branch → main / (root) → Save**。
6. 預計網址：`https://stelo73.github.io/world-pulse/`（要等 GitHub Pages 部署完成）。

排程：香港時間約 08:15、12:15、18:15、23:15（GitHub Actions 的 schedule 可能延遲；公開 Repository 長期無活動可能自動停用排程）。資料頁面會顯示最後更新時間；超過 24 小時會提示。

## 本地測試

在專案根目錄執行：

```bash
python scripts/update.py
python -m http.server 8000
```

然後用瀏覽器打開 `http://localhost:8000`。**不要直接以 file:// 開啟**，因為瀏覽器可能阻止讀取 JSON。

## 費用與資料限制

- GitHub Pages、公開 Repository 的標準 GitHub Actions 用量按目前 GitHub 免費政策運作；須遵守 GitHub 政策及合理使用規範，並非保證永遠免費或永遠可用。
- 公開 RSS／Reddit／Trends 來源可變動、封鎖、限速或調整授權。請遵守各來源服務條款；若某來源不再可用，該區會清楚標示無資料。
- 程式沒有使用任何付費 API、第三方代理、金鑰或信用卡；股票圖表由外部服務直接載入。
- 網站公開展示來源標題及連結，並不重製新聞全文。

## 主要檔案

- `index.html`：完整前端（手機／iPad／電腦）
- `scripts/update.py`：抓取公開 RSS、整理來源資訊、輸出 JSON
- `.github/workflows/update.yml`：定時更新並提交 JSON
- `data/pulse.json`：預設為 pending，不包含示範或假新聞

如需真正生成式 AI 摘要，必須額外配置可信模型／執行環境、測試輸出及核對機制；免費配額不保證長期穩定，故沒有將其偽裝為本版功能。
