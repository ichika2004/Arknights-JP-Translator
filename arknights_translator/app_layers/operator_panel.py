"""Phase 23.6: one unified, draggable operator skill/module panel.
Keeps Phase 23.3 manual scan toolbar, circular app icon and rogue toggle.
"""
from __future__ import annotations
import sys
if '--ocr-worker' in sys.argv or '--rogue-worker' in sys.argv:
    from arknights_translator.app_layers.base_ui import main
    raise SystemExit(main())

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton, QLabel
from PySide6.QtCore import Qt
from arknights_translator.module_details import ModuleDetails
import arknights_translator.app_layers.floating_toolbar as p233


class Controller(p233.Controller):
    def __init__(self, app):
        super().__init__(app)
        details = self.circle.details
        layout = details.body.layout()
        # Keep the existing header (operator name/close/exit) and footer
        # (size grip). Move all old skill content, including its layouts,
        # into a tab page; existing widgets and signals remain intact.
        skill_page = QWidget(details.body)
        skill_layout = QVBoxLayout(skill_page)
        skill_layout.setContentsMargins(2, 0, 2, 0)
        while layout.count() > 2:
            item = layout.takeAt(1)
            if item.widget():
                widget = item.widget()
                widget.setParent(skill_page)
                skill_layout.addWidget(widget)
            elif item.layout():
                skill_layout.addLayout(item.layout())
            elif item.spacerItem():
                skill_layout.addItem(item.spacerItem())
        self._operator_stack = QStackedWidget(details.body)
        self._operator_stack.addWidget(skill_page)
        # Create an embedded version instead of a second top-level dialog.
        previous_dialog = self.module_dialog
        previous_dialog.hide()
        previous_dialog.deleteLater()
        self.module_dialog = ModuleDetails(details.body, embedded=True)
        self._operator_stack.addWidget(self.module_dialog)
        tab_row = QHBoxLayout()
        self._skills_tab = QPushButton('技能')
        self._modules_tab = QPushButton('模組／特性')
        for button in (self._skills_tab, self._modules_tab):
            button.setCheckable(True)
            tab_row.addWidget(button)
        self._skills_tab.clicked.connect(lambda: self._set_operator_tab(0))
        self._modules_tab.clicked.connect(lambda: self._set_operator_tab(1))
        # Remove Phase 23.1's standalone dialog trigger, now redundant.
        self.module_button.hide()
        self.module_button.deleteLater()
        layout.insertLayout(1, tab_row)
        layout.insertWidget(2, self._operator_stack, 1)
        self._module_last_character = None
        self._set_operator_tab(0)
        details.resize(max(600, details.width()), max(530, details.height()))

    def _set_operator_tab(self, tab: int):
        self._operator_stack.setCurrentIndex(tab)
        self._skills_tab.setChecked(tab == 0)
        self._modules_tab.setChecked(tab == 1)
        if tab == 1:
            cid = self.skill.search.text().strip()
            if cid:
                if self._module_last_character != cid:
                    self.module_dialog.show_character(cid)
                    self._module_last_character = cid
            else:
                self.module_dialog.header.setText('尚未辨識到幹員，請先按「掃描」。')

    def open_modules(self):
        # Preserve the old API and redirect all triggers to the same panel.
        self._set_operator_tab(1)
        if not self.circle.details.isVisible():
            self.circle.details.show()

    def on_character_bbox(self, cid, bbox, confidence):
        previous = getattr(self, '_module_last_character', None)
        result = super().on_character_bbox(cid, bbox, confidence)
        if cid != previous:
            self._module_last_character = None
            if self._operator_stack.currentIndex() == 1 and cid:
                self.module_dialog.show_character(cid)
                self._module_last_character = cid
        return result


p233.old.p231.base.Controller = Controller
if __name__ == '__main__':
    raise SystemExit(p233.old.p231.base.main())
