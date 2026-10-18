# Arknights JP Translator

Windows 遊戲畫面日文輔助翻譯（繁體中文）。

## 執行

Python 3.11，請先依 `requirements.txt` 安裝相依套件及 PaddleOCR 執行環境。

```powershell
conda activate arknights-translator
python main.py
```

**正式啟動入口只有 `main.py`**。原 Phase 22–23 的必要實作已移至 `arknights_translator/app_layers/`，不再是獨立啟動檔。為保留已驗證的功能，這些內部模組仍依原有層次呼叫，尚未改成單一 OCR Worker。

## 功能

- 常駐掃描／清除控制列；掃描才執行 OCR，清除會移除所有翻譯提示
- 使用 `assets/app_icon.png` 的圓形設定圖示；控制列可拖曳
- 角色技能、原始特性、模組及 Stage 效果在同一半透明面板查看
- 模組 Story 預設收合；台服繁中優先，缺少時以簡中轉繁、日文備援
- 集成戰略可按需啟用：分隊、收藏品、事件及選項
- 統一關閉流程；預設顯示翻譯驚嘆號

## 資料

主要索引位於 `data/generated/`。重建模組索引可使用：

```powershell
python scripts/build_module_index.py --refresh
python scripts/build_operator_traits.py
```

`data/raw/modules/` 包含資料建置所使用的 JP/TW/CN 遊戲資料快取；更新時請遵守原始資料來源的授權與再散布條件。

## 打包 Windows EXE

```powershell
python build_exe.py
```

## 驗證注意事項

此版做了程式組織與匯入路徑重整，已進行語法、模組路徑及封裝結構檢查；**尚未在 Windows 遊戲中執行 GUI/OCR 端到端測試**。請先驗證操作正常再取代既有可用版本。第三方遊戲資料及商標歸各自權利人所有。
