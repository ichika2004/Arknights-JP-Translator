"""Phase 23.4: choose a module before choosing its phase; independent collapsed story.
Compatible with the Phase 23.3 generated operator_modules.json.
"""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QTextEdit, QPushButton, QScrollArea,
                               QWidget, QFrame)
ROOT = Path(__file__).resolve().parents[1]

try:
    from opencc import OpenCC
    _s2t = OpenCC('s2twp')
except ImportError:
    _s2t = None

def localized(tw, cn, jp='', *, label=False):
    """Return display text, source: tw, cn, or jp. Never call converted CN official TW."""
    if tw:return (str(tw),'tw')
    if cn:
        value = _s2t.convert(str(cn)) if _s2t else str(cn)
        return (value,'cn_converted' if _s2t else 'cn')
    if jp:return (str(jp),'jp')
    return ('','missing')

def source_label(src):
    return {'tw':'', 'cn_converted':'〔簡中轉繁，非官方繁中〕',
            'cn':'〔簡中原文，非官方繁中〕','jp':'〔日文原文〕', 'missing':''}.get(src,'')

def display_list(tw,cn,jp):
    data=tw or cn or jp or []
    src='tw' if tw else ('cn' if cn else 'jp')
    if src=='cn' and _s2t:
        data=[_s2t.convert(str(x)) for x in data]
        src='cn_converted'
    return data,src



class ModuleDetails(QDialog):
    def __init__(self, parent=None, embedded=False):
        super().__init__(parent)
        self.embedded = embedded
        self.setWindowTitle('幹員模組：效果與階段')
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(630, 580)
        self.setMinimumSize(420, 350)
        self.database = {}
        self.current_cid = None
        self.setStyleSheet('''
            QDialog { background: #161e2a; color: #f0f4fa; }
            QLabel { color: #eef3fb; }
            QComboBox, QTextEdit { background: #243344; color: #f3f6fa;
                                   border: 1px solid #45566e; border-radius: 6px; padding: 6px; }
            QPushButton { background: #304760; color: white; border: none;
                          border-radius: 7px; padding: 9px 12px; }
            QPushButton:hover { background: #3e6181; }
        ''')
        root = QVBoxLayout(self)
        self.header = QLabel('請先辨識幹員')
        self.header.setWordWrap(True)
        root.addWidget(self.header)
        selector = QHBoxLayout()
        selector.addWidget(QLabel('模組'))
        self.combo = QComboBox()
        selector.addWidget(self.combo, 1)
        root.addLayout(selector)
        stage_row = QHBoxLayout()
        stage_row.addWidget(QLabel('強化階段'))
        self.stage = QComboBox()
        stage_row.addWidget(self.stage, 1)
        root.addLayout(stage_row)
        self.effect_label = QLabel('模組效果')
        self.effect_label.setStyleSheet('font-size: 15px; font-weight: bold;')
        root.addWidget(self.effect_label)
        self.effects = QTextEdit()
        self.effects.setReadOnly(True)
        root.addWidget(self.effects, 1)
        self.story_button = QPushButton('▶ 展開 Story（模組故事）')
        self.story_button.setCheckable(True)
        self.story_button.setChecked(False)
        root.addWidget(self.story_button)
        self.story = QTextEdit()
        self.story.setReadOnly(True)
        self.story.setVisible(False)
        self.story.setMinimumHeight(125)
        root.addWidget(self.story)
        self.story_button.toggled.connect(self._toggle_story)
        self.combo.currentIndexChanged.connect(self._switch_module)
        self.stage.currentIndexChanged.connect(self.refresh)
        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton('關閉')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)
        if embedded:
            close.hide()

    def show_character(self, cid):
        previous = self.combo.currentData() if self.current_cid == cid else None
        self.current_cid = cid
        path = ROOT / 'data' / 'generated' / 'operator_modules.json'
        if path.is_file():
            try:
                self.database = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                self.database = {}
                self.effects.setPlainText(f'模組索引無法讀取：{exc}')
        else:
            self.database = {}
            self.effects.setPlainText('尚無模組資料，請執行 python scripts/build_module_index.py')
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem('ORIGINAL｜未裝備模組', '__original__')
        for mid in self.database.get('by_character', {}).get(cid, []):
            rec = self.database.get('modules', {}).get(mid, {})
            typ,_=localized(rec.get('type_tw'),rec.get('type_cn'),rec.get('type_jp'))
            name,name_src=localized(rec.get('name_tw'),rec.get('name_cn'),rec.get('name_jp'))
            name=(name or mid)+source_label(name_src)
            self.combo.addItem(f'{typ}｜{name}' if typ else name, mid)
        i = self.combo.findData(previous)
        self.combo.setCurrentIndex(i if i >= 0 else (1 if self.combo.count() > 1 else 0))
        self.combo.blockSignals(False)
        notice = '' if self.combo.count()>1 else '｜目前索引無此角色模組，請以 --refresh 更新或確認角色是否已有模組'
        self.header.setText(f'幹員 ID：{cid}｜{self.combo.count()-1} 個模組'+notice)
        self._switch_module()
        if not self.embedded:
            self.show()
            self.raise_()
            self.activateWindow()

    def _module(self):
        return self.database.get('modules', {}).get(self.combo.currentData(), {})

    def _switch_module(self, *_):
        rec = self._module()
        is_original = self.combo.currentData() == '__original__'
        self.stage.blockSignals(True)
        self.stage.clear()
        if not is_original:
            for s in rec.get('stages', []):
                lv = s.get('level')
                if lv is not None:
                    self.stage.addItem(f'Stage {lv}', lv)
        self.stage.setEnabled(not is_original and self.stage.count() > 0)
        self.stage.blockSignals(False)
        # Story belongs to the module, not a stage. Reset only on module change.
        self.story_button.setChecked(False)
        self.story_button.setEnabled(not is_original)
        self.story_button.setVisible(not is_original)
        if not is_original:
            story, src=localized(rec.get('story_tw') or rec.get('description_tw'),
                                  rec.get('story_cn') or rec.get('description_cn'),
                                  rec.get('description_jp'))
            self.story.setPlainText((source_label(src)+'\n'+story).strip() if story else '目前資料沒有可讀的模組敘述。')
        else:self.story.setPlainText('')
        self.refresh()

    def _toggle_story(self, checked):
        self.story.setVisible(checked)
        self.story_button.setText('▼ 收合 Story（模組故事）' if checked else
                                  '▶ 展開 Story（模組故事）')

    def _original_text(self):
        path = ROOT / 'data' / 'generated' / 'operator_traits.json'
        record = {}
        if path.is_file():
            try:
                record = json.loads(path.read_text(encoding='utf-8')).get(self.current_cid, {})
            except (OSError, ValueError, TypeError):
                pass
        lines = ['ORIGINAL｜未裝備模組', '', '【原始特性】']
        lines.append(record.get('trait_tw') or '尚未建置原始特性索引；請執行 python scripts/build_operator_traits.py')
        lines.append('')
        lines.append('【原始天賦】')
        talents = record.get('talents_tw') or []
        lines.extend('• ' + t for t in talents) if talents else lines.append('尚無可確認的原始天賦文字。')
        return '\n'.join(lines)

    def refresh(self, *_):
        mid = self.combo.currentData()
        if mid == '__original__':
            self.effect_label.setText('ORIGINAL｜原始狀態')
            self.effects.setPlainText(
                self._original_text())
            return
        rec = self._module()
        level = self.stage.currentData()
        mod_name,_=localized(rec.get('name_tw'),rec.get('name_cn'),rec.get('name_jp'))
        self.effect_label.setText(f'{mod_name or mid}｜Stage {level or "—"} 效果')
        lines = [f'模組 ID：{mid}']
        if rec.get('translation_status') == 'jp_only':
            lines.append('⚠ 日服模組：目前繁中資料未收錄此模組；以下僅顯示可取得的日文資訊，不會冒充官方繁中翻譯。')
        if rec.get('name_jp'):
            lines.append(f'日文：{rec["name_jp"]}')
        typ,typ_src=localized(rec.get('type_tw'),rec.get('type_cn'),rec.get('type_jp'))
        if typ:lines.append(f'模組類型：{typ} {source_label(typ_src)}')
        lines += ['', '━━ 模組階段效果 ━━']
        selected = next((s for s in rec.get('stages', []) if s.get('level') == level), None)
        if selected:
            attributes=selected.get('attributes_tw') or selected.get('attributes_cn') or selected.get('attributes_jp') or {}
            a_src=('tw' if selected.get('attributes_tw') else ('cn' if selected.get('attributes_cn') else 'jp'))
            traits,t_src=display_list(selected.get('traits_tw'),selected.get('traits_cn'),selected.get('traits_jp'))
            talents,ta_src=display_list(selected.get('talents_tw'),selected.get('talents_cn'),selected.get('talents_jp'))
            effects,e_src=display_list(selected.get('effects_tw'),selected.get('effects_cn'),selected.get('effects_jp'))
            if attributes:
                lines.extend(['【屬性加成】 '+source_label(a_src)]+[f'• {k}：{v:+g}' if isinstance(v,(int,float)) else f'• {k}：{v}' for k,v in attributes.items()])
            if traits:
                lines.extend(['', '【模組後特性】 '+source_label(t_src)]+[f'• {x}' for x in traits])
            else:
                lines.extend(['', '【特性】', '本階段沒有可確認的特性覆寫文字；不代表特性未受影響。'])
            if talents:
                lines.extend(['', '【天賦】 '+source_label(ta_src)]+[f'• {x}' for x in talents])
            extra=[x for x in effects if x not in traits and x not in talents]
            if extra:
                lines.extend(['', '【其他資料描述】 '+source_label(e_src)]+[f'• {x}' for x in extra])
            if not any((attributes,traits,talents,extra)):
                lines += ['本階段沒有可可靠解析的屬性或效果文字。',
                          '可嘗試 python scripts/build_module_index.py --refresh 更新資料。']
        else:
            lines.append('沒有對應階段資料；可使用 --refresh 更新日文與繁中資料。')
        self.effects.setPlainText('\n'.join(lines))
