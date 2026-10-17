# Arknights JP Translator（明日方舟日服技能翻譯器）

Windows 桌面工具：透過螢幕截圖、PaddleOCR 文字偵測與單行辨識辨識幹員名稱，查詢本地技能資料庫，以繁體中文候選文本顯示技能資訊。

> **非官方專案。** 遊戲角色、技能敘述與商標相關權利歸原權利人所有；翻譯來自第三方資料整理，未逐筆校對。發布前請確認再散布權限。如有權利疑慮，應移除相關圖片和資料庫並使用合規的使用者自行下載流程。

## Download for Windows

[**Download Latest Release**](https://github.com/ichika2004/Arknights-JP-Translator/releases/latest)

1. Download the Windows x64 ZIP.
2. Extract the entire folder.
3. Run `Arknights-JP-Translator.exe`.

No Python or Conda installation required.

## 功能

- 自動辨識畫面中的日文幹員名稱，不需手動框選
- 角色技能 1／2／3 查詢與畫面技能名稱提示（非技能施放狀態）
- 台服繁體中文優先，缺少時使用陸服簡轉繁候選；以日服數值資料渲染動態參數
- 可拖曳／滾輪縮放的圓形圖標，按一下開啟可調整大小及捲動的技能視窗，右鍵可結束程式
- 有歧義的名字不強行指派角色（例如阿米婭不同形態）

## 系統需求

- Windows 10/11、Python 3.11（建議 Conda）
- 遊戲以**視窗化或無邊框視窗**模式執行；獨佔全螢幕未保證支援 Overlay
- 主螢幕顯示遊戲畫面，控制面板盡量最小化，以免影響螢幕擷取

## 安裝與執行（PowerShell）

```powershell
conda create -n arknights-translator python=3.11 -y
conda activate arknights-translator
python -m pip install -r requirements.txt
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
python skill_auto_overlay_viewer.py
```

`paddlepaddle` 在不同 CPU/GPU/Windows 環境的 wheel 與相依套件相容性可能不同；若安裝失敗請先依 Paddle 官方安裝說明選擇相容版本。第一次啟動 PaddleOCR 可能下載偵測與辨識模型。

啟動後請在控制面板選擇「幹員資訊畫面」或「關卡選取畫面」，勾選每三秒檢查；將控制面板最小化。點選圖標查看技能、拖曳移動位置、滾輪縮放；右鍵圖標可結束翻譯器。若技能自動判斷不明確，可手動切換。

## 專案結構

```text
skill_auto_overlay_viewer.py       # 正式入口
arknights_translator/
  auto_detect_panel.py              # 擷取、掃描控制 GUI
  auto_detection_worker.py          # 常駐 Det + Rec 子程序
  phase10_core.py                   # 名稱候選框與資料庫匹配
  phase12_overlay.py                # 圓形圖標及技能面板
  skill_panel.py                    # 技能資料查詢與顯示
  skill_renderer.py                 # 日服技能數值參數渲染
  name_match.py                     # 名稱比對輔助
  capture.py                        # 擷取工具
assets/app_icon.png                 # 自訂圖標（可自行替換）
data/generated/character_names.json
 data/generated/skill_database.json
scripts/                          # 可選的資料重建與 OCR 測試工具
```

## 翻譯資料來源及限制

- JP / EN 原始遊戲資料：[ArknightsGamedata](https://github.com/ArknightsAssets/ArknightsGamedata)
- 台服翻譯候選：[arknights-data-tw-for-maa](https://github.com/arkntools/arknights-data-tw-for-maa)
- 陸服簡體資料經 OpenCC `s2twp` 轉換做備援

技能數值依 JP blackboard、SP 與持續時間等欄位，但跨服文字中的佔位符意義可能不同，**不能保證所有翻譯與倍率已驗證**。對於缺失資料，程式可能顯示日文原文。

此次 ZIP 為精簡原始碼與資料版，移除了 `data/raw`、試驗輸出及 `.git`。資料庫重建腳本需要先下載各服原始資料；不會在啟動時自動下載原始資料。ZIP 中的 JSON 屬第三方遊戲資料衍生內容，公開上傳前請另外確認授權／許可。

## 已知限制

- 目前截取主螢幕而不是指定遊戲視窗；其他視窗遮擋可能影響辨識。
- 自動技能提示屬畫面上的**技能名稱辨識**，不是使用中技能狀態。
- 相近技能名稱、同名不同形態、畫面縮放與字體效果可能造成未匹配。
- `SetWindowDisplayAffinity` 取決於 Windows 與擷取方式，未保證在所有環境排除 Overlay。
- 未在全新 Windows 安裝環境進行端對端測試；以已安裝相容依賴的 Windows 環境為優先。

## 專案程式碼授權

未隨意替你指定 LICENSE。發布前請自行選擇程式碼授權，並區隔第三方遊戲資料及圖像的權利。
