import copy
import datetime
import json
import threading
import time
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QPainter, QPen, QImage, QDesktopServices, QAction
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, QPushButton, QComboBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QFormLayout, QDialog, QDialogButtonBox, QDoubleSpinBox, QSpinBox,
    QTabWidget, QGroupBox, QSystemTrayIcon, QMenu, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QLineEdit)
from .config import Config
from .paths import data_dir, select_directory
from .migration import copy_data, validate_destination
from .engine import eligible
from .worker import Worker, Bus, devices
from .storage import Store
from .alerts import Alerts, icon, dock

STYLE = '''
QWidget {font-family:"Microsoft YaHei UI","Segoe UI";font-size:13px;color:#203b43;}
QMainWindow, QDialog {background:#f2f6f5;}
QLabel#title {font-size:26px;font-weight:700;color:#123d3a;}
QLabel#muted {color:#52676c;}
QLabel#status {background:#e0efeb;color:#16594e;border-radius:8px;padding:9px;font-weight:600;}
QPushButton {background:white;border:1px solid #cbd9d6;border-radius:7px;padding:8px 13px;min-height:20px;}
QPushButton:hover {background:#e5f0ed;border-color:#168278;}
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {border:2px solid #168278;}
QPushButton#primary {background:#126e63;color:white;border:1px solid #126e63;font-weight:600;}
QPushButton#primary:hover {background:#0c5a50;}
QPushButton:disabled {color:#879895;background:#e9eeec;}
QComboBox,QSpinBox,QDoubleSpinBox {background:white;border:1px solid #bdceca;border-radius:5px;padding:6px;min-height:20px;}
QGroupBox {border:1px solid #d5e1dd;border-radius:8px;margin-top:12px;padding:14px;background:white;}
QGroupBox::title {subcontrol-origin:margin;left:12px;padding:0 5px;color:#3f5c57;}
QTabWidget::pane {border:1px solid #d5e1dd;background:white;}
QTabBar::tab {padding:10px 18px;background:#e7eeeb;}
QTabBar::tab:selected {background:white;color:#126e63;}
QCheckBox {spacing:7px;padding:4px;}
QTableWidget {background:white;gridline-color:#e4ece9;}
QHeaderView::section {background:#e9f1ee;border:0;padding:7px;}
'''

def button(text, fn, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName('primary')
    b.clicked.connect(fn)
    return b

class Preview(QWidget):
    selected = Signal(object, bool)
    def __init__(self):
        super().__init__()
        self.setMinimumSize(240, 180)
        self.image = None
        self.boxes = []
        self.cfg = Config()
        self.mode = None
        self.origin = self.finish = None
        self.setMouseTracking(True)

    def target(self):
        if self.image is None:
            return QRectF(self.rect())
        w, h = self.image.width(), self.image.height()
        scale = min(self.width()/w, self.height()/h)
        return QRectF((self.width()-w*scale)/2, (self.height()-h*scale)/2, w*scale, h*scale)

    def set_frame(self, frame, boxes, cfg):
        h, w = frame.shape[:2]
        self.image = QImage(frame.data, w, h, frame.strides[0], QImage.Format.Format_BGR888).copy()
        self.boxes, self.cfg = boxes, copy.deepcopy(cfg)
        self.update()

    def clear(self):
        self.image = None
        self.boxes = []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#12272c'))
        if self.image is None:
            p.setPen(QColor('#c0d5d4'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '摄像头画面将在这里显示\n\n先预览并框选走廊，再开始监测')
            return
        r = self.target()
        p.drawImage(r, self.image)
        def rect(b):
            return QRectF(r.x()+b[0]*r.width(), r.y()+b[1]*r.height(), (b[2]-b[0])*r.width(), (b[3]-b[1])*r.height())
        p.setPen(QPen(QColor('#42d8c0'), 2, Qt.PenStyle.DashLine))
        p.drawRect(rect(self.cfg.roi))
        for b in self.cfg.exclusions:
            p.fillRect(rect(b), QColor(230, 80, 80, 55))
            p.setPen(QPen(QColor('#ff8d8d'), 2, Qt.PenStyle.DashLine))
            p.drawRect(rect(b))
        for b, score in self.boxes:
            color = '#f5bd59' if eligible(b, self.cfg) else '#91a6ad'
            p.setPen(QPen(QColor(color), 2))
            br = rect(b)
            p.drawRect(br)
            p.drawText(br.topLeft()+QPointF(3, 15), f'人体 {score:.0%}')
        if self.origin is not None and self.finish is not None:
            p.setPen(QPen(QColor('#ffaaaa' if self.mode == 'exclude' else '#42d8c0'), 2))
            p.drawRect(QRectF(self.origin, self.finish).normalized())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.mode and self.image is not None and self.target().contains(e.position()):
            self.origin = self.finish = e.position()

    def mouseMoveEvent(self, e):
        if self.origin is not None:
            r = self.target()
            self.finish = QPointF(max(r.left(), min(r.right(), e.position().x())), max(r.top(), min(r.bottom(), e.position().y())))
            self.update()

    def mouseReleaseEvent(self, e):
        if self.origin is None:
            return
        self.mouseMoveEvent(e)
        b = QRectF(self.origin, self.finish).normalized()
        r = self.target()
        if b.width() >= 12 and b.height() >= 12:
            self.selected.emit([(b.left()-r.left())/r.width(), (b.top()-r.top())/r.height(), (b.right()-r.left())/r.width(), (b.bottom()-r.top())/r.height()], self.mode == 'exclude')
        self.origin = self.finish = None
        self.mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

class Settings(QDialog):
    def __init__(self, cfg, parent):
        super().__init__(parent)
        self.setWindowTitle('监测设置')
        self.setMinimumWidth(540)
        self.values = {}
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        def page(name):
            w = QWidget()
            f = QFormLayout(w)
            f.setSpacing(12)
            tabs.addTab(w, name)
            return f
        def check(f, key, text):
            w = QCheckBox(text)
            w.setChecked(getattr(cfg, key))
            f.addRow(w)
            self.values[key] = w
        def number(f, key, label, lo, hi, step=1, decimals=None):
            w = QDoubleSpinBox() if decimals is not None else QSpinBox()
            w.setRange(lo, hi)
            w.setSingleStep(step)
            if decimals is not None:
                w.setDecimals(decimals)
            w.setValue(getattr(cfg, key))
            f.addRow(label, w)
            self.values[key] = w
        f = page('画面与检测')
        self.resolution = QComboBox()
        for text, pair in [('标准 · 640×480', (640,480)), ('宽屏 · 640×360', (640,360)), ('节能 · 320×240', (320,240))]:
            self.resolution.addItem(text, pair)
        self.resolution.setCurrentIndex(max(0, self.resolution.findData((cfg.width,cfg.height))))
        f.addRow('请求分辨率', self.resolution)
        check(f, 'rotate', '画面旋转 180°')
        check(f, 'mirror', '水平翻转')
        number(f, 'fps', '每秒检测次数', 2, 10)
        number(f, 'confidence', '检测置信度', .1, .95, .05, 2)
        number(f, 'min_height', '最小人体高度占比', 0., .8, .05, 2)
        number(f, 'dwell', '持续确认时间（秒）', .2, 3., .1, 1)
        number(f, 'repeat', '重复间隔（秒，0 = 仅一次）', 0, 300)
        hint = QLabel('确认时间越长，越容易过滤快速路过的人。\n目标尺寸仅用于粗略过滤远处的人，不代表实际距离。')
        hint.setWordWrap(True)
        f.addRow(hint)
        f = page('提醒')
        for k,t in [('popup','边角迷你弹窗'),('taskbar','任务栏图标闪烁'),('notification','Windows 系统通知'),('sound','提示音'),('border','屏幕边框闪烁')]:
            check(f,k,t)
        number(f,'volume','提示音音量（%）',0,100)
        self.corner = QComboBox()
        self.corner.addItems(['右下','右上','左下','左上'])
        self.corner.setCurrentText(cfg.corner)
        f.addRow('提醒 / 迷你窗口位置',self.corner)
        self.screen = QComboBox()
        self.screen.addItem('主显示器','')
        for s in QApplication.screens():
            self.screen.addItem(s.name(),s.name())
        self.screen.setCurrentIndex(max(0,self.screen.findData(cfg.screen)))
        f.addRow('显示器',self.screen)
        f.addRow(QLabel('完全隐藏到托盘后使用托盘图标提示。\n系统通知受 Windows 通知设置影响。'))
        f = page('本地记录')
        self.directory = data_dir()
        self.path_label = QLineEdit(str(self.directory))
        self.path_label.setReadOnly(True)
        self.path_label.setMinimumWidth(300)
        self.path_label.setAccessibleName('当前本地数据目录')
        f.addRow('数据目录', self.path_label)
        f.addRow(button('更改目录…', self.choose_directory))
        check(f,'screenshots','保存触发截图（仅检测区域）')
        number(f,'retention','保留天数',1,90)
        number(f,'max_mb','截图容量上限（MB）',10,2000)
        hint = QLabel('默认只保留事件文字，不录像、不上传。\n更改目录后点击“保存”，设置、日志和截图会一起复制。\n原目录保留备份；新目录请使用本机磁盘上的空文件夹。')
        hint.setWordWrap(True)
        f.addRow(hint)
        f.addRow(button('打开当前数据目录',lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(self, '选择本地空文件夹', str(self.directory))
        if folder:
            try:
                _, self.directory = validate_destination(data_dir(), folder)
                self.path_label.setText(str(self.directory))
            except (OSError, ValueError) as e:
                QMessageBox.warning(self, '无法使用此目录', str(e))

    def apply(self,cfg):
        c = copy.deepcopy(cfg)
        for key,w in self.values.items():
            setattr(c,key,w.isChecked() if isinstance(w,QCheckBox) else w.value())
        c.width,c.height = self.resolution.currentData()
        c.corner,c.screen = self.corner.currentText(),self.screen.currentData()
        return c

class Mini(QWidget):
    def __init__(self, main):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle('BehindWatch')
        self.setWindowIcon(icon())
        self.setStyleSheet(STYLE)
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        self.label = QLabel('已暂停')
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.preview = Preview()
        self.preview.setMinimumSize(240,150)
        layout.addWidget(self.preview)
        row=QHBoxLayout()
        row.addWidget(button('主窗口',main.restore))
        row.addWidget(button('折叠',self.fold))
        row.addWidget(button('启停',main.toggle))
        layout.addLayout(row)
        self.resize(300,250)

    def fold(self):
        self.preview.setVisible(not self.preview.isVisible())
        self.adjustSize()
        dock(self,self.main.cfg)

class MainWindow(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.cfg = Config.load()
        self.demo = demo
        self.worker = None
        self.pending = None
        self.pending_directory = None
        self.quitting = False
        self.stopping_since = None
        self.rendered = -1
        self.last_alarm = -100.
        self.status_kind = 'off'
        self.store = Store()
        self.bus = Bus()
        self.bus.status.connect(self.on_status)
        self.bus.event.connect(self.on_event)
        self.bus.enumerated.connect(self.on_devices)
        self.setWindowTitle('BehindWatch 1.1 · 身后来人提醒')
        self.setWindowIcon(icon())
        self.resize(900,750)
        self.setMinimumSize(740,640)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24,20,24,20)
        layout.setSpacing(12)
        top = QHBoxLayout()
        words=QVBoxLayout()
        title=QLabel('BehindWatch')
        title.setObjectName('title')
        words.addWidget(title)
        sub=QLabel('专注手头工作，留意身后来人。')
        sub.setObjectName('muted')
        words.addWidget(sub)
        top.addLayout(words)
        top.addStretch()
        top.addWidget(button('迷你模式',self.show_mini))
        top.addWidget(button('设置',self.settings))
        layout.addLayout(top)
        row=QHBoxLayout()
        self.cameras=QComboBox()
        self.cameras.setMinimumWidth(250)
        self.cameras.setAccessibleName('选择摄像头')
        self.cameras.currentIndexChanged.connect(self.camera_changed)
        row.addWidget(self.cameras,1)
        self.refresh_button=button('刷新设备',self.refresh)
        row.addWidget(self.refresh_button)
        self.preview_button=button('预览画面',self.preview_start)
        row.addWidget(self.preview_button)
        self.start_button=button('开始监测',self.toggle,True)
        row.addWidget(self.start_button)
        layout.addLayout(row)
        self.status=QLabel('已暂停 · 选择摄像头后预览')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.preview=Preview()
        self.preview.selected.connect(self.set_region)
        layout.addWidget(self.preview,1)
        row=QHBoxLayout()
        row.addWidget(button('框选走廊',lambda:self.pick(False)))
        row.addWidget(button('添加排除区',lambda:self.pick(True)))
        row.addWidget(button('区域数值',self.numeric_roi))
        row.addWidget(button('重置区域',self.reset_roi))
        row.addStretch()
        self.metrics=QLabel('纯本地处理 · 默认不保存画面')
        self.metrics.setObjectName('muted')
        row.addWidget(self.metrics)
        layout.addLayout(row)
        group=QGroupBox('日常控制')
        controls=QHBoxLayout(group)
        controls.addWidget(QLabel('灵敏度'))
        self.sensitivity=QComboBox()
        self.sensitivity.addItems(['自定义','低 · 减少打扰','中 · 推荐','高 · 更早提醒'])
        self.sensitivity.currentIndexChanged.connect(self.change_sensitivity)
        controls.addWidget(self.sensitivity)
        self.dnd=QCheckBox('勿扰 · 仅图标')
        self.dnd.setChecked(self.cfg.dnd)
        self.dnd.toggled.connect(self.change_dnd)
        controls.addWidget(self.dnd)
        controls.addStretch()
        controls.addWidget(button('测试提醒',self.test_alert))
        controls.addWidget(button('事件日志',self.logs))
        layout.addWidget(group)
        self.footer=QLabel('绿色虚线：检测区域   红色区域：排除   黄色框：符合区域条件的人体')
        self.footer.setObjectName('muted')
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        self.tray=QSystemTrayIcon(icon(),self)
        self.tray.setToolTip('BehindWatch · 已暂停')
        menu=QMenu()
        for title,callback in [('显示主窗口',self.restore),('迷你模式',self.show_mini),('开始 / 停止监测',self.toggle)]:
            menu.addAction(title,callback)
        self.dnd_action=QAction('勿扰模式',self)
        self.dnd_action.setCheckable(True)
        self.dnd_action.setChecked(self.cfg.dnd)
        self.dnd_action.triggered.connect(self.dnd.setChecked)
        menu.addAction(self.dnd_action)
        menu.addSeparator()
        menu.addAction('退出',self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.restore() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.alerts=Alerts(self,self.tray)
        self.mini=Mini(self)
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        QApplication.instance().screenRemoved.connect(lambda s:dock(self.mini,self.cfg))
        self.store.submit('启动',{'版本':'1.1.0'},cfg=copy.deepcopy(self.cfg))
        if not demo:
            self.refresh()

    def persist(self):
        try:
            self.cfg.save()
        except OSError:
            self.footer.setText('设置保存失败，请检查本地数据目录权限。')

    def refresh(self):
        if self.worker:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText('正在枚举摄像头…')
        threading.Thread(target=lambda:self.bus.enumerated.emit(devices()),daemon=True).start()

    def on_devices(self, items):
        self.cameras.blockSignals(True)
        self.cameras.clear()
        for d in items:
            self.cameras.addItem(f"{d['name']} · {'常规模式' if d['backend']==700 else '兼容模式'}",d)
        idx=next((i for i,d in enumerate(items) if d['path']==self.cfg.camera_path and d['backend']==self.cfg.backend),0)
        self.cameras.setCurrentIndex(idx if items else -1)
        self.cameras.blockSignals(False)
        self.camera_changed()
        self.refresh_button.setEnabled(True)
        self.on_status('已暂停 · 可以先预览并框选走廊' if items else '未找到摄像头 · 检查连接与 Windows 相机权限后刷新', 'off' if items else 'error')

    def camera_changed(self):
        d=self.cameras.currentData()
        if d:
            changed=self.cfg.camera_path and self.cfg.camera_path != d['path']
            self.cfg.camera_path,self.cfg.camera_name,self.cfg.backend=d['path'],d['name'],d['backend']
            if changed:
                self.cfg.roi,self.cfg.exclusions=[0.,0.,1.,1.],[]
                self.footer.setText('已切换摄像头，请重新框选检测区域。')
            self.persist()

    def launch(self, monitoring):
        if self.worker:
            self.worker.update(self.cfg,monitoring)
        else:
            if not self.cfg.camera_path:
                QMessageBox.information(self,'选择摄像头','请连接摄像头并点击“刷新设备”。')
                return
            self.worker=Worker(self.cfg,self.bus,monitoring)
            self.rendered=-1
            self.worker.start()
        self.start_button.setText('停止监测' if monitoring else '开始监测')
        self.preview_button.setText('关闭预览' if not monitoring else '检测画面')
        self.preview_button.setEnabled(not monitoring)
        self.cameras.setEnabled(False)
        self.refresh_button.setEnabled(False)

    def toggle(self):
        if self.worker and self.worker.stop_event.is_set():
            return
        if self.worker and self.worker.monitoring:
            self.stop()
        else:
            self.launch(True)

    def preview_start(self):
        if self.worker:
            if not self.worker.monitoring:
                self.stop()
            return
        self.launch(False)

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.stopping_since=time.monotonic()
            self.start_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.status.setText('正在释放摄像头…')
        self.alerts.silence()
        self.preview.clear()
        self.mini.preview.clear()

    def tick(self):
        if self.worker and self.worker.stop_event.is_set():
            if self.stopping_since and time.monotonic()-self.stopping_since > 6 and self.worker.alive():
                self.status.setText('摄像头驱动未响应。请从托盘退出程序后重试。')
                if self.quitting:
                    self.finish_quit()
                return
            if not self.worker.alive():
                self.worker=None
                self.start_button.setEnabled(True)
                self.preview_button.setEnabled(True)
                self.start_button.setText('开始监测')
                self.preview_button.setText('预览画面')
                self.cameras.setEnabled(True)
                self.refresh_button.setEnabled(True)
                self.on_status('已暂停 · 摄像头已释放','off')
                if self.quitting:
                    self.finish_quit()
                    return
                if self.pending_directory is not None:
                    target, mode = self.pending_directory
                    self.pending_directory = None
                    self.move_directory(target, mode)
                    return
                if self.pending is not None:
                    mode,self.pending=self.pending,None
                    self.launch(mode)
            return
        if self.worker:
            with self.worker.lock:
                result=self.worker.result
            if result and time.monotonic()-result[5] < 1.5:
                seq,frame,boxes,actual,ms,_=result
                if seq != self.rendered:
                    if self.isVisible() and not self.isMinimized():
                        self.preview.set_frame(frame,boxes,self.cfg)
                    if self.mini.isVisible() and self.mini.preview.isVisible():
                        self.mini.preview.set_frame(frame,boxes,self.cfg)
                    self.rendered=seq
                    self.metrics.setText(f'{actual[0]}×{actual[1]} · {ms:.0f} ms · {self.cfg.fps} 次/秒')
            elif not self.demo:
                self.preview.clear()
                self.mini.preview.clear()
        if self.store.error:
            self.footer.setText(self.store.error)
        if self.status_kind != 'alert' and time.monotonic()-self.last_alarm > 3:
            self.tray.setIcon(icon({'on':'#168278','error':'#b44545','off':'#718787','preview':'#718787','busy':'#718787'}.get(self.status_kind,'#168278')))

    def on_status(self,text,kind):
        if self.worker and self.worker.stop_event.is_set():
            return
        self.status_kind=kind
        self.status.setText(text + (' · 勿扰' if self.cfg.dnd else ''))
        self.mini.label.setText(self.status.text())
        self.tray.setToolTip('BehindWatch · '+self.status.text())
        colors={'alert':('#fff0d8','#805010'),'error':('#fbe5e5','#9b3232'),'off':('#e5ecea','#465e59')}
        bg,fg=colors.get(kind,('#e0efeb','#16594e'))
        self.status.setStyleSheet(f'background:{bg};color:{fg};')
        self.tray.setIcon(icon('#b56a16' if kind=='alert' else '#b44545' if kind=='error' else '#168278' if kind=='on' else '#718787'))

    def on_event(self,event):
        if not self.worker or self.worker.stop_event.is_set() or event['session'] != self.worker.session or event['epoch'] != self.worker.epoch:
            return
        self.last_alarm=time.monotonic()
        # Use current DND state even if changed while inference was running.
        channels=self.alerts.notify(self.cfg,len(event['events']))
        for i,e in enumerate(event['events']):
            e={**e,'session':event['session'],'提醒':channels}
            self.store.submit('人体触发',e,event['frame'] if i==0 else None,event['cfg'])

    def changed(self):
        self.persist()
        if self.worker and not self.worker.stop_event.is_set():
            self.worker.update(self.cfg,self.worker.monitoring)
        self.preview.cfg=copy.deepcopy(self.cfg)
        self.preview.update()

    def pick(self,exclude):
        if self.preview.image is None:
            self.footer.setText('请先点击“预览画面”，画面出现后再框选。')
            return
        self.preview.mode='exclude' if exclude else 'roi'
        self.preview.setCursor(Qt.CursorShape.CrossCursor)
        self.footer.setText('在画面内拖动矩形，松开鼠标保存。'+('排除区内的人体中心将被忽略。' if exclude else '只监测所选走廊。'))

    def set_region(self,box,exclude):
        if exclude:
            self.cfg.exclusions.append(box)
        else:
            self.cfg.roi=box
        self.changed()
        self.footer.setText('区域已保存。绿色虚线为检测区，红色为排除区。')

    def reset_roi(self):
        self.cfg.roi,self.cfg.exclusions=[0.,0.,1.,1.],[]
        self.changed()
        self.footer.setText('已恢复全画面检测并清除排除区，请注意避开自己。')

    def numeric_roi(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('检测区域百分比（键盘可操作）')
        form=QFormLayout(dialog)
        values=[]
        for title,v in zip(['左边界 %','上边界 %','右边界 %','下边界 %'],self.cfg.roi):
            w=QDoubleSpinBox()
            w.setRange(0,100)
            w.setValue(v*100)
            form.addRow(title,w)
            values.append(w)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec():
            b=[w.value()/100 for w in values]
            if b[0]<b[2] and b[1]<b[3]:
                self.set_region(b,False)
            else:
                QMessageBox.warning(self,'区域无效','左边界必须小于右边界，上边界必须小于下边界。')

    def change_sensitivity(self,i):
        if i:
            self.cfg.confidence,self.cfg.min_height,self.cfg.dwell=[(.6,.22,1.),(.45,.15,.6),(.3,.08,.3)][i-1]
            self.changed()

    def change_dnd(self,on):
        self.cfg.dnd=on
        self.dnd_action.setChecked(on)
        if on:
            self.alerts.silence()
        self.persist()
        # DND affects delivery only; do not reset tracking/cooldowns.
        if self.worker:
            with self.worker.lock:
                self.worker.cfg.dnd=on
        self.footer.setText('勿扰已开启：继续监测和记录事件，仅更新图标。' if on else '勿扰已关闭。')

    def test_alert(self):
        self.last_alarm=time.monotonic()
        self.alerts.notify(self.cfg,test=True)
        self.footer.setText('已测试当前提醒选项。'+('勿扰开启，只显示图标。' if self.cfg.dnd else ''))

    def settings(self):
        dialog=Settings(self.cfg,self)
        if dialog.exec():
            new=dialog.apply(self.cfg)
            if new.rotate!=self.cfg.rotate or new.mirror!=self.cfg.mirror:
                new.roi,new.exclusions=[0.,0.,1.,1.],[]
                self.footer.setText('画面方向已改变，检测区域已重置，请重新框选。')
            restart=self.worker is not None and (new.width,new.height)!=(self.cfg.width,self.cfg.height)
            self.cfg=new
            self.sensitivity.blockSignals(True)
            self.sensitivity.setCurrentIndex(0)
            self.sensitivity.blockSignals(False)
            if dialog.directory != data_dir():
                self.persist()
                if self.worker:
                    self.pending_directory = (dialog.directory, self.worker.monitoring)
                    self.stop()
                    self.footer.setText('正在释放摄像头，随后复制本地数据…')
                else:
                    self.move_directory(dialog.directory, None)
                return
            if restart:
                self.pending=self.worker.monitoring
                self.stop()
                self.persist()
            else:
                self.changed()
            dock(self.mini,self.cfg)
            self.store.submit('设置更新',{'截图':self.cfg.screenshots},cfg=copy.deepcopy(self.cfg))

    def move_directory(self, target, resume_mode=None):
        original = data_dir()
        closed = False
        self.setEnabled(False)
        try:
            validate_destination(original, target)
            closed = self.store.close()
            if not closed:
                raise OSError('日志仍在写入，请稍后重试。')
            copy_data(original, target)
            select_directory(target)
            self.store = Store()
            self.persist()
            self.store.submit('数据目录已更改', {'目录':str(target)}, cfg=copy.deepcopy(self.cfg))
            self.footer.setText(f'数据已迁移至 {target}；原目录保留备份。')
        except Exception as e:
            if data_dir() != original:
                select_directory(original)
            if closed:
                self.store = Store()
            self.footer.setText('迁移未完成，继续使用原数据目录。')
            QMessageBox.warning(self, '目录迁移未完成', str(e))
        finally:
            self.setEnabled(True)
        if resume_mode is not None:
            self.launch(resume_mode)

    def logs(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('本地事件日志 · 最近 300 条')
        dialog.resize(850,420)
        layout=QVBoxLayout(dialog)
        table=QTableWidget(0,4)
        table.setHorizontalHeaderLabels(['时间','类型','详情','截图'])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0,155)
        layout.addWidget(table)
        try:
            rows=self.store.rows()
        except Exception:
            rows=[]
        for i,(ts,kind,details,path) in enumerate(rows):
            table.insertRow(i)
            for j,v in enumerate([datetime.datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S'),kind,details,'双击查看' if path else '未保存']):
                table.setItem(i,j,QTableWidgetItem(v))
            table.item(i,3).setData(Qt.ItemDataRole.UserRole,path)
        def open_image(row,col):
            path=table.item(row,3).data(Qt.ItemDataRole.UserRole)
            if col==3 and path:
                from pathlib import Path
                if Path(path).exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                else:
                    QMessageBox.information(dialog,'截图已清理','截图已按保留期限或容量上限清理。')
        table.cellDoubleClicked.connect(open_image)
        layout.addWidget(button('打开数据目录',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))))
        dialog.exec()

    def show_mini(self):
        self.mini.show()
        dock(self.mini,self.cfg)
        self.hide()
        self.rendered=-1

    def restore(self):
        self.mini.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.rendered=-1

    def closeEvent(self,event):
        if self.demo or self.quitting:
            event.accept()
            return
        event.ignore()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.setToolTip('BehindWatch · 后台运行；双击打开，右键退出')
        else:
            self.showMinimized()

    def quit(self):
        self.quitting=True
        self.mini.hide()
        if self.worker:
            self.stop()
            self.show()
        else:
            self.finish_quit()

    def finish_quit(self):
        self.timer.stop()
        self.alerts.silence()
        self.tray.hide()
        self.store.close()
        QApplication.instance().quit()
