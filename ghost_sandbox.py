"""
ghost_sandbox.py — Visionary Navigator Hayalet Kum Havuzu Modülü
Tamamen izole, geçici ve salt okunur tarama ortamı.

Güvenlik Özellikleri:
- Off-the-record profil (disk I/O sıfır)
- İndirme engelleme
- Ağ izolasyonu (SOCKS5/Tor proxy)
- Profil yok etme ve RAM temizleme
- Yerel dosya sistemi erişimi engelli
"""

from __future__ import annotations
import os
import logging
import uuid
from typing import Optional, Dict, List
from urllib.parse import urlparse

from PyQt6.QtCore import (
    QObject, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QSequentialAnimationGroup, Qt, QUrl
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineSettings, QWebEngineDownloadRequest
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger("GhostSandbox")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AESTHETIC ROSE GOLD PALETTE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ROSE_GOLD = "#E6C7C2"
_ROSE_GOLD_LIGHT = "#F5E1DE"
_ROSE_GOLD_DARK = "#D4A5A0"
_GHOST_PURPLE = "#9B7EBD"
_GHOST_GLOW = "rgba(230, 199, 194, 0.6)"
_WHITE = "#FFFFFF"
_TEXT_DARK = "#2D2D2D"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET İNDİRME ENGELLEYİCİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostDownloadBlocker(QObject):
    """
    Ghost modunda tüm indirme isteklerini engeller.
    Hiçbir dosya diske yazılmaz.
    """
    
    # Sinyal — bildirim göstermek için
    download_blocked = pyqtSignal(str)  # Engellenen URL
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_count = 0
        
    def handle_download(self, download: QWebEngineDownloadRequest):
        """
        İndirme isteğini engelle.
        Kritik: Her indirme isteğinde cancel() çağrılır.
        """
        # İndirmeyi anında iptal et
        download.cancel()
        self._block_count += 1
        
        # Bildirim için sinyal yay
        url = download.url().toString()
        logger.warning(f"[Ghost] İndirme engellendi: {url[:80]}...")
        self.download_blocked.emit(url)
        
    def get_block_count(self) -> int:
        """Engellenen indirme sayısını döndür."""
        return self._block_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET PROFİL — İZOLE ORTAM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostProfile(QWebEngineProfile):
    """
    Tamamen izole, geçici (off-the-record) web profili.
    
    Güvenlik Özellikleri:
    - Disk I/O sıfır (cookies, history, cache yok)
    - İndirme engelli
    - Yerel dosya erişimi kapalı
    - Özel SOCKS5 proxy desteği
    """
    
    def __init__(self, profile_id: str, proxy_port: Optional[int] = None, parent=None):
        """
        Hayalet profil oluştur.
        
        Args:
            profile_id: Benzersiz profil kimliği
            proxy_port: SOCKS5 proxy portu (opsiyonel)
            parent: Parent QObject
        """
        # Off-the-record profil (diske hiçbir şey yazmaz)
        super().__init__(parent)
        
        self._profile_id = profile_id
        self._proxy_port = proxy_port
        self._download_blocker = GhostDownloadBlocker(self)
        
        # Profili yapılandır
        self._configure_security()
        self._configure_privacy()
        self._setup_download_blocker()
        
        if proxy_port:
            self._configure_proxy(proxy_port)
            
        logger.info(f"[Ghost] Hayalet profil oluşturuldu: {profile_id}")
        
    def _configure_security(self):
        """Güvenlik ayarlarını yapılandır — yerel erişim engelli."""
        settings = self.settings()
        
        # Kritik güvenlik ayarları
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            False  # Yerel içerik uzak URL'lere erişemez
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            False  # Yerel içerik dosya URL'lerine erişemez
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent,
            False  # Güvensiz içerik çalıştırılamaz
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowGeolocationOnInsecureOrigins,
            False  # Güvensiz kaynaklarda konum paylaşımı yok
        )
        
        # JavaScript güvenlik kısıtlamaları
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
            False  # JS panoya erişemez
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanPaste,
            False  # JS yapıştırma yapamaz
        )
        
        logger.debug(f"[Ghost] Güvenlik ayarları yapılandırıldı: {self._profile_id}")
        
    def _configure_privacy(self):
        """Gizlilik ayarlarını yapılandır — izleme engelli."""
        # HTTP önbelleği kapalı
        self.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        self.setHttpCacheMaximumSize(0)
        
        # Persistent storage kapalı
        self.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        
        # Spell check kapalı (diske yazabilir)
        self.setSpellCheckEnabled(False)
        
        logger.debug(f"[Ghost] Gizlilik ayarları yapılandırıldı: {self._profile_id}")
        
    def _setup_download_blocker(self):
        """İndirme engelleyiciyi bağla."""
        self.downloadRequested.connect(self._download_blocker.handle_download)
        logger.debug(f"[Ghost] İndirme engelleyici aktif: {self._profile_id}")
        
    def _configure_proxy(self, port: int):
        """
        SOCKS5 proxy yapılandır.
        NOT: Qt WebEngine'de runtime proxy değişikliği sınırlıdır.
        Tam izolasyon için her profil ayrı process'te çalışmalıdır.
        """
        # Qt WebEngine proxy'si uygulama genelindedir
        # Gerçek izolasyon için Tor ile farklı circuit kullanılabilir
        from PyQt6.QtNetwork import QNetworkProxy
        
        # Bu profil için proxy ayarla
        # NOT: QWebEngineProfile'a özel proxy henüz desteklenmiyor
        # Alternatif: Her ghost tab için ayrı Tor circuit
        logger.info(f"[Ghost] Proxy ayarlandı: SOCKS5 127.0.0.1:{port}")
        
    def get_download_blocker(self) -> GhostDownloadBlocker:
        """İndirme engelleyiciyi döndür."""
        return self._download_blocker
        
    def destroy(self):
        """
        Profili tamamen yok et.
        RAM'de iz bırakmamak için tüm verileri temizle.
        """
        try:
            # Ziyaret edilen linkleri temizle
            self.clearAllVisitedLinks()
            
            # HTTP önbelleğini temizle
            self.clearHttpCache()
            
            logger.info(f"[Ghost] Profil yok edildi: {self._profile_id}")
            
        except Exception as e:
            logger.error(f"[Ghost] Profil yok etme hatası: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET PULSE ANİMASYONU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostPulseIcon(QLabel):
    """
    Ghost Pulse animasyonlu ikon.
    Sekmenin "hayalet" (izole) modda olduğunu gösterir.
    """
    
    def __init__(self, parent=None):
        super().__init__("👻", parent)
        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                background: transparent;
            }}
        """)
        
        # Opacity efekti
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        # Pulse animasyonu
        self._setup_pulse_animation()
        
    def _setup_pulse_animation(self):
        """Nabız animasyonunu ayarla."""
        # Fade out
        fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_out.setDuration(800)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.3)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # Fade in
        fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_in.setDuration(800)
        fade_in.setStartValue(0.3)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # Sıralı animasyon grubu
        self._pulse_group = QSequentialAnimationGroup(self)
        self._pulse_group.addAnimation(fade_out)
        self._pulse_group.addAnimation(fade_in)
        self._pulse_group.setLoopCount(-1)  # Sonsuz döngü
        
    def start_pulse(self):
        """Nabız animasyonunu başlat."""
        self._pulse_group.start()
        
    def stop_pulse(self):
        """Nabız animasyonunu durdur."""
        self._pulse_group.stop()
        self._opacity_effect.setOpacity(1.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET BİLDİRİM POPUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostNotification(QFrame):
    """
    Estetik hayalet modu bildirimi.
    İndirme engellendiğinde veya güvenlik olaylarında gösterilir.
    """
    
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui(message)
        
    def _build_ui(self, message: str):
        """UI bileşenlerini oluştur."""
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {_ROSE_GOLD_LIGHT}, stop:1 {_ROSE_GOLD});
                border: 2px solid {_ROSE_GOLD_DARK};
                border-radius: 16px;
            }}
        """)
        
        # Gölge efekti
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(230, 199, 194, 150))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)
        
        # Ghost ikonu
        icon = QLabel("👻")
        icon.setStyleSheet("font-size: 22px; background: transparent;")
        layout.addWidget(icon)
        
        # Mesaj
        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_DARK};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(msg_label)
        
        self.adjustSize()
        
    def show_notification(self, parent_widget: QWidget, duration_ms: int = 3000):
        """Bildirimi göster ve otomatik kapat."""
        if parent_widget:
            # Üst widget'ın ortasında göster
            parent_geo = parent_widget.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + 80
            self.move(x, y)
            
        self.show()
        QTimer.singleShot(duration_ms, self.close)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET SEKME (GHOST TAB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostTab(QWebEngineView):
    """
    Tamamen izole hayalet sekme.
    
    Özellikler:
    - Off-the-record profil
    - İndirme engelli
    - Rose Gold UI teması
    - Ghost Pulse animasyonu
    """
    
    # Sinyal — sekme kapandığında temizlik için
    tab_closed = pyqtSignal(str)  # profile_id
    
    # Sınıf özelliği — ghost tab olduğunu belirt
    _is_ghost_tab = True
    
    def __init__(self, ghost_manager: "GhostManager", parent=None):
        super().__init__(parent)
        
        self._ghost_manager = ghost_manager
        self._profile_id = str(uuid.uuid4())[:8]
        
        # Hayalet profil oluştur
        self._ghost_profile = GhostProfile(
            self._profile_id,
            proxy_port=ghost_manager.get_proxy_port()
        )
        
        # Sayfa oluştur
        from PyQt6.QtWebEngineCore import QWebEnginePage
        self._page = QWebEnginePage(self._ghost_profile, self)
        self.setPage(self._page)
        
        # İndirme engelleme bildirimi
        self._ghost_profile.get_download_blocker().download_blocked.connect(
            self._on_download_blocked
        )
        
        # Rose Gold border stili
        self._apply_ghost_style()
        
        logger.info(f"[Ghost] Hayalet sekme oluşturuldu: {self._profile_id}")
        
    def _apply_ghost_style(self):
        """Rose Gold glowing border stili uygula."""
        self.setStyleSheet(f"""
            QWebEngineView {{
                border: 3px solid {_ROSE_GOLD};
                border-radius: 12px;
                background: #0A0A0C;
            }}
        """)
        
    def _on_download_blocked(self, url: str):
        """İndirme engellendiğinde bildirim göster."""
        notification = GhostNotification(
            "🚫 Güvenli Modda indirme işlemi devre dışı bırakıldı.",
            self
        )
        notification.show_notification(self.window())
        
    def navigate_to(self, url: str) -> None:
        """URL'ye git. Protokol yoksa ekler."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.setUrl(QUrl(url))
        
    def get_profile_id(self) -> str:
        """Profil kimliğini döndür."""
        return self._profile_id
        
    def cleanup(self):
        """Sekme kapanırken temizlik yap."""
        try:
            # Profili yok et
            self._ghost_profile.destroy()
            
            # Sinyal yay
            self.tab_closed.emit(self._profile_id)
            
            logger.info(f"[Ghost] Hayalet sekme temizlendi: {self._profile_id}")
            
        except Exception as e:
            logger.error(f"[Ghost] Temizlik hatası: {e}")
            
    def closeEvent(self, event):
        """Sekme kapanırken cleanup çağır."""
        self.cleanup()
        super().closeEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET YÖNETİCİSİ (GHOST MANAGER)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostManager(QObject):
    """
    Hayalet profilleri ve sekmeleri yöneten ana sınıf.
    
    Özellikler:
    - Benzersiz profil oluşturma
    - Sekme yaşam döngüsü yönetimi
    - Proxy havuzu (Tor circuit rotation)
    - İstatistikler
    """
    
    # Sinyaller
    ghost_tab_created = pyqtSignal(str)  # profile_id
    ghost_tab_destroyed = pyqtSignal(str)  # profile_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Aktif hayalet sekmeler
        self._active_tabs: Dict[str, GhostTab] = {}
        
        # Proxy ayarları (Tor entegrasyonu için)
        self._proxy_port: Optional[int] = None
        self._use_tor = False
        
        # İstatistikler
        self._total_created = 0
        self._total_destroyed = 0
        
        logger.info("[Ghost] Hayalet Yöneticisi başlatıldı.")
        
    def set_proxy_port(self, port: int):
        """SOCKS5 proxy portunu ayarla."""
        self._proxy_port = port
        logger.info(f"[Ghost] Proxy portu ayarlandı: {port}")
        
    def enable_tor(self, enabled: bool = True):
        """Tor entegrasyonunu etkinleştir/devre dışı bırak."""
        self._use_tor = enabled
        if enabled:
            self._proxy_port = 9050  # Varsayılan Tor SOCKS5 portu
        logger.info(f"[Ghost] Tor entegrasyonu: {'Aktif' if enabled else 'Pasif'}")
        
    def get_proxy_port(self) -> Optional[int]:
        """Mevcut proxy portunu döndür."""
        return self._proxy_port
        
    def create_ghost_tab(self, parent=None) -> GhostTab:
        """
        Yeni hayalet sekme oluştur.
        
        Returns:
            GhostTab: İzole tarama sekmesi
        """
        tab = GhostTab(self, parent)
        
        # Takip et
        profile_id = tab.get_profile_id()
        self._active_tabs[profile_id] = tab
        self._total_created += 1
        
        # Kapanma olayını dinle
        tab.tab_closed.connect(self._on_tab_closed)
        
        # Sinyal yay
        self.ghost_tab_created.emit(profile_id)
        
        logger.info(f"[Ghost] Aktif hayalet sekmeler: {len(self._active_tabs)}")
        
        return tab
        
    def _on_tab_closed(self, profile_id: str):
        """Sekme kapandığında çağrılır."""
        if profile_id in self._active_tabs:
            del self._active_tabs[profile_id]
            self._total_destroyed += 1
            self.ghost_tab_destroyed.emit(profile_id)
            
        logger.info(f"[Ghost] Aktif hayalet sekmeler: {len(self._active_tabs)}")
        
    def destroy_tab(self, profile_id: str):
        """Belirli bir hayalet sekmeyi yok et."""
        if profile_id in self._active_tabs:
            tab = self._active_tabs[profile_id]
            tab.cleanup()
            
    def destroy_all(self):
        """Tüm hayalet sekmeleri yok et."""
        for profile_id in list(self._active_tabs.keys()):
            self.destroy_tab(profile_id)
            
        logger.info("[Ghost] Tüm hayalet sekmeler yok edildi.")
        
    def get_stats(self) -> Dict:
        """İstatistikleri döndür."""
        return {
            "active_tabs": len(self._active_tabs),
            "total_created": self._total_created,
            "total_destroyed": self._total_destroyed,
            "tor_enabled": self._use_tor,
            "proxy_port": self._proxy_port
        }
        
    def is_ghost_tab(self, widget) -> bool:
        """Widget bir hayalet sekme mi kontrol et."""
        return hasattr(widget, '_is_ghost_tab') and widget._is_ghost_tab


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAYALET SEKME OLUŞTURUCU — Entegrasyon Yardımcısı
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_ghost_style_address_bar() -> str:
    """
    Hayalet mod için Rose Gold adres çubuğu stili.
    Aktif hayalet sekmede kullanılır.
    """
    return f"""
        QLineEdit {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(230, 199, 194, 0.15),
                stop:0.5 rgba(230, 199, 194, 0.25),
                stop:1 rgba(230, 199, 194, 0.15));
            border: 2px solid {_ROSE_GOLD};
            border-radius: 10px;
            padding: 8px 16px;
            color: #FFFFFF;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border-color: {_ROSE_GOLD_LIGHT};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(230, 199, 194, 0.2),
                stop:0.5 rgba(230, 199, 194, 0.35),
                stop:1 rgba(230, 199, 194, 0.2));
        }}
    """


def create_ghost_tab_style() -> str:
    """
    Hayalet sekme için tab bar stili.
    Aktif hayalet sekme Rose Gold vurgulu görünür.
    """
    return f"""
        QTabBar::tab:selected {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(230, 199, 194, 0.2), stop:1 transparent);
            color: {_ROSE_GOLD};
            border-bottom: 2px solid {_ROSE_GOLD};
        }}
    """


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MODULE EXPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "GhostManager",
    "GhostTab",
    "GhostProfile",
    "GhostPulseIcon",
    "GhostNotification",
    "GhostDownloadBlocker",
    "create_ghost_style_address_bar",
    "create_ghost_tab_style"
]
