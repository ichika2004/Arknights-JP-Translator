# Arknights JP Translator — Phase 1

Windows PC prototype: mouse-select a Japanese dialogue area, recognize text using PaddleOCR 3.x, translate with deep-translator, and show Chinese in a click-through Qt overlay.

## Install (Python 3.11 suggested)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

For PowerShell activation policy errors, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` then `.\.venv\Scripts\python.exe main.py` without activating.

Paddle models download automatically on first launch. The translation backend depends on an unofficial Google Translate web wrapper: network connectivity is required and service/rate-limit changes can break it. It is not an official Google Cloud Translate API. Replace `OnlineTranslator` with an official provider for reliability.

## Usage

1. Run Arknights in a window or borderless-window mode.
2. Start program and allow OCR to initialize.
3. Click region selection, drag over Japanese dialogue, release.
4. Choose subtitle or cover mode and start.
5. Stop to select a new region, or change modes while running.

## Limitations

- Single-primary-monitor ROI selection, static rectangular ROI; it does not follow a moved game window.
- Cover mode places one Chinese panel over the ROI; no per-line inpainting/replacement.
- Not guaranteed to work over exclusive fullscreen or with anti-cheat-protected capture.
- The overlay is temporarily hidden during each capture to avoid OCR reading translated text.
- Accuracy and latency depend on OCR models, network, scene and text animation.
- Avoid including unrelated personal/sensitive data in the capture rectangle because recognized text is sent to an external service.
- Follow the game's terms of service and do not bypass anti-cheat protections.
