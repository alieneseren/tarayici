"""
privacy_engine.py — Visionary Navigator Gizlilik Motoru
Tor Entegrasyonu + Agresif Reklam/Tracker Engelleyici
"""

from __future__ import annotations
import os
import logging
import subprocess
import socket
import time
import re
import shutil
from typing import Optional, Set, List
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestInterceptor,
    QWebEngineUrlRequestInfo
)

logger = logging.getLogger("PrivacyEngine")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REKLAM VE TRACKER ENGELLEYİCİ — Agresif Filtreleme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Engellenecek domain listesi (EasyList + özel eklemeler)
BLOCKED_DOMAINS: Set[str] = {
    # Reklam ağları
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "googletagservices.com",
    "adservice.google.com", "pagead2.googlesyndication.com",
    "adsense.google.com", "adwords.google.com",
    
    # Facebook/Meta
    "facebook.net", "fbcdn.net", "connect.facebook.net",
    "pixel.facebook.com", "an.facebook.com",
    
    # Twitter/X
    "ads-twitter.com", "analytics.twitter.com",
    "ads-api.twitter.com", "syndication.twitter.com",
    
    # Diğer reklam ağları
    "adsrvr.org", "adnxs.com", "criteo.com", "criteo.net",
    "outbrain.com", "taboola.com", "mgid.com", "revcontent.com",
    "amazon-adsystem.com", "media.net", "pubmatic.com",
    "rubiconproject.com", "openx.net", "bidswitch.net",
    "casalemedia.com", "contextweb.com", "advertising.com",
    "2mdn.net", "admeld.com", "admob.com", "adsymptotic.com",
    "adtechus.com", "advertising.com", "atwola.com",
    "bluekai.com", "bounceexchange.com", "branch.io",
    "brealtime.com", "buysellads.com", "chartbeat.com",
    "clicktale.net", "cloudflare-insights.com", "cquotient.com",
    "crazyegg.com", "crwdcntrl.net", "demdex.net",
    "disqus.com", "dmp.bloomberg.com", "dotomi.com",
    "everesttech.net", "exelator.com", "eyeota.net",
    "fastclick.net", "flashtalking.com", "fls-na.amazon.com",
    "fwmrm.net", "gemius.pl", "gfx.ms", "gigya.com",
    "go-mpulse.net", "grapeshot.co.uk", "gumgum.com",
    "hotjar.com", "hubspot.com", "iasds01.com",
    "id5-sync.com", "idsync.rlcdn.com", "imrworldwide.com",
    "indexww.com", "insightexpressai.com", "intellitxt.com",
    "invitemedia.com", "iqzone.com", "jivox.com",
    "js-agent.newrelic.com", "justpremium.com",
    "krxd.net", "licdn.com", "lijit.com", "linksynergy.com",
    "liveintent.com", "liverail.com", "lkqd.net",
    "lnkd.in", "localytics.com", "lockerdome.com",
    "lotame.com", "luckyorange.com", "marchex.io",
    "marketo.com", "mathtag.com", "maxmind.com",
    "mediaplex.com", "meetrics.net", "microad.jp",
    "mixpanel.com", "ml314.com", "mookie1.com",
    "moatads.com", "mxpnl.com", "myvisualiq.net",
    "nativo.com", "netmng.com", "newrelic.com",
    "nexac.com", "nr-data.net", "nuggad.net",
    "omnitagjs.com", "omtrdc.net", "onelink.me",
    "onetag.com", "onesignal.com", "onsugar.com",
    "optimizely.com", "owneriq.net", "parsely.com",
    "petametrics.com", "pippio.com", "pixel.ad",
    "placed.com", "plista.com", "popt.in",
    "postrelease.com", "powerlinks.com", "pr-cy.ru",
    "prism.app-measurement.com", "pro-market.net",
    "propellerads.com", "proofpositivemedia.com",
    "pubmine.com", "purch.com", "pushwoosh.com",
    "quantcast.com", "quantserve.com", "quora.com",
    "rayjump.com", "researchgate.net", "resellerratings.com",
    "rfihub.com", "richrelevance.com", "rlcdn.com",
    "rnengage.com", "rtbsystem.com", "rubiconproject.com",
    "s-onetag.com", "sail-horizon.com", "salesforce.com",
    "samba.tv", "sascdn.com", "sb.scorecardresearch.com",
    "scarab.io", "scene7.com", "scorecardresearch.com",
    "segment.com", "segment.io", "serving-sys.com",
    "sharethis.com", "sharethrough.com", "shopify.com",
    "sift.com", "siftscience.com", "simpli.fi",
    "siteimproveanalytics.com", "sitescout.com",
    "sixpackabs.com", "skimresources.com", "smartadserver.com",
    "smaato.net", "smadex.com", "smartclip.com",
    "snapchat.com", "snssdk.com", "sociaplus.com",
    "speedcurve.com", "spiceworks.com", "spotxchange.com",
    "springserve.com", "stackadapt.com", "steelhousemedia.com",
    "stickyadstv.com", "tapad.com", "tapjoy.com",
    "teads.tv", "technorati.com", "telaria.com",
    "thetradedesk.com", "tidaltv.com", "tiqcdn.com",
    "tns-counter.ru", "trackcmp.net", "tradedoubler.com",
    "tremorhub.com", "tribalfusion.com", "triggit.com",
    "trk.pinterest.com", "truoptik.com", "trustpilot.com",
    "turn.com", "tvpixel.com", "tvsquared.com",
    "tynt.com", "uicdn.com", "umbel.com",
    "undertone.com", "unifymedia.com", "unrulymedia.com",
    "usabilla.com", "valueclickmedia.com", "veinteractive.com",
    "verizonmedia.com", "verticalresponse.com", "viglink.com",
    "visualiq.com", "vizury.com", "vk.com",
    "vmmpxl.com", "w55c.net", "webtrends.com",
    "wideorbit.com", "wigetmedia.com", "wistia.com",
    "wpdigital.net", "wsod.com", "xaxis.com",
    "xg4ken.com", "xiti.com", "xlisting.jp",
    "y2mate.com", "yandex.ru", "yieldlab.net",
    "yieldmanager.com", "yieldmo.com", "yieldoptimizer.com",
    "yimg.com", "yldbt.com", "yldmg.com",
    "yotpo.com", "zemanta.com", "zenaps.com",
    "zeotap.com", "zergnet.com", "zoho.com",
    "zopim.com", "zqtk.net", "adroll.com",
    
    # Türk reklam ağları
    "medyanet.net", "adform.net", "rtbhouse.com",
    "criteo.com", "sizmek.com", "admatic.com.tr",
    "reklamstore.com", "vidyard.com",
}

# Engellenecek URL pattern'leri
BLOCKED_URL_PATTERNS: List[str] = [
    r"/ads/",
    r"/adserver/",
    r"/advert",
    r"/banner",
    r"/tracking",
    r"/analytics",
    r"/pixel",
    r"/beacon",
    r"\.gif\?.*track",
    r"\.png\?.*ad",
    r"/collect\?",
    r"/log\?",
    r"/stats\?",
    r"/_track",
    r"/pagead/",
    r"/ad_",
    r"_ad\.",
    r"/sponsored",
    r"/promo",
    r"/popup",
    r"/interstitial",
]

# Engellenecek kaynak türleri (iframe, script vb.)
BLOCKED_RESOURCE_TYPES = {
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeScript,
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeImage,
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSubFrame,
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypePing,
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypePluginResource,
}


class AdBlockerInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Agresif reklam ve tracker engelleyici.
    QWebEngineUrlRequestInterceptor kullanarak tüm istekleri filtreler.
    """
    
    # İstatistikler
    blocked_count = 0
    allowed_count = 0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._whitelist: Set[str] = set()
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in BLOCKED_URL_PATTERNS]
        logger.info("Reklam engelleyici başlatıldı.")
        
    def interceptRequest(self, info: QWebEngineUrlRequestInfo):
        """Her HTTP isteğini yakala ve filtrele."""
        if not self._enabled:
            return
            
        url = info.requestUrl()
        url_str = url.toString().lower()
        host = url.host().lower()
        
        # Whitelist kontrolü
        if self._is_whitelisted(host):
            self.allowed_count += 1
            return
            
        # Domain engellemesi
        if self._is_blocked_domain(host):
            info.block(True)
            self.blocked_count += 1
            logger.debug(f"[ENGEL] Domain: {host}")
            return
            
        # URL pattern engellemesi
        if self._matches_blocked_pattern(url_str):
            info.block(True)
            self.blocked_count += 1
            logger.debug(f"[ENGEL] Pattern: {url_str[:80]}")
            return
            
        # Kaynak türü engellemesi (reklam scriptleri vb.)
        resource_type = info.resourceType()
        if resource_type in BLOCKED_RESOURCE_TYPES:
            if self._looks_like_ad(url_str, host):
                info.block(True)
                self.blocked_count += 1
                logger.debug(f"[ENGEL] Resource: {url_str[:80]}")
                return
                
        self.allowed_count += 1
        
    def _is_blocked_domain(self, host: str) -> bool:
        """Domain engelleme listesinde mi kontrol et."""
        # Tam eşleşme
        if host in BLOCKED_DOMAINS:
            return True
            
        # Alt domain kontrolü (ads.example.com → example.com)
        parts = host.split('.')
        for i in range(len(parts) - 1):
            domain = '.'.join(parts[i:])
            if domain in BLOCKED_DOMAINS:
                return True
                
        return False
        
    def _is_whitelisted(self, host: str) -> bool:
        """Whitelist'te mi kontrol et."""
        for w in self._whitelist:
            if host.endswith(w):
                return True
        return False
        
    def _matches_blocked_pattern(self, url: str) -> bool:
        """URL pattern'e uyuyor mu kontrol et."""
        for pattern in self._compiled_patterns:
            if pattern.search(url):
                return True
        return False
        
    def _looks_like_ad(self, url: str, host: str) -> bool:
        """URL reklam gibi görünüyor mu?"""
        ad_keywords = ['ad', 'ads', 'advert', 'banner', 'sponsor', 'promo', 
                       'track', 'pixel', 'beacon', 'analytics', 'stat']
        url_lower = url.lower()
        for kw in ad_keywords:
            if kw in url_lower:
                return True
        return False
        
    def set_enabled(self, enabled: bool):
        """Engelleyiciyi aç/kapat."""
        self._enabled = enabled
        logger.info(f"Reklam engelleyici: {'Aktif' if enabled else 'Pasif'}")
        
    def add_whitelist(self, domain: str):
        """Domain'i whitelist'e ekle."""
        self._whitelist.add(domain.lower())
        logger.info(f"Whitelist'e eklendi: {domain}")
        
    def remove_whitelist(self, domain: str):
        """Domain'i whitelist'ten kaldır."""
        self._whitelist.discard(domain.lower())
        
    def get_stats(self) -> dict:
        """Engelleme istatistiklerini döndür."""
        return {
            "blocked": self.blocked_count,
            "allowed": self.allowed_count,
            "block_rate": f"{(self.blocked_count / max(1, self.blocked_count + self.allowed_count)) * 100:.1f}%"
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOR YÖNETİCİSİ — SOCKS5 Proxy Entegrasyonu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TorManager(QObject):
    """
    Tor subprocess yöneticisi.
    - Tor başlatma/durdurma
    - SOCKS5 proxy durumu
    - IP değiştirme (yeni devre)
    """
    
    # Sinyaller
    status_changed = pyqtSignal(str)  # "connected", "disconnected", "connecting", "error"
    ip_changed = pyqtSignal(str)  # Yeni IP adresi
    
    TOR_SOCKS_PORT = 9050
    TOR_CONTROL_PORT = 9051
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tor_process: Optional[subprocess.Popen] = None
        self._is_connected = False
        self._current_ip = ""
        self._tor_executable: Optional[str] = None
        
    def _find_tor_executable(self) -> Optional[str]:
        """Tor binary yolunu bul."""
        candidates = [
            os.environ.get("TOR_PATH", "").strip(),
            shutil.which("tor") or "",
            "/opt/homebrew/bin/tor",   # macOS Apple Silicon
            "/usr/local/bin/tor",      # macOS Intel / Linux
            "/opt/local/bin/tor",      # MacPorts
        ]
        
        for path in candidates:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None
        
    def _get_tor_executable(self) -> Optional[str]:
        """Tor binary yolunu önbellekli şekilde döndür."""
        if self._tor_executable and os.path.isfile(self._tor_executable):
            return self._tor_executable
        self._tor_executable = self._find_tor_executable()
        return self._tor_executable
        
    def is_tor_available(self) -> bool:
        """Sistemde Tor kurulu mu kontrol et."""
        return bool(self._get_tor_executable())
            
    def is_connected(self) -> bool:
        """Tor bağlantısı aktif mi?"""
        return self._is_connected
        
    def start_tor(self) -> bool:
        """Tor'u başlat."""
        if self._is_connected:
            logger.warning("Tor zaten çalışıyor.")
            return True
            
        self.status_changed.emit("connecting")
        
        # Önce mevcut Tor süreci var mı kontrol et
        if self._is_tor_port_open():
            logger.info("Mevcut Tor bağlantısı bulundu.")
            self._is_connected = True
            self.status_changed.emit("connected")
            self._fetch_current_ip()
            return True
            
        # Tor kurulu mu?
        tor_bin = self._get_tor_executable()
        if not tor_bin:
            logger.error(
                "Tor kurulu değil veya PATH içinde bulunamadı! "
                "macOS: brew install tor | Linux: sudo apt install tor"
            )
            self.status_changed.emit("error")
            return False
            
        try:
            # Tor'u arka planda başlat
            self._tor_process = subprocess.Popen(
                [tor_bin],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # Bağlantıyı bekle (max 30 saniye)
            for _ in range(30):
                time.sleep(1)
                if self._is_tor_port_open():
                    self._is_connected = True
                    self.status_changed.emit("connected")
                    self._fetch_current_ip()
                    logger.info("Tor başarıyla başlatıldı.")
                    return True
                    
            logger.error("Tor başlatılamadı: Zaman aşımı")
            self.status_changed.emit("error")
            return False
            
        except Exception as e:
            logger.error(f"Tor başlatma hatası: {e}")
            self.status_changed.emit("error")
            return False
            
    def stop_tor(self):
        """Tor'u durdur."""
        if self._tor_process:
            try:
                self._tor_process.terminate()
                self._tor_process.wait(timeout=5)
            except Exception:
                self._tor_process.kill()
            self._tor_process = None
            
        self._is_connected = False
        self.status_changed.emit("disconnected")
        logger.info("Tor durduruldu.")
        
    def new_identity(self):
        """Yeni Tor devresi iste (IP değiştir)."""
        if not self._is_connected:
            return
            
        try:
            from stem import Signal
            from stem.control import Controller
            
            with Controller.from_port(port=self.TOR_CONTROL_PORT) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
                logger.info("Yeni Tor kimliği istendi.")
                time.sleep(1)
                self._fetch_current_ip()
                
        except ImportError:
            logger.warning("stem kütüphanesi kurulu değil: pip install stem")
        except Exception as e:
            logger.error(f"Yeni kimlik hatası: {e}")
            
    def _is_tor_port_open(self) -> bool:
        """SOCKS5 portu açık mı kontrol et."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.TOR_SOCKS_PORT))
            sock.close()
            return result == 0
        except Exception:
            return False
            
    def _fetch_current_ip(self):
        """Mevcut Tor IP'sini al."""
        try:
            import requests
            proxies = {
                'http': f'socks5h://127.0.0.1:{self.TOR_SOCKS_PORT}',
                'https': f'socks5h://127.0.0.1:{self.TOR_SOCKS_PORT}'
            }
            response = requests.get(
                'https://api.ipify.org?format=json',
                proxies=proxies,
                timeout=10
            )
            ip = response.json().get('ip', 'Bilinmiyor')
            self._current_ip = ip
            self.ip_changed.emit(ip)
            logger.info(f"Tor IP: {ip}")
        except Exception as e:
            logger.warning(f"IP alınamadı: {e}")
            
    def get_proxy_settings(self) -> dict:
        """Qt proxy ayarları için dict döndür."""
        return {
            "type": "socks5",
            "host": "127.0.0.1",
            "port": self.TOR_SOCKS_PORT
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GİZLİLİK MOTORU — Birleşik Yönetici
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PrivacyEngine(QObject):
    """
    Birleşik gizlilik motoru.
    - Ad Blocker
    - Tor Manager
    - Privacy Score
    """
    
    privacy_status_changed = pyqtSignal(dict)  # {tor: bool, blocker: bool, score: int}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Bileşenler
        self.ad_blocker = AdBlockerInterceptor(self)
        self.tor_manager = TorManager(self)
        
        # Tor durumu değişince yay
        self.tor_manager.status_changed.connect(self._on_tor_status_changed)
        
        logger.info("Gizlilik Motoru başlatıldı.")
        
    def get_ad_blocker(self) -> AdBlockerInterceptor:
        """Ad blocker interceptor'ı döndür (profile'a eklemek için)."""
        return self.ad_blocker
        
    def enable_tor(self) -> bool:
        """Tor'u etkinleştir."""
        return self.tor_manager.start_tor()
        
    def disable_tor(self):
        """Tor'u devre dışı bırak."""
        self.tor_manager.stop_tor()
        
    def is_tor_enabled(self) -> bool:
        """Tor aktif mi?"""
        return self.tor_manager.is_connected()
        
    def new_tor_identity(self):
        """Yeni Tor kimliği iste."""
        self.tor_manager.new_identity()
        
    def enable_ad_blocker(self):
        """Ad blocker'ı etkinleştir."""
        self.ad_blocker.set_enabled(True)
        self._emit_status()
        
    def disable_ad_blocker(self):
        """Ad blocker'ı devre dışı bırak."""
        self.ad_blocker.set_enabled(False)
        self._emit_status()
        
    def get_privacy_score(self) -> int:
        """Gizlilik skoru hesapla (0-100)."""
        score = 50  # Temel skor
        
        # Ad blocker aktifse +25
        if self.ad_blocker._enabled:
            score += 25
            
        # Tor aktifse +25
        if self.tor_manager.is_connected():
            score += 25
            
        return min(100, score)
        
    def get_status(self) -> dict:
        """Mevcut gizlilik durumunu döndür."""
        blocker_stats = self.ad_blocker.get_stats()
        return {
            "tor_enabled": self.tor_manager.is_connected(),
            "tor_ip": self.tor_manager._current_ip,
            "blocker_enabled": self.ad_blocker._enabled,
            "blocked_requests": blocker_stats["blocked"],
            "allowed_requests": blocker_stats["allowed"],
            "block_rate": blocker_stats["block_rate"],
            "privacy_score": self.get_privacy_score()
        }
        
    def _on_tor_status_changed(self, status: str):
        """Tor durumu değiştiğinde."""
        self._emit_status()
        
    def _emit_status(self):
        """Durum sinyali yayınla."""
        self.privacy_status_changed.emit(self.get_status())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROXY AYARLARI — QWebEngineProfile için
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def apply_tor_proxy_to_profile(profile, tor_manager: TorManager):
    """
    QWebEngineProfile'a Tor SOCKS5 proxy uygula.
    
    NOT: Qt WebEngine doğrudan SOCKS5 proxy desteklemiyor.
    Tam proxy desteği için uygulama yeniden başlatılmalı.
    """
    if not tor_manager.is_connected():
        logger.warning("Tor bağlı değil, proxy uygulanamadı.")
        return False
        
    from PyQt6.QtNetwork import QNetworkProxy
    
    # QNetworkProxy ayarla (QNetwork tabanlı istekler için çalışır)
    proxy = QNetworkProxy()
    proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
    proxy.setHostName("127.0.0.1")
    proxy.setPort(tor_manager.TOR_SOCKS_PORT)
    
    QNetworkProxy.setApplicationProxy(proxy)
    logger.info("Sistem proxy'si Tor'a yönlendirildi.")
    
    # Tor proxy flag'ini ayarla (bir sonraki başlatmada kullanılacak)
    _save_tor_state(True)
    
    return True


def remove_proxy():
    """Proxy'yi kaldır."""
    from PyQt6.QtNetwork import QNetworkProxy
    QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
    _save_tor_state(False)
    logger.info("Proxy kaldırıldı.")


def _save_tor_state(enabled: bool):
    """Tor durumunu kaydet."""
    import json
    import config
    state_file = os.path.join(config.BASE_DIR, ".tor_state")
    try:
        with open(state_file, 'w') as f:
            json.dump({"enabled": enabled}, f)
    except Exception as e:
        logger.warning(f"Tor durumu kaydedilemedi: {e}")


def is_tor_mode_enabled() -> bool:
    """Kayıtlı Tor durumunu kontrol et."""
    import json
    import config
    state_file = os.path.join(config.BASE_DIR, ".tor_state")
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                data = json.load(f)
                return data.get("enabled", False)
    except Exception:
        pass
    return False


def get_tor_chromium_flags() -> str:
    """Tor için Chromium flags döndür."""
    if is_tor_mode_enabled():
        return "--proxy-server=socks5://127.0.0.1:9050"
    return ""
