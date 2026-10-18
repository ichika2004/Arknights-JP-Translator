"""Phase 23.7: reliable shutdown for the unified operator panel.

Keeps the Phase 23.6 UI; only fixes shutdown signal wiring and cleanup.
"""
from __future__ import annotations
import sys

if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton
import arknights_translator.app_layers.operator_panel as previous


class Controller(previous.Controller):
    def __init__(self, app):
        self._exit_requested = False
        self._exit_cleaned = False
        super().__init__(app)
        # Every application launch defaults to showing translation pins.
        # A previous QSettings value (or old migration flag) must not leave
        # the checkbox unchecked. Users can still toggle it during this run.
        self.panel.pins.blockSignals(True)
        self.panel.pins.setChecked(True)
        self.panel.pins.blockSignals(False)
        self.pins_enabled = True
        self.settings.setValue('pins_enabled', True)
        self.settings.sync()
        # Also synchronize the pin visibility in the two overlaid viewers.
        self._apply_mode()
        # The legacy SkillDetails button called QApplication.quit directly.
        # It must go through the same path as the settings' Exit button.
        for button in self.circle.details.findChildren(QPushButton):
            if button.text().strip() == '結束程式':
                try:
                    button.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass
                button.clicked.connect(self.shutdown)
        # aboutToQuit was connected to the overridden cleanup during base init.

    def _stop_process(self, proc):
        if proc is None:
            return
        try:
            if proc.state() == proc.ProcessState.NotRunning:
                return
            proc.blockSignals(True)
            proc.terminate()
            if not proc.waitForFinished(250):
                proc.kill()
                proc.waitForFinished(600)
        except RuntimeError:
            # Wrapped Qt object already destroyed while exiting.
            pass
        finally:
            try:
                proc.blockSignals(False)
            except RuntimeError:
                pass

    def cleanup(self):
        if self._exit_cleaned:
            return
        self._exit_cleaned = True
        self.shutting_down = True
        # Invalidate pending OCR responses immediately.
        self._generation = getattr(self, '_generation', 0) + 1
        self._accept_skill = False
        try:
            self.rogue.accept_results = False
        except (RuntimeError, AttributeError):
            pass
        try:
            if hasattr(self, 'toolbar'):
                self.settings.setValue('phase23_toolbar_position', self.toolbar.pos())
            if hasattr(self, '_rogue_enabled'):
                self.settings.setValue('phase23_2/rogue_enabled', bool(self._rogue_enabled))
        except RuntimeError:
            pass
        for timer in (getattr(self, '_manual_timer', None),
                      getattr(self, '_stagger_timer', None),
                      getattr(self, '_status_timer', None),
                      getattr(getattr(self, 'skill', None), 'timer', None),
                      getattr(getattr(self, 'rogue', None), 'timer', None),
                      getattr(getattr(self, 'circle', None), 'timer', None)):
            try:
                if timer is not None:
                    timer.stop()
            except RuntimeError:
                pass
        for name in ('skill', 'rogue'):
            obj = getattr(self, name, None)
            if obj is not None:
                self._stop_process(getattr(obj, 'proc', None))
        for window in (getattr(self, 'skill_pin', None),
                       getattr(getattr(self, 'circle', None), 'details', None),
                       getattr(getattr(self, 'rogue', None), '_popup', None),
                       getattr(self, 'panel', None),
                       getattr(self, 'toolbar', None),
                       getattr(self, 'circle', None)):
            try:
                if window is not None:
                    window.hide()
            except RuntimeError:
                pass
        try:
            self.rogue.clear_pins()
        except (RuntimeError, AttributeError):
            pass
        try:
            self.settings.sync()
        except RuntimeError:
            pass

    def shutdown(self):
        if self._exit_requested:
            return
        self._exit_requested = True
        try:
            self.cleanup()
        finally:
            # Finish after the current button-click signal stack unwinds.
            QTimer.singleShot(0, self.app.quit)


previous.p233.old.p231.base.Controller = Controller
if __name__ == '__main__':
    raise SystemExit(previous.p233.old.p231.base.main())
