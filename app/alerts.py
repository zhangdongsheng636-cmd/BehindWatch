import ctypes
import sys
import time
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QSystemTrayIcon
from PySide6.QtMultimedia import QSoundEffect
from .config import ROOT

def icon(color='#168278'):
    p = QPixmap(64, 64)
    p.fill(Qt.GlobalColor.transparent)
    painter = QPainter(p)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(3, 3, 58, 58, 17, 17)
    painter.setPen(QPen(QColor('white'), 4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(13, 20, 38, 24)
    painter.setBrush(QColor('white'))
    painter.drawEllipse(26, 26, 12, 12)
    painter.end()
    return QIcon(p)

def chosen_screen(cfg):
    return next((s for s in QApplication.screens() if s.name() == cfg.screen), QApplication.primaryScreen())

def dock(widget, cfg):
    rect = chosen_screen(cfg).availableGeometry()
    x = rect.left()+16 if '左' in cfg.corner else rect.right()-widget.width()-16
    y = rect.top()+16 if '上' in cfg.corner else rect.bottom()-widget.height()-16
    widget.move(x, y)

class Border(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QPen(QColor('#e4a144'), 5))
        p.drawRect(self.rect().adjusted(3, 3, -3, -3))

class Alerts:
    def __init__(self, window, tray):
        self.window, self.tray = window, tray
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        self.popup = QWidget(None, flags)
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.popup.setFixedSize(260, 84)
        self.popup.setStyleSheet('background:#123d3a;color:white;border-radius:10px;')
        layout = QVBoxLayout(self.popup)
        self.title = QLabel('身后有人')
        self.title.setStyleSheet('font:600 18px "Microsoft YaHei UI";')
        layout.addWidget(self.title)
        layout.addWidget(QLabel('BehindWatch · 留意走廊方向'))
        self.border = Border()
        self.sound = QSoundEffect(window)
        self.sound.setSource(QUrl.fromLocalFile(str(ROOT/'assets/chime.wav')))
        self.hide_timer = QTimer(window)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.clear_visuals)
        self.border_timer = QTimer(window)
        self.border_timer.timeout.connect(lambda: self.border.setVisible(not self.border.isVisible()))
        self.last = -100.

    def clear_visuals(self):
        self.popup.hide()
        self.border_timer.stop()
        self.border.hide()

    def silence(self):
        self.hide_timer.stop()
        self.clear_visuals()
        self.sound.stop()

    def notify(self, cfg, count=1, test=False):
        self.tray.setIcon(icon('#b56a16'))
        if cfg.dnd:
            self.silence()
            return '仅图标（勿扰）'
        now = time.monotonic()
        if not test and now-self.last < 3:
            return '图标；其他提醒已合并'
        self.last = now
        channels = ['图标']
        self.title.setText('提醒测试' if test else ('身后有人' if count == 1 else f'身后有 {count} 个目标'))
        if cfg.popup:
            dock(self.popup, cfg)
            self.popup.show()
            channels.append('弹窗')
        if cfg.border:
            self.border.setGeometry(chosen_screen(cfg).geometry())
            self.border.show()
            self.border_timer.start(350)
            channels.append('边框')
        if cfg.sound:
            self.sound.setVolume(cfg.volume/100.)
            self.sound.play()
            channels.append('声音')
        if cfg.notification:
            self.tray.showMessage('BehindWatch', '提醒测试' if test else '检测区域有人进入', QSystemTrayIcon.MessageIcon.Information, 2000)
            channels.append('系统通知请求')
        if cfg.taskbar and sys.platform == 'win32' and self.window.isVisible():
            from ctypes import wintypes
            class FLASHWINFO(ctypes.Structure):
                _fields_ = [('cbSize', wintypes.UINT), ('hwnd', wintypes.HWND), ('dwFlags', wintypes.DWORD), ('uCount', wintypes.UINT), ('dwTimeout', wintypes.DWORD)]
            f = FLASHWINFO(ctypes.sizeof(FLASHWINFO), int(self.window.winId()), 2, 3, 0)
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(f))
            channels.append('任务栏')
        self.hide_timer.start(2200)
        return '、'.join(channels)
