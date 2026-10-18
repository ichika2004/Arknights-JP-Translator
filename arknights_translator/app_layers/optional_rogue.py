"""Phase 23.2: operator-first manual scanner, optional rogue mode, original icon.
Requires Phase23.1 and Phase22.x files in the same project directory.
"""
from __future__ import annotations
import sys
from pathlib import Path

# The existing frozen/CLI worker entry points remain in Phase22 files.
if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QMenu
import arknights_translator.app_layers.manual_scan as p231

# p231.base.Controller is Phase23.1's ManualController.
OriginalController = p231.ManualController

class Controller(OriginalController):
    def __init__(self, app):
        self._rogue_enabled = False
        self._changing_rogue = False
        super().__init__(app)
        self.settings.beginGroup('phase23_2')
        self._rogue_enabled = self.settings.value('rogue_enabled', False, type=bool)
        self.settings.endGroup()

        # Preserve the actual custom app icon; avoid substituting a gear.
        icon = Path(__file__).resolve().parents[2] / 'assets' / 'app_icon.png'
        button = self.toolbar.settings_button
        if icon.is_file():
            pix = QPixmap(str(icon))
            if not pix.isNull():
                button.setText('')
                button.setIcon(QIcon(pix))
                button.setIconSize(self._icon_size())
                button.setFixedSize(54,54)
                button.setToolTip('原本的 Icon：點擊開啟設定')
        else:
            button.setText('設定')
            button.setToolTip('設定（找不到 assets/app_icon.png）')
        button.setStyleSheet('QPushButton { border-radius: 27px; padding: 2px; background: transparent; }')
        self.toolbar.adjustSize()

        # Phase22's mutually-exclusive selector becomes a fixed operator core.
        self.panel.mode.blockSignals(True)
        idx=self.panel.mode.findData('skill')
        if idx >= 0:self.panel.mode.setCurrentIndex(idx)
        self.panel.mode.setEnabled(False)
        self.panel.mode.hide()
        self.panel.mode.blockSignals(False)
        self.panel.layout().insertWidget(2, QLabel('幹員技能與模組：始終啟用（手動掃描）'))
        self.rogue_toggle = QCheckBox('額外啟用集成戰略：收藏品、分隊、事件與選項')
        self.rogue_toggle.setChecked(self._rogue_enabled)
        self.panel.layout().insertWidget(3, self.rogue_toggle)
        self.rogue_toggle.toggled.connect(self.set_rogue_enabled)
        self.panel.setWindowTitle('Arknights JP Translator — Phase 23.2 設定')

        self._stop_rogue_when_unused()
        if self._rogue_enabled:self._ensure_rogue_worker()
        self.rogue.hide_pins_btn.setChecked(not self._rogue_enabled)
        self.panel.topic.setEnabled(self._rogue_enabled)
        self.panel.status.setText('待命中：按「掃描」查看幹員；開啟集成戰略後同時掃描肉鴿。')

    @staticmethod
    def _icon_size():
        from PySide6.QtCore import QSize
        return QSize(46,46)

    def _stop_rogue_when_unused(self):
        self.rogue.accept_results = False
        self.rogue.auto.setChecked(False)
        self.rogue.timer.stop()
        self.rogue.clear_pins()
        if self.rogue._popup:self.rogue._popup.hide()
        proc=self.rogue.proc
        if proc.state() != proc.ProcessState.NotRunning:
            proc.blockSignals(True)
            proc.kill()
            proc.waitForFinished(1500)
            proc.blockSignals(False)
        self.rogue.ready=False
        self.rogue.busy=False

    def _ensure_rogue_worker(self):
        if self.rogue.proc.state() == self.rogue.proc.ProcessState.NotRunning:
            self.rogue.start_worker()
        self.rogue.auto.setChecked(False)
        self.rogue.timer.stop()

    def set_rogue_enabled(self, enabled):
        if self._changing_rogue:return
        enabled=bool(enabled)
        if enabled == self._rogue_enabled:return
        # Invalidate any pending results before tearing down a worker.
        self.clear_results()
        self._rogue_enabled=enabled
        self.settings.beginGroup('phase23_2')
        self.settings.setValue('rogue_enabled',enabled)
        self.settings.endGroup()
        if enabled:self._ensure_rogue_worker()
        else:self._stop_rogue_when_unused()
        self.rogue.hide_pins_btn.setChecked(not enabled)
        self.panel.topic.setEnabled(enabled)
        self.panel.status.setText('集成戰略已開啟；下次掃描包括幹員與肉鴿。' if enabled else '集成戰略已關閉；只掃描幹員技能與模組。')

    def _apply_mode(self, first=False):
        # Parent constructor calls this before rogue_toggle exists.
        super()._apply_mode(first=False)
        if getattr(self,'_manual_timer',None):self._manual_timer.stop() if self._scan_step is None else None
        self.skill.auto_box.setChecked(False)
        self.rogue.auto.setChecked(False)
        self.skill.timer.stop()
        self.rogue.timer.stop()

    def apply_settings(self,*args):
        super().apply_settings(*args)
        # All automatic scan timers must stay off regardless of saved Phase22 state.
        self.skill.auto_box.setChecked(False)
        self.rogue.auto.setChecked(False)
        self.skill.timer.stop()
        self.rogue.timer.stop()
        if getattr(self,'rogue_toggle',None):
            self.rogue.hide_pins_btn.setChecked(not self._rogue_enabled)

    def scan_once(self):
        if not hasattr(self,'toolbar') or self._scan_step is not None:return
        self.clear_results()
        self._scan_generation=self._generation
        self.toolbar.scan_button.setEnabled(False)
        self.toolbar.scan_button.setText('辨識中…')
        self._scan_step='waiting'
        # Operator always scans first. Rogue scan runs only on user opt-in.
        self._tasks=['skill']+(['rogue'] if self._rogue_enabled else [])
        self._manual_timer.start()
        self._start_next()

    def _check_progress(self):
        # Bypass Phase23.1's shortcut that skips skills on rogue hits.
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
            self._start_next()
        elif step=='skill' and not self.skill.busy:
            self._accept_skill=False
            self._start_next()

    def refresh_status(self):
        if self._scan_step is not None:
            self.panel.status.setText(f'辨識中：{self._scan_step}（手動掃描，無背景輪詢）')

    def cleanup(self):
        if hasattr(self,'rogue_toggle'):
            self.settings.beginGroup('phase23_2')
            self.settings.setValue('rogue_enabled', self._rogue_enabled)
            self.settings.endGroup()
        super().cleanup()

# Swap the application controller, preserving all previous functionality.
p231.base.Controller=Controller
if __name__=='__main__':
    raise SystemExit(p231.base.main())
