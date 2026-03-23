"""
proxy_engine.py — Visionary Navigator Gelişmiş Proxy Motoru
Per-Profile proxy desteği ile PyQt6 WebEngine entegrasyonu.

ÖNEMLİ NOTLAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QNetworkProxy vs QWebEngineProfile Proxy Farkı:

1. QNetworkProxy.setApplicationProxy():
   - GLOBAL seviyede çalışır
   - Tüm QNetworkAccessManager isteklerini etkiler
   - QWebEngine'i ETKİLEMEZ (Chromium kendi network stack'ini kullanır)

2. Chromium/WebEngine Proxy:
   - WebEngine, Chromium'un network stack'ini kullanır
   - Proxy ayarı QApplication başlamadan ÖNCE ayarlanmalı
   - --proxy-server="host:port" argümanı ile yapılır
   - VEYA ortam değişkenleri ile (HTTP_PROXY, HTTPS_PROXY)

3. Per-Profile Proxy (Bu modülün çözümü):
   - Her profil için ayrı QWebEngineUrlRequestInterceptor
   - Proxy rotasyonu ve izolasyon
   - Session bazlı proxy yönetimi
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations
import json
import logging
import os
import socket
import time
import urllib.request
import concurrent.futures
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path

from PyQt6.QtCore import (
    QObject, QThread, pyqtSignal, QTimer, QUrl, 
    QPropertyAnimation, QEasingCurve, Qt
)
from PyQt6.QtNetwork import QNetworkProxy
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, 
    QGraphicsOpacityEffect, QApplication
)
from PyQt6.QtGui import QColor

# WebEngine imports (lazy load için kontrol)
try:
    from PyQt6.QtWebEngineCore import (
        QWebEngineProfile, 
        QWebEngineUrlRequestInterceptor,
        QWebEngineUrlRequestInfo
    )
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

logger = logging.getLogger("ProxyEngine")
logger.setLevel(logging.INFO)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SABITLER & ENUM'LAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyType(Enum):
    """Desteklenen proxy türleri."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    SOCKS4 = "socks4"
    DIRECT = "direct"  # Proxy yok


class ProxyStatus(Enum):
    """Proxy bağlantı durumları."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"
    VALIDATING = "validating"


# Desteklenen ülkeler (emoji + isim)
PROXY_COUNTRIES = {
    "US": "🇺🇸 Amerika",
    "GB": "🇬🇧 İngiltere", 
    "DE": "🇩🇪 Almanya",
    "FR": "🇫🇷 Fransa",
    "NL": "🇳🇱 Hollanda",
    "JP": "🇯🇵 Japonya",
    "SG": "🇸🇬 Singapur",
    "CA": "🇨🇦 Kanada",
    "AU": "🇦🇺 Avustralya",
    "BR": "🇧🇷 Brezilya",
    "IN": "🇮🇳 Hindistan",
    "RU": "🇷🇺 Rusya",
    "TR": "🇹🇷 Türkiye",
    "KR": "🇰🇷 Güney Kore",
}

# UI Renkleri
COLORS = {
    "connected": "#2ECC71",      # Yeşil
    "disconnected": "#95A5A6",   # Gri
    "failed": "#E74C3C",         # Kırmızı
    "connecting": "#F39C12",     # Turuncu
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROXY VERİ YAPISI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ProxyConfig:
    """Proxy yapılandırma bilgisi."""
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    country: str = "Bilinmiyor"
    country_code: str = "XX"
    
    # Durum bilgileri
    is_alive: bool = False
    speed_ms: int = 0
    last_check: float = 0.0
    fail_count: int = 0
    
    def to_url(self) -> str:
        """Proxy URL formatı döndür."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"
    
    def to_chromium_arg(self) -> str:
        """Chromium --proxy-server argümanı formatı."""
        if self.proxy_type == ProxyType.SOCKS5:
            return f"socks5://{self.host}:{self.port}"
        elif self.proxy_type == ProxyType.SOCKS4:
            return f"socks4://{self.host}:{self.port}"
        else:
            return f"{self.host}:{self.port}"
    
    def to_qt_proxy(self) -> QNetworkProxy:
        """QNetworkProxy nesnesi oluştur."""
        proxy_type_map = {
            ProxyType.HTTP: QNetworkProxy.ProxyType.HttpProxy,
            ProxyType.HTTPS: QNetworkProxy.ProxyType.HttpProxy,
            ProxyType.SOCKS5: QNetworkProxy.ProxyType.Socks5Proxy,
            ProxyType.SOCKS4: QNetworkProxy.ProxyType.Socks5Proxy,  # Qt'de SOCKS4 yok
            ProxyType.DIRECT: QNetworkProxy.ProxyType.NoProxy,
        }
        
        proxy = QNetworkProxy()
        proxy.setType(proxy_type_map.get(self.proxy_type, QNetworkProxy.ProxyType.HttpProxy))
        proxy.setHostName(self.host)
        proxy.setPort(self.port)
        
        if self.username:
            proxy.setUser(self.username)
        if self.password:
            proxy.setPassword(self.password)
            
        return proxy
    
    def __str__(self) -> str:
        status = "✓" if self.is_alive else "✗"
        return f"[{status}] {self.country} ({self.host}:{self.port}) - {self.speed_ms}ms"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HATA SINIFLARI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyError(Exception):
    """Proxy ile ilgili genel hata."""
    pass


class ProxyValidationError(ProxyError):
    """Proxy doğrulama hatası."""
    pass


class ProxyConnectionError(ProxyError):
    """Proxy bağlantı hatası."""
    pass


class ProxyAuthError(ProxyError):
    """Proxy kimlik doğrulama hatası."""
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROXY DOĞRULAMA WORKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyValidator(QThread):
    """
    Proxy'leri arka planda doğrular.
    Concurrent (eşzamanlı) test ile hızlı sonuç.
    """
    
    # Sinyaller
    validation_complete = pyqtSignal(object, bool, int)  # proxy, is_valid, speed_ms
    all_validated = pyqtSignal(list)  # List[ProxyConfig]
    progress = pyqtSignal(int, int)  # current, total
    
    def __init__(self, proxies: List[ProxyConfig], timeout: int = 8, max_workers: int = 10):
        super().__init__()
        self._proxies = proxies
        self._timeout = timeout
        self._max_workers = max_workers
        self._stop_requested = False
        
    def stop(self):
        """Doğrulamayı durdur."""
        self._stop_requested = True
        
    def run(self):
        """Proxy'leri paralel doğrula."""
        valid_proxies = []
        total = len(self._proxies)
        
        logger.info(f"Proxy doğrulama başlıyor: {total} proxy")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_proxy = {
                executor.submit(self._validate_single, proxy): proxy
                for proxy in self._proxies
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_proxy):
                if self._stop_requested:
                    break
                    
                proxy = future_to_proxy[future]
                completed += 1
                
                try:
                    is_valid, speed_ms = future.result()
                    proxy.is_alive = is_valid
                    proxy.speed_ms = speed_ms
                    proxy.last_check = time.time()
                    
                    self.validation_complete.emit(proxy, is_valid, speed_ms)
                    self.progress.emit(completed, total)
                    
                    if is_valid:
                        valid_proxies.append(proxy)
                        
                except Exception as e:
                    logger.debug(f"Proxy doğrulama hatası: {e}")
                    proxy.is_alive = False
                    proxy.fail_count += 1
                    
        # Hıza göre sırala
        valid_proxies.sort(key=lambda x: x.speed_ms)
        
        logger.info(f"Doğrulama tamamlandı: {len(valid_proxies)}/{total} aktif")
        self.all_validated.emit(valid_proxies)
        
    def _validate_single(self, proxy: ProxyConfig) -> tuple[bool, int]:
        """Tek proxy'yi doğrula."""
        start = time.time()
        
        try:
            # Proxy handler oluştur
            if proxy.proxy_type in (ProxyType.SOCKS5, ProxyType.SOCKS4):
                # SOCKS için socket test
                return self._test_socks(proxy)
            else:
                # HTTP proxy test
                return self._test_http(proxy)
                
        except Exception as e:
            logger.debug(f"Doğrulama hatası {proxy.host}: {e}")
            return False, 0
            
    def _test_http(self, proxy: ProxyConfig) -> tuple[bool, int]:
        """HTTP proxy test."""
        start = time.time()
        
        proxy_url = f"http://{proxy.host}:{proxy.port}"
        if proxy.username and proxy.password:
            proxy_url = f"http://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
            
        handler = urllib.request.ProxyHandler({
            'http': proxy_url,
            'https': proxy_url
        })
        opener = urllib.request.build_opener(handler)
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        ]
        
        # Test endpoint'leri
        test_urls = [
            'http://ip-api.com/json',
            'http://httpbin.org/ip',
        ]
        
        for url in test_urls:
            try:
                response = opener.open(url, timeout=self._timeout)
                data = response.read().decode('utf-8')
                elapsed = int((time.time() - start) * 1000)
                
                # JSON yanıt kontrolü
                if data and ('{' in data):
                    logger.info(f"✓ HTTP proxy aktif: {proxy.host}:{proxy.port} ({elapsed}ms)")
                    return True, elapsed
            except urllib.error.URLError:
                continue
            except Exception:
                continue
                
        return False, 0
        
    def _test_socks(self, proxy: ProxyConfig) -> tuple[bool, int]:
        """SOCKS proxy test (socket level)."""
        start = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            
            result = sock.connect_ex((proxy.host, proxy.port))
            sock.close()
            
            elapsed = int((time.time() - start) * 1000)
            
            if result == 0:
                logger.info(f"✓ SOCKS proxy aktif: {proxy.host}:{proxy.port} ({elapsed}ms)")
                return True, elapsed
                
        except Exception as e:
            logger.debug(f"SOCKS test hatası: {e}")
            
        return False, 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROXY LİSTE ÇEKME WORKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyFetcher(QThread):
    """Ücretsiz proxy listelerinden güncel proxy çeker."""
    
    proxies_fetched = pyqtSignal(list)  # List[ProxyConfig]
    fetch_error = pyqtSignal(str)
    fetch_progress = pyqtSignal(str)  # Status message
    
    def __init__(self, country_code: Optional[str] = None, proxy_type: ProxyType = ProxyType.HTTP):
        super().__init__()
        self._country_code = country_code
        self._proxy_type = proxy_type
        
    def run(self):
        """Proxy listelerini çek."""
        all_proxies = []
        
        self.fetch_progress.emit("Proxy kaynakları taranıyor...")
        
        # Kaynak 1: ProxyScrape
        try:
            proxies = self._fetch_proxyscrape()
            all_proxies.extend(proxies)
            self.fetch_progress.emit(f"ProxyScrape: {len(proxies)} proxy")
        except Exception as e:
            logger.warning(f"ProxyScrape hatası: {e}")
            
        # Kaynak 2: Geonode
        try:
            proxies = self._fetch_geonode()
            all_proxies.extend(proxies)
            self.fetch_progress.emit(f"Geonode: {len(proxies)} proxy")
        except Exception as e:
            logger.warning(f"Geonode hatası: {e}")
            
        # Ülke filtrele
        if self._country_code and self._country_code != "XX":
            filtered = [p for p in all_proxies if p.country_code == self._country_code]
            if filtered:
                all_proxies = filtered
                
        # Benzersiz yap
        seen = set()
        unique = []
        for p in all_proxies:
            key = f"{p.host}:{p.port}"
            if key not in seen:
                seen.add(key)
                unique.append(p)
                
        logger.info(f"Toplam {len(unique)} benzersiz proxy bulundu")
        self.proxies_fetched.emit(unique[:100])  # Max 100
        
    def _fetch_proxyscrape(self) -> List[ProxyConfig]:
        """ProxyScrape API."""
        proxies = []
        
        protocol = "http" if self._proxy_type == ProxyType.HTTP else "socks5"
        url = f"https://api.proxyscrape.com/v2/?request=displayproxies&protocol={protocol}&timeout=10000&country=all&ssl=all&anonymity=all"
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode('utf-8')
            
        for line in data.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                try:
                    host, port = line.split(':')
                    proxies.append(ProxyConfig(
                        host=host.strip(),
                        port=int(port.strip()),
                        proxy_type=self._proxy_type,
                        country="Bilinmiyor",
                        country_code="XX"
                    ))
                except:
                    pass
                    
        return proxies
        
    def _fetch_geonode(self) -> List[ProxyConfig]:
        """Geonode API (ülke bilgisi ile)."""
        proxies = []
        
        protocol = "http" if self._proxy_type == ProxyType.HTTP else "socks5"
        url = f"https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&protocols={protocol}"
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        for item in data.get('data', []):
            try:
                proxies.append(ProxyConfig(
                    host=item.get('ip', ''),
                    port=int(item.get('port', 0)),
                    proxy_type=self._proxy_type,
                    country=item.get('country', 'Bilinmiyor'),
                    country_code=item.get('country', 'XX')[:2].upper()
                ))
            except:
                pass
                
        return proxies


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOAST BİLDİRİM WIDGET'I
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyToast(QWidget):
    """Estetik toast bildirim widget'ı."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._setup_ui()
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Otomatik gizleme timer
        self._hide_timer = QTimer(self)
        self._hide_timer.timeout.connect(self._fade_out)
        self._hide_timer.setSingleShot(True)
        
    def _setup_ui(self):
        """UI oluştur."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # İkon
        self._icon_label = QLabel("🌍")
        self._icon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(self._icon_label)
        
        # Mesaj
        self._msg_label = QLabel("")
        self._msg_label.setStyleSheet("""
            color: white;
            font-size: 13px;
            font-weight: 500;
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        """)
        layout.addWidget(self._msg_label)
        
        self.setFixedHeight(48)
        
    def show_message(self, message: str, status: ProxyStatus, duration: int = 3000):
        """Toast göster."""
        self._msg_label.setText(message)
        
        # Durum rengine göre arka plan
        color_map = {
            ProxyStatus.CONNECTED: ("#27AE60", "✅"),
            ProxyStatus.DISCONNECTED: ("#7F8C8D", "⚫"),
            ProxyStatus.FAILED: ("#E74C3C", "❌"),
            ProxyStatus.CONNECTING: ("#F39C12", "🔄"),
            ProxyStatus.VALIDATING: ("#3498DB", "🔍"),
        }
        
        bg_color, icon = color_map.get(status, ("#34495E", "🌍"))
        self._icon_label.setText(icon)
        
        self.setStyleSheet(f"""
            ProxyToast {{
                background-color: {bg_color};
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        
        # Konumlandır (sağ üst)
        if self.parent():
            parent_rect = self.parent().rect()
            self.move(parent_rect.width() - self.width() - 20, 70)
            
        # Göster
        self._opacity_effect.setOpacity(1.0)
        self.show()
        self.raise_()
        
        # Timer başlat
        self._hide_timer.start(duration)
        
    def _fade_out(self):
        """Fade out animasyonu."""
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANA PROXY MANAGER SINIFI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyManager(QObject):
    """
    Gelişmiş Proxy Yöneticisi.
    
    Özellikler:
    - Per-profile proxy desteği
    - Otomatik proxy doğrulama
    - Ülke bazlı seçim
    - Yedek proxy havuzu
    - UI geri bildirimi (signal/slot)
    
    Kullanım:
        manager = ProxyManager(parent_widget)
        manager.set_proxy_to_profile(profile, "1.2.3.4", 8080, ProxyType.HTTP)
    """
    
    # Sinyaller
    status_changed = pyqtSignal(ProxyStatus, str)  # status, message
    proxy_connected = pyqtSignal(str, str, int)     # country, host, port
    proxy_disconnected = pyqtSignal()
    proxy_failed = pyqtSignal(str)                  # error message
    proxies_available = pyqtSignal(list)            # List[ProxyConfig]
    validation_progress = pyqtSignal(int, int)      # current, total
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        self._parent = parent
        self._status = ProxyStatus.DISCONNECTED
        
        # Profile -> ProxyConfig mapping (GC önleme)
        self._profile_proxies: Dict[int, ProxyConfig] = {}
        
        # Global proxy (ana tarayıcı için)
        self._global_proxy: Optional[ProxyConfig] = None
        
        # Proxy havuzu
        self._proxy_pool: List[ProxyConfig] = []
        self._selected_country: Optional[str] = None
        
        # Workers (referans tut - GC önleme)
        self._fetcher: Optional[ProxyFetcher] = None
        self._validator: Optional[ProxyValidator] = None
        
        # Toast widget
        self._toast: Optional[ProxyToast] = None
        if parent:
            self._toast = ProxyToast(parent)
            
        # Durum dosyası
        self._state_file = Path(__file__).parent / ".proxy_engine_state"
        
        # Ayarları yükle
        self._load_state()
        
        logger.info("ProxyManager başlatıldı.")
        
    # ─────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────────────
    
    def set_proxy_to_profile(
        self,
        profile: 'QWebEngineProfile',
        host: str,
        port: int,
        proxy_type: ProxyType = ProxyType.HTTP,
        username: Optional[str] = None,
        password: Optional[str] = None,
        validate: bool = True
    ) -> bool:
        """
        Belirli bir profile'a proxy ata.
        
        Args:
            profile: QWebEngineProfile instance
            host: Proxy sunucu adresi
            port: Proxy port numarası
            proxy_type: Proxy türü (HTTP, SOCKS5, vs.)
            username: Kimlik doğrulama kullanıcı adı
            password: Kimlik doğrulama şifresi
            validate: Proxy'yi önce doğrula
            
        Returns:
            True başarılı, False başarısız
            
        Raises:
            ProxyValidationError: Proxy doğrulama başarısız
            ProxyConnectionError: Bağlantı hatası
        """
        if not WEBENGINE_AVAILABLE:
            raise ProxyError("PyQt6 WebEngine yüklü değil")
            
        # Proxy config oluştur
        proxy_config = ProxyConfig(
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=username,
            password=password
        )
        
        self._update_status(ProxyStatus.VALIDATING, "Proxy doğrulanıyor...")
        
        # Doğrulama (senkron - blocking)
        if validate:
            is_valid, speed = self._validate_proxy_sync(proxy_config)
            if not is_valid:
                self._update_status(ProxyStatus.FAILED, "Proxy bağlantısı başarısız")
                raise ProxyValidationError(f"Proxy doğrulanamadı: {host}:{port}")
            proxy_config.is_alive = True
            proxy_config.speed_ms = speed
            
        # Profile'a proxy ata
        try:
            # Qt proxy nesnesi
            qt_proxy = proxy_config.to_qt_proxy()
            
            # Profile ID (GC önleme için)
            profile_id = id(profile)
            self._profile_proxies[profile_id] = proxy_config
            
            # NOT: QWebEngineProfile doğrudan proxy API'si yok
            # Chromium --proxy-server argümanı uygulama başlangıcında verilmeli
            # Alternatif: Environment variable
            
            # macOS için environment variable
            os.environ['HTTP_PROXY'] = proxy_config.to_url()
            os.environ['HTTPS_PROXY'] = proxy_config.to_url()
            os.environ['http_proxy'] = proxy_config.to_url()
            os.environ['https_proxy'] = proxy_config.to_url()
            
            # QNetworkProxy global (non-WebEngine requests için)
            QNetworkProxy.setApplicationProxy(qt_proxy)
            
            self._global_proxy = proxy_config
            self._save_state()
            
            self._update_status(
                ProxyStatus.CONNECTED, 
                f"Proxy bağlandı: {proxy_config.country}"
            )
            
            self.proxy_connected.emit(
                proxy_config.country,
                proxy_config.host,
                proxy_config.port
            )
            
            logger.info(f"Proxy ayarlandı: {proxy_config}")
            return True
            
        except Exception as e:
            self._update_status(ProxyStatus.FAILED, str(e))
            raise ProxyConnectionError(f"Proxy bağlantı hatası: {e}")
            
    def remove_proxy_from_profile(self, profile: 'QWebEngineProfile'):
        """Profile'dan proxy kaldır."""
        profile_id = id(profile)
        
        if profile_id in self._profile_proxies:
            del self._profile_proxies[profile_id]
            
        # Environment temizle
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(var, None)
            
        # Global proxy kaldır
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        
        self._global_proxy = None
        self._save_state()
        
        self._update_status(ProxyStatus.DISCONNECTED, "Proxy bağlantısı kesildi")
        self.proxy_disconnected.emit()
        
        logger.info("Proxy kaldırıldı")
        
    def get_profile_proxy(self, profile: 'QWebEngineProfile') -> Optional[ProxyConfig]:
        """Profile'ın mevcut proxy ayarını döndür."""
        return self._profile_proxies.get(id(profile))
        
    def is_proxy_active(self, profile: 'QWebEngineProfile' = None) -> bool:
        """Proxy aktif mi kontrol et."""
        if profile:
            return id(profile) in self._profile_proxies
        return self._global_proxy is not None
        
    def get_status(self) -> ProxyStatus:
        """Mevcut durumu döndür."""
        return self._status
        
    def get_current_proxy(self) -> Optional[ProxyConfig]:
        """Aktif proxy'yi döndür."""
        return self._global_proxy
        
    # ─────────────────────────────────────────────────────────────────────
    #  PROXY HAVUZU YÖNETİMİ
    # ─────────────────────────────────────────────────────────────────────
    
    def fetch_proxies(self, country_code: Optional[str] = None, proxy_type: ProxyType = ProxyType.HTTP):
        """Ücretsiz proxy listesi çek."""
        self._selected_country = country_code
        
        self._update_status(ProxyStatus.CONNECTING, "Proxy listesi alınıyor...")
        
        self._fetcher = ProxyFetcher(country_code, proxy_type)
        self._fetcher.proxies_fetched.connect(self._on_proxies_fetched)
        self._fetcher.fetch_error.connect(self._on_fetch_error)
        self._fetcher.fetch_progress.connect(lambda msg: self._show_toast(msg, ProxyStatus.VALIDATING))
        self._fetcher.start()
        
    def validate_proxies(self, proxies: List[ProxyConfig] = None):
        """Proxy listesini doğrula."""
        if proxies is None:
            proxies = self._proxy_pool
            
        if not proxies:
            self._update_status(ProxyStatus.FAILED, "Doğrulanacak proxy yok")
            return
            
        self._update_status(ProxyStatus.VALIDATING, "Proxy'ler test ediliyor...")
        
        self._validator = ProxyValidator(proxies)
        self._validator.all_validated.connect(self._on_validation_complete)
        self._validator.progress.connect(self.validation_progress.emit)
        self._validator.start()
        
    def get_proxy_pool(self) -> List[ProxyConfig]:
        """Proxy havuzunu döndür."""
        return self._proxy_pool.copy()
        
    def connect_fastest_proxy(self) -> bool:
        """En hızlı proxy'ye bağlan."""
        alive = [p for p in self._proxy_pool if p.is_alive]
        if not alive:
            self._update_status(ProxyStatus.FAILED, "Kullanılabilir proxy yok")
            return False
            
        # En hızlı proxy
        fastest = min(alive, key=lambda x: x.speed_ms)
        
        try:
            # Dummy profile (global için)
            return self.set_proxy_to_profile(
                None,  # Global
                fastest.host,
                fastest.port,
                fastest.proxy_type,
                fastest.username,
                fastest.password,
                validate=False  # Zaten doğrulandı
            )
        except Exception as e:
            logger.error(f"Proxy bağlantı hatası: {e}")
            return False
            
    # ─────────────────────────────────────────────────────────────────────
    #  INTERNAL METHODS
    # ─────────────────────────────────────────────────────────────────────
    
    def _validate_proxy_sync(self, proxy: ProxyConfig, timeout: int = 10) -> tuple[bool, int]:
        """Senkron proxy doğrulama."""
        start = time.time()
        
        try:
            proxy_url = f"http://{proxy.host}:{proxy.port}"
            if proxy.username and proxy.password:
                proxy_url = f"http://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
                
            handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url
            })
            opener = urllib.request.build_opener(handler)
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            
            response = opener.open('http://ip-api.com/json', timeout=timeout)
            data = response.read().decode('utf-8')
            
            elapsed = int((time.time() - start) * 1000)
            
            if data and 'status' in data:
                return True, elapsed
                
        except Exception as e:
            logger.debug(f"Doğrulama hatası: {e}")
            
        return False, 0
        
    def _on_proxies_fetched(self, proxies: List[ProxyConfig]):
        """Proxy listesi geldi."""
        if proxies:
            self._proxy_pool = proxies
            self._show_toast(f"{len(proxies)} proxy bulundu, test ediliyor...", ProxyStatus.VALIDATING)
            self.validate_proxies(proxies)
        else:
            self._update_status(ProxyStatus.FAILED, "Proxy bulunamadı")
            
    def _on_fetch_error(self, error: str):
        """Fetch hatası."""
        self._update_status(ProxyStatus.FAILED, error)
        
    def _on_validation_complete(self, valid_proxies: List[ProxyConfig]):
        """Doğrulama tamamlandı."""
        self._proxy_pool = valid_proxies
        self.proxies_available.emit(valid_proxies)
        
        if valid_proxies:
            self._show_toast(
                f"{len(valid_proxies)} aktif proxy hazır",
                ProxyStatus.CONNECTED
            )
            # Otomatik bağlan
            self.connect_fastest_proxy()
        else:
            self._update_status(ProxyStatus.FAILED, "Aktif proxy bulunamadı")
            
    def _update_status(self, status: ProxyStatus, message: str):
        """Durumu güncelle."""
        self._status = status
        self.status_changed.emit(status, message)
        self._show_toast(message, status)
        
    def _show_toast(self, message: str, status: ProxyStatus, duration: int = 3000):
        """Toast bildirim göster."""
        if self._toast:
            self._toast.show_message(message, status, duration)
        logger.info(f"[{status.value}] {message}")
        
    def _save_state(self):
        """Durumu kaydet."""
        try:
            state = {
                "enabled": self._global_proxy is not None,
                "country": self._selected_country,
            }
            if self._global_proxy:
                state["proxy"] = {
                    "host": self._global_proxy.host,
                    "port": self._global_proxy.port,
                    "type": self._global_proxy.proxy_type.value,
                    "country": self._global_proxy.country,
                }
            self._state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"Durum kaydedilemedi: {e}")
            
    def _load_state(self):
        """Kaydedilmiş durumu yükle."""
        try:
            if self._state_file.exists():
                state = json.loads(self._state_file.read_text())
                self._selected_country = state.get("country")
                
                if state.get("enabled") and state.get("proxy"):
                    p = state["proxy"]
                    self._global_proxy = ProxyConfig(
                        host=p["host"],
                        port=p["port"],
                        proxy_type=ProxyType(p.get("type", "http")),
                        country=p.get("country", "Bilinmiyor")
                    )
                    # Environment variable ayarla
                    os.environ['HTTP_PROXY'] = self._global_proxy.to_url()
                    os.environ['HTTPS_PROXY'] = self._global_proxy.to_url()
                    
        except Exception as e:
            logger.warning(f"Durum yüklenemedi: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GHOST TAB PROXY ENTEGRASYONU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostProxyProfile:
    """
    Ghost Tab için izole proxy profili.
    
    Her GhostTab'ın kendi proxy ayarı olabilir.
    Profile instance'ı ve proxy reference'ı saklanır (GC önleme).
    """
    
    def __init__(self, profile: 'QWebEngineProfile'):
        self._profile = profile
        self._proxy: Optional[ProxyConfig] = None
        self._qt_proxy: Optional[QNetworkProxy] = None  # GC önleme
        
    def set_proxy(self, proxy_config: ProxyConfig):
        """Proxy ayarla."""
        self._proxy = proxy_config
        self._qt_proxy = proxy_config.to_qt_proxy()
        
        # NOT: QWebEngineProfile'a doğrudan proxy atanamaz
        # Bu sınıf metadata saklar
        
    def get_proxy(self) -> Optional[ProxyConfig]:
        """Proxy döndür."""
        return self._proxy
        
    def clear_proxy(self):
        """Proxy temizle."""
        self._proxy = None
        self._qt_proxy = None
        
    @property
    def profile(self) -> 'QWebEngineProfile':
        return self._profile


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CHROMIUM PROXY AYARLARI YARDIMCI FONKSİYONLAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_chromium_proxy_args(proxy: ProxyConfig) -> List[str]:
    """
    Chromium için proxy argümanları döndür.
    
    Bu argümanlar QApplication oluşturulmadan ÖNCE 
    sys.argv'a eklenmelidir.
    
    Örnek kullanım (main.py başında):
        if proxy_enabled:
            args = get_chromium_proxy_args(proxy_config)
            sys.argv.extend(args)
        app = QApplication(sys.argv)
    """
    args = [
        f'--proxy-server={proxy.to_chromium_arg()}',
    ]
    
    # Bypass listesi
    args.append('--proxy-bypass-list=localhost;127.0.0.1')
    
    return args


def set_macos_system_proxy(proxy: ProxyConfig) -> bool:
    """
    macOS sistem proxy ayarlarını değiştir.
    Yönetici yetkisi gerektirebilir.
    """
    import subprocess
    
    try:
        interface = "Wi-Fi"  # veya "Ethernet"
        
        if proxy.proxy_type == ProxyType.HTTP:
            subprocess.run([
                'networksetup', '-setwebproxy', interface,
                proxy.host, str(proxy.port)
            ], check=True)
            subprocess.run([
                'networksetup', '-setsecurewebproxy', interface,
                proxy.host, str(proxy.port)
            ], check=True)
        elif proxy.proxy_type == ProxyType.SOCKS5:
            subprocess.run([
                'networksetup', '-setsocksfirewallproxy', interface,
                proxy.host, str(proxy.port)
            ], check=True)
            
        logger.info("macOS sistem proxy ayarlandı")
        return True
        
    except Exception as e:
        logger.error(f"macOS proxy hatası: {e}")
        return False


def clear_macos_system_proxy() -> bool:
    """macOS sistem proxy ayarlarını temizle."""
    import subprocess
    
    try:
        interface = "Wi-Fi"
        
        subprocess.run(['networksetup', '-setwebproxystate', interface, 'off'], check=True)
        subprocess.run(['networksetup', '-setsecurewebproxystate', interface, 'off'], check=True)
        subprocess.run(['networksetup', '-setsocksfirewallproxystate', interface, 'off'], check=True)
        
        logger.info("macOS sistem proxy temizlendi")
        return True
        
    except Exception as e:
        logger.error(f"macOS proxy temizleme hatası: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    # Sınıflar
    'ProxyManager',
    'ProxyConfig',
    'ProxyValidator',
    'ProxyFetcher',
    'ProxyToast',
    'GhostProxyProfile',
    
    # Enum'lar
    'ProxyType',
    'ProxyStatus',
    
    # Hatalar
    'ProxyError',
    'ProxyValidationError',
    'ProxyConnectionError',
    'ProxyAuthError',
    
    # Sabitler
    'PROXY_COUNTRIES',
    
    # Yardımcı fonksiyonlar
    'get_chromium_proxy_args',
    'set_macos_system_proxy',
    'clear_macos_system_proxy',
]
