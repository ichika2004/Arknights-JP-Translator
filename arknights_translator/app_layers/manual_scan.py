"""Phase 23.0: on-demand translation toolbar (scan / clear / settings).
Run from repository root alongside Phase 22 and Phase 22.4 files.
"""
from __future__ import annotations
import sys
if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QMenu, QApplication
from arknights_translator.module_details import ModuleDetails
from arknights_translator.phase12_overlay import exclude_from_capture
import arknights_translator.app_layers.rogue_context as previous
base = previous.base


class OnceRogueViewer(previous.FasterRogueViewer):
    def __init__(self):
        self.accept_results = False
        super().__init__()

    def process(self, lines, elapsed):
        if not self.accept_results:
            return
        return super().process(lines, elapsed)


base.OverlayViewer = OnceRogueViewer


class FloatingToolbar(QWidget):
    """Draggable single-row toolbar; click controls, drag by its background."""
    def __init__(self, controller):
        super().__init__(None)
        self.controller = controller
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet('''
          QWidget#toolbar {background-color: rgba(19,27,39,230);border:1px solid #688097;border-radius:18px;}
          QPushButton {border:0;border-radius:13px;padding:10px 15px;color:#f8fafc;
                       font-size:14px;font-weight:600;background:#34475b;}
          QPushButton:hover {background:#50647a;}
          QPushButton#scan {background:#1674b4;}
          QPushButton#scan:hover {background:#2393d5;}
          QPushButton:disabled {background:#5c6270;color:#d1d5db;}
        ''')
        self.setObjectName('toolbar')
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(7)
        self.scan_button = QPushButton('⌕ 掃描')
        self.scan_button.setObjectName('scan')
        self.scan_button.clicked.connect(controller.scan_once)
        self.clear_button = QPushButton('✕ 清除')
        self.clear_button.clicked.connect(controller.clear_results)
        self.settings_button = QPushButton('⚙ 設定')
        self.settings_button.clicked.connect(controller.toggle_settings)
        for button in (self.scan_button,self.clear_button,self.settings_button):
            row.addWidget(button)
        self.adjustSize()
        self._drag_origin = None
        self._window_origin = None
        self.setToolTip('按「掃描」翻譯畫面｜按「清除」移除 !｜拖曳按鈕之間的空白處移動')

    def showEvent(self, event):
        super().showEvent(event)
        exclude_from_capture(self)

    def mousePressEvent(self, event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._drag_origin=event.globalPosition().toPoint()
            self._window_origin=self.pos()
            event.accept()

    def mouseMoveEvent(self,event):
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._window_origin + event.globalPosition().toPoint()-self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self,event):
        self._drag_origin=None
        event.accept()

    def contextMenuEvent(self,event):
        menu=QMenu(self)
        a=menu.addAction('掃描目前畫面')
        b=menu.addAction('清除所有 !')
        c=menu.addAction('設定')
        menu.addSeparator()
        d=menu.addAction('結束程式')
        selected=menu.exec(event.globalPos())
        if selected==a:self.controller.scan_once()
        elif selected==b:self.controller.clear_results()
        elif selected==c:self.controller.toggle_settings()
        elif selected==d:self.controller.shutdown()


class ManualController(base.Controller):
    def __init__(self,app):
        self._suppress_settings=False
        self._generation=0
        self._scan_generation=0
        self._scan_step=None
        self._scan_deadline=0
        self._manual_timer=None
        self._accept_skill=False
        self._rogue_before_scan=0
        super().__init__(app)
        self.module_dialog=ModuleDetails()
        self.module_button=QPushButton("查看模組")
        self.module_button.clicked.connect(self.open_modules)
        self.circle.details.body.layout().insertWidget(1,self.module_button)
        self._stagger_timer.stop()
        self._manual_timer=QTimer(self.panel)
        self._manual_timer.setInterval(180)
        self._manual_timer.timeout.connect(self._check_progress)
        # Never leave automatic inference enabled even when Phase22 stored True.
        self.panel.auto.blockSignals(True)
        self.panel.auto.setChecked(False)
        self.panel.auto.setEnabled(False)
        self.panel.auto.setText('背景自動掃描已停用（Phase 23 手動模式）')
        self.panel.auto.blockSignals(False)
        self.skill.auto_box.setChecked(False)
        self.rogue.auto.setChecked(False)
        self.skill.timer.stop()
        self.rogue.timer.stop()
        self._stagger_timer.stop()
        self.circle.hide()  # Replace settings-only round icon with permanent 3-button toolbar.
        self.toolbar=FloatingToolbar(self)
        screen=app.primaryScreen().availableGeometry()
        saved=self.settings.value('phase23_toolbar_position')
        if isinstance(saved,QPoint):
            self.toolbar.move(saved)
        else:
            self.toolbar.move(screen.right()-self.toolbar.width()-24,screen.top()+64)
        self.toolbar.show()
        self.panel.setWindowTitle('Arknights JP Translator — Phase 23 設定（手動掃描）')
        # On creation the original controller schedules scan_once via QTimer.singleShot.
        # scan_once below deliberately requires explicit user invocation.

    def _apply_mode(self, first=False):
        # Called during parent construction before manual controls exist.
        super()._apply_mode(first=False)
        self.skill.auto_box.setChecked(False)
        self.rogue.auto.setChecked(False)
        self.skill.timer.stop()
        self.rogue.timer.stop()
        if getattr(self,'_stagger_timer',None):self._stagger_timer.stop()

    def apply_settings(self,*args):
        if not hasattr(self,'panel'):return
        self.panel.auto.blockSignals(True)
        self.panel.auto.setChecked(False)
        self.panel.auto.blockSignals(False)
        super().apply_settings(*args)
        if getattr(self,'_stagger_timer',None):self._stagger_timer.stop()

    def on_character_bbox(self,cid,bbox,confidence):
        if not self._accept_skill or self._scan_generation!=self._generation:
            return
        return super().on_character_bbox(cid,bbox,confidence)

    def open_modules(self):
        cid=self.skill.search.text().strip()
        if not cid:
            self.panel.status.setText("尚未辨識角色，請先掃描技能畫面。")
            return
        self.module_dialog.show_character(cid)

    def _clear_visuals(self):
        if hasattr(self,"module_dialog"):self.module_dialog.hide()
        self.clear_skill_pin()
        self.circle.details.hide()
        self.rogue.clear_pins()
        if self.rogue._popup:self.rogue._popup.hide()

    def clear_results(self):
        self._generation+=1
        self._accept_skill=False
        self.rogue.accept_results=False
        self._scan_step=None
        if self._manual_timer:self._manual_timer.stop()
        self._clear_visuals()
        if hasattr(self,'toolbar'):
            self.toolbar.scan_button.setEnabled(True)
            self.toolbar.scan_button.setText('⌕ 掃描')
        self.panel.status.setText('已清除所有翻譯提示；等待手動掃描。')

    def scan_once(self):
        # A single user click starts a bounded sequential job, never a timer loop.
        if not hasattr(self,'toolbar') or self._scan_step is not None:return
        self.clear_results()
        self._scan_generation=self._generation
        self.toolbar.scan_button.setEnabled(False)
        self.toolbar.scan_button.setText('辨識中…')
        self._scan_step='waiting'
        self._tasks=[]
        mode=self.panel.mode.currentData()
        if mode in ('auto','rogue'):self._tasks.append('rogue')
        if mode in ('auto','skill'):self._tasks.append('skill')
        self._manual_timer.start()
        self._start_next()

    def _start_next(self):
        if self._scan_generation!=self._generation:return
        if not self._tasks:
            self._finish_scan()
            return
        task=self._tasks.pop(0)
        self._scan_step=task
        import time
        self._scan_deadline=time.monotonic()+90
        if task=='rogue':
            if not self.rogue.ready or self.rogue.busy:
                self._scan_step='wait_rogue'
                return
            self._rogue_before_scan=len(self.rogue._pins)
            self.rogue.accept_results=True
            self.rogue.scan()
        else:
            if not self.skill.ready or self.skill.busy:
                self._scan_step='wait_skill'
                return
            self._accept_skill=True
            self.skill.scan(True)

    def _check_progress(self):
        import time
        if self._scan_generation!=self._generation:return
        step=self._scan_step
        if step is None:return
        if time.monotonic()>self._scan_deadline:
            self.rogue.accept_results=False
            self._accept_skill=False
            self._start_next()
            return
        if step=='wait_rogue':
            if self.rogue.ready and not self.rogue.busy:
                self._tasks.insert(0,'rogue');self._start_next()
        elif step=='wait_skill':
            if self.skill.ready and not self.skill.busy:
                self._tasks.insert(0,'skill');self._start_next()
        elif step=='rogue' and not self.rogue.busy:
            self.rogue.accept_results=False
            # Fast auto: if the rogue scan found usable cards, do not run a
            # second full-screen skill OCR on the same frame. Skill-only mode
            # remains available for a skill screen.
            if self.panel.mode.currentData() == 'auto' and len(self.rogue._pins)>0:
                self._tasks=[t for t in self._tasks if t!='skill']
            self._start_next()
        elif step=='skill' and not self.skill.busy:
            self._accept_skill=False
            self._start_next()

    def _finish_scan(self):
        self._scan_step=None
        self._manual_timer.stop()
        self.rogue.accept_results=False
        self._accept_skill=False
        self.toolbar.scan_button.setText('⌕ 掃描')
        self.toolbar.scan_button.setEnabled(True)
        self.panel.status.setText(f'本次掃描完成：集成戰略 {len(self.rogue._pins)} 個提示，角色 {int(self.skill_pin is not None)} 個提示。')

    def refresh_status(self):
        if self._scan_step is None:
            return
        self.panel.status.setText(f'手動辨識中：{self._scan_step}。模型載入後才會開始推論。')

    def cleanup(self):
        if getattr(self,'toolbar',None):
            self.settings.setValue('phase23_toolbar_position',self.toolbar.pos())
        if self._manual_timer:self._manual_timer.stop()
        if hasattr(self,"module_dialog"):self.module_dialog.close()
        super().cleanup()

base.Controller=ManualController

if __name__=='__main__':
    raise SystemExit(base.main())
