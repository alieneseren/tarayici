"""
new_tab_page.py — Visionary Navigator New Tab Command Center
Ultra-Modern Glassmorphism Design with Responsive Layout
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QSize
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QFrame, QGraphicsDropShadowEffect, QComboBox,
    QGridLayout, QSizePolicy, QScrollArea
)

if TYPE_CHECKING:
    from browser_core import VisionaryBrowser

logger = logging.getLogger("NewTabPage")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RENK PALETİ — Ultra Modern Aesthetic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Colors:
    # Arka plan
    BG_START = "#0F0F1A"      # Koyu mor-mavi
    BG_END = "#1A1A2E"        # Biraz daha açık
    
    # Glass efekt
    GLASS = "rgba(255, 255, 255, 0.08)"
    GLASS_BORDER = "rgba(255, 255, 255, 0.15)"
    GLASS_HOVER = "rgba(255, 255, 255, 0.12)"
    
    # Metin
    TEXT_WHITE = "#FFFFFF"
    TEXT_LIGHT = "rgba(255, 255, 255, 0.9)"
    TEXT_MUTED = "rgba(255, 255, 255, 0.6)"
    TEXT_DIM = "rgba(255, 255, 255, 0.4)"
    
    # Aksanlar
    ACCENT_PURPLE = "#A855F7"  # Mor
    ACCENT_PINK = "#EC4899"    # Pembe
    ACCENT_BLUE = "#3B82F6"    # Mavi
    ACCENT_CYAN = "#06B6D4"    # Cyan
    ACCENT_GREEN = "#10B981"   # Yeşil
    
    # Gradient
    GRADIENT_PURPLE_PINK = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #A855F7, stop:1 #EC4899)"
    GRADIENT_BLUE_CYAN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #06B6D4)"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLASS CARD BASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GlassCard(QFrame):
    """Glassmorphism efektli kart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        
    def _setup_style(self):
        self.setStyleSheet(f"""
            GlassCard {{
                background: {Colors.GLASS};
                border: 1px solid {Colors.GLASS_BORDER};
                border-radius: 20px;
            }}
            GlassCard:hover {{
                background: {Colors.GLASS_HOVER};
                border: 1px solid rgba(255, 255, 255, 0.25);
            }}
        """)
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANA ARAMA ÇUBUĞU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SearchBar(QFrame):
    """Modern glassmorphism arama çubuğu."""
    
    search_requested = pyqtSignal(str, str)  # (query, engine)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchBar")
        self._setup_ui()
        
    def _setup_ui(self):
        self.setStyleSheet(f"""
            #searchBar {{
                background: {Colors.GLASS};
                border: 1px solid {Colors.GLASS_BORDER};
                border-radius: 28px;
            }}
            #searchBar:focus-within {{
                border: 1px solid {Colors.ACCENT_PURPLE};
                background: rgba(255, 255, 255, 0.12);
            }}
        """)
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(168, 85, 247, 60))  # Mor glow
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Motor seçici (Dropdown menü)
        self._engine_combo = QComboBox()
        self._engine_combo.setFixedSize(130, 44)
        self._engine_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._engine_combo.addItem("🔍  Google", "google")
        self._engine_combo.addItem("🦆  DuckDuckGo", "duckduckgo")
        self._engine_combo.addItem("Ⓑ  Bing", "bing")
        self._engine_combo.addItem("✨  Visionary", "visionary")
        self._engine_combo.setStyleSheet(f"""
            QComboBox {{
                background: rgba(168, 85, 247, 0.2);
                color: {Colors.TEXT_WHITE};
                border: none;
                border-radius: 22px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                background: rgba(168, 85, 247, 0.35);
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: #1A1A2E;
                color: {Colors.TEXT_WHITE};
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 12px;
                padding: 8px;
                selection-background-color: rgba(168, 85, 247, 0.3);
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 10px 16px;
                border-radius: 8px;
                min-height: 36px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: rgba(168, 85, 247, 0.2);
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: rgba(168, 85, 247, 0.4);
            }}
        """)
        layout.addWidget(self._engine_combo)
        
        # Arama input
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ne aramak istersiniz?")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {Colors.TEXT_WHITE};
                border: none;
                font-size: 17px;
                padding: 12px 8px;
                selection-background-color: {Colors.ACCENT_PURPLE};
            }}
            QLineEdit::placeholder {{
                color: {Colors.TEXT_DIM};
            }}
        """)
        self._input.returnPressed.connect(self._on_search)
        layout.addWidget(self._input, 1)
        
        # Arama butonu
        search_btn = QPushButton("→")
        search_btn.setFixedSize(44, 44)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.GRADIENT_PURPLE_PINK};
                color: white;
                border: none;
                border-radius: 22px;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #B66EF8, stop:1 #F05DA3);
            }}
        """)
        search_btn.clicked.connect(self._on_search)
        layout.addWidget(search_btn)
        
    def _on_search(self):
        """Arama yap."""
        query = self._input.text().strip()
        if query:
            engine = self._engine_combo.currentData()
            self.search_requested.emit(query, engine)
            
    def focus_input(self):
        """Input'a focus ver."""
        self._input.setFocus()
        self._input.selectAll()
        
    def set_text(self, text: str):
        """Input metnini ayarla."""
        self._input.setText(text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HIZLI ERİŞİM KARTLARI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class QuickAccessCard(QFrame):
    """Hızlı erişim kartı (favori siteler, müzik vb.)."""
    
    clicked = pyqtSignal()
    
    def __init__(self, icon: str, title: str, subtitle: str = "", color: str = Colors.ACCENT_PURPLE, parent=None):
        super().__init__(parent)
        self._color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui(icon, title, subtitle)
        
    def _setup_ui(self, icon: str, title: str, subtitle: str):
        self.setFixedSize(160, 100)
        self.setStyleSheet(f"""
            QuickAccessCard {{
                background: {Colors.GLASS};
                border: 1px solid {Colors.GLASS_BORDER};
                border-radius: 16px;
            }}
            QuickAccessCard:hover {{
                background: {Colors.GLASS_HOVER};
                border: 1px solid {self._color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        
        # İkon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                color: {self._color};
            }}
        """)
        layout.addWidget(icon_label)
        
        # Başlık
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_WHITE};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(title_label)
        
        # Alt başlık
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.TEXT_DIM};
                    font-size: 11px;
                }}
            """)
            layout.addWidget(sub_label)
            
        layout.addStretch()
        
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAVA DURUMU WIDGET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class WeatherWidget(GlassCard):
    """Kompakt hava durumu widget'ı."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 120)
        self._setup_ui()
        QTimer.singleShot(500, self._load_weather)
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        
        # Üst satır: Konum + İkon
        top_row = QHBoxLayout()
        
        self._location = QLabel("Konum alınıyor...")
        self._location.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 12px;
            }}
        """)
        top_row.addWidget(self._location)
        top_row.addStretch()
        
        self._icon = QLabel("🌤️")
        self._icon.setStyleSheet("font-size: 24px;")
        top_row.addWidget(self._icon)
        
        layout.addLayout(top_row)
        
        # Sıcaklık
        self._temp = QLabel("--°")
        self._temp.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_WHITE};
                font-size: 36px;
                font-weight: 300;
            }}
        """)
        layout.addWidget(self._temp)
        
        # Durum
        self._condition = QLabel("Yükleniyor...")
        self._condition.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_DIM};
                font-size: 12px;
            }}
        """)
        layout.addWidget(self._condition)
        
    def _load_weather(self):
        """Hava durumu verilerini al."""
        try:
            import requests
            
            # Konum al
            loc = requests.get("https://ipinfo.io/json", timeout=5).json()
            city = loc.get("city", "Bilinmiyor")
            coords = loc.get("loc", "0,0").split(",")
            lat, lon = float(coords[0]), float(coords[1])
            
            # Hava durumu
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather = requests.get(url, timeout=5).json()
            current = weather.get("current_weather", {})
            temp = current.get("temperature", 0)
            code = current.get("weathercode", 0)
            
            self._location.setText(f"📍 {city}")
            self._temp.setText(f"{int(temp)}°")
            self._icon.setText(self._get_icon(code))
            self._condition.setText(self._get_condition(code))
            
        except Exception as e:
            logger.warning(f"Hava durumu alınamadı: {e}")
            self._temp.setText("--°")
            self._condition.setText("Bağlantı hatası")
            
    def _get_icon(self, code: int) -> str:
        icons = {0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️",
                 51: "🌧️", 53: "🌧️", 55: "🌧️", 61: "🌧️", 63: "🌧️", 65: "🌧️",
                 71: "🌨️", 73: "🌨️", 75: "🌨️", 80: "🌧️", 81: "🌧️", 82: "🌧️",
                 95: "⛈️", 96: "⛈️", 99: "⛈️"}
        return icons.get(code, "🌤️")
        
    def _get_condition(self, code: int) -> str:
        conditions = {0: "Açık", 1: "Az bulutlu", 2: "Parçalı bulutlu", 3: "Bulutlu",
                     45: "Sisli", 48: "Puslu", 51: "Çisenti", 53: "Yağmurlu", 55: "Yoğun yağmur",
                     61: "Hafif yağmur", 63: "Yağmurlu", 65: "Şiddetli yağmur",
                     71: "Hafif kar", 73: "Karlı", 75: "Yoğun kar",
                     95: "Gök gürültülü", 96: "Dolu", 99: "Şiddetli fırtına"}
        return conditions.get(code, "Bilinmiyor")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SAAT WIDGET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ClockWidget(QWidget):
    """Büyük dijital saat."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
        # Her saniye güncelle
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
        self._update_time()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Saat
        self._time_label = QLabel("00:00")
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_WHITE};
                font-size: 72px;
                font-weight: 200;
                letter-spacing: -2px;
            }}
        """)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._time_label)
        
        # Tarih
        self._date_label = QLabel("")
        self._date_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_MUTED};
                font-size: 16px;
                font-weight: 400;
            }}
        """)
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._date_label)
        
    def _update_time(self):
        from datetime import datetime
        now = datetime.now()
        self._time_label.setText(now.strftime("%H:%M"))
        
        # Türkçe tarih
        days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        day_name = days[now.weekday()]
        month_name = months[now.month - 1]
        self._date_label.setText(f"{day_name}, {now.day} {month_name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NEW TAB PAGE — Ana Sayfa
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class NewTabPage(QWidget):
    """
    Visionary Navigator — Yeni Sekme Sayfası
    Ultra-modern glassmorphism tasarım.
    """
    
    _is_new_tab_page = True
    
    search_requested = pyqtSignal(str, str)
    open_music_page = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser: Optional[VisionaryBrowser] = None
        self._setup_ui()
        
    def set_browser(self, browser: "VisionaryBrowser"):
        self._browser = browser
        
    def _setup_ui(self):
        # Arka plan gradient
        self.setStyleSheet(f"""
            NewTabPage {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Colors.BG_START},
                    stop:0.5 {Colors.BG_END},
                    stop:1 #16162B
                );
            }}
        """)
        
        # Ana layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(0)
        
        # Üst boşluk
        main_layout.addStretch(2)
        
        # Saat
        clock = ClockWidget()
        main_layout.addWidget(clock, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addSpacing(40)
        
        # Arama çubuğu
        self._search_bar = SearchBar()
        self._search_bar.setFixedWidth(600)
        self._search_bar.setFixedHeight(60)
        self._search_bar.search_requested.connect(self._on_search)
        main_layout.addWidget(self._search_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addSpacing(50)
        
        # Hızlı erişim kartları
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Müzik kartı
        music_card = QuickAccessCard("🎵", "Müzik", "Çal ve keşfet", Colors.ACCENT_PINK)
        music_card.clicked.connect(self.open_music_page.emit)
        cards_layout.addWidget(music_card)
        
        # YouTube kartı
        youtube_card = QuickAccessCard("▶️", "YouTube", "Video izle", Colors.ACCENT_PURPLE)
        youtube_card.clicked.connect(lambda: self._open_url("https://youtube.com"))
        cards_layout.addWidget(youtube_card)
        
        # GitHub kartı
        github_card = QuickAccessCard("💻", "GitHub", "Kod paylaş", Colors.ACCENT_CYAN)
        github_card.clicked.connect(lambda: self._open_url("https://github.com"))
        cards_layout.addWidget(github_card)
        
        # Twitter kartı  
        twitter_card = QuickAccessCard("🐦", "Twitter", "Sosyal medya", Colors.ACCENT_BLUE)
        twitter_card.clicked.connect(lambda: self._open_url("https://twitter.com"))
        cards_layout.addWidget(twitter_card)
        
        main_layout.addLayout(cards_layout)
        
        main_layout.addSpacing(40)
        
        # Alt widget'lar (hava durumu)
        bottom_layout = QHBoxLayout()
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.setSpacing(20)
        
        weather = WeatherWidget()
        bottom_layout.addWidget(weather)
        
        main_layout.addLayout(bottom_layout)
        
        # Alt boşluk
        main_layout.addStretch(3)
        
        # Footer
        footer = QLabel("🛡️ Gizlilik Koruması Aktif  •  🚀 Visionary Navigator")
        footer.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_DIM};
                font-size: 11px;
            }}
        """)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(footer)
        
    def _on_search(self, query: str, engine: str):
        """Arama işle."""
        self.search_requested.emit(query, engine)
        
        # URL oluştur
        if engine == "google":
            url = f"https://www.google.com/search?q={query}"
        elif engine == "duckduckgo":
            url = f"https://duckduckgo.com/?q={query}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={query}"
        elif engine == "visionary":
            # Visionary meta-search
            if self._browser and hasattr(self._browser, '_search_manager'):
                from visionary_search import VisionarySearchPage
                page = self._browser._search_manager.search(query)
                page.link_clicked.connect(self._open_url)
                
                # Bu sekmeyi değiştir
                current_idx = self._browser._tab_widget.currentIndex()
                self._browser._tab_widget.removeTab(current_idx)
                self.deleteLater()
                
                idx = self._browser._tab_widget.addTab(page, f"🔍 {query[:15]}...")
                self._browser._tab_widget.setCurrentIndex(idx)
            return
        else:
            url = f"https://www.google.com/search?q={query}"
            
        self._open_url(url)
        
    def _open_url(self, url: str):
        """URL'yi aç."""
        if not self._browser:
            return
            
        # Mevcut new tab page'i kaldır ve yeni sekme aç
        current_idx = self._browser._tab_widget.currentIndex()
        self._browser._tab_widget.removeTab(current_idx)
        self.deleteLater()
        
        # Yeni sekme aç
        self._browser.add_new_tab(QUrl(url))
        
    def showEvent(self, event):
        """Sayfa gösterildiğinde."""
        super().showEvent(event)
        QTimer.singleShot(100, self._search_bar.focus_input)
        
    def update_music_info(self, title: str, is_playing: bool):
        """Müzik bilgisini güncelle (uyumluluk için)."""
        pass
