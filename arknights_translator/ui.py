from __future__ import annotations
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication


class RegionSelector(QWidget):
    selected = Signal(object)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.position().toPoint()
            self.end = self.start
            self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is None or self.end is None:
            return
        self.end = event.position().toPoint()
        rect = QRect(self.start, self.end).normalized()
        if rect.width() > 30 and rect.height() > 20:
            top_left = self.mapToGlobal(rect.topLeft())
            self.selected.emit((top_left.x(), top_left.y(), rect.width(), rect.height()))
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 85))
        if self.start is not None and self.end is not None:
            rect = QRect(self.start, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(65, 175, 255), 2))
            painter.drawRect(rect)


class TranslationOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(
            "QLabel { background-color: rgba(12, 17, 26, 225); color: white;"
            "border: 1px solid rgba(100, 160, 240, 190); border-radius: 8px;"
            "padding: 9px; font-size: 17px; font-family: 'Microsoft JhengHei'; }"
        )
        layout.addWidget(self.label)

    def display(self, text: str, rect: tuple[int, int, int, int], mode: str) -> None:
        x, y, w, h = rect
        self.label.setText(text)
        if mode == "cover":
            self.setGeometry(x, y, max(w, 260), max(h, 70))
        else:
            # Subtitle mode uses a separate floating line below the ROI.
            self.setGeometry(x, y + h + 12, max(w, 450), 110)
        if text:
            self.show()
        else:
            self.hide()
