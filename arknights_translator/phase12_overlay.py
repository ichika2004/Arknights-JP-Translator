"""Compact, resizable launcher and scrollable three-skill overlay for Phase 11.

The OCR/skill logic stays in AutoDetectPanel; overlay only mirrors its widgets.
"""
from __future__ import annotations

import ctypes
import time
import sys
from pathlib import Path
from ctypes import wintypes
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QFont, QMouseEvent, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QComboBox, QSizeGrip, QApplication, QMenu, QMessageBox,
)

WDA_EXCLUDEFROMCAPTURE = 0x11
FLAGS = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
         Qt.WindowType.WindowStaysOnTopHint)


def exclude_from_capture(widget: QWidget) -> bool:
    if sys.platform != 'win32':
        return False
    try:
        api = ctypes.WinDLL('user32', use_last_error=True).SetWindowDisplayAffinity
        api.argtypes = (wintypes.HWND, wintypes.DWORD)
        api.restype = wintypes.BOOL
        ctypes.set_last_error(0)
        ok = bool(api(wintypes.HWND(int(widget.winId())), WDA_EXCLUDEFROMCAPTURE))
        print(f'[Overlay] {type(widget).__name__} capture exclusion: {ok}' +
              (f' error={ctypes.get_last_error()}' if not ok else ''), flush=True)
        return ok
    except Exception as exc:
        print(f'[Overlay] Capture exclusion error: {exc}', flush=True)
        return False


class SkillDetails(QWidget):
    def __init__(self, source):
        super().__init__(None)
        self.source = source
        self.setWindowFlags(FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(540, 480)
        self.setMinimumSize(330, 220)
        self._last_character_id = None
        self._last_text = None

        self.setStyleSheet('''
            QFrame#body { background: rgba(18,24,36,245); border-radius: 12px; }
            QLabel { color: #f3f5fa; font-size: 14px; }
            QPushButton { color: white; background: #344255; border: 0;
                          border-radius: 7px; padding: 7px 12px; }
            QPushButton:checked { background: #247cb4; }
            QPushButton:hover { background: #46617e; }
            QComboBox { color: white; background: #344255; border-radius: 6px; padding: 5px; }
            QScrollArea { border: none; background: transparent; }
            QWidget#scrollContent { background: transparent; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.body = QFrame()
        self.body.setObjectName('body')
        outer.addWidget(self.body)
        layout = QVBoxLayout(self.body)
        top = QHBoxLayout()
        self.title = QLabel('等待角色辨識…')
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-weight: 700; font-size: 17px;')
        top.addWidget(self.title, 1)
        close = QPushButton('收起 ×')
        close.clicked.connect(self.hide)
        top.addWidget(close)
        exit_btn = QPushButton('結束程式')
        exit_btn.setToolTip('停止 OCR 子程序並退出翻譯器')
        exit_btn.clicked.connect(QApplication.instance().quit)
        top.addWidget(exit_btn)
        layout.addLayout(top)

        selection = QHBoxLayout()
        self.skill_buttons = []
        for i in range(3):
            b = QPushButton(f'技能 {i + 1}')
            b.setCheckable(True)
            b.clicked.connect(lambda _, idx=i: self.choose_skill(idx))
            self.skill_buttons.append(b)
            selection.addWidget(b)
        layout.addLayout(selection)
        self.detected_hint=QLabel('畫面目前技能：未判定')
        self.detected_hint.setWordWrap(True)
        layout.addWidget(self.detected_hint)

        level_row = QHBoxLayout()
        level_row.addWidget(QLabel('等級'))
        self.level_picker = QComboBox()
        self.level_picker.currentIndexChanged.connect(self.choose_level)
        level_row.addWidget(self.level_picker, 1)
        layout.addLayout(level_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll = scroll
        content = QWidget()
        content.setObjectName('scrollContent')
        content_layout = QVBoxLayout(content)
        self.skill_name = QLabel()
        self.skill_name.setWordWrap(True)
        self.skill_name.setStyleSheet('font-weight: 700; font-size: 16px;')
        self.stats = QLabel()
        self.stats.setWordWrap(True)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.setStyleSheet('color: #b8c0cf; font-size: 12px;')
        for w in (self.skill_name, self.stats, self.description, self.notice):
            content_layout.addWidget(w)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(QLabel('拖曳右下角調整大小'))
        bottom.addWidget(QSizeGrip(self))
        layout.addLayout(bottom)

    def showEvent(self, event):
        super().showEvent(event)
        exclude_from_capture(self)
        self.refresh(force=True)

    def choose_skill(self, idx):
        panel = self.source
        if idx >= panel.skill_combo.count():
            return
        panel.manual_skill_until=time.monotonic()+20.0
        panel.skill_combo.setCurrentIndex(idx)
        self.refresh(force=True)
        self.scroll.verticalScrollBar().setValue(0)

    def choose_level(self, index):
        if index < 0 or index >= self.source.level_combo.count():
            return
        self.source.level_combo.setCurrentIndex(index)
        self.refresh(force=True)

    def refresh(self, force=False):
        panel = self.source
        char = getattr(panel, 'current_character', None)
        if not isinstance(char, dict):
            self.title.setText('等待角色辨識…')
            self.description.setText('尚未找到角色。')
            return
        cid = panel.search.text() if hasattr(panel, 'search') else ''
        if cid != self._last_character_id:
            self._last_character_id = cid
            self.scroll.verticalScrollBar().setValue(0)
        name = char.get('name_zh_tw') or char.get('name_zh_tw_candidate') or char.get('name_jp') or cid
        jp = char.get('name_jp') or ''
        name_text = f'{name} / {jp}' if name != jp else name
        self.title.setText(name_text)
        slot=getattr(panel,'detected_skill_slot',None)
        manual=time.monotonic()<getattr(panel,'manual_skill_until',0)
        self.detected_hint.setText(
            (f'畫面顯示：技能 {slot}' if slot else '畫面目前技能：尚未判定')
            + ('｜手動選擇優先（20 秒）' if manual else '')
        )
        current_idx = panel.skill_combo.currentIndex()
        for i, button in enumerate(self.skill_buttons):
            button.setVisible(i < panel.skill_combo.count())
            button.setChecked(i == current_idx)
        self.level_picker.blockSignals(True)
        self.level_picker.clear()
        for i in range(panel.level_combo.count()):
            self.level_picker.addItem(panel.level_combo.itemText(i))
        self.level_picker.setCurrentIndex(panel.level_combo.currentIndex())
        self.level_picker.blockSignals(False)
        values = (
            panel.skill_name.text(), panel.stats.text(),
            panel.description.toPlainText(), panel.notice.text()
        )
        if force or values != self._last_text:
            self._last_text = values
            self.skill_name.setText(values[0])
            self.stats.setText(values[1])
            self.description.setText(values[2])
            self.notice.setText(values[3])


class TranslationOverlay(QWidget):
    """Draggable icon; click to open details; mouse wheel to scale icon."""
    def __init__(self, source):
        super().__init__(None)
        self.source = source
        self.details = SkillDetails(source)
        self.setWindowFlags(FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.icon_size = 58
        self.setFixedSize(self.icon_size, self.icon_size)
        self._press_global = None
        self._press_pos = None
        self._moved = False
        self.icon_path = Path(__file__).resolve().parents[1] / 'assets' / 'app_icon.png'
        self._image = QPixmap(str(self.icon_path)) if self.icon_path.is_file() else QPixmap()
        self._icon = QLabel('譯', self)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._resize_icon()
        self.setToolTip('左鍵展開｜右鍵選單（結束程式）｜拖曳移動｜滾輪縮放')
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    def _resize_icon(self):
        self.setFixedSize(self.icon_size, self.icon_size)
        self._icon.setGeometry(0, 0, self.icon_size, self.icon_size)
        if not self._image.isNull():
            # A genuine round icon: center-crop image to square, then apply an
            # anti-aliased circular alpha mask. Works with PNG/JPG source images.
            n = self.icon_size
            side = min(self._image.width(), self._image.height())
            source = self._image.copy(
                (self._image.width() - side) // 2,
                (self._image.height() - side) // 2,
                side, side,
            )
            scaled = source.scaled(
                n, n,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            circle = QPixmap(n, n)
            circle.fill(Qt.GlobalColor.transparent)
            painter = QPainter(circle)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            path = QPainterPath()
            path.addEllipse(0, 0, n, n)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            self._icon.setStyleSheet('background: transparent; border: none;')
            self._icon.setText('')
            self._icon.setPixmap(circle)
            return

        # Fallback when assets/app_icon.png is absent or invalid.
        self._icon.clear()
        self._icon.setText('譯')
        font = QFont()
        font.setPointSize(max(15, int(self.icon_size * .38)))
        font.setBold(True)
        self._icon.setFont(font)
        radius = self.icon_size // 2
        self._icon.setStyleSheet(
            f'color:white; background-color:rgba(29,107,155,235); '
            f'border:2px solid rgba(225,240,250,210); border-radius:{radius}px;'
        )

    def showEvent(self, event):
        super().showEvent(event)
        exclude_from_capture(self)

    def refresh(self):
        if self.details.isVisible():
            self.details.refresh()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_pos = self.pos()
            self._moved = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._press_global is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() > 4:
                self._moved = True
            self.move(self._press_pos + delta)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            self._press_global = None
            if not self._moved:
                if self.details.isVisible():
                    self.details.hide()
                else:
                    self.details.refresh(force=True)
                    screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
                    area = screen.availableGeometry()
                    x = min(self.x(), area.right() - self.details.width())
                    y = min(self.y() + self.height() + 8, area.bottom() - self.details.height())
                    self.details.move(max(area.left(), x), max(area.top(), y))
                    self.details.show()
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        detail_action = menu.addAction('展開技能資訊' if not self.details.isVisible() else '收起技能資訊')
        menu.addSeparator()
        quit_action = menu.addAction('結束翻譯器')
        chosen = menu.exec(event.globalPos())
        if chosen == quit_action:
            QApplication.instance().quit()
        elif chosen == detail_action:
            if self.details.isVisible():
                self.details.hide()
            else:
                self.details.refresh(force=True)
                screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
                area = screen.availableGeometry()
                x = min(self.x(), area.right() - self.details.width())
                y = min(self.y() + self.height() + 8, area.bottom() - self.details.height())
                self.details.move(max(area.left(), x), max(area.top(), y))
                self.details.show()
        event.accept()

    def wheelEvent(self, event):
        change = 6 if event.angleDelta().y() > 0 else -6
        if self.icon_size + change >= 36 and self.icon_size + change <= 120:
            self.icon_size += change
            self._resize_icon()
        event.accept()

    def closeEvent(self, event):
        self.timer.stop()
        self.details.close()
        super().closeEvent(event)
