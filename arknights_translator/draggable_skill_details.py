"""Phase 21.2: draggable, position-persistent skill details (Qt/PySide6).

Keep the stable skill content/layout intact; title is the drag handle.
"""
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtWidgets import QApplication
from .phase12_overlay import SkillDetails


class DraggableSkillDetails(SkillDetails):
    SETTINGS_GROUP = 'skill_details'

    def __init__(self, source):
        super().__init__(source)
        self._drag_origin = None
        self._drag_window_pos = None
        self._position_initialized = False
        self._initializing_position = False
        self.title.setCursor(Qt.CursorShape.SizeAllCursor)
        self.title.setToolTip('按住此處拖曳技能面板')
        self.title.installEventFilter(self)
        self._restore_saved_position()

    @staticmethod
    def _settings():
        return QSettings('Arknights-JP-Translator', 'UnifiedOverlay')

    def _available_for(self, point):
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def _clamp(self, point):
        area = self._available_for(point)
        # Keep the entire panel inside its screen when possible.
        x = max(area.left(), min(point.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(point.y(), area.bottom() - self.height() + 1))
        return QPoint(x, y)

    def _restore_saved_position(self):
        settings = self._settings()
        position = settings.value(f'{self.SETTINGS_GROUP}/position')
        if isinstance(position, QPoint):
            # Ignore stale coordinates from a disconnected monitor.
            if QApplication.screenAt(position) is not None:
                self._initializing_position = True
                self.move(self._clamp(position))
                self._initializing_position = False
                self._position_initialized = True

    def ensure_initial_position(self, anchor):
        if self._position_initialized:
            return
        screen = QApplication.screenAt(anchor.geometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        # Prefer beside the launcher; if no room, place below it.
        right_x = anchor.x() - self.width() - 12
        if right_x >= area.left():
            x = right_x
            y = anchor.y()
        else:
            x = anchor.x()
            y = anchor.y() + anchor.height() + 10
        self._initializing_position = True
        self.move(self._clamp(QPoint(x, y)))
        self._initializing_position = False
        self._position_initialized = True
        self._save_position()

    def _save_position(self):
        if self._position_initialized and not self._initializing_position:
            self._settings().setValue(f'{self.SETTINGS_GROUP}/position', self.pos())

    def eventFilter(self, watched, event):
        if watched is self.title:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_origin = event.globalPosition().toPoint()
                self._drag_window_pos = self.pos()
                return True
            if t == QEvent.Type.MouseMove and self._drag_origin is not None:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    delta = event.globalPosition().toPoint() - self._drag_origin
                    self.move(self._clamp(self._drag_window_pos + delta))
                    return True
            if t == QEvent.Type.MouseButtonRelease and self._drag_origin is not None:
                self._drag_origin = None
                self._drag_window_pos = None
                self._position_initialized = True
                self._save_position()
                return True
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self._save_position()
        super().hideEvent(event)
