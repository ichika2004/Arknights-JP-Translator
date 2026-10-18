"""Phase 22.4: cached context matching and staggered OCR scans."""
from __future__ import annotations
import sys
if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtCore import QTimer
import arknights_translator.app_layers.base_ui as base
from arknights_translator.rogue_context_fast import CachedContextMatcher
from arknights_translator.rogue_context_cards import merge_cards

class FasterRogueViewer(base.OverlayViewer):
    def __init__(self):
        self.matcher=CachedContextMatcher()
        super().__init__()
        print('[Phase22.4] Cached squad names:',len(self.matcher.squad_names),flush=True)

    def process(self,lines,elapsed):
        from arknights_translator import rogue_layout_engine as engine
        original=engine.analyze
        def extended(raw,records,*args,**kwargs):
            report=original(raw,records,*args,**kwargs)
            cards=self.matcher.match(raw,records,topic=kwargs.get('topic'))
            return merge_cards(report,cards)
        engine.analyze=extended
        try:return super().process(lines,elapsed)
        finally:engine.analyze=original

base.OverlayViewer=FasterRogueViewer

class FasterController(base.Controller):
    def __init__(self,app):
        self._stagger_timer=None
        self._scan_next='rogue'
        super().__init__(app)
        self._stagger_timer=QTimer(self.panel)
        self._stagger_timer.setInterval(2800)
        self._stagger_timer.timeout.connect(self._scan_staggered)
        self._apply_mode()

    def _apply_mode(self, first=False):
        super()._apply_mode(first)
        # Disable independent periodic scans: two Paddle OCR processes should
        # not run inference simultaneously on the same CPU.
        self.skill.timer.stop()
        self.rogue.timer.stop()
        if self._stagger_timer:
            if self.panel.auto.isChecked():self._stagger_timer.start()
            else:self._stagger_timer.stop()

    def _scan_staggered(self):
        if self.shutting_down or not self.panel.auto.isChecked():return
        mode=self.panel.mode.currentData()
        if mode=='skill':
            if self.skill.ready and not self.skill.busy:self.skill.scan(True)
            return
        if mode=='rogue':
            if self.rogue.ready and not self.rogue.busy:self.rogue.scan()
            return
        # Strictly sequential: never request a new screenshot while either OCR
        # process is doing inference. Worker processes stay resident.
        if self.skill.busy or self.rogue.busy:return
        if self._scan_next=='rogue':
            if self.rogue.ready:
                self.rogue.scan()
                self._scan_next='skill'
            elif self.skill.ready:self.skill.scan(True)
        else:
            if self.skill.ready:
                self.skill.scan(True)
                self._scan_next='rogue'
            elif self.rogue.ready:self.rogue.scan()

    def scan_once(self):
        if not hasattr(self,'skill') or not hasattr(self,'rogue'):return
        if self.skill.busy or self.rogue.busy:return
        if self.panel.auto.isChecked() and self._stagger_timer:
            self._scan_staggered()
        else:
            mode=self.panel.mode.currentData()
            if mode in ('auto','rogue') and self.rogue.ready:self.rogue.scan()
            elif mode in ('auto','skill') and self.skill.ready:self.skill.scan(True)

    def cleanup(self):
        if self._stagger_timer:self._stagger_timer.stop()
        super().cleanup()

base.Controller=FasterController

if __name__=='__main__':
    raise SystemExit(base.main())
