from __future__ import annotations
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from .ocr import JapaneseOCR
from .translator import OnlineTranslator


class TranslationWorker(QObject):
    completed = Signal(str, str)
    error = Signal(str)
    ready = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.ocr = None
        self.translator = None
        self.previous_source = ""
        self.previous_translation = ""

    @Slot()
    def initialize(self) -> None:
        try:
            self.ocr = JapaneseOCR()
            self.translator = OnlineTranslator()
            self.ready.emit()
        except Exception as exc:
            self.error.emit(f"初始化失敗: {exc}")

    @Slot(object)
    def process(self, image: np.ndarray) -> None:
        if self.ocr is None or self.translator is None:
            self.error.emit("OCR 尚未初始化")
            return
        try:
            source = self.ocr.recognize(image)
            if source and source == self.previous_source:
                self.completed.emit(source, self.previous_translation)
                return
            if not source:
                self.completed.emit("", "")
                return
            translation = self.translator.translate(source)
            self.previous_source = source
            self.previous_translation = translation
            self.completed.emit(source, translation)
        except Exception as exc:
            self.error.emit(f"辨識或翻譯失敗: {exc}")
