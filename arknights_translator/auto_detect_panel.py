"""Automatic on-screen character name detection GUI, Phase 11."""
from __future__ import annotations
import json
import time
import sys
import tempfile
from pathlib import Path

import cv2
import mss
import numpy as np
from PySide6.QtCore import QProcess,QTimer
from PySide6.QtWidgets import QHBoxLayout,QLabel,QPushButton,QCheckBox,QComboBox
from .skill_panel import SkillPanel,DEFAULT_DB

class AutoDetectPanel(SkillPanel):
    def __init__(self,db_path=DEFAULT_DB):
        super().__init__(db_path)
        self.setWindowTitle('Arknights JP Translator — 自動辨識控制台')
        self.proc=QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self.read_stdout)
        self.proc.readyReadStandardError.connect(self.read_stderr)
        self.proc.finished.connect(self.on_exit)
        self.ready=False
        self.busy=False
        self.seq=0
        self.pending=None
        self.detected_skill_slot=None
        self.detected_skill_text=''
        self.skill_detection_label=QLabel('目前顯示技能：尚未判定')
        self.buffer=''
        self.previous_preview=None
        self.capture_file=Path(tempfile.gettempdir())/f'arknights_phase11_{id(self)}.png'
        bar=QHBoxLayout()
        self.scene_box=QComboBox()
        self.scene_box.addItem('幹員資訊畫面','operator')
        self.scene_box.addItem('關卡選取畫面','battle')
        self.scene_box.addItem('自動候選（實驗）','auto')
        self.scene_box.currentIndexChanged.connect(self.reset_tracking)
        bar.addWidget(self.scene_box)
        self.scan_button=QPushButton('辨識一次')
        self.scan_button.clicked.connect(lambda:self.scan(True))
        bar.addWidget(self.scan_button)
        self.auto_box=QCheckBox('每 3 秒自動檢查')
        self.auto_box.toggled.connect(self.toggle)
        bar.addWidget(self.auto_box)
        self.restart_button=QPushButton('重啟 OCR')
        self.restart_button.clicked.connect(self.start_worker)
        bar.addWidget(self.restart_button)
        self.layout().insertLayout(1,bar)
        self.status=QLabel('OCR 尚未初始化')
        self.status.setWordWrap(True)
        self.layout().insertWidget(2,self.status)
        self.layout().insertWidget(3,self.skill_detection_label)
        self.timer=QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(lambda:self.scan(False))
        self.start_worker()

    def reset_tracking(self,*_):
        self.previous_preview=None

    def start_worker(self):
        self.timer.stop()
        self.ready=False
        self.busy=False
        self.buffer=''
        self.pending=None
        self.detected_skill_slot=None
        self.detected_skill_text=''
        self.skill_detection_label.setText('目前顯示技能：尚未判定')
        self.reset_tracking()
        if self.proc.state()!=QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(1500)
        self.status.setText('初始化文字偵測與辨識模型…')
        self.proc.start(sys.executable,['-u','-m','arknights_translator.auto_detection_worker'])

    def toggle(self,enabled):
        if enabled and self.ready:
            self.timer.start()
            self.scan(True)
        else:
            self.timer.stop()

    def capture_screen(self):
        # Primary display only, actual physical pixels; don't capture overlay app if visible over game.
        with mss.mss() as sct:
            display=sct.monitors[1]
            shot=np.asarray(sct.grab(display))
        return np.ascontiguousarray(shot[:,:,:3])

    def scan(self,force=False):
        if not self.ready or self.busy:
            return
        try:
            frame=self.capture_screen()
            thumb=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(96,54),interpolation=cv2.INTER_AREA)
            if not force and self.previous_preview is not None:
                diff=float(np.mean(cv2.absdiff(thumb,self.previous_preview)))
                if diff<3.0:
                    return
            self.previous_preview=thumb
            success,buffer=cv2.imencode('.png',frame)
            if not success:
                raise RuntimeError('PNG encode failed')
            buffer.tofile(str(self.capture_file))
            self.seq+=1
            self.pending=self.seq
            req={'id':self.seq,'image_path':str(self.capture_file),'scene':self.scene_box.currentData()}
            self.busy=True
            self.proc.write((json.dumps(req,ensure_ascii=True)+'\n').encode('ascii'))
            self.status.setText('偵測文字框並辨識名稱…')
        except Exception as exc:
            self.busy=False
            self.status.setText('擷取失敗：'+str(exc))

    def read_stdout(self):
        self.buffer+=bytes(self.proc.readAllStandardOutput()).decode('utf-8','replace')
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            if not line.startswith('OCR_JSON='):
                continue
            try:
                data=json.loads(line[len('OCR_JSON='):])
            except ValueError:
                continue
            if data.get('ready'):
                self.ready=True
                self.status.setText(f'模型就緒，載入 {data.get("init_seconds")} 秒；可開始自動偵測。')
                if self.auto_box.isChecked():
                    self.timer.start()
                continue
            if data.get('id')!=self.pending:
                if 'error' in data and not self.ready:
                    self.status.setText('模型載入失敗：'+str(data['error']))
                continue
            self.busy=False
            if 'error' in data:
                self.status.setText('辨識失敗：'+str(data['error']))
                return
            cid=data.get('character_id')
            candidates=data.get('candidates') or []
            duration=float(data.get('detection_seconds',0))+float(data.get('recognition_seconds',0))
            if not cid or cid not in self.characters:
                self.reset_tracking()
                preview=', '.join(str(c.get('ocr_text','')) for c in candidates[:3])
                self.status.setText(f'未確認角色；候選：{preview or "無"}；耗時 {duration:.2f}s')
                return
            # Valid and unambiguous name match: update immediately.
            # The worker already rejects weak/ambiguous results.
            self.status.setText(f'已辨識：{data.get("ocr_text")!r} → {cid}；耗時 {duration:.2f}s')
            changed=self.search.text()!=cid
            if changed:
                self.search.setText(cid)
                self.detected_skill_slot=None
                self.detected_skill_text=''
            skill=data.get('skill_detection')
            if skill and skill.get('slot'):
                slot=int(skill['slot'])
                idx=next((i for i in range(self.skill_combo.count())
                          if int((self.skill_combo.itemData(i) or {}).get('slot') or i+1)==slot),None)
                if idx is not None:
                    self.detected_skill_slot=slot
                    self.detected_skill_text=skill.get('text','')
                    if time.monotonic()>=getattr(self,'manual_skill_until',0):
                        self.skill_combo.setCurrentIndex(idx)
                    self.skill_detection_label.setText(f'畫面顯示：技能 {slot}（{self.detected_skill_text}）')
            else:
                self.skill_detection_label.setText('畫面中未能明確辨識技能；保留目前選擇')

    def read_stderr(self):
        msg=bytes(self.proc.readAllStandardError()).decode('utf-8','replace')
        if msg:
            print('[Paddle]',msg[-1500:],file=sys.stderr)

    def on_exit(self,code,status):
        self.ready=False
        self.busy=False
        self.timer.stop()
        if self.isVisible():
            self.status.setText(f'OCR 子程序結束（exit={code}），請重啟。')

    def closeEvent(self,event):
        self.timer.stop()
        if self.proc.state()!=QProcess.ProcessState.NotRunning:
            self.proc.closeWriteChannel()
            if not self.proc.waitForFinished(1000):
                self.proc.kill()
                self.proc.waitForFinished(2000)
        super().closeEvent(event)
