# -*- coding: utf-8 -*-
"""
نقطة الدخول للتطبيق: يربط بين محرك الشبكة وواجهة المستخدم
يحاول تشغيل التطبيق بصلاحيات المسؤول على ويندوز، وإذا لم ينجح يعرض تحذيراً
كل سطر مشروح باللغة العربية.
"""
import sys
import os
import ctypes
from PyQt6 import QtWidgets
from ui_core import MainWindow, ScannerThread
from network_engine import NetworkEngine, precheck_environment
from PyQt6.QtWidgets import QMessageBox


def is_admin() -> bool:
    # يفحص إذا كان البرنامج يعمل كمسؤول على ويندوز
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    # يحاول إعادة تشغيل السكربت بصلاحيات مسؤول عبر ShellExecute
    if sys.platform != 'win32':
        return False
    params = ' '.join([f'"{arg}"' for arg in sys.argv])
    try:
        ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, params, None, 1)
        return True
    except Exception:
        return False


def main():
    # نحاول الحصول على صلاحيات المسؤول، وإلا نعرض تحذيراً لكن نستمر
    if sys.platform == 'win32' and not is_admin():
        # لا نحاول إعادة التشغيل التلقائي بصلاحيات المسؤول
        # لأن ذلك قد يؤدي إلى إغلاق العملية الحالية تلقائياً.
        # بدلاً من ذلك نعرض تحذيراً ويستمر التطبيق في العمل بوضع المحاكاة إن لزم.
        print('تحذير: التطبيق لا يعمل بصلاحيات المسؤول. بعض وظائف الفحص قد لا تعمل.')

    # فحص بيئي سريع قبل البدء
    env = precheck_environment()
    missing = [k for k, v in env.items() if v in ('MISSING', 'NO')]
    if missing:
        # عرض تحذير احترافي للمستخدم مع ملخص النواقص
        msg = QMessageBox()
        msg.setWindowTitle('Pre-check Warning')
        details = '\n'.join([f'{k}: {v}' for k, v in env.items()])
        msg.setText('تنبيه: بعض المتطلبات قد تكون غير متوفرة. التطبيق سيعمل بوضع المحاكاة إذا لزم.')
        msg.setInformativeText(details)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()

    # إنشاء محرك الشبكة
    engine = NetworkEngine()

    # إنشاء واجهة المستخدم وتشغيل التطبيق
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(engine=engine)
    win.show()

    # تشغيل خيط الماسح المتقدم الذي يرسل تحديثات وسجلات إلى الواجهة
    scanner = ScannerThread(engine=engine, interval=3.0)
    # ربط إشارات السجل بتحديثات الواجهة
    def handle_log(msg):
        print(msg)
    scanner.log.connect(handle_log)
    # ربط إشعار الأجهزة بالنافذة الرئيسية لعرضها وتخزينها
    scanner.devices_updated.connect(win.on_devices_updated)
    scanner.start()

    # تأكد من إيقاف الخيط عند إغلاق التطبيق
    def on_about_to_quit():
        try:
            scanner.stop()
        except Exception:
            pass

    app.aboutToQuit.connect(on_about_to_quit)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
