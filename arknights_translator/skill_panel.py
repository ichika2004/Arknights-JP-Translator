"""Skill database browser UI (standalone, no OCR initialization)."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QComboBox, QTextEdit, QSplitter, QMessageBox,
)

from .skill_renderer import render_description


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "generated" / "skill_database.json"
SP_TYPES = {
    "INCREASE_WITH_TIME": "自動回復",
    "INCREASE_WHEN_ATTACK": "攻擊回復",
    "INCREASE_WHEN_TAKEN_DAMAGE": "受擊回復",
    "NO_INCREASE": "不自動回復",
}


def clean(value) -> str:
    return str(value).strip() if value is not None else ""


class SkillPanel(QWidget):
    def __init__(self, db_path: Path = DEFAULT_DB):
        super().__init__()
        self.setWindowTitle("Arknights JP Translator — 技能資料查詢 (Phase 2)")
        self.resize(1000, 680)
        self.db_path = Path(db_path)
        data = json.loads(self.db_path.read_text(encoding="utf-8-sig"))
        self.characters = data["characters"]
        names_path = self.db_path.parent / "character_names.json"
        self.name_db = json.loads(names_path.read_text(encoding="utf-8-sig")) if names_path.exists() else {}
        self.current_character = None
        self.current_skill = None

        root = QVBoxLayout(self)
        note = QLabel("資料來源：日服數值／繁中候選描述。尚未逐項核對版本與翻譯，請勿視為已驗證內容。")
        note.setWordWrap(True)
        root.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋日文、英文、繁中名稱或角色 ID（例：エクシア）")
        self.search.textChanged.connect(self.update_search)
        left_layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.currentItemChanged.connect(self.select_character)
        left_layout.addWidget(self.results)
        self.match_label = QLabel("")
        left_layout.addWidget(self.match_label)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.heading = QLabel("請從左側選擇角色")
        self.heading.setWordWrap(True)
        self.heading.setStyleSheet("font-size: 19px; font-weight: bold;")
        right_layout.addWidget(self.heading)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("技能："))
        self.skill_combo = QComboBox()
        self.skill_combo.currentIndexChanged.connect(self.select_skill)
        selector.addWidget(self.skill_combo, 2)
        selector.addWidget(QLabel("等級："))
        self.level_combo = QComboBox()
        self.level_combo.currentIndexChanged.connect(self.show_level)
        selector.addWidget(self.level_combo, 1)
        right_layout.addLayout(selector)

        self.skill_name = QLabel("")
        self.skill_name.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.skill_name.setWordWrap(True)
        right_layout.addWidget(self.skill_name)
        self.stats = QLabel("")
        self.stats.setWordWrap(True)
        right_layout.addWidget(self.stats)
        self.description = QTextEdit()
        self.description.setReadOnly(True)
        right_layout.addWidget(self.description, 1)
        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        right_layout.addWidget(self.notice)
        splitter.addWidget(right)
        splitter.setSizes([330, 670])
        self.update_search()

    def update_search(self):
        query = self.search.text().strip().casefold()
        matches = []
        for cid, character in self.characters.items():
            fields = [cid, clean(character.get("name_jp")), clean(character.get("name_zh_tw") or character.get("name_zh_tw_candidate")), clean((self.name_db.get(cid) or {}).get("name_en")), clean((self.name_db.get(cid) or {}).get("name_zh_tw"))]
            if not query or any(query in field.casefold() for field in fields):
                matches.append((cid, character))
        matches.sort(key=lambda pair: (query not in clean(pair[1].get("name_jp")).casefold(), clean(pair[1].get("name_jp"))))
        self.results.blockSignals(True)
        self.results.clear()
        for cid, character in matches[:300]:
            jp = clean(character.get("name_jp")) or cid
            tw = clean(character.get("name_zh_tw") or character.get("name_zh_tw_candidate"))
            en = clean((self.name_db.get(cid) or {}).get("name_en"))
            label = " / ".join(x for x in (jp, en, tw) if x) + f"  [{cid}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setToolTip(cid)
            self.results.addItem(item)
        self.results.blockSignals(False)
        self.match_label.setText(f"符合 {len(matches)} 位（顯示前 {min(len(matches), 300)} 位）")
        if self.results.count():
            self.results.setCurrentRow(0)
            self.select_character(self.results.currentItem(), None)
        else:
            self.current_character = None
            self.heading.setText("找不到角色")
            self.skill_combo.clear()
            self.description.clear()
            self.skill_name.clear()
            self.stats.clear()
            self.notice.clear()

    def select_character(self, current, previous):
        if current is None:
            return
        cid = current.data(Qt.ItemDataRole.UserRole)
        character = self.characters.get(cid)
        if character is None:
            return
        self.current_character = character
        jp = clean(character.get("name_jp"))
        tw = clean(character.get("name_zh_tw") or character.get("name_zh_tw_candidate")) or "繁中名稱未匹配"
        self.heading.setText(f"{jp}  /  {tw}\n{cid}")
        self.skill_combo.blockSignals(True)
        self.skill_combo.clear()
        for skill in character.get("skills", []):
            levels = skill.get("levels") or []
            name = clean(levels[-1].get("name_zh_tw_candidate")) if levels else ""
            self.skill_combo.addItem(f"技能 {skill.get('slot', '?')}  {name or skill.get('skill_id', '')}", skill)
        self.skill_combo.blockSignals(False)
        self.select_skill(0)

    def select_skill(self, index):
        if index < 0:
            return
        self.current_skill = self.skill_combo.itemData(index)
        if not self.current_skill:
            return
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        levels = self.current_skill.get("levels") or []
        for level in levels:
            level_number = int(level.get("level") or 0)
            label = f"等級 {level_number}" if level_number <= 7 else f"專精 {level_number - 7}"
            self.level_combo.addItem(label, level)
        self.level_combo.blockSignals(False)
        if levels:
            self.level_combo.setCurrentIndex(len(levels) - 1)
            self.show_level(len(levels) - 1)
        else:
            self.skill_name.setText("無技能等級資料")
            self.description.clear()

    def show_level(self, index):
        if index < 0 or self.current_skill is None:
            return
        level = self.level_combo.itemData(index)
        if not isinstance(level, dict):
            return
        name = clean(level.get("name_zh_tw_candidate")) or clean(level.get("name_jp"))
        self.skill_name.setText(name)
        sp = level.get("sp_data_jp") or {}
        duration = level.get("duration_jp")
        sp_type = SP_TYPES.get(sp.get("spType"), clean(sp.get("spType")) or "未知")
        duration_text = "彈藥／特殊持續時間" if duration == -1 else (f"{duration:g} 秒" if isinstance(duration, (int, float)) and duration > 0 else "瞬發／被動／未指定")
        self.stats.setText(
            f"回復：{sp_type}  |  初始 SP：{sp.get('initSp', '—')}  |  消耗 SP：{sp.get('spCost', '—')}  |  持續：{duration_text}"
        )
        raw = clean(level.get("description_zh_tw_candidate_raw"))
        if not raw:
            self.description.setPlainText("尚無繁中候選描述。\n\n日文原文：\n" + clean(level.get("description_jp_raw")))
            self.notice.setText("缺少中文對照：請勿直接當作已翻譯。")
            return
        rendered, missing = render_description(raw, level.get("blackboard_jp") or [])
        self.description.setPlainText(rendered)
        warnings = ["繁中內容尚未校對；技能數值採日服 blackboard，需確認兩服佔位符語義一致。"]
        if missing:
            warnings.append("未解析參數：" + ", ".join(missing))
        source = clean(level.get("translation_source"))
        if source.startswith("cn_opencc"):
            warnings.append("翻譯來源：陸服簡體中文轉繁體（未校對）。")
        elif source.startswith("tw"):
            warnings.append("翻譯來源：台服繁體中文候選（未校對）。")
        elif source.startswith("jp"):
            warnings.append("翻譯來源：日服原文備援，尚未有中文對照。")
        elif source:
            warnings.append("翻譯來源：" + source + "（請確認版本與內容）。")
        else:
            warnings.append("翻譯來源尚未標記，請確認內容。")
        self.notice.setText("\n".join(warnings))
