"""Phase 17 prototype: independent roguelike OCR viewer (does not change skill UI)."""
from __future__ import annotations
import json,sys,tempfile,unicodedata,re,ctypes
from pathlib import Path
from arknights_translator.rogue_layout_engine import analyze

from PySide6.QtCore import Qt,QProcess,QTimer
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QCheckBox,QPlainTextEdit
import mss,numpy as np,cv2

TOPICS={'rogue_1':'傀影與猩紅孤鑽','rogue_2':'水月與深藍之樹','rogue_3':'探索者的銀凇止境','rogue_4':'薩卡茲的無終奇語','rogue_5':'歲的界園志異'}

def normalize(s):
    s=unicodedata.normalize('NFKC',str(s or '')).lower()
    return re.sub(r'[\s「」『』“”"\'・·。、，:：!！?？\-—]','',s)

class Viewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Arknights 集成戰略 OCR — Phase 17.4 畫面結構測試')
        self.resize(540,460)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.proc=QProcess(self);self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self.read_out)
        self.proc.readyReadStandardError.connect(self.read_err)
        self.proc.finished.connect(self.finished)
        self.pending=None;self.counter=0;self.ready=False;self.busy=False;self.buffer=''
        self.snapshot=Path(tempfile.gettempdir())/f'arknights_rogue_{id(self)}.png'
        self.records=self.load_records()
        layout=QVBoxLayout(self)
        line=QHBoxLayout();line.addWidget(QLabel('集成戰略主題：'))
        self.topic=QComboBox();self.topic.addItem('尚未指定（防止效果誤判）',None)
        for key,name in TOPICS.items():self.topic.addItem(name,key)
        line.addWidget(self.topic,1)
        layout.addLayout(line)
        layout.addWidget(QLabel('掃描區域：完整螢幕（不裁切任何區域）'))
        self.debug=QCheckBox('顯示原始 OCR 文字（診斷模式）')
        self.debug.setChecked(False)
        layout.addWidget(self.debug)
        self.short=QCheckBox('精簡模式：只顯示名稱及實際效果（不顯示背景故事）')
        self.short.setChecked(True)
        layout.addWidget(self.short)
        self.hud=QCheckBox('略過常駐 HUD 雜訊（耐久值／希望／資金／等級）')
        self.hud.setChecked(True)
        layout.addWidget(self.hud)
        self._capture_excluded=False
        buttons=QHBoxLayout();self.scan_btn=QPushButton('辨識一次');self.scan_btn.clicked.connect(self.scan)
        buttons.addWidget(self.scan_btn)
        self.auto=QCheckBox('每 5 秒自動辨識');buttons.addWidget(self.auto)
        self.restart_btn=QPushButton('重啟 OCR');self.restart_btn.clicked.connect(self.start_worker);buttons.addWidget(self.restart_btn)
        layout.addLayout(buttons)
        self.status=QLabel('尚未啟動 OCR');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.result=QPlainTextEdit();self.result.setReadOnly(True);layout.addWidget(self.result,1)
        self.timer=QTimer(self);self.timer.setInterval(5000);self.timer.timeout.connect(self.scan)
        self.auto.toggled.connect(lambda checked:self.timer.start() if checked else self.timer.stop())
        self.start_worker()

    def showEvent(self,event):
        super().showEvent(event)
        if sys.platform=='win32' and not self._capture_excluded:
            try:
                import ctypes.wintypes
                fn=ctypes.WinDLL('user32',use_last_error=True).SetWindowDisplayAffinity
                fn.argtypes=(ctypes.wintypes.HWND,ctypes.wintypes.DWORD)
                fn.restype=ctypes.wintypes.BOOL
                self._capture_excluded=bool(fn(int(self.winId()),0x11))
                print('[Phase17.1] Exclude OCR GUI from capture:',self._capture_excluded,flush=True)
            except Exception as exc:
                print('[Phase17.1] Capture exclusion unavailable:',exc,flush=True)

    def load_records(self):
        path=Path(__file__).resolve().parent/'data'/'generated'/'rogue_unified_index.json'
        if not path.exists():
            raise FileNotFoundError(f'缺少統一索引：{path}\n請先執行 python -m scripts.build_rogue_unified_index')
        return json.loads(path.read_text(encoding='utf-8-sig'))

    def start_worker(self):
        self.ready=False;self.busy=False;self.pending=None;self.buffer='';self.timer.stop()
        self.auto.setChecked(False)
        if self.proc.state()!=QProcess.ProcessState.NotRunning:
            self.proc.kill();self.proc.waitForFinished(2000)
        self.status.setText('初始化 OCR 模型中…')
        if getattr(sys,'frozen',False):self.proc.start(sys.executable,['--rogue-worker'])
        else:self.proc.start(sys.executable,['-u','-m','arknights_translator.rogue_ocr_worker'])

    def scan(self):
        if not self.ready or self.busy:return
        self.busy=True
        if not self._capture_excluded and self.isVisible():
            self.hide()
            QTimer.singleShot(220,self._capture_and_send)
        else:
            self._capture_and_send()

    def _capture_and_send(self):
        try:
            with mss.mss() as sct:
                frame=np.ascontiguousarray(np.asarray(sct.grab(sct.monitors[1]))[:,:,:3])
            # Scan every pixel of the selected primary monitor. No fixed ROI.
            ok,buf=cv2.imencode('.png',frame)
            if not ok:raise RuntimeError('PNG encoding error')
            buf.tofile(str(self.snapshot))
            self.counter+=1;self.pending=self.counter
            req={'id':self.counter,'image_path':str(self.snapshot)}
            self.proc.write((json.dumps(req)+'\n').encode('utf-8'))
            self.status.setText('OCR 辨識中…')
        except Exception as e:self.busy=False;self.status.setText('擷取失敗：'+repr(e))
        finally:
            if not self.isVisible():self.show()

    def process(self,lines,elapsed):
        report=analyze(lines,self.records,topic=self.topic.currentData(), suppress_hud=self.hud.isChecked())
        out=[]
        label={'item':'物品／收藏品','choice':'事件選項','scene':'事件場景'}
        for i,card in enumerate(report['cards'],1):
            if card['status'] != 'matched' and not self.debug.isChecked():
                continue
            out.append('─'*28)
            if card['status']=='matched':
                out.append(f"{i}. {label.get(card['category'],card['category'])}｜{card['title_tw'] or '未提供繁中名稱'}")
                if card['description_tw']:
                    out.append('效果：'+card['description_tw'])
                if card['locked_tw']:
                    out.append('條件：'+card['locked_tw'])
                if not self.short.isChecked():
                    out.append('原文：'+card['ocr_text'])
                    if card.get('flavor_tw'):
                        out.append('背景：'+card['flavor_tw'])
                    if card['nearby_ocr']:
                        out.append('附近 OCR（未驗證關聯）：'+ ' / '.join(card['nearby_ocr']))
            else:
                out.append(f"{i}. 待確認：{card['ocr_text']}")
                for row in card['alternatives'][:3]:
                    out.append(f"  {TOPICS.get(row['topic_id'],row['topic_id'])}｜{row['title_tw']}")
        if not report['cards']:
            out.append('找不到足夠可靠的資料庫名稱匹配。可開啟原始 OCR 檢查，或更換遊戲畫面再試。')
        if self.debug.isChecked():
            out.extend(['','=== 全螢幕 OCR 原始文字 ==='])
            out.extend(f"{i:02d}. [{line.get('confidence',0):.2f}] {line.get('text','')}" for i,line in enumerate(lines,1))
        self.result.setPlainText('\n'.join(out))
        matched=sum(c['status']=='matched' for c in report['cards'])
        ambiguous=sum(c['status']=='ambiguous' for c in report['cards'])
        self.status.setText(f'OCR {len(lines)} 框｜確認 {matched}｜歧義 {ambiguous}｜{elapsed:.1f}s（附近文字不代表選項已配對）')

    def read_out(self):
        self.buffer+=bytes(self.proc.readAllStandardOutput()).decode('utf-8','replace')
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            if not line.startswith('OCR_JSON='):continue
            try:d=json.loads(line[9:])
            except ValueError:continue
            if d.get('ready'):
                self.ready=True;self.status.setText(f'OCR 就緒（{d.get("init_seconds")} 秒）')
            elif d.get('id')==self.pending:
                self.busy=False
                if 'error' in d:self.status.setText('OCR 錯誤：'+str(d['error']))
                else:self.process(d.get('lines') or [],float(d.get('seconds') or 0))
            elif 'error' in d and not self.ready:self.status.setText('初始化失敗：'+str(d['error']))

    def read_err(self):
        content=bytes(self.proc.readAllStandardError()).decode('utf-8','replace')
        if content:print('[Rogue OCR]',content[-1000:],file=sys.stderr,flush=True)

    def finished(self,code,status):
        self.ready=False;self.busy=False;self.timer.stop();self.auto.setChecked(False)
        self.status.setText(f'OCR 子程序已結束 (exit={code})')

    def closeEvent(self,event):
        self.timer.stop()
        if self.proc.state()!=QProcess.ProcessState.NotRunning:
            self.proc.closeWriteChannel()
            if not self.proc.waitForFinished(1200):self.proc.kill();self.proc.waitForFinished(1500)
        super().closeEvent(event)

def main():
    app=QApplication(sys.argv);ui=Viewer();ui.show();return app.exec()

if __name__=='__main__':
    if '--rogue-worker' in sys.argv:
        from arknights_translator.rogue_ocr_worker import main as worker_main
        raise SystemExit(worker_main())
    raise SystemExit(main())
