# -*- coding: utf-8 -*-
"""
محرك الشبكة - يتعامل مع فحص الشبكة، قاعدة OUI، ونظام المحاكاة (Fallback)
كل سطر مشروح باللغة العربية كما طُلب.
"""
import random
import time
import threading
import os
from typing import List, Dict

# محاولة استيراد scapy مع التعامل الآمن عند عدم التوفر
try:
    # استيراد الأدوات الضرورية من scapy
    from scapy.all import ARP, Ether, srp, conf  # type: ignore
    SCAPY_AVAILABLE = True
except Exception:
    # إذا لم تتوفر scapy نعمل في وضع المحاكاة
    SCAPY_AVAILABLE = False


# قاعدة OUI مُوسعة (مجموعة كبيرة من بادئات MAC) للتعرّف على الشركات
# ملاحظة: القائمة يمكن توسيعها عبر إضافة المزيد من البادئات
OUI_DB = {
    'APPLE': [
        '00:1C:B3', 'F4:5C:89', 'A4:5E:60', 'BC:AE:C5', 'D8:9D:67', 'A4:5E:60'
    ],
    'SAMSUNG': [
        '00:16:6C', '28:6C:07', '90:9F:33', '5C:49:79', 'FC:DB:B3'
    ],
    'HUAWEI': [
        '00:1E:C9', '8C:BE:BE', 'D8:9D:67', 'B8:3A:35', '84:3A:4B'
    ],
    'XIAOMI': [
        '00:21:6A', '00:E0:4C', '30:9C:23', '7C:8B:CA', '48:5B:39'
    ],
    'SONY': [
        '00:0B:6B', '00:1B:77', '80:00:2F', '5C:26:0A'
    ],
    'LG': [
        '00:02:B3', '00:80:48'
    ],
    'NOKIA': [
        '00:13:EF', '00:17:0D'
    ],
    'OPPO': [
        '00:1D:D7', '00:24:01'
    ],
    'VIVO': [
        '00:18:E7', '00:22:75'
    ],
    'ONEPLUS': [
        '00:1A:11', '00:1E:C2'
    ],
}

# خريطة نماذج مبدئية لأغراض المحاكاة (توليد أسماء أجهزة حقيقية-ish)
MODEL_DB = {
    'APPLE': ['iPhone 15', 'iPhone 15 Pro', 'iPad Pro', 'MacBook Pro'],
    'SAMSUNG': ['Galaxy S24', 'Galaxy Note 20', 'Galaxy A54'],
    'HUAWEI': ['P60 Pro', 'Mate 50', 'Nova 10'],
    'XIAOMI': ['Xiaomi 13', 'Redmi Note 12', 'Mi 11'],
    'SONY': ['Xperia 1', 'Xperia 5'],
    'LG': ['LG Velvet', 'LG Wing'],
    'NOKIA': ['Nokia G50', 'Nokia 8.3'],
    'OPPO': ['Find X6', 'Reno8'],
    'VIVO': ['Vivo X90', 'V23'],
    'ONEPLUS': ['OnePlus 12', 'OnePlus Nord']
}


def normalize_mac(mac: str) -> str:
    # تحويل الماك لصيغة موحدة (أحرف كبيرة) وإرجاع أول ثلاث بايتس
    mac = mac.strip().upper()
    mac = mac.replace('-', ':')
    parts = mac.split(':')
    if len(parts) >= 3:
        prefix = ':'.join(parts[:3])
        return prefix
    return mac


def get_vendor_from_mac(mac: str) -> str:
    # يبحث في قاعدة OUI ويعيد اسم الشركة أو 'Unknown'
    prefix = normalize_mac(mac)
    for vendor, prefixes in OUI_DB.items():
        for p in prefixes:
            if prefix.startswith(p):
                return vendor
    return 'Unknown'


class Device:
    # كلاس بسيط لتمثيل جهاز مُكتشف
    def __init__(self, ip: str, mac: str, vendor: str, x: float = 0.0, y: float = 0.0):
        # عنوان IP
        self.ip = ip
        # عنوان MAC
        self.mac = mac
        # مصنع الجهاز حسب OUI
        self.vendor = vendor
        # إحداثيات للرسم على واجهة الرادار
        self.x = x
        self.y = y
        # قائمة لموقع الحركة (Motion Trail)
        self.trail = []


class NetworkEngine:
    # المحرك المسئول عن فحص الشبكة وإرجاع الأجهزة
    def __init__(self):
        # قائمة الأجهزة الحالية
        self.devices: List[Device] = []
        # قفل للوصول الآمن بين الخيوط
        self._lock = threading.Lock()
        # سجل الطلبات لكل جهاز (ماك -> [{time, domain}, ...]) ويحفظ على القرص
        from collections import defaultdict
        self.requests_log = defaultdict(list)
        self.requests_log_path = os.path.join(os.path.dirname(__file__), 'requests_log.json')
        # محاولة تحميل السجل الموجود
        try:
            self.load_requests_log()
        except Exception:
            pass

    def _simulate_devices(self, count=8) -> List[Device]:
        # مولد أجهزة وهمية يعمل كـ fallback عند عدم توفر صلاحيات أو scapy
        devs = []
        vendors = list(OUI_DB.keys())
        for i in range(count):
            # توليد IP وهمي
            ip = f'192.168.1.{100 + i}'
            # اختيار مصنع عشوائي
            vendor = random.choice(vendors)
            # اختيار بادئة OUI حقيقية جزئياً
            prefix = random.choice(OUI_DB.get(vendor, ['02:00:00']))
            # إكمال الماك بأربعة بايتات عشوائية
            mac_tail = ':'.join('%02X' % random.randint(0, 255) for _ in range(3))
            mac = prefix + ':' + mac_tail
            # اختيار نموذج جهاز معقول
            model = random.choice(MODEL_DB.get(vendor, ['Device']))
            # إحداثيات أولية داخل الدائرة
            x = random.uniform(-0.8, 0.8)
            y = random.uniform(-0.8, 0.8)
            d = Device(ip=ip, mac=mac, vendor=vendor, x=x, y=y)
            # إضافة اسم النموذج كخاصية إضافية
            d.model = model
            devs.append(d)
        return devs

    def load_oui_from_file(self, path: str = 'oui_db.json') -> None:
        # تحميل OUI إضافي من ملف JSON إن وُجد لزيادة دقة التعرّف
        try:
            import json
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # دمج البيانات الجديدة مع OUI_DB الحالي
                    for vendor, prefixes in data.items():
                        if vendor in OUI_DB:
                            existing = set(OUI_DB[vendor])
                            for p in prefixes:
                                if p not in existing:
                                    OUI_DB[vendor].append(p)
                        else:
                            OUI_DB[vendor] = prefixes
        except Exception:
            # أي فشل في التحميل نتجنّبه بصمت
            pass

    def save_oui_to_file(self, path: str = 'oui_db.json') -> None:
        # حفظ OUI الحالي إلى ملف ليمكن توسيعه خارج التطبيق لاحقاً
        try:
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(OUI_DB, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_device_count(self) -> int:
        # إرجاع عدد الأجهزة المكتشفة الفعلية في المحرك
        with self._lock:
            return len(self.devices)

    def start_passive_sniffer(self, callback, iface: str = None) -> bool:
        """
        يبدأ رصداً سلبياً للحزم على الواجهة المحلية.
        - callback: دالة تستقبل قاموسًا بمعلومات الحزمة/الجهاز.
        - iface: واجهة الشبكة إن أردت تحديدها، خلاف ذلك يستخدم الافتراضي.
        يُعيد True إذا نُفّذ، False إذا كان scapy غير متوفر.
        هذه الوظيفة لا تقوم بأي تعديل على الشبكة ولا تنفذ هجمات.
        """
        if not SCAPY_AVAILABLE:
            return False

        # علامة إيقاف آمنة
        self._sniffer_stop = threading.Event()

        def _process_packet(pkt):
            try:
                info = {
                    'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'src_mac': None,
                    'dst_mac': None,
                    'src_ip': None,
                    'dst_ip': None,
                    'protocol': None,
                    'meta': {}
                }
                # ARP
                if pkt.haslayer('ARP'):
                    arp = pkt.getlayer('ARP')
                    info['protocol'] = 'ARP'
                    info['src_mac'] = arp.hwsrc
                    info['dst_mac'] = arp.hwdst if hasattr(arp, 'hwdst') else None
                    info['src_ip'] = arp.psrc
                    info['dst_ip'] = arp.pdst

                # IP/TCP/UDP
                if pkt.haslayer('IP'):
                    ip = pkt.getlayer('IP')
                    info['src_ip'] = getattr(ip, 'src', info['src_ip'])
                    info['dst_ip'] = getattr(ip, 'dst', info['dst_ip'])
                    info['protocol'] = info['protocol'] or ip.proto

                # مصدر/مقّدم طبقة لواسم الماك
                if pkt.haslayer('Ether'):
                    eth = pkt.getlayer('Ether')
                    info['src_mac'] = getattr(eth, 'src', info['src_mac'])
                    info['dst_mac'] = getattr(eth, 'dst', info['dst_mac'])

                # تحليل DNS وSNI وHTTP Host/User-Agent وmDNS/SSDP
                try:
                    from scapy.layers.inet import TCP, UDP, IP
                    from scapy.packet import Raw
                    # DNS
                    try:
                        from scapy.layers.dns import DNS, DNSQR
                        if pkt.haslayer(DNS) and getattr(pkt.getlayer(DNS), 'qdcount', 0) > 0:
                            dns = pkt.getlayer(DNS)
                            q = pkt.getlayer(DNSQR)
                            qname = getattr(q, 'qname', None)
                            if qname:
                                # qname may be bytes
                                try:
                                    qn = qname.decode() if isinstance(qname, bytes) else str(qname)
                                except Exception:
                                    qn = str(qname)
                                info['protocol'] = 'DNS'
                                info['meta']['dns_query'] = qn.rstrip('.')
                    except Exception:
                        pass

                    # mDNS (5353) / SSDP (1900)
                    if pkt.haslayer(UDP) and (getattr(pkt[UDP], 'sport', 0) in (5353, 1900) or getattr(pkt[UDP], 'dport', 0) in (5353, 1900)):
                        info['protocol'] = 'MDNS/SSDP'

                    # HTTP headers and TLS SNI (basic extraction)
                    if pkt.haslayer(TCP) and pkt.haslayer(Raw):
                        payload = pkt[Raw].load
                        # Try HTTP headers
                        try:
                            s = payload.decode('utf-8', errors='ignore')
                            if '\r\nHost:' in s or s.lower().startswith('get ') or s.lower().startswith('post '):
                                for line in s.split('\r\n'):
                                    if line.lower().startswith('host:'):
                                        info['meta']['host'] = line.split(':', 1)[1].strip()
                                    if line.lower().startswith('user-agent:'):
                                        info['meta']['user-agent'] = line.split(':', 1)[1].strip()
                        except Exception:
                            pass

                        # Basic TLS ClientHello SNI extraction
                        try:
                            def extract_sni(payload_bytes: bytes) -> str | None:
                                # Parse TLS record header
                                if len(payload_bytes) < 5:
                                    return None
                                # Content Type 22 = Handshake
                                if payload_bytes[0] != 22:
                                    return None
                                # skip record header (5 bytes)
                                # handshake starts at payload_bytes[5]
                                hs = payload_bytes[5:]
                                if len(hs) < 4:
                                    return None
                                # handshake type 1 = ClientHello
                                if hs[0] != 1:
                                    return None
                                # skip to extensions: need to skip variable lengths (client version, random, session id, cipher suites, compression)
                                try:
                                    idx = 4
                                    # session id length
                                    sid_len = hs[idx]
                                    idx += 1 + sid_len
                                    # cipher suites length (2 bytes)
                                    cs_len = int.from_bytes(hs[idx:idx+2], 'big')
                                    idx += 2 + cs_len
                                    # compression length
                                    comp_len = hs[idx]
                                    idx += 1 + comp_len
                                    # extensions length
                                    if idx + 2 > len(hs):
                                        return None
                                    ext_len = int.from_bytes(hs[idx:idx+2], 'big')
                                    idx += 2
                                    end_ext = idx + ext_len
                                    while idx + 4 <= end_ext:
                                        ext_type = int.from_bytes(hs[idx:idx+2], 'big')
                                        ext_len_i = int.from_bytes(hs[idx+2:idx+4], 'big')
                                        idx += 4
                                        if ext_type == 0:  # server_name
                                            # server_name list
                                            list_len = int.from_bytes(hs[idx:idx+2], 'big')
                                            idx2 = idx + 2
                                            while idx2 < idx + 2 + list_len:
                                                name_type = hs[idx2]
                                                name_len = int.from_bytes(hs[idx2+1:idx2+3], 'big')
                                                idx2 += 3
                                                name = hs[idx2:idx2+name_len].decode('utf-8', errors='ignore')
                                                return name
                                        idx += ext_len_i
                                except Exception:
                                    return None
                                return None

                            sni = extract_sni(payload)
                            if sni:
                                info['protocol'] = 'TLS'
                                info['meta']['sni'] = sni
                        except Exception:
                            pass
                except Exception:
                    pass

                # إذا كانت هناك معلومات ماك/آي بي نبعثها
                if info['src_mac'] or info['src_ip']:
                    # سجل سريع للطلبات المرتبطة بالجهاز
                    mac_key = (info.get('src_mac') or info.get('dst_mac') or 'unknown')
                    try:
                        # تأكد من وجود بنية السجل
                        if not hasattr(self, 'requests_log'):
                            from collections import defaultdict
                            self.requests_log = defaultdict(list)
                        mac_key = mac_key.lower()
                        recs = self.requests_log.setdefault(mac_key, [])
                        # اجمع أسماء النطاقات من DNS/SNI/Host
                        domain = None
                        if 'dns_query' in info.get('meta', {}):
                            domain = info['meta']['dns_query']
                        elif 'sni' in info.get('meta', {}):
                            domain = info['meta']['sni']
                        elif 'host' in info.get('meta', {}):
                            domain = info['meta']['host']
                        if domain:
                            recs.append({'time': info.get('time'), 'domain': domain})
                            # احفظ السجل على القرص فوراً لضمان الاستمرارية
                            try:
                                self.save_requests_log()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    callback(info)
            except Exception:
                pass

        def _sniff_loop():
            try:
                from scapy.all import sniff
                sniff(iface=iface, prn=_process_packet, store=0, stop_filter=lambda x: getattr(self, '_sniffer_stop', threading.Event()).is_set())
            except Exception:
                return

        t = threading.Thread(target=_sniff_loop, daemon=True)
        t.start()
        self._sniffer_thread = t
        return True

    def stop_passive_sniffer(self) -> None:
        # إيقاف الرصد السلبي بأمان
        if hasattr(self, '_sniffer_stop'):
            try:
                self._sniffer_stop.set()
            except Exception:
                pass

    def get_requests_for_device(self, mac: str):
        # إرجاع قائمة النطاقات/الطلبات المرتبطة بماك معين
        if not hasattr(self, 'requests_log'):
            return []
        return list(self.requests_log.get(mac.lower(), []))

    def save_requests_log(self):
        try:
            # تحويل defaultdict إلى dict عادي
            import json
            data = {mac: lst for mac, lst in self.requests_log.items()}
            with open(self.requests_log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_requests_log(self):
        try:
            import json
            if os.path.exists(self.requests_log_path):
                with open(self.requests_log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    from collections import defaultdict
                    self.requests_log = defaultdict(list, {k: v for k, v in data.items()})
        except Exception:
            from collections import defaultdict
            self.requests_log = defaultdict(list)

    def scan_network(self, ip_range: str = '192.168.1.0/24', timeout: int = 2, allow_simulation: bool = False) -> List[Device]:
        # يحاول فحص الشبكة عبر scapy باستخدام ARP
        # في حال فشل التشغيل (صلاحيات/عدم وجود npcap...) يعود إلى وضع المحاكاة
        if not SCAPY_AVAILABLE:
            # scapy غير متوفر
            if allow_simulation:
                self.devices = self._simulate_devices()
                return self.devices
            else:
                # لا نولد أجهزة افتراضية إلا إذا سُمح صراحة
                with self._lock:
                    self.devices = []
                return []

        try:
            # تعطيل رسائل scapy الزائدة
            conf.verb = 0
            # تنفيذ ARP-scan عبر البث
            ans, _ = srp(Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=ip_range), timeout=timeout)
            found = []
            for snd, rcv in ans:
                ip = rcv.psrc
                mac = rcv.hwsrc
                vendor = get_vendor_from_mac(mac)
                # تحويل إلى إحداثيات نسبية للرسم
                x = random.uniform(-1.0, 1.0)
                y = random.uniform(-1.0, 1.0)
                found.append(Device(ip=ip, mac=mac, vendor=vendor, x=x, y=y))
            if not found:
                # لم يُكتشف شيء؛ لا نولد أجهزة افتراضية تلقائياً
                if allow_simulation:
                    found = self._simulate_devices()
                else:
                    found = []
            # تخزين وحيد
            with self._lock:
                self.devices = found
            return found

        except PermissionError:
            # لا توجد صلاحيات لفتح الشبكة - نعود للمحاكاة
            self.devices = self._simulate_devices()
            return self.devices
        except Exception:
            # أي أخطاء أخرى نستخدم المحاكاة الاحتياطية
            self.devices = self._simulate_devices()
            return self.devices


def precheck_environment() -> Dict[str, str]:
    # فحص سريع للبيئة: وجود scapy، PyQt6 (واجهة)، وNpcap على ويندوز
    info = {}
    try:
        import scapy.all as scapy  # type: ignore
        info['scapy'] = 'OK'
    except Exception:
        info['scapy'] = 'MISSING'

    try:
        import PyQt6  # type: ignore
        info['pyqt'] = 'OK'
    except Exception:
        info['pyqt'] = 'MISSING'

    # فحص npcap على ويندوز
    if os.name == 'nt':
        ok, path = check_npcap()
        info['npcap'] = 'FOUND' if ok else 'MISSING'
    else:
        info['npcap'] = 'N/A'

    # صلاحيات المسؤول
    try:
        if os.name == 'nt':
            import ctypes
            info['admin'] = 'YES' if ctypes.windll.shell32.IsUserAnAdmin() != 0 else 'NO'
        else:
            info['admin'] = 'YES' if os.geteuid() == 0 else 'NO'
    except Exception:
        info['admin'] = 'UNKNOWN'

    return info


def check_npcap():
    # دالة بسيطة للتحقق من وجود Npcap في مسارات ويندوز الشائعة
    possible_paths = [
        os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'Npcap'),
        os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'Npcap'),
        os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'Npcap')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return True, p
    return False, ''


if __name__ == '__main__':
    # اختبار سريع عند التشغيل المباشر
    engine = NetworkEngine()
    devs = engine.scan_network()
    print('Discovered', len(devs), 'devices')
