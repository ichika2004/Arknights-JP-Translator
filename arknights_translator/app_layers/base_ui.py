"""Phase 22: settings-only launcher with clickable skill and rogue pins.
Run from repository root: python arknights_translator.app_layers.base_ui.py
Uses existing OCR worker implementations; automatic means both are active.
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSettings, QPoint
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QMenu, QMessageBox

if '--ocr-worker' in sys.argv:
    from arknights_translator.auto_detection_worker import main
    raise SystemExit(main())
if '--rogue-worker' in sys.argv:
    from arknights_translator.rogue_ocr_worker import main
    raise SystemExit(main())

from arknights_translator.auto_detect_panel import AutoDetectPanel
from arknights_translator.phase12_overlay import TranslationOverlay, exclude_from_capture
from arknights_translator import phase12_overlay as old_overlay
from arknights_translator.draggable_skill_details import DraggableSkillDetails
from rogue_translation_overlay import OverlayViewer, TranslationPin

old_overlay.SkillDetails = DraggableSkillDetails


class ObservedSkillPanel(AutoDetectPanel):
    """Inspect the same OCR JSON without changing the stable skill panel logic."""
    def __init__(self, callback):
        self._on_character_bbox = callback
        self._observe_buffer = ''
        super().__init__()

    def read_stdout(self):
        # Original handler consumes self.buffer. Forward raw stdout into it once.
        raw = bytes(self.proc.readAllStandardOutput()).decode('utf-8', 'replace')
        self._observe_buffer += raw
        found = []
        while '\n' in self._observe_buffer:
            line, self._observe_buffer = self._observe_buffer.split('\n', 1)
            if not line.startswith('OCR_JSON='):
                continue
            try:
                data = json.loads(line[len('OCR_JSON='):])
            except ValueError:
                continue
            if data.get('id') != self.pending or not data.get('character_id'):
                continue
            cid = data['character_id']
            for c in data.get('candidates') or []:
                if c.get('character_id') == cid and c.get('bbox'):
                    found.append((cid, c['bbox'], c.get('ocr_confidence', 0)))
                    break
        self.buffer += raw
        super().read_stdout()
        for cid, bbox, conf in found:
            if self.search.text() == cid:
                self._on_character_bbox(cid, bbox, conf)


class SettingsCircle(TranslationOverlay):
    def __init__(self, controller, skill):
        super().__init__(skill)
        self.controller = controller
        # TranslationOverlay creates a skill detail widget. Only the ! opens it.
        self.setToolTip('左鍵：設定｜右鍵：設定與退出｜拖曳：移動')

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            self._press_global = None
            if not self._moved:
                self.controller.toggle_settings()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        settings = menu.addAction('設定')
        toggle = menu.addAction('顯示／隱藏翻譯提示')
        menu.addSeparator()
        exit_action = menu.addAction('結束程式')
        result = menu.exec(event.globalPos())
        if result == settings:
            self.controller.toggle_settings()
        elif result == toggle:
            self.controller.set_pins_enabled(not self.controller.pins_enabled)
        elif result == exit_action:
            self.controller.shutdown()
        event.accept()


class SettingsPanel(QWidget):
    def __init__(self, controller):
        super().__init__(None)
        self.controller = controller
        self.setWindowTitle('Arknights JP Translator — 設定')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(390, 320)
        layout = QVBoxLayout(self)
        title = QLabel('翻譯器設定')
        title.setStyleSheet('font-size: 19px; font-weight: 700')
        layout.addWidget(title)
        layout.addWidget(QLabel('翻譯模式'))
        self.mode = QComboBox()
        self.mode.addItem('自動辨識（技能與集成戰略）', 'auto')
        self.mode.addItem('只辨識幹員技能', 'skill')
        self.mode.addItem('只辨識集成戰略', 'rogue')
        layout.addWidget(self.mode)
        self.auto = QCheckBox('啟用自動辨識')
        layout.addWidget(self.auto)
        self.pins = QCheckBox('顯示畫面上的 ! 翻譯提示')
        layout.addWidget(self.pins)
        layout.addWidget(QLabel('集成戰略主題'))
        self.topic = QComboBox()
        self.topic.addItem('尚未指定（避免同名效果誤判）', None)
        from rogue_translation_viewer import TOPICS
        for topic_id, topic_name in TOPICS.items():
            self.topic.addItem(topic_name, topic_id)
        layout.addWidget(self.topic)
        self.status = QLabel('等待 OCR 啟動…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        once = QPushButton('辨識一次')
        once.clicked.connect(controller.scan_once)
        buttons.addWidget(once)
        hide = QPushButton('收起設定')
        hide.clicked.connect(self.hide)
        buttons.addWidget(hide)
        quit_button = QPushButton('結束程式')
        quit_button.clicked.connect(controller.shutdown)
        buttons.addWidget(quit_button)
        layout.addLayout(buttons)
        self.mode.currentIndexChanged.connect(controller.apply_settings)
        self.auto.toggled.connect(controller.apply_settings)
        self.pins.toggled.connect(controller.apply_settings)
        self.topic.currentIndexChanged.connect(controller.apply_settings)

    def showEvent(self, event):
        super().showEvent(event)
        exclude_from_capture(self)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class Controller:
    def __init__(self, app):
        self.app = app
        self.shutting_down = False
        self.settings = QSettings('Arknights-JP-Translator', 'Phase22')
        self.pins_enabled = True
        self.skill_pin = None
        self.skill = ObservedSkillPanel(self.on_character_bbox)
        self.skill.hide()
        self.rogue = OverlayViewer()
        self.rogue.hide()
        # A child close button must never terminate the unified app.
        self.rogue.exit_button.hide()
        self.circle = SettingsCircle(self, self.skill)
        self.panel = SettingsPanel(self)
        screen = app.primaryScreen().availableGeometry()
        self.circle.move(screen.right()-self.circle.width()-22, screen.top()+68)
        self.circle.show()
        self.panel.move(max(screen.left(), screen.right()-self.panel.width()-95), screen.top()+150)
        # Default is auto ON on first run. Persist explicit user changes.
        self.panel.mode.setCurrentIndex(max(0, self.panel.mode.findData(self.settings.value('mode', 'auto'))))
        self.panel.auto.setChecked(self.settings.value('auto_enabled', True, type=bool))
        self.panel.pins.setChecked(self.settings.value('pins_enabled', True, type=bool))
        saved_topic = self.settings.value('topic_id', '') or None
        topic_i = self.panel.topic.findData(saved_topic)
        self.panel.topic.setCurrentIndex(max(0,topic_i))
        self.app.aboutToQuit.connect(self.cleanup)
        self._pin_screen = None
        self._apply_mode(first=True)
        self._status_timer = QTimer(self.panel)
        self._status_timer.timeout.connect(self.refresh_status)
        self._status_timer.start(1200)
        # Settings panel starts collapsed; icon is the settings entry point.

    def _skill_point(self, bbox):
        # Worker bbox in primary-screen physical pixels; convert to Qt coordinates.
        import mss
        with mss.mss() as sct:
            capture = sct.monitors[1]
        qscreen = QApplication.primaryScreen().geometry()
        fx = qscreen.width()/capture['width']
        fy = qscreen.height()/capture['height']
        return QPoint(round(qscreen.left() + bbox[2]*fx + 5),
                      round(qscreen.top() + bbox[1]*fy - 10))

    def on_character_bbox(self, cid, bbox, confidence):
        if self.shutting_down or not self.pins_enabled or self.panel.mode.currentData() == 'rogue':
            return
        try:
            pos = self._skill_point(bbox)
            if self.skill_pin is not None and getattr(self, '_skill_pin_id', None) == cid:
                if (self.skill_pin.pos()-pos).manhattanLength() <= 12:
                    return
            self.clear_skill_pin()
            card = {'title_tw':'查看角色技能', 'character_id':cid}
            self.skill_pin = TranslationPin(card,pos,self.show_skill_details)
            self._skill_pin_id = cid
            self.skill_pin.show()
            exclude_from_capture(self.skill_pin)
        except Exception as exc:
            print('[Skill pin]', repr(exc), flush=True)

    def show_skill_details(self, card, point):
        details = self.circle.details
        cid = card.get('character_id')
        if cid and self.skill.search.text() != cid:
            self.skill.search.setText(cid)
        if details.isVisible():
            details.hide()
        else:
            details.refresh(force=True)
            details.ensure_initial_position(self.circle)
            details.show()
            details.raise_()

    def clear_skill_pin(self):
        if self.skill_pin is not None:
            self.skill_pin.close()
            self.skill_pin.deleteLater()
            self.skill_pin = None

    def toggle_settings(self):
        self.panel.setVisible(not self.panel.isVisible())
        if self.panel.isVisible():
            self.panel.raise_()

    def set_pins_enabled(self, enabled):
        self.panel.pins.setChecked(enabled)
        self.apply_settings()

    def apply_settings(self, *_):
        if self.shutting_down or not hasattr(self, 'rogue'):
            return
        self.settings.setValue('mode', self.panel.mode.currentData())
        self.settings.setValue('auto_enabled', self.panel.auto.isChecked())
        self.settings.setValue('pins_enabled', self.panel.pins.isChecked())
        self.settings.setValue('topic_id', self.panel.topic.currentData() or '')
        self._apply_mode()

    def _apply_mode(self, first=False):
        mode = self.panel.mode.currentData()
        enabled = self.panel.auto.isChecked()
        skill_active = mode in ('auto','skill')
        rogue_active = mode in ('auto','rogue')
        self.pins_enabled = self.panel.pins.isChecked()
        if not self.pins_enabled or not skill_active:
            self.clear_skill_pin()
            self.circle.details.hide()
        if not self.pins_enabled or not rogue_active:
            self.rogue.hide_pins_btn.setChecked(True)
        else:
            self.rogue.hide_pins_btn.setChecked(False)
        self.rogue.topic.blockSignals(True)
        topic_index = self.rogue.topic.findData(self.panel.topic.currentData())
        if topic_index >= 0 and topic_index != self.rogue.topic.currentIndex():
            self.rogue.topic.setCurrentIndex(topic_index)
            self.rogue.clear_pins()
        self.rogue.topic.blockSignals(False)
        # Keep loaded models resident; toggle timers rather than killing workers.
        self.skill.auto_box.setChecked(bool(enabled and skill_active))
        self.rogue.auto.setChecked(bool(enabled and rogue_active))
        # Start a scan once models report ready (QTimers alone may wait for next interval).
        if first:
            QTimer.singleShot(1600, self.scan_once)

    def scan_once(self):
        mode = self.panel.mode.currentData()
        if mode in ('auto','skill'):
            self.skill.scan(True)
        if mode in ('auto','rogue') and self.rogue.ready and not self.rogue.busy:
            self.rogue.scan()

    def refresh_status(self):
        self.panel.status.setText(
            f'技能 OCR：{"就緒" if self.skill.ready else "載入中"}　'
            f'集成戰略 OCR：{"就緒" if self.rogue.ready else "載入中"}\n'
            f'自動辨識：{"開" if self.panel.auto.isChecked() else "關"}　'
            f'提示：{"顯示" if self.pins_enabled else "隱藏"}'
        )

    @staticmethod
    def _kill(proc):
        if proc.state() != proc.ProcessState.NotRunning:
            proc.blockSignals(True)
            proc.kill()
            proc.waitForFinished(350)
            proc.blockSignals(False)

    def cleanup(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        self._status_timer.stop()
        self.clear_skill_pin()
        self.circle.details.hide()
        self.circle.timer.stop()
        self.skill.timer.stop()
        self.rogue.timer.stop()
        self.rogue.clear_pins()
        self._kill(self.skill.proc)
        self._kill(self.rogue.proc)
        if self.rogue._popup:
            self.rogue._popup.hide()
        self.settings.sync()

    def shutdown(self):
        self.cleanup()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = Controller(app)
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
