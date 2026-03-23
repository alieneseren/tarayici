"""
guardian_security.py — Visionary Guardian Hibrit Güvenlik Modülü
Çok katmanlı URL tarama ve zararlı site engelleme sistemi.

Katman 1: Yerel kara liste (SQLite) — Anında engelleme
Katman 2: Google Safe Browsing API — Gerçek zamanlı tarama
Katman 3: PhishTank API — Oltalama tespit
"""

from __future__ import annotations
import os
import json
import sqlite3
import hashlib
import logging
import time
from typing import Optional, Set, Dict, List, Tuple
from urllib.parse import urlparse, quote
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor

import config

logger = logging.getLogger("GuardianSecurity")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AESTHETIC NUDE PALETTE — Uyarı Sayfası İçin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_WHITE = "#FFFFFF"
_CREAM = "#FEFDF5"
_SOFT_BEIGE = "#F5E8E0"
_WARM_TAUPE = "#D4C4B5"
_MUTED_ROSE = "#C9A9A6"
_DANGER_RED = "#E53935"
_DANGER_LIGHT = "#FFEBEE"
_WARNING_ORANGE = "#FF9800"
_TEXT_PRIMARY = "#1A1A1A"
_TEXT_SECONDARY = "#6B6B6B"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  YEREL KARA LİSTE VERİTABANI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LocalBlacklist:
    """
    SQLite tabanlı yerel kara liste.
    Bilinen zararlı domainleri anında engeller.
    """
    
    # Varsayılan zararlı domain listesi
    DEFAULT_MALICIOUS_DOMAINS: Set[str] = {
        # Bilinen phishing siteleri
        "malware-site.com", "phishing-example.net", "fake-bank-login.com",
        "secure-paypal-login.xyz", "amazon-security-alert.tk",
        "microsoft-support-scam.ml", "facebook-login-verify.ga",
        
        # Kripto dolandırıcılık
        "free-bitcoin-generator.com", "crypto-doubler.io",
        "elon-musk-giveaway.xyz", "tesla-crypto-promo.net",
        
        # Sahte teknik destek
        "windows-error-fix.com", "virus-alert-microsoft.com",
        "apple-security-warning.net", "your-pc-infected.com",
        
        # Adware / Malware dağıtım
        "free-movie-download.xyz", "crack-software-free.net",
        "keygen-download.com", "serial-keys-free.net",
        
        # Sahte e-ticaret
        "cheap-iphone-sale.com", "discount-luxury-brand.net",
        "replica-watches-cheap.com", "fake-designer-outlet.xyz",
    }
    
    def __init__(self, db_path: Optional[str] = None):
        """Veritabanını başlat."""
        if db_path is None:
            db_path = os.path.join(config.BASE_DIR, "guardian_blacklist.db")
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._init_database()
        
    def _init_database(self):
        """Veritabanı tablolarını oluştur."""
        self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
        cursor = self._connection.cursor()
        
        # Kara liste tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                threat_type TEXT DEFAULT 'unknown',
                source TEXT DEFAULT 'local',
                added_date TEXT DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 0,
                last_hit TEXT
            )
        """)
        
        # Beyaz liste tablosu (kullanıcı istisnaları)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                added_date TEXT DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        """)
        
        # Tarama önbelleği (API çağrılarını azaltmak için)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_cache (
                url_hash TEXT PRIMARY KEY,
                is_safe INTEGER NOT NULL,
                threat_type TEXT,
                scanned_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self._connection.commit()
        
        # Varsayılan domainleri ekle
        self._populate_defaults()
        
    def _populate_defaults(self):
        """Varsayılan zararlı domainleri ekle."""
        cursor = self._connection.cursor()
        for domain in self.DEFAULT_MALICIOUS_DOMAINS:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO blacklist (domain, threat_type, source) VALUES (?, ?, ?)",
                    (domain.lower(), "malware", "builtin")
                )
            except sqlite3.Error:
                pass
        self._connection.commit()
        logger.info(f"Yerel kara liste başlatıldı: {len(self.DEFAULT_MALICIOUS_DOMAINS)} domain")
        
    def is_blacklisted(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        URL'nin kara listede olup olmadığını kontrol et.
        Döndürür: (engellendi_mi, tehdit_türü)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            
            if not domain:
                return False, None
                
            cursor = self._connection.cursor()
            
            # Önce beyaz listede mi kontrol et
            cursor.execute("SELECT 1 FROM whitelist WHERE domain = ?", (domain,))
            if cursor.fetchone():
                return False, None
                
            # Kara listede mi kontrol et
            cursor.execute(
                "SELECT threat_type FROM blacklist WHERE domain = ?",
                (domain,)
            )
            result = cursor.fetchone()
            
            if result:
                # Hit sayısını güncelle
                cursor.execute(
                    "UPDATE blacklist SET hit_count = hit_count + 1, last_hit = ? WHERE domain = ?",
                    (datetime.now().isoformat(), domain)
                )
                self._connection.commit()
                return True, result[0]
                
            # Alt domain kontrolü (örn: evil.example.com -> example.com)
            parts = domain.split(".")
            if len(parts) > 2:
                parent_domain = ".".join(parts[-2:])
                cursor.execute(
                    "SELECT threat_type FROM blacklist WHERE domain = ?",
                    (parent_domain,)
                )
                result = cursor.fetchone()
                if result:
                    return True, result[0]
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Kara liste kontrolü hatası: {e}")
            return False, None
            
    def add_to_blacklist(self, domain: str, threat_type: str = "unknown", source: str = "user"):
        """Domain'i kara listeye ekle."""
        domain = domain.lower().replace("www.", "")
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO blacklist (domain, threat_type, source) VALUES (?, ?, ?)",
                (domain, threat_type, source)
            )
            self._connection.commit()
            logger.info(f"Kara listeye eklendi: {domain} ({threat_type})")
        except sqlite3.Error as e:
            logger.error(f"Kara listeye ekleme hatası: {e}")
            
    def add_to_whitelist(self, domain: str, reason: str = ""):
        """Domain'i beyaz listeye ekle (kullanıcı istisnası)."""
        domain = domain.lower().replace("www.", "")
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO whitelist (domain, reason) VALUES (?, ?)",
                (domain, reason)
            )
            self._connection.commit()
            logger.info(f"Beyaz listeye eklendi: {domain}")
        except sqlite3.Error as e:
            logger.error(f"Beyaz listeye ekleme hatası: {e}")
            
    def remove_from_whitelist(self, domain: str):
        """Domain'i beyaz listeden kaldır."""
        domain = domain.lower().replace("www.", "")
        try:
            cursor = self._connection.cursor()
            cursor.execute("DELETE FROM whitelist WHERE domain = ?", (domain,))
            self._connection.commit()
        except sqlite3.Error as e:
            logger.error(f"Beyaz listeden kaldırma hatası: {e}")
            
    def get_cached_result(self, url: str) -> Optional[Tuple[bool, Optional[str]]]:
        """Önbellekten tarama sonucunu al (24 saat geçerli)."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT is_safe, threat_type, scanned_date FROM scan_cache WHERE url_hash = ?",
                (url_hash,)
            )
            result = cursor.fetchone()
            
            if result:
                is_safe, threat_type, scanned_date = result
                # 24 saatten eski mi kontrol et
                scan_time = datetime.fromisoformat(scanned_date)
                if datetime.now() - scan_time < timedelta(hours=24):
                    return bool(is_safe), threat_type
                    
        except Exception as e:
            logger.error(f"Önbellek okuma hatası: {e}")
        return None
        
    def cache_result(self, url: str, is_safe: bool, threat_type: Optional[str] = None):
        """Tarama sonucunu önbelleğe kaydet."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO scan_cache (url_hash, is_safe, threat_type) VALUES (?, ?, ?)",
                (url_hash, int(is_safe), threat_type)
            )
            self._connection.commit()
        except sqlite3.Error as e:
            logger.error(f"Önbellek yazma hatası: {e}")
            
    def get_stats(self) -> Dict:
        """İstatistikleri döndür."""
        cursor = self._connection.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM blacklist")
        blacklist_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM whitelist")
        whitelist_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(hit_count) FROM blacklist")
        total_blocks = cursor.fetchone()[0] or 0
        
        return {
            "blacklist_count": blacklist_count,
            "whitelist_count": whitelist_count,
            "total_blocks": total_blocks
        }
        
    def close(self):
        """Veritabanı bağlantısını kapat."""
        if self._connection:
            self._connection.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GOOGLE SAFE BROWSING API İSTEMCİSİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SafeBrowsingClient:
    """
    Google Safe Browsing API v4 istemcisi.
    NOT: Gerçek kullanım için API anahtarı gerekir.
    """
    
    API_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    
    # Tehdit türleri
    THREAT_TYPES = [
        "MALWARE",
        "SOCIAL_ENGINEERING",
        "UNWANTED_SOFTWARE",
        "POTENTIALLY_HARMFUL_APPLICATION"
    ]
    
    # Platform türleri
    PLATFORM_TYPES = ["ANY_PLATFORM", "WINDOWS", "OSX", "LINUX"]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        API istemcisini başlat.
        api_key: Google Safe Browsing API anahtarı
        """
        self._api_key = api_key or os.environ.get("GOOGLE_SAFE_BROWSING_API_KEY", "")
        self._enabled = bool(self._api_key)
        
        if not self._enabled:
            logger.warning(
                "Google Safe Browsing API anahtarı bulunamadı. "
                "GOOGLE_SAFE_BROWSING_API_KEY ortam değişkenini ayarlayın."
            )
            
    def is_enabled(self) -> bool:
        """API etkin mi?"""
        return self._enabled
        
    def check_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        URL'yi Google Safe Browsing ile kontrol et.
        Döndürür: (güvenli_mi, tehdit_türü)
        """
        if not self._enabled:
            return True, None  # API yoksa güvenli kabul et
            
        try:
            import urllib.request
            import json
            
            request_body = {
                "client": {
                    "clientId": "visionary-navigator",
                    "clientVersion": "1.0.0"
                },
                "threatInfo": {
                    "threatTypes": self.THREAT_TYPES,
                    "platformTypes": self.PLATFORM_TYPES,
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": url}]
                }
            }
            
            api_url = f"{self.API_URL}?key={self._api_key}"
            
            req = urllib.request.Request(
                api_url,
                data=json.dumps(request_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                
            # Eşleşme varsa tehlikeli
            if "matches" in data and data["matches"]:
                threat_type = data["matches"][0].get("threatType", "UNKNOWN")
                logger.warning(f"Safe Browsing uyarısı: {url} - {threat_type}")
                return False, self._translate_threat_type(threat_type)
                
            return True, None
            
        except urllib.error.HTTPError as e:
            if e.code == 400:
                logger.error("Safe Browsing API: Geçersiz istek")
            elif e.code == 403:
                logger.error("Safe Browsing API: Yetkilendirme hatası")
            else:
                logger.error(f"Safe Browsing API HTTP hatası: {e.code}")
            return True, None  # Hata durumunda güvenli kabul et
            
        except Exception as e:
            logger.error(f"Safe Browsing API hatası: {e}")
            return True, None
            
    def _translate_threat_type(self, threat_type: str) -> str:
        """Tehdit türünü Türkçe'ye çevir."""
        translations = {
            "MALWARE": "Zararlı Yazılım",
            "SOCIAL_ENGINEERING": "Oltalama / Sosyal Mühendislik",
            "UNWANTED_SOFTWARE": "İstenmeyen Yazılım",
            "POTENTIALLY_HARMFUL_APPLICATION": "Potansiyel Zararlı Uygulama",
            "UNKNOWN": "Bilinmeyen Tehdit"
        }
        return translations.get(threat_type, threat_type)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHISHTANK API İSTEMCİSİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PhishTankClient:
    """
    PhishTank API istemcisi.
    Oltalama (phishing) sitelerini tespit eder.
    """
    
    API_URL = "https://checkurl.phishtank.com/checkurl/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        API istemcisini başlat.
        api_key: PhishTank API anahtarı (opsiyonel, anonim kullanım da mümkün)
        """
        self._api_key = api_key or os.environ.get("PHISHTANK_API_KEY", "")
        
    def check_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        URL'yi PhishTank ile kontrol et.
        Döndürür: (güvenli_mi, tehdit_türü)
        """
        try:
            import urllib.request
            import urllib.parse
            
            # POST verileri hazırla
            data = urllib.parse.urlencode({
                "url": url,
                "format": "json",
                "app_key": self._api_key
            }).encode("utf-8")
            
            req = urllib.request.Request(
                self.API_URL,
                data=data,
                headers={
                    "User-Agent": "phishtank/visionary-navigator"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                
            # Sonuçları kontrol et
            if result.get("results", {}).get("in_database"):
                if result["results"].get("valid"):
                    logger.warning(f"PhishTank uyarısı: {url} - Oltalama sitesi")
                    return False, "Oltalama Sitesi (Phishing)"
                    
            return True, None
            
        except urllib.error.HTTPError as e:
            logger.error(f"PhishTank API HTTP hatası: {e.code}")
            return True, None
            
        except Exception as e:
            logger.error(f"PhishTank API hatası: {e}")
            return True, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TARAMA WORKER THREAD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScanWorker(QObject):
    """
    Arka planda URL taraması yapan worker.
    UI'ı dondurmadan güvenlik kontrolleri yapar.
    """
    
    # Sinyaller
    scan_complete = pyqtSignal(str, bool, str)  # (url, is_safe, threat_type)
    
    def __init__(
        self,
        url: str,
        blacklist: LocalBlacklist,
        safe_browsing: SafeBrowsingClient,
        phishtank: PhishTankClient
    ):
        super().__init__()
        self._url = url
        self._blacklist = blacklist
        self._safe_browsing = safe_browsing
        self._phishtank = phishtank
        
    def run(self):
        """Tarama işlemini başlat."""
        url = self._url
        
        # Katman 1: Yerel kara liste (anında)
        is_blocked, threat_type = self._blacklist.is_blacklisted(url)
        if is_blocked:
            self.scan_complete.emit(url, False, threat_type or "Kara Listede")
            return
            
        # Önbellekte var mı kontrol et
        cached = self._blacklist.get_cached_result(url)
        if cached is not None:
            is_safe, threat_type = cached
            self.scan_complete.emit(url, is_safe, threat_type or "")
            return
            
        # Katman 2: Google Safe Browsing
        is_safe, threat_type = self._safe_browsing.check_url(url)
        if not is_safe:
            self._blacklist.cache_result(url, False, threat_type)
            # Domain'i kara listeye ekle
            parsed = urlparse(url)
            self._blacklist.add_to_blacklist(parsed.netloc, threat_type, "safe_browsing")
            self.scan_complete.emit(url, False, threat_type)
            return
            
        # Katman 3: PhishTank
        is_safe, threat_type = self._phishtank.check_url(url)
        if not is_safe:
            self._blacklist.cache_result(url, False, threat_type)
            parsed = urlparse(url)
            self._blacklist.add_to_blacklist(parsed.netloc, threat_type, "phishtank")
            self.scan_complete.emit(url, False, threat_type)
            return
            
        # Tüm kontroller geçti
        self._blacklist.cache_result(url, True)
        self.scan_complete.emit(url, True, "")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ÖZEL UYARI SAYFASI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GuardianWarningPage(QWidget):
    """
    Aesthetic tasarımlı güvenlik uyarı sayfası.
    Zararlı site tespit edildiğinde gösterilir.
    """
    
    # Sinyaller
    go_back_clicked = pyqtSignal()
    proceed_anyway_clicked = pyqtSignal(str)  # URL
    
    def __init__(self, url: str, threat_type: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._threat_type = threat_type
        self._build_ui()
        
    def _build_ui(self):
        """UI bileşenlerini oluştur."""
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {_CREAM}, stop:1 {_SOFT_BEIGE});
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(30)
        
        # Ana kart
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_WHITE};
                border: 2px solid {_DANGER_RED};
                border-radius: 30px;
            }}
        """)
        
        # Gölge efekti
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(229, 57, 53, 60))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(50, 50, 50, 50)
        card_layout.setSpacing(25)
        
        # Uyarı ikonu
        icon_label = QLabel("🛡️")
        icon_label.setStyleSheet("font-size: 72px; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        # Başlık
        title = QLabel("⚠️ Güvenlik Uyarısı")
        title.setStyleSheet(f"""
            QLabel {{
                color: {_DANGER_RED};
                font-size: 28px;
                font-weight: 700;
                background: transparent;
            }}
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)
        
        # Açıklama
        desc = QLabel(
            "Visionary Guardian bu siteyi <b>tehlikeli</b> olarak işaretledi.\n"
            "Devam etmeniz önerilmez."
        )
        desc.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 16px;
                line-height: 1.6;
                background: transparent;
            }}
        """)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc)
        
        # Tehdit bilgi kutusu
        threat_box = QFrame()
        threat_box.setStyleSheet(f"""
            QFrame {{
                background: {_DANGER_LIGHT};
                border: 1px solid {_DANGER_RED};
                border-radius: 15px;
                padding: 5px;
            }}
        """)
        threat_layout = QVBoxLayout(threat_box)
        threat_layout.setContentsMargins(20, 15, 20, 15)
        threat_layout.setSpacing(10)
        
        # Tehdit türü
        threat_type_label = QLabel(f"🔴 Tespit Edilen Tehdit: {self._threat_type}")
        threat_type_label.setStyleSheet(f"""
            QLabel {{
                color: {_DANGER_RED};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        threat_layout.addWidget(threat_type_label)
        
        # URL
        url_label = QLabel(f"📍 URL: {self._url[:80]}{'...' if len(self._url) > 80 else ''}")
        url_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 12px;
                font-family: monospace;
                background: transparent;
            }}
        """)
        url_label.setWordWrap(True)
        threat_layout.addWidget(url_label)
        
        card_layout.addWidget(threat_box)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        
        # Geri dön butonu (ana buton)
        back_btn = QPushButton("← Güvenli Sayfaya Dön")
        back_btn.setFixedSize(220, 50)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_DANGER_RED};
                color: {_WHITE};
                border: none;
                border-radius: 25px;
                font-size: 15px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #C62828;
            }}
        """)
        back_btn.clicked.connect(self.go_back_clicked.emit)
        btn_layout.addWidget(back_btn)
        
        # Yine de devam et butonu (gizli tehlike)
        proceed_btn = QPushButton("Yine de Devam Et")
        proceed_btn.setFixedSize(180, 50)
        proceed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        proceed_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_TEXT_SECONDARY};
                border: 1px solid {_WARM_TAUPE};
                border-radius: 25px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {_SOFT_BEIGE};
                color: {_TEXT_PRIMARY};
            }}
        """)
        proceed_btn.clicked.connect(lambda: self.proceed_anyway_clicked.emit(self._url))
        btn_layout.addWidget(proceed_btn)
        
        card_layout.addLayout(btn_layout)
        
        # Bilgi notu
        info_note = QLabel(
            "💡 Bu sayfa Visionary Guardian tarafından korunmaktadır.\n"
            "Şüpheli siteleri engellemek cihazınızı ve verilerinizi korur."
        )
        info_note.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 12px;
                background: transparent;
            }}
        """)
        info_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(info_note)
        
        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANA GÜVENLİK MOTORU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VisionaryGuardian(QObject):
    """
    Visionary Guardian — Hibrit Güvenlik Motoru
    
    Özellikler:
    - 3 katmanlı URL tarama
    - Yerel kara liste (SQLite)
    - Google Safe Browsing API
    - PhishTank API
    - Önbellekleme
    - Beyaz liste desteği
    """
    
    # Sinyaller
    url_blocked = pyqtSignal(str, str)  # (url, threat_type)
    url_allowed = pyqtSignal(str)
    scan_started = pyqtSignal(str)
    status_changed = pyqtSignal(bool)  # enabled/disabled
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._enabled = True
        
        # Bileşenler
        self._blacklist = LocalBlacklist()
        self._safe_browsing = SafeBrowsingClient()
        self._phishtank = PhishTankClient()
        
        # Aktif tarama threadleri
        self._active_scans: Dict[str, QThread] = {}
        
        # Güvenli domain listesi (taramayı atla)
        self._safe_domains: Set[str] = {
            "google.com", "google.com.tr", "youtube.com", "github.com",
            "stackoverflow.com", "microsoft.com", "apple.com",
            "amazon.com", "amazon.com.tr", "twitter.com", "x.com",
            "facebook.com", "instagram.com", "linkedin.com",
            "wikipedia.org", "reddit.com", "netflix.com",
            "trendyol.com", "hepsiburada.com", "n11.com",
            "sahibinden.com", "gittigidiyor.com",
        }
        
        logger.info("Visionary Guardian başlatıldı.")
        
    def is_enabled(self) -> bool:
        """Guardian etkin mi?"""
        return self._enabled
        
    def set_enabled(self, enabled: bool):
        """Guardian'ı etkinleştir/devre dışı bırak."""
        self._enabled = enabled
        self.status_changed.emit(enabled)
        logger.info(f"Guardian {'etkin' if enabled else 'devre dışı'}")
        
    def toggle(self) -> bool:
        """Guardian durumunu değiştir ve yeni durumu döndür."""
        self.set_enabled(not self._enabled)
        return self._enabled
        
    def should_scan(self, url: str) -> bool:
        """Bu URL taranmalı mı?"""
        if not self._enabled:
            return False
            
        try:
            parsed = urlparse(url)
            
            # Şema kontrolü
            if parsed.scheme not in ("http", "https"):
                return False
                
            # Domain kontrolü
            domain = parsed.netloc.lower().replace("www.", "")
            
            # Güvenli domainler taranmaz
            if domain in self._safe_domains:
                return False
                
            # IP adresleri taranır (genellikle şüpheli)
            # Local IP'ler hariç
            if domain.startswith("127.") or domain.startswith("192.168."):
                return False
            if domain == "localhost":
                return False
                
            return True
            
        except Exception:
            return False
            
    def check_url_sync(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        URL'yi senkron olarak kontrol et.
        Sadece yerel kara liste kontrolü yapar (hızlı).
        
        Döndürür: (güvenli_mi, tehdit_türü)
        """
        if not self._enabled:
            return True, None
            
        if not self.should_scan(url):
            return True, None
            
        # Yerel kara liste kontrolü (anında)
        is_blocked, threat_type = self._blacklist.is_blacklisted(url)
        if is_blocked:
            return False, threat_type
            
        # Önbellek kontrolü
        cached = self._blacklist.get_cached_result(url)
        if cached is not None:
            is_safe, threat_type = cached
            return is_safe, threat_type
            
        return True, None
        
    def check_url_async(self, url: str):
        """
        URL'yi asenkron olarak kontrol et.
        Tüm katmanları (API dahil) tarar.
        Sonuç url_blocked veya url_allowed sinyali ile döner.
        """
        if not self._enabled:
            self.url_allowed.emit(url)
            return
            
        if not self.should_scan(url):
            self.url_allowed.emit(url)
            return
            
        # Zaten taranıyor mu?
        if url in self._active_scans:
            return
            
        self.scan_started.emit(url)
        
        # Worker thread başlat
        thread = QThread()
        worker = ScanWorker(
            url,
            self._blacklist,
            self._safe_browsing,
            self._phishtank
        )
        worker.moveToThread(thread)
        
        # Bağlantılar
        thread.started.connect(worker.run)
        worker.scan_complete.connect(self._on_scan_complete)
        worker.scan_complete.connect(thread.quit)
        thread.finished.connect(lambda: self._cleanup_thread(url))
        
        self._active_scans[url] = thread
        thread.start()
        
    def _on_scan_complete(self, url: str, is_safe: bool, threat_type: str):
        """Tarama tamamlandığında çağrılır."""
        if is_safe:
            self.url_allowed.emit(url)
        else:
            self.url_blocked.emit(url, threat_type)
            
    def _cleanup_thread(self, url: str):
        """Thread'i temizle."""
        if url in self._active_scans:
            del self._active_scans[url]
            
    def add_to_blacklist(self, url: str, threat_type: str = "user_reported"):
        """URL'yi kara listeye ekle."""
        parsed = urlparse(url)
        self._blacklist.add_to_blacklist(parsed.netloc, threat_type, "user")
        
    def add_to_whitelist(self, url: str):
        """URL'yi beyaz listeye ekle."""
        parsed = urlparse(url)
        self._blacklist.add_to_whitelist(parsed.netloc, "Kullanıcı tarafından eklendi")
        
    def add_safe_domain(self, domain: str):
        """Domain'i güvenli listeye ekle (tarama atlanır)."""
        self._safe_domains.add(domain.lower().replace("www.", ""))
        
    def get_stats(self) -> Dict:
        """İstatistikleri döndür."""
        stats = self._blacklist.get_stats()
        stats["guardian_enabled"] = self._enabled
        stats["safe_domains_count"] = len(self._safe_domains)
        stats["active_scans"] = len(self._active_scans)
        return stats
        
    def create_warning_page(self, url: str, threat_type: str) -> GuardianWarningPage:
        """Uyarı sayfası oluştur."""
        return GuardianWarningPage(url, threat_type)
        
    def cleanup(self):
        """Kaynakları temizle."""
        # Aktif taramaları durdur
        for thread in self._active_scans.values():
            thread.quit()
            thread.wait(1000)
        self._active_scans.clear()
        
        # Veritabanını kapat
        self._blacklist.close()
        
        logger.info("Guardian kapatıldı.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MODULE EXPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "VisionaryGuardian",
    "GuardianWarningPage",
    "LocalBlacklist",
    "SafeBrowsingClient",
    "PhishTankClient",
    "ScanWorker"
]
