"""Phase 23.3 — draggable toolbar, circular original icon, module stage effects."""
from __future__ import annotations
import sys
from pathlib import Path
if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QIcon
from PySide6.QtWidgets import QPushButton, QApplication
import arknights_translator.app_layers.optional_rogue as old

OriginalController = old.Controller

class DraggableRoundToolbar(old.p231.FloatingToolbar):
    """Explicit grab handle: button events never steal dragging gestures."""
    def __init__(self, controller):
        super().__init__(controller)
        self.drag_handle = QPushButton('⠿', self)
        self.drag_handle.setFixedSize(37, 48)
        self.drag_handle.setToolTip('按住這裡拖曳整條控制列')
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_handle.setStyleSheet('QPushButton {background:#253849; color:#d7e8f5; border-radius:12px; padding:0; font-size:23px;}')
        self.layout().insertWidget(0, self.drag_handle)
        self.drag_handle.installEventFilter(self)
        self._handle_origin = None
        self._toolbar_origin = None
        self.settings_button.setFixedSize(54,54)
        self._round_icon()
        self.adjustSize()

    def _round_icon(self):
        image_path = Path(__file__).resolve().parents[2] / 'assets' / 'app_icon.png'
        if not image_path.is_file():
            self.settings_button.setText('設定')
            return
        original = QPixmap(str(image_path))
        if original.isNull():return
        n=49
        s=min(original.width(),original.height())
        original=original.copy((original.width()-s)//2,(original.height()-s)//2,s,s)
        scaled=original.scaled(n,n,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
        output=QPixmap(n,n)
        output.fill(Qt.GlobalColor.transparent)
        painter=QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path=QPainterPath();path.addEllipse(0,0,n,n)
        painter.setClipPath(path)
        painter.drawPixmap(0,0,scaled)
        painter.end()
        self.settings_button.setText('')
        self.settings_button.setIcon(QIcon(output))
        self.settings_button.setIconSize(QSize(n,n))
        self.settings_button.setStyleSheet('QPushButton {border:0;background:transparent;padding:2px;border-radius:27px;}')

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.drag_handle:
            typ=event.type()
            if typ == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._handle_origin=event.globalPosition().toPoint()
                self._toolbar_origin=self.pos()
                return True
            if typ == QEvent.Type.MouseMove and self._handle_origin is not None:
                dest=self._toolbar_origin+event.globalPosition().toPoint()-self._handle_origin
                screen=QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
                if screen:
                    area=screen.availableGeometry()
                    x=max(area.left()-self.width()+80,min(dest.x(),area.right()-80))
                    y=max(area.top(),min(dest.y(),area.bottom()-self.height()+1))
                    dest=QPoint(x,y)
                self.move(dest)
                return True
            if typ == QEvent.Type.MouseButtonRelease and self._handle_origin is not None:
                self._handle_origin=None
                self._toolbar_origin=None
                self.controller.settings.setValue('phase23_toolbar_position',self.pos())
                return True
        return super().eventFilter(obj,event)

class Controller(OriginalController):
    def __init__(self, app):
        super().__init__(app)
        position=self.toolbar.pos()
        self.toolbar.hide()
        self.toolbar.deleteLater()
        self.toolbar=DraggableRoundToolbar(self)
        self.toolbar.move(position)
        self.toolbar.show()
        self.panel.status.setText('手動掃描待命｜拖曳左側 ⠿ 可移動整條控制列。')

old.p231.base.Controller=Controller
if __name__=='__main__':
    raise SystemExit(old.p231.base.main())
