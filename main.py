from __future__ import annotations
import ctypes
import sys
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QHBoxLayout
)
from arknights_translator.capture import capture_rect
from arknights_translator.ui import RegionSelector, TranslationOverlay
from arknights_translator.worker import TranslationWorker


class ControlWindow(QWidget):
    request_process = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arknights JP Translator — Phase 1")
        self.resize(490, 280)
        self.region = None
        self.selector = None
        self.busy = False
        self.ready = False
        self.overlay = TranslationOverlay()
        self.timer = QTimer(self)
        self.timer.setInterval(1100)
        self.timer.timeout.connect(self.prepare_capture)

        layout = QVBoxLayout(self)
        self.status = QLabel("載入 OCR 模型中，首次執行可能需要下載模型…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.select_button = QPushButton("1. 框選遊戲中的日文對話區域")
        self.select_button.clicked.connect(self.select_region)
        layout.addWidget(self.select_button)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("顯示模式："))
        self.mode = QComboBox()
        self.mode.addItem("字幕模式（原文下方）", "subtitle")
        self.mode.addItem("覆蓋模式（遮住原文）", "cover")
        self.mode.currentIndexChanged.connect(self.redraw)
        mode_row.addWidget(self.mode)
        layout.addLayout(mode_row)
        self.start_button = QPushButton("2. 開始翻譯")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.toggle)
        layout.addWidget(self.start_button)
        self.original = QLabel("日文：")
        self.original.setWordWrap(True)
        self.translation = QLabel("繁體中文：")
        self.translation.setWordWrap(True)
        layout.addWidget(self.original)
        layout.addWidget(self.translation)
        layout.addWidget(QLabel("說明：先選取文字區域；請使用視窗化遊戲。Esc 可取消框選。"))

        self.worker_thread = QThread(self)
        self.worker = TranslationWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.initialize)
        self.request_process.connect(self.worker.process)
        self.worker.ready.connect(self.on_ready)
        self.worker.completed.connect(self.on_completed)
        self.worker.error.connect(self.on_error)
        self.worker_thread.start()

    def on_ready(self):
        self.ready = True
        self.status.setText("OCR 已就緒，請框選對話區域。")
        self.start_button.setEnabled(self.region is not None)

    def select_region(self):
        self.timer.stop()
        self.start_button.setText("2. 開始翻譯")
        self.overlay.hide()
        self.hide()
        self.selector = RegionSelector()
        self.selector.selected.connect(self.on_region)
        self.selector.cancelled.connect(self.show)
        self.selector.show()

    def on_region(self, rect):
        self.region = rect
        self.status.setText(f"已選取畫面區域：{rect}")
        self.start_button.setEnabled(self.ready)
        self.show()

    def toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.overlay.hide()
            self.start_button.setText("2. 開始翻譯")
            self.status.setText("翻譯已暫停")
        else:
            self.timer.start()
            self.start_button.setText("暫停翻譯")
            self.status.setText("即時翻譯中…")
            self.prepare_capture()

    def prepare_capture(self):
        if self.busy or self.region is None:
            return
        self.busy = True
        # Temporarily remove our overlay from the screenshot.
        self.overlay.hide()
        QTimer.singleShot(110, self.capture_and_dispatch)

    def capture_and_dispatch(self):
        try:
            image = capture_rect(self.region)
            self.request_process.emit(image)
        except Exception as exc:
            self.busy = False
            self.status.setText(f"畫面擷取失敗：{exc}")
            return
        # Restore previous text while worker processes new screenshot.
        if self.timer.isActive() and self.translation.text() != "繁體中文：":
            self.redraw()

    def on_completed(self, source, translated):
        self.busy = False
        self.original.setText("日文：" + (source or "（未辨識到文字）"))
        self.translation.setText("繁體中文：" + translated)
        self.redraw()
        if self.timer.isActive():
            self.status.setText("即時翻譯中…")

    def on_error(self, message):
        self.busy = False
        self.status.setText(message)
        if not self.ready:
            self.start_button.setEnabled(False)

    def redraw(self):
        if not self.timer.isActive() or not self.region:
            return
        content = self.translation.text().removeprefix("繁體中文：").strip()
        self.overlay.display(content, self.region, self.mode.currentData())

    def closeEvent(self, event):
        self.timer.stop()
        self.overlay.close()
        self.worker_thread.quit()
        if not self.worker_thread.wait(1500):
            # Don't destroy a QThread that is still running.
            event.ignore()
            self.status.setText("背景翻譯尚未結束，請稍後再關閉。")
            return
        event.accept()


def main():
    # Use physical screen coordinates on Windows to keep mss and Qt aligned.
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
    app = QApplication(sys.argv)
    window = ControlWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
