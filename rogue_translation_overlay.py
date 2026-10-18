"""Phase 18 standalone clickable on-screen translation pins.
Reuses Phase 17.5 viewer, full-screen OCR worker, and unified typed index.
Does not modify the stable skill translator.
"""
from __future__ import annotations
import sys
import cv2
import numpy as np
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QScrollArea
from rogue_translation_viewer import Viewer, TOPICS

FLAGS = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
         Qt.WindowType.WindowStaysOnTopHint)


class DetailPopup(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(380, 250)
        self.frame = QFrame(self)
        self.frame.setObjectName('popup')
        self.frame.setStyleSheet('''QFrame#popup {background-color:rgba(22,29,40,245);border:1px solid #64748b;border-radius:12px}
          QLabel{color:#f8fafc;font-size:14px} QPushButton{background:#334155;color:white;border:0;border-radius:6px;padding:6px}''')
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.addWidget(self.frame)
        inner=QVBoxLayout(self.frame)
        head=QHBoxLayout()
        self.title=QLabel();self.title.setWordWrap(True)
        self.title.setStyleSheet('font-weight:bold;font-size:17px')
        head.addWidget(self.title,1)
        close=QPushButton('×');close.setFixedWidth(32);close.clicked.connect(self.hide)
        head.addWidget(close)
        inner.addLayout(head)
        self.meta=QLabel();self.meta.setWordWrap(True);inner.addWidget(self.meta)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        scroll.setStyleSheet('background:transparent;border:0')
        wrap=QWidget();v=QVBoxLayout(wrap)
        self.description=QLabel();self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.description);v.addStretch()
        scroll.setWidget(wrap);inner.addWidget(scroll,1)

    def open_card(self,card,near):
        self.title.setText(card.get('title_tw') or '未提供翻譯')
        category={'item':'物品／收藏品','choice':'事件選項','scene':'事件場景'}.get(card.get('category'),'翻譯')
        self.meta.setText(f"{TOPICS.get(card.get('topic_id'), '集成戰略')} · {category}")
        sections=[]
        if card.get('description_tw'):sections.append(card['description_tw'])
        if card.get('locked_tw'):sections.append('條件：'+card['locked_tw'])
        if not sections:sections=['此項目沒有額外效果敘述。']
        self.description.setText('\n\n'.join(sections))
        screen=QGuiApplication.screenAt(near) or QGuiApplication.primaryScreen()
        g=screen.availableGeometry()
        x=max(g.left(),min(near.x()+24,g.right()-self.width()+1))
        y=max(g.top(),min(near.y()+18,g.bottom()-self.height()+1))
        self.move(x,y);self.show();self.raise_()


class TranslationPin(QWidget):
    def __init__(self,card,position,callback):
        super().__init__(None)
        self.card=card
        self.setWindowFlags(FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(30,30)
        button=QPushButton('!',self)
        button.setGeometry(1,1,28,28)
        button.setToolTip(f"{card.get('title_tw','翻譯')}（點擊檢視）")
        button.setStyleSheet('''QPushButton{background:#d97706;color:white;border:2px solid #fff4c5;
          border-radius:14px;font-size:17px;font-weight:bold;padding:0}
          QPushButton:hover{background:#f59e0b}''')
        button.clicked.connect(lambda:callback(self.card,self.geometry().center()))
        self.move(position)


class OverlayViewer(Viewer):
    def __init__(self):
        self._pins=[]
        self._popup=None
        self._capture_origin=(0,0)
        self._capture_size=None
        super().__init__()
        self.setWindowTitle('Arknights 集成戰略 — Phase 18 座標翻譯提示')
        self.resize(485,290)
        self._popup=DetailPopup()
        self.result.hide()  # Do not show long debug output unless user chooses console prototype.
        self.short.hide()
        self.hud.setChecked(True)
        self.pin_status=QLabel('尚無翻譯提示；請在遊戲畫面按「辨識一次」。')
        self.pin_status.setWordWrap(True)
        self.layout().addWidget(self.pin_status)
        self.hide_pins_btn=QPushButton('隱藏翻譯提示')
        self.hide_pins_btn.setCheckable(True)
        self.hide_pins_btn.toggled.connect(self.toggle_pins)
        self.layout().addWidget(self.hide_pins_btn)
        self.topic.currentIndexChanged.connect(self.clear_pins)
        self._last_cards=[]
        self._pin_signature=None
        self._empty_scans=0
        self._capture_pin_visibility=[]
        self._capture_popup_visible=False
        self._closing=False
        self._last_image_thumb=None
        self._unchanged_skips=0
        self.exit_button=QPushButton('結束程式 ×')
        self.exit_button.setToolTip('關閉所有翻譯提示並停止 OCR 子程序')
        self.exit_button.clicked.connect(self.close)
        self.layout().addWidget(self.exit_button)

    def toggle_pins(self,hidden):
        self.hide_pins_btn.setText('顯示翻譯提示' if hidden else '隱藏翻譯提示')
        if self._popup:self._popup.hide()
        for pin in self._pins:
            pin.setVisible(not hidden)

    def clear_pins(self,*_):
        self._pin_signature=None
        self._empty_scans=0
        if self._popup:self._popup.hide()
        for pin in self._pins:pin.close();pin.deleteLater()
        self._pins=[]

    def scan(self):
        # Keep previous confirmed translation while the next OCR is running.
        # Temporarily hide pins to prevent the screenshot from recognizing them.
        if self._closing or not self.ready or self.busy:
            return
        super().scan()

    def start_worker(self):
        self._last_image_thumb=None
        self._unchanged_skips=0
        super().start_worker()

    def _capture_and_send(self):
        if self._closing:
            return
        # The parent scans the full primary monitor. We only conceal overlay
        # decorations for the actual screenshot, then restore immediately.
        import mss
        with mss.mss() as sct:
            m=sct.monitors[1]
            self._capture_origin=(m['left'],m['top'])
            self._capture_size=(m['width'],m['height'])
        self._capture_pin_visibility=[(p,p.isVisible()) for p in self._pins]
        self._capture_popup_visible=bool(self._popup and self._popup.isVisible())
        for pin,_ in self._capture_pin_visibility:
            pin.hide()
        if self._popup and self._capture_popup_visible:
            self._popup.hide()
        # Qt hide() takes effect synchronously; process queued paint work before grab.
        QApplication.processEvents()
        try:
            import mss
            with mss.mss() as sct:
                frame=np.ascontiguousarray(np.asarray(sct.grab(sct.monitors[1]))[:,:,:3])
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            thumb=cv2.resize(gray,(128,72),interpolation=cv2.INTER_AREA)
            if self.auto.isChecked() and self._last_image_thumb is not None:
                delta=float(np.mean(cv2.absdiff(thumb,self._last_image_thumb)))
                if delta < 2.0 and self._unchanged_skips < 12:
                    self._unchanged_skips+=1
                    self.busy=False
                    self.status.setText(f'畫面未變：沿用 {len(self._pins)} 個翻譯提示（已略過 {self._unchanged_skips} 次 OCR）')
                    return
            self._last_image_thumb=thumb
            self._unchanged_skips=0
            ok, buf=cv2.imencode('.png',frame)
            if not ok:raise RuntimeError('PNG encoding error')
            buf.tofile(str(self.snapshot))
            self.counter+=1
            self.pending=self.counter
            import json
            self.proc.write((json.dumps({'id':self.counter,'image_path':str(self.snapshot)})+'\n').encode('utf-8'))
            self.status.setText('全畫面 OCR 辨識中…')
        except Exception as exc:
            self.busy=False
            self.status.setText('擷取失敗：'+repr(exc))
        finally:
            for pin,was_visible in self._capture_pin_visibility:
                if was_visible and not self.hide_pins_btn.isChecked():
                    pin.show()
            if self._popup and self._capture_popup_visible:
                self._popup.show()
            self._capture_pin_visibility=[]
            self._capture_popup_visible=False

    def _map_box(self,bbox):
        """OCR physical pixel coordinates -> Qt logical global coordinates."""
        if not self._capture_size:return None
        screen=QGuiApplication.primaryScreen()
        if screen is None:return None
        geom=screen.geometry()
        sx=geom.width()/self._capture_size[0]
        sy=geom.height()/self._capture_size[1]
        x1,y1,x2,y2=bbox
        return QPoint(round(geom.left()+x2*sx+5),round(geom.top()+y1*sy-10))

    @staticmethod
    def _cards_signature(cards):
        # Ignore OCR score fluctuation, and allow a few pixels of bbox jitter.
        return tuple(sorted((
            c.get('topic_id'), c.get('category'),
            c.get('record_id') or c.get('id') or c.get('title_tw'),
            round(c['bbox'][0]/16), round(c['bbox'][1]/16),
            c.get('title_tw'), c.get('description_tw'), c.get('locked_tw'),
        ) for c in cards))

    def process(self,lines,elapsed):
        if self._closing:
            return
        from arknights_translator.rogue_layout_engine import analyze
        report=analyze(lines,self.records,topic=self.topic.currentData(),suppress_hud=self.hud.isChecked())
        cards=[c for c in report['cards'] if c['status']=='matched' and c.get('title_tw')]
        # A transient empty scan (animation, movement, OCR miss) must not delete
        # the previous pins. Expire after THREE consecutive empty OCR scans.
        if not cards:
            self._empty_scans+=1
            if self._empty_scans>=3:
                self.clear_pins()
                self.pin_status.setText('連續 3 次未找到可靠匹配，已清除舊提示。')
            else:
                self.pin_status.setText(
                    f'本次未找到可靠匹配（{self._empty_scans}/3）；保留上次 {len(self._pins)} 個提示。'
                )
            self.status.setText(f'OCR {len(lines)} 框｜耗時 {elapsed:.1f}s')
            return
        self._empty_scans=0
        signature=self._cards_signature(cards)
        if signature==self._pin_signature:
            # No flickering or popup reset when the same items are still shown.
            self.pin_status.setText(f'翻譯提示維持 {len(self._pins)} 個｜OCR {len(lines)} 框｜耗時 {elapsed:.1f}s。')
            return

        # Build replacement pins before clearing the old batch.
        new_pins=[]
        used=[]
        for card in sorted(cards,key=lambda c:c.get('score',0),reverse=True):
            pos=self._map_box(card['bbox'])
            if pos is None:continue
            if any((pos-other).manhattanLength()<36 for other in used):continue
            used.append(pos)
            new_pins.append(TranslationPin(card,pos,self.show_detail))
        if not new_pins:
            self.pin_status.setText('畫面辨識成功，但無法定位圖標；保留上一輪結果。')
            return

        # Atomic replacement: clear old cards only after replacements exist.
        self.clear_pins()
        self._pins=new_pins
        self._pin_signature=signature
        for pin in self._pins:
            if not self.hide_pins_btn.isChecked():pin.show()
        self.pin_status.setText(f'找到 {len(self._pins)} 個可點擊翻譯提示｜OCR {len(lines)} 框｜耗時 {elapsed:.1f}s。')
        self.status.setText('點擊遊戲畫面旁的 ! 查看效果。')
        if self.debug.isChecked():
            print('[Phase18 OCR]', '\n'.join(str(x.get('text','')) for x in lines),flush=True)

    def show_detail(self,card,point):
        if self._popup:
            self._popup.open_card(card,point)

    def closeEvent(self,event):
        # Tool windows are not guaranteed to trigger QApplication's automatic
        # quitOnLastWindowClosed. Explicitly quit the app after closing.
        if self._closing:
            event.accept()
            return
        self._closing=True
        self.timer.stop()
        self.auto.blockSignals(True)
        self.auto.setChecked(False)
        self.auto.blockSignals(False)
        self.ready=False
        self.busy=False
        self.clear_pins()
        if self._popup:
            self._popup.close()
            self._popup.deleteLater()
            self._popup=None
        # Paddle predictor.run() can take a long time and will not necessarily
        # react to EOF on stdin. Never use the parent's graceful-close wait.
        # Kill the child process, then use only a short bounded reap.
        if self.proc.state()!=self.proc.ProcessState.NotRunning:
            try:
                self.proc.blockSignals(True)
                self.proc.kill()
                self.proc.waitForFinished(350)
            except Exception as exc:
                print('[Rogue OCR] Closing worker:',repr(exc),file=sys.stderr,flush=True)
        event.accept()
        QTimer.singleShot(0,QApplication.instance().quit)


def main():
    app=QApplication(sys.argv)
    gui=OverlayViewer();gui.show()
    return app.exec()

if __name__=='__main__':
    raise SystemExit(main())
