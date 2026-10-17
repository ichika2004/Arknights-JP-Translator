"""Phase 13: compact launcher + expandable skills; existing Phase 11 OCR unchanged."""
import sys


def main():
    from PySide6.QtWidgets import QApplication
    from arknights_translator.auto_detect_panel import AutoDetectPanel
    from arknights_translator.phase12_overlay import TranslationOverlay
    app = QApplication(sys.argv)
    control = AutoDetectPanel()
    control.show()  # Keep controls out of the captured game name area; minimize as needed.

    overlay = TranslationOverlay(control)
    screen = app.primaryScreen().availableGeometry()
    overlay.move(screen.right() - overlay.width() - 22, screen.top() + 68)
    overlay.show()
    app.aboutToQuit.connect(overlay.close)
    app.aboutToQuit.connect(control.close)
    return app.exec()


if __name__ == '__main__':
    # The frozen executable doubles as a background OCR worker.
    # Check before importing PySide6 or creating QApplication.
    if '--ocr-worker' in sys.argv:
        from arknights_translator.auto_detection_worker import main as worker_main
        sys.exit(worker_main())
    sys.exit(main())
