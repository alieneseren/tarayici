"""
Visionary Navigator — Tam Sayfa Müzik Sayfası [CYBERPUNK NEON EDITION]
Gelecekçi neon holografik temalı, Cyberpunk 2077 tarzı müzik arayüzü.
YouTube'dan arama, indirme, streaming, gömülü video izleme.
Matrix rain, neon spectrum visualizer, glitch effects.
Tüm UI metinleri ve yorumlar Türkçe'dir.
"""

import logging
import random
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl, QThread, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QSizePolicy, QSlider,
    QGraphicsDropShadowEffect, QSplitter, QStackedWidget, QComboBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

import config

logger = logging.getLogger("MusicFullPage")
logger.setLevel(logging.INFO)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CYBERPUNK RENK PALETİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_CYBER_BG = "#050510"          # Derin uzay siyahı mavi ton
_CYBER_SURFACE = "#0A0A1A"     # Panel yüzeyi
_CYBER_SURFACE2 = "#0D0D22"    # Daha açık yüzey
_CYBER_SURFACE3 = "#12122A"    # Kart arkaplanı
_CYAN = "#00FFFF"              # Birincil neon vurgu
_MAGENTA = "#FF00FF"           # İkincil neon vurgu
_CYAN_DIM = "rgba(0,255,255,0.15)"    # İnce cyan
_MAGENTA_DIM = "rgba(255,0,255,0.12)" # İnce magenta
_NEON_GREEN = "#39FF14"        # Matrix yeşili özel elementler
_TEXT_PRIMARY = "#E0E0FF"      # Hafif mavi tonlu beyaz
_TEXT_SECONDARY = "#7A7AAA"    # Soluk mavi-gri
_TEXT_TERTIARY = "#44446A"     # Koyu soluk
_GLASS_BG = "rgba(8,8,24,0.88)"       # Cam panel arkaplan
_GLASS_BORDER = "rgba(0,255,255,0.2)" # Cyan cam border
_CARD_BG = "rgba(12,12,30,0.7)"
_CARD_HOVER = "rgba(0,255,255,0.06)"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MATRIX RAIN WIDGET — Arka plan Matrix kod yağmuru
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _MatrixRainWidget(QWidget):
    """
    Arka plan Matrix kod yağmuru.
    Rastgele katakana/latin karakterler sütunlarda düşer.
    Yeşil/cyan tonlu düşük opaklık (~0.08).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setStyleSheet(f"background: {_CYBER_BG};")
        
        self._chars = "ｱｲｳｴｵｶｷｸｹｺ01ABCDEF♪♫◈◉▲▼"
        self._columns = []
        self._num_cols = 30
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(80)
        
    def showEvent(self, event):
        super().showEvent(event)
        self._init_columns()
        
    def _init_columns(self):
        """Sütunları başlat."""
        if not self.width() or not self.height():
            return
        col_width = max(20, self.width() // self._num_cols)
        self._columns = []
        for i in range(self._num_cols):
            col = {
                'x': i * col_width,
                'y': random.randint(-200, 0),
                'speed': random.uniform(2, 6),
                'chars': [random.choice(self._chars) for _ in range(15)],
            }
            self._columns.append(col)
    
    def _animate(self):
        """Animasyon adımı."""
        if not self._columns:
            return
        for col in self._columns:
            col['y'] += col['speed']
            if col['y'] > self.height() + 100:
                col['y'] = -100
                col['chars'] = [random.choice(self._chars) for _ in range(15)]
        self.update()
    
    def paintEvent(self, event):
        """QPainter ile düşen karakterleri çiz."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        font = QFont("Courier", 12)
        painter.setFont(font)
        
        for col in self._columns:
            x = col['x']
            y = col['y']
            for i, char in enumerate(col['chars']):
                char_y = int(y + i * 20)
                if 0 <= char_y <= self.height():
                    # Fade efekti: üsttekiler parlak, alttakiler soluk
                    alpha = max(5, int(255 * (1 - i / len(col['chars']))))
                    if i == 0:
                        # En üstteki karakter en parlak (yeşil)
                        painter.setPen(QColor(0, 255, 255, min(alpha, 180)))
                    else:
                        painter.setPen(QColor(0, 255, 200, min(alpha // 2, 50)))
                    painter.drawText(x, char_y, char)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NEON SPECTRUM WIDGET — Ses spektrum görselleştiricisi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _NeonSpectrumWidget(QWidget):
    """
    Ses spektrum görselleştiricisi ~32 çubuklu.
    QMediaPlayer ham ses vermediği için reaktiviteyi simüle eder:
    - Müzik çalarken: çubuklar rastgele yüksekliklerle animasyonludur
    - Duraklatıldığında: çubuklar yavaşça minimuma iner
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet("background: transparent;")
        
        self._num_bars = 32
        self._bar_heights = np.zeros(self._num_bars)
        self._target_heights = np.zeros(self._num_bars)
        self._is_playing = False
        self._activity_counter = 0
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)  # 20 FPS
        
    def set_playing(self, playing: bool):
        """Çalma durumu ayarla."""
        self._is_playing = playing
        
    def _animate(self):
        """Animasyon adımı."""
        if self._is_playing:
            # Yeni hedefler oluştur (merkez yüksek, kenarlar alçak)
            if random.random() < 0.3:  # %30 şans her karede
                for i in range(self._num_bars):
                    # Gaussian dağılım: merkez yüksek
                    center_factor = 1.0 - abs(i - self._num_bars / 2) / (self._num_bars / 2)
                    base = 0.2 + center_factor * 0.6
                    self._target_heights[i] = base + random.uniform(-0.15, 0.15)
                    self._target_heights[i] = np.clip(self._target_heights[i], 0.1, 1.0)
        else:
            # Duraklatıldı: hedefleri minimuma indir
            self._target_heights *= 0.95
            
        # Mevcut yükseklikleri hedefe doğru yumuşat (lerp)
        self._bar_heights += (self._target_heights - self._bar_heights) * 0.15
        self.update()
        
    def paintEvent(self, event):
        """QPainter ile neon çubukları çiz."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        bar_width = width / self._num_bars
        
        for i in range(self._num_bars):
            bar_height = self._bar_heights[i] * height * 0.8
            x = i * bar_width
            y = height - bar_height
            
            # Gradient: alt cyan → üst magenta
            gradient = QLinearGradient(x, height, x, y)
            gradient.setColorAt(0, QColor(0, 255, 255, 200))
            gradient.setColorAt(1, QColor(255, 0, 255, 200))
            
            # Glow efekti: önce geniş soluk çubuk (glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 255, 255, 30)))
            painter.drawRect(int(x - 2), int(y), int(bar_width + 4), int(bar_height))
            
            # Sonra keskin renkli çubuk
            painter.setBrush(QBrush(gradient))
            painter.drawRect(int(x + 1), int(y), int(bar_width - 2), int(bar_height))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLITCH OVERLAY — Glitch efekti
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _GlitchOverlay(QWidget):
    """
    Saydam overlay widget en üstte.
    Tetiklendiğinde hızlı flaş: 3 hızlı kare (50ms) kaydırılmış renkli çubuklar.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")
        self.hide()
        
        self._bars = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_glitch)
        self._frame = 0
        
    def trigger_glitch(self):
        """Glitch efektini tetikle."""
        self._frame = 0
        self._bars = []
        for _ in range(4):
            bar = {
                'y': random.randint(0, self.height() - 50),
                'height': random.randint(20, 80),
                'offset': random.randint(-10, 10),
            }
            self._bars.append(bar)
        self.show()
        self.raise_()
        self._timer.start(50)
        
    def _advance_glitch(self):
        """Glitch animasyonu ilerlet."""
        self._frame += 1
        self.update()
        if self._frame >= 3:
            self._timer.stop()
            self.hide()
            
    def paintEvent(self, event):
        """Glitch çubuklarını çiz."""
        if not self._bars:
            return
        painter = QPainter(self)
        for bar in self._bars:
            y = bar['y']
            h = bar['height']
            offset = bar['offset']
            # Cyan bar
            painter.fillRect(offset, y, self.width(), h, QColor(0, 255, 255, 80))
            # Magenta bar offset
            painter.fillRect(offset + 5, y + 2, self.width(), h, QColor(255, 0, 255, 60))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NEON BUTTON — Tekrar kullanılabilir neon-glow butonu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _NeonButton(QPushButton):
    """
    Neon glow efektli buton.
    Hover'da glow yoğunlaşır.
    """
    def __init__(self, text="", color=_CYAN, parent=None):
        super().__init__(text, parent)
        self._color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Varsayılan glow
        self._glow = QGraphicsDropShadowEffect()
        self._glow.setBlurRadius(10)
        self._glow.setColor(QColor(color))
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)
        
    def _ensure_glow(self):
        """Glow efekti silinmişse yeniden oluştur."""
        try:
            self._glow.blurRadius()  # erişilebilir mi kontrol et
        except RuntimeError:
            self._glow = QGraphicsDropShadowEffect()
            self._glow.setBlurRadius(10)
            self._glow.setColor(QColor(self._color))
            self._glow.setOffset(0, 0)
            self.setGraphicsEffect(self._glow)

    def enterEvent(self, event):
        """Hover: glow yoğunlaştır."""
        self._ensure_glow()
        self._glow.setBlurRadius(20)
        c = QColor(self._color)
        c.setAlpha(200)
        self._glow.setColor(c)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Hover bitir: glow azalt."""
        self._ensure_glow()
        self._glow.setBlurRadius(10)
        c = QColor(self._color)
        c.setAlpha(150)
        self._glow.setColor(c)
        super().leaveEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Video Stream Worker — yt-dlp arka plan thread
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _VideoStreamWorker(QThread):
    """yt-dlp ile video stream URL'si çözer (arka plan thread)."""
    stream_ready = pyqtSignal(str, str)   # (stream_url, title)
    error = pyqtSignal(str)

    def __init__(self, youtube_url: str, title: str = ""):
        super().__init__()
        self._url = youtube_url
        self._title = title

    def run(self):
        try:
            import yt_dlp
            opts = {
                'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._url, download=False)
                title = self._title or info.get('title', 'Video')
                url = info.get('url', '')
                if not url:
                    fmts = info.get('formats', [])
                    for f in reversed(fmts):
                        if (f.get('url') and
                                f.get('vcodec', 'none') != 'none' and
                                f.get('acodec', 'none') != 'none'):
                            url = f['url']
                            break
                    if not url and fmts:
                        url = fmts[-1].get('url', '')
                if url:
                    self.stream_ready.emit(url, title)
                else:
                    self.error.emit("Video stream URL alınamadı")
        except Exception as e:
            self.error.emit(str(e)[:80])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tam Ekran Video Penceresi — Cyberpunk themed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _FullScreenVideoWindow(QWidget):
    """
    Tam ekran video penceresi. Video çıkışını devralır,
    üzerine otomatik gizlenen kontrol çubuğu koyar.
    """
    closed = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet(f"background: {_CYBER_BG};")
        self.setMouseTracking(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Tam ekran video widget
        self._video_widget_fs = QVideoWidget()
        self._video_widget_fs.setStyleSheet(f"background: {_CYBER_BG};")
        self._video_widget_fs.setMouseTracking(True)
        lay.addWidget(self._video_widget_fs, 1)

        # Alt overlay kontrol çubuğu — cyberpunk glass
        self._overlay = QFrame(self)
        self._overlay.setFixedHeight(70)
        self._overlay.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-top: 2px solid {_CYAN};
            }}
        """)
        overlay_lay = QHBoxLayout(self._overlay)
        overlay_lay.setContentsMargins(20, 6, 20, 10)
        overlay_lay.setSpacing(16)

        # Çıkış butonu — neon red
        exit_btn = _NeonButton("✕  Çık", "#FF0055")
        exit_btn.setFixedHeight(34)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,0,85,0.15); 
                border: 1px solid rgba(255,0,85,0.3);
                border-radius: 17px; 
                font-size: 12px; 
                font-weight: 600;
                color: {_TEXT_PRIMARY}; 
                padding: 0 16px;
            }}
            QPushButton:hover {{ 
                background: rgba(255,0,85,0.3); 
                border-color: rgba(255,0,85,0.6); 
            }}
        """)
        exit_btn.clicked.connect(self.exit_fullscreen)

        info_lbl = QLabel("ESC — Tam ekrandan çık  |  SPACE — Oynat/Duraklat")
        info_lbl.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 11px; background: transparent;")

        overlay_lay.addWidget(exit_btn)
        overlay_lay.addStretch()
        overlay_lay.addWidget(info_lbl)

        # Otomatik gizleme zamanlayıcısı
        self._hide_timer = QTimer(self)
        self._hide_timer.setInterval(3000)
        self._hide_timer.timeout.connect(self._hide_overlay)

        lay.addWidget(self._overlay)
        self._overlay.hide()

    def video_widget(self):
        """Tam ekran video widget'ını döndür."""
        return self._video_widget_fs

    def keyPressEvent(self, event):
        """ESC ile tam ekrandan çık."""
        if event.key() == Qt.Key.Key_Escape:
            self.exit_fullscreen()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        """Fare hareketi ile overlay'i göster."""
        self._overlay.show()
        self._hide_timer.start()
        super().mouseMoveEvent(event)

    def _hide_overlay(self):
        """Overlay'i gizle."""
        self._overlay.hide()

    def exit_fullscreen(self):
        """Tam ekrandan çık."""
        self.hide()
        self.closed.emit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MUSIC FULL PAGE — Ana widget (Cyberpunk Edition)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MusicFullPage(QWidget):
    """
    Ana müzik sayfası widget'ı.
    YouTube arama, indirme, streaming, video oynatma.
    Cyberpunk neon holografik tema.
    """
    open_in_browser = pyqtSignal(str)
    _is_music_fullpage = True

    def __init__(self):
        super().__init__()
        self._browser = None
        
        # Oynatma durumu
        self._playing_url = ""
        self._playing_title = ""
        self._is_playing = False
        self._current_position = 0
        self._current_duration = 0
        self._seeking = False
        
        # Video durumu
        self._video_url = ""
        self._video_title = ""
        self._video_position = 0
        self._video_duration = 0
        self._video_seeking = False
        
        # İşçiler
        self._search_worker = None
        self._stream_worker = None
        self._download_worker = None
        
        # Animasyonlar
        self._breath_anims = []
        self._glow_timer = None
        
        # UI bileşenleri
        self._matrix_rain = None
        self._glitch_overlay = None
        self._spectrum = None
        
        self._setup_ui()

    def set_browser(self, browser):
        """Tarayıcı referansı ayarla."""
        self._browser = browser

    def cleanup(self):
        """Temizlik: worker'ları ve timer'ları durdur."""
        # Worker'ları durdur
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.terminate()
            self._search_worker.wait()
        if self._stream_worker and self._stream_worker.isRunning():
            self._stream_worker.terminate()
            self._stream_worker.wait()
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.terminate()
            self._download_worker.wait()
            
        # Animasyon timer'larını durdur
        if self._glow_timer:
            self._glow_timer.stop()
        for anim in self._breath_anims:
            if anim:
                anim.stop()
                
        # Matrix rain timer
        if self._matrix_rain:
            self._matrix_rain._timer.stop()
            
        # Spectrum timer
        if self._spectrum:
            self._spectrum._timer.stop()

    def _setup_ui(self):
        """Ana UI kurulumu."""
        self.setStyleSheet(f"background: {_CYBER_BG};")
        
        # Ana layout
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        # Matrix rain arka plan
        self._matrix_rain = _MatrixRainWidget(self)
        self._matrix_rain.lower()
        
        # İçerik container
        content = QWidget()
        content_lay = QHBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)
        
        # Sol sidebar (270px)
        self._sidebar = self._build_sidebar()
        content_lay.addWidget(self._sidebar)
        
        # Sağ ana içerik
        right_area = QWidget()
        right_lay = QVBoxLayout(right_area)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)
        
        # Arama başlığı + URL bar
        search_header = self._build_search_header()
        right_lay.addWidget(search_header)
        
        # Spectrum visualizer
        self._spectrum = _NeonSpectrumWidget()
        right_lay.addWidget(self._spectrum)
        
        # Durum etiketi
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"""
            color: {_TEXT_SECONDARY}; 
            font-size: 11px; 
            padding: 8px 20px;
            background: transparent;
        """)
        right_lay.addWidget(self._status_lbl)
        
        # Sonuçlar / Video stacked
        self._stacked = QStackedWidget()
        self._stacked.setStyleSheet("background: transparent;")
        
        # Sayfa 0: Arama sonuçları
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {_CYBER_SURFACE};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {_CYAN_DIM};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_CYAN};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(20, 10, 20, 20)
        self._results_layout.setSpacing(8)
        self._results_scroll.setWidget(self._results_container)
        self._stacked.addWidget(self._results_scroll)
        
        # Sayfa 1: Video oynatıcı
        video_page = self._build_video_page()
        self._stacked.addWidget(video_page)
        
        right_lay.addWidget(self._stacked, 1)
        
        # Now playing bar
        now_playing = self._build_now_playing_bar()
        right_lay.addWidget(now_playing)
        
        content_lay.addWidget(right_area, 1)
        
        main_lay.addWidget(content, 1)
        
        # Glitch overlay en üstte
        self._glitch_overlay = _GlitchOverlay(self)
        
        # Başlangıç: trend müzikleri yükle
        QTimer.singleShot(300, self._load_trends)
        
        # Glow pulse animasyonu başlat
        self._start_glow_pulse()

    def _build_sidebar(self):
        """Sol sidebar — Kütüphane, Playlists."""
        sidebar = QFrame()
        sidebar.setFixedWidth(270)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {_CYBER_SURFACE};
                border-right: 2px solid {_CYAN};
            }}
        """)
        
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        
        # Header — KÜTÜPHANE
        header = QLabel("⟨⟩ KÜTÜPHANE")
        header.setStyleSheet(f"""
            color: {_CYAN};
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 2px;
            padding: 20px 16px 10px 16px;
            background: transparent;
        """)
        # Glow efekti
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(15)
        glow.setColor(QColor(_CYAN))
        glow.setOffset(0, 0)
        header.setGraphicsEffect(glow)
        lay.addWidget(header)
        
        # Alt çizgi gradient
        underline = QFrame()
        underline.setFixedHeight(3)
        underline.setStyleSheet(f"""
            background: qlineargradient(x1:0, x2:1, 
                stop:0 {_CYAN}, 
                stop:1 {_MAGENTA});
            border-radius: 1px;
        """)
        lay.addWidget(underline)
        
        lay.addSpacing(10)
        
        # Navigasyon butonları — Trendler / İndirilenler / Kütüphane
        nav_container = QWidget()
        nav_lay = QHBoxLayout(nav_container)
        nav_lay.setContentsMargins(12, 0, 12, 0)
        nav_lay.setSpacing(8)
        
        btn_trend = self._create_nav_button("🔥 Trendler")
        btn_trend.clicked.connect(self._load_trends)
        nav_lay.addWidget(btn_trend)
        
        btn_downloads = self._create_nav_button("📥 İndirilenler")
        btn_downloads.clicked.connect(self._refresh_library)
        nav_lay.addWidget(btn_downloads)
        
        lay.addWidget(nav_container)
        lay.addSpacing(10)
        
        # Kütüphane scroll
        self._lib_scroll = QScrollArea()
        self._lib_scroll.setWidgetResizable(True)
        self._lib_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._lib_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {_CYBER_SURFACE2};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {_CYAN_DIM};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_CYAN};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._lib_container = QWidget()
        self._lib_layout = QVBoxLayout(self._lib_container)
        self._lib_layout.setContentsMargins(12, 5, 12, 10)
        self._lib_layout.setSpacing(6)
        self._lib_scroll.setWidget(self._lib_container)
        lay.addWidget(self._lib_scroll, 1)
        
        # Playlist başlığı
        pl_header = QLabel("⟨⟩ PLAYLISTLER")
        pl_header.setStyleSheet(f"""
            color: {_MAGENTA};
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 10px 16px 5px 16px;
            background: transparent;
        """)
        lay.addWidget(pl_header)
        
        # Playlist scroll
        self._pl_scroll = QScrollArea()
        self._pl_scroll.setWidgetResizable(True)
        self._pl_scroll.setFixedHeight(120)
        self._pl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pl_scroll.setStyleSheet(self._lib_scroll.styleSheet())
        self._pl_container = QWidget()
        self._pl_layout = QVBoxLayout(self._pl_container)
        self._pl_layout.setContentsMargins(12, 5, 12, 10)
        self._pl_layout.setSpacing(6)
        self._pl_scroll.setWidget(self._pl_container)
        lay.addWidget(self._pl_scroll)
        
        # İlk yükleme
        self._refresh_library()
        self._refresh_playlists()
        
        return sidebar

    def _create_nav_button(self, text):
        """Navigasyon butonu oluştur."""
        btn = _NeonButton(text, _CYAN)
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CARD_BG};
                border: 1px solid {_CYAN_DIM};
                border-radius: 6px;
                color: {_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {_CARD_HOVER};
                border-color: {_CYAN};
            }}
        """)
        return btn

    def _build_search_header(self):
        """Arama başlığı — floating glass panel."""
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 12px;
                margin: 15px;
            }}
        """)
        
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 15, 20, 15)
        lay.setSpacing(12)
        
        # Başlık
        title = QLabel("⟨ CYBER MUSIC ⟩")
        title.setStyleSheet(f"""
            color: {_CYAN};
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 3px;
            background: transparent;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Glow
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(_CYAN))
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)
        lay.addWidget(title)
        
        # Arama satırı
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("YouTube'da ara...")
        self._search_input.setFixedHeight(40)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_CYBER_SURFACE2};
                border: 2px solid {_CYAN_DIM};
                border-radius: 20px;
                color: {_TEXT_PRIMARY};
                font-size: 13px;
                padding: 0 16px;
            }}
            QLineEdit:focus {{
                border-color: {_CYAN};
            }}
        """)
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input, 1)
        
        search_btn = _NeonButton("🔍 ARA", _CYAN)
        search_btn.setFixedSize(100, 40)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, x2:1, 
                    stop:0 {_CYAN}, 
                    stop:1 {_MAGENTA});
                border: none;
                border-radius: 20px;
                color: {_CYBER_BG};
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, x2:1, 
                    stop:0 {_MAGENTA}, 
                    stop:1 {_CYAN});
            }}
        """)
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        
        lay.addLayout(search_row)
        
        # URL indirme satırı
        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        
        url_lbl = QLabel("URL:")
        url_lbl.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        url_row.addWidget(url_lbl)
        
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Doğrudan YouTube URL'si...")
        self._url_input.setFixedHeight(32)
        self._url_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_CYBER_SURFACE2};
                border: 1px solid {_CYAN_DIM};
                border-radius: 16px;
                color: {_TEXT_PRIMARY};
                font-size: 11px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border-color: {_MAGENTA};
            }}
        """)
        self._url_input.returnPressed.connect(self._download_url)
        url_row.addWidget(self._url_input, 1)
        
        dl_btn = _NeonButton("⬇ İNDİR", _NEON_GREEN)
        dl_btn.setFixedSize(90, 32)
        dl_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(57,255,20,0.15);
                border: 1px solid {_NEON_GREEN};
                border-radius: 16px;
                color: {_NEON_GREEN};
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(57,255,20,0.3);
            }}
        """)
        dl_btn.clicked.connect(self._download_url)
        url_row.addWidget(dl_btn)
        
        lay.addLayout(url_row)
        
        return container

    def _build_now_playing_bar(self):
        """Alt now playing bar — glass panel."""
        container = QFrame()
        container.setFixedHeight(100)
        container.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-top: 2px solid transparent;
                border-image: linear-gradient(90deg, {_CYAN} 0%, {_MAGENTA} 100%) 1;
            }}
        """)
        
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(8)
        
        # Üst satır: kontroller
        top_row = QHBoxLayout()
        top_row.setSpacing(15)
        
        # Önceki
        self._prev_btn = _NeonButton("⏮", _MAGENTA)
        self._prev_btn.setFixedSize(40, 40)
        self._prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYBER_SURFACE2};
                border: 2px solid {_MAGENTA_DIM};
                border-radius: 20px;
                color: {_MAGENTA};
                font-size: 16px;
            }}
            QPushButton:hover {{
                border-color: {_MAGENTA};
                background: {_CARD_HOVER};
            }}
        """)
        self._prev_btn.clicked.connect(self._on_prev)
        top_row.addWidget(self._prev_btn)
        
        # Oynat/Duraklat — pulsing glow
        self._play_btn = _NeonButton("▶", _CYAN)
        self._play_btn.setFixedSize(50, 50)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYAN};
                border: none;
                border-radius: 25px;
                color: {_CYBER_BG};
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_MAGENTA};
            }}
        """)
        self._play_btn.clicked.connect(self._toggle_play)
        # Pulsing glow için özel effect
        self._play_glow = QGraphicsDropShadowEffect()
        self._play_glow.setBlurRadius(12)
        self._play_glow.setColor(QColor(_CYAN))
        self._play_glow.setOffset(0, 0)
        self._play_btn.setGraphicsEffect(self._play_glow)
        top_row.addWidget(self._play_btn)
        
        # Sonraki
        self._next_btn = _NeonButton("⏭", _MAGENTA)
        self._next_btn.setFixedSize(40, 40)
        self._next_btn.setStyleSheet(self._prev_btn.styleSheet())
        self._next_btn.clicked.connect(self._on_next)
        top_row.addWidget(self._next_btn)
        
        top_row.addSpacing(10)
        
        # Şarkı bilgisi
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        
        self._np_title = QLabel("Şarkı seçilmedi")
        self._np_title.setStyleSheet(f"""
            color: {_TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
            background: transparent;
        """)
        info_col.addWidget(self._np_title)
        
        self._np_time = QLabel("0:00 / 0:00")
        self._np_time.setStyleSheet(f"""
            color: {_TEXT_TERTIARY};
            font-size: 10px;
            background: transparent;
        """)
        info_col.addWidget(self._np_time)
        
        top_row.addLayout(info_col, 1)
        
        # Ses kontrolü
        vol_lbl = QLabel("🔊")
        vol_lbl.setStyleSheet(f"color: {_MAGENTA}; background: transparent;")
        top_row.addWidget(vol_lbl)
        
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(100)
        self._vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_CYBER_SURFACE2};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {_MAGENTA};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {_MAGENTA};
                border-radius: 3px;
            }}
        """)
        self._vol_slider.valueChanged.connect(self._on_vol_changed)
        top_row.addWidget(self._vol_slider)
        
        lay.addLayout(top_row)
        
        # Alt satır: progress bar
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        
        self._prog_slider = QSlider(Qt.Orientation.Horizontal)
        self._prog_slider.setRange(0, 1000)
        self._prog_slider.setValue(0)
        self._prog_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_CYBER_SURFACE2};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {_CYAN};
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
                border: 2px solid {_CYBER_BG};
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, x2:1, 
                    stop:0 {_CYAN}, 
                    stop:1 {_MAGENTA});
                border-radius: 4px;
            }}
        """)
        self._prog_slider.sliderPressed.connect(self._on_seek_start)
        self._prog_slider.sliderReleased.connect(self._on_seek_end)
        prog_row.addWidget(self._prog_slider, 1)
        
        lay.addLayout(prog_row)
        
        # Progress güncelleyici
        self._prog_timer = QTimer(self)
        self._prog_timer.setInterval(200)
        self._prog_timer.timeout.connect(self._update_progress)
        self._prog_timer.start()
        
        return container

    def _build_video_page(self):
        """Video oynatıcı sayfası."""
        container = QWidget()
        container.setStyleSheet(f"background: {_CYBER_BG};")
        
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        
        # Üst header — geri butonu
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-bottom: 2px solid {_CYAN};
            }}
        """)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(15, 10, 15, 10)
        
        back_btn = _NeonButton("← GERİ", _CYAN)
        back_btn.setFixedSize(100, 38)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CARD_BG};
                border: 2px solid {_CYAN};
                border-radius: 19px;
                color: {_CYAN};
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_CARD_HOVER};
            }}
        """)
        back_btn.clicked.connect(self._close_video)
        header_lay.addWidget(back_btn)
        
        self._vid_title_lbl = QLabel("")
        self._vid_title_lbl.setStyleSheet(f"""
            color: {_TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
            background: transparent;
        """)
        header_lay.addWidget(self._vid_title_lbl, 1)
        
        open_browser_btn = _NeonButton("🌐 TARAYICIDA AÇ", _MAGENTA)
        open_browser_btn.setFixedSize(150, 38)
        open_browser_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CARD_BG};
                border: 2px solid {_MAGENTA};
                border-radius: 19px;
                color: {_MAGENTA};
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_CARD_HOVER};
            }}
        """)
        open_browser_btn.clicked.connect(self._open_video_in_browser)
        header_lay.addWidget(open_browser_btn)
        
        lay.addWidget(header)
        
        # Video widget
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet(f"background: {_CYBER_BG};")
        lay.addWidget(self._video_widget, 1)
        
        # Video kontrol çubuğu
        controls = QFrame()
        controls.setFixedHeight(90)
        controls.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-top: 2px solid {_MAGENTA};
            }}
        """)
        controls_lay = QVBoxLayout(controls)
        controls_lay.setContentsMargins(20, 10, 20, 10)
        controls_lay.setSpacing(8)
        
        # Seek bar
        seek_row = QHBoxLayout()
        self._vid_time_lbl = QLabel("0:00")
        self._vid_time_lbl.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        seek_row.addWidget(self._vid_time_lbl)
        
        self._vid_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._vid_seek_slider.setRange(0, 1000)
        self._vid_seek_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_CYBER_SURFACE2};
                height: 10px;
                border-radius: 5px;
            }}
            QSlider::handle:horizontal {{
                background: {_CYAN};
                width: 18px;
                height: 18px;
                margin: -4px 0;
                border-radius: 9px;
                border: 2px solid {_CYBER_BG};
            }}
            QSlider::sub-page:horizontal {{
                background: {_CYAN};
                border-radius: 5px;
            }}
        """)
        self._vid_seek_slider.sliderPressed.connect(lambda: setattr(self, '_video_seeking', True))
        self._vid_seek_slider.sliderReleased.connect(self._vid_on_seek_end)
        seek_row.addWidget(self._vid_seek_slider, 1)
        
        self._vid_dur_lbl = QLabel("0:00")
        self._vid_dur_lbl.setStyleSheet(self._vid_time_lbl.styleSheet())
        seek_row.addWidget(self._vid_dur_lbl)
        
        controls_lay.addLayout(seek_row)
        
        # Kontrol butonları
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        # Geri 10s
        bwd_btn = _NeonButton("⏪ 10s", _CYAN)
        bwd_btn.setFixedSize(80, 36)
        bwd_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYBER_SURFACE2};
                border: 2px solid {_CYAN_DIM};
                border-radius: 18px;
                color: {_CYAN};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {_CYAN};
                background: {_CARD_HOVER};
            }}
        """)
        bwd_btn.clicked.connect(lambda: self._vid_seek_rel(-10000))
        btn_row.addWidget(bwd_btn)
        
        # Oynat/Duraklat
        self._vid_play_btn = _NeonButton("▶", _CYAN)
        self._vid_play_btn.setFixedSize(50, 50)
        self._vid_play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYAN};
                border: none;
                border-radius: 25px;
                color: {_CYBER_BG};
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_MAGENTA};
            }}
        """)
        self._vid_play_btn.clicked.connect(self._vid_toggle_play)
        btn_row.addWidget(self._vid_play_btn)
        
        # İleri 10s
        fwd_btn = _NeonButton("10s ⏩", _CYAN)
        fwd_btn.setFixedSize(80, 36)
        fwd_btn.setStyleSheet(bwd_btn.styleSheet())
        fwd_btn.clicked.connect(lambda: self._vid_seek_rel(10000))
        btn_row.addWidget(fwd_btn)
        
        btn_row.addSpacing(20)
        
        # Hız kontrolü
        speed_lbl = QLabel("Hız:")
        speed_lbl.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        btn_row.addWidget(speed_lbl)
        
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self._speed_combo.setCurrentIndex(2)
        self._speed_combo.setFixedSize(80, 32)
        self._speed_combo.setStyleSheet(f"""
            QComboBox {{
                background: {_CYBER_SURFACE2};
                border: 1px solid {_CYAN_DIM};
                border-radius: 6px;
                color: {_TEXT_PRIMARY};
                font-size: 11px;
                padding: 5px;
            }}
            QComboBox:hover {{
                border-color: {_CYAN};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {_CYBER_SURFACE2};
                color: {_TEXT_PRIMARY};
                selection-background-color: {_CARD_HOVER};
            }}
        """)
        self._speed_combo.currentIndexChanged.connect(self._vid_set_speed)
        btn_row.addWidget(self._speed_combo)
        
        btn_row.addStretch()
        
        # Tam ekran
        fs_btn = _NeonButton("⛶ TAM EKRAN", _MAGENTA)
        fs_btn.setFixedSize(120, 36)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYBER_SURFACE2};
                border: 2px solid {_MAGENTA_DIM};
                border-radius: 18px;
                color: {_MAGENTA};
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {_MAGENTA};
                background: {_CARD_HOVER};
            }}
        """)
        fs_btn.clicked.connect(self._vid_toggle_fullscreen)
        btn_row.addWidget(fs_btn)
        
        controls_lay.addLayout(btn_row)
        
        lay.addWidget(controls)
        
        # Video player kurulumu
        self._video_player = QMediaPlayer()
        self._video_audio = QAudioOutput()
        self._video_player.setAudioOutput(self._video_audio)
        self._video_player.setVideoOutput(self._video_widget)
        
        # Sinyal bağlantıları
        self._video_player.playbackStateChanged.connect(self._on_video_state_changed)
        self._video_player.positionChanged.connect(self._vid_on_position_changed)
        self._video_player.durationChanged.connect(self._vid_on_duration_changed)
        
        # Tam ekran penceresi
        self._fullscreen_window = _FullScreenVideoWindow()
        self._fullscreen_window.closed.connect(self._exit_fullscreen)
        
        return container

    def _create_nav_icon_button(self, icon_text):
        """Navigasyon ikon butonu."""
        btn = _NeonButton(icon_text, _CYAN)
        btn.setFixedSize(36, 36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYBER_SURFACE2};
                border: 2px solid {_CYAN_DIM};
                border-radius: 18px;
                color: {_CYAN};
                font-size: 14px;
            }}
            QPushButton:hover {{
                border-color: {_CYAN};
                background: {_CARD_HOVER};
            }}
        """)
        return btn

    def _start_glow_pulse(self):
        """Glow pulse animasyonu başlat."""
        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(1500)
        self._glow_phase = 0
        
        def pulse():
            self._glow_phase = (self._glow_phase + 1) % 2
            if self._play_glow:
                if self._glow_phase == 0:
                    self._play_glow.setBlurRadius(12)
                else:
                    self._play_glow.setBlurRadius(20)
        
        self._glow_timer.timeout.connect(pulse)
        self._glow_timer.start()

    def _do_search(self):
        """Arama yap."""
        query = self._search_input.text().strip()
        if not query:
            return
            
        self._clear_results()
        self._status_lbl.setText(f"🔍 '{query}' aranıyor...")
        self._stacked.setCurrentIndex(0)
        
        from voice_engine import YouTubeSearchWorker
        worker = YouTubeSearchWorker(query)
        worker.results_ready.connect(self._on_search_results)
        worker.error.connect(lambda e: self._status_lbl.setText(f"⚠ {e}"))
        self._search_worker = worker
        worker.start()

    def _on_search_results(self, results):
        """Arama sonuçları geldiğinde."""
        self._clear_results()
        if not results:
            self._status_lbl.setText("Sonuç bulunamadı.")
            return
            
        self._status_lbl.setText(f"{len(results)} sonuç bulundu")
        for idx, res in enumerate(results, 1):
            self._add_result_item(idx, res)
        self._results_layout.addStretch()

    def _clear_results(self):
        """Sonuç listesini temizle."""
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_result_item(self, num, result):
        """Sonuç öğesi ekle."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border: 1px solid {_CYAN_DIM};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border-color: {_CYAN};
                background: {_CARD_HOVER};
            }}
        """)
        card.setFixedHeight(70)
        
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)
        
        # Numara badge
        num_lbl = QLabel(str(num))
        num_lbl.setFixedSize(32, 32)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setStyleSheet(f"""
            background: transparent;
            border: 2px solid {_CYAN};
            border-radius: 16px;
            color: {_CYAN};
            font-size: 13px;
            font-weight: 700;
        """)
        lay.addWidget(num_lbl)
        
        # Başlık
        title = result.get('title', 'Bilinmeyen')
        title_lbl = QLabel(title[:60] + ('...' if len(title) > 60 else ''))
        title_lbl.setStyleSheet(f"""
            color: {_TEXT_PRIMARY};
            font-size: 12px;
            font-weight: 500;
            background: transparent;
        """)
        lay.addWidget(title_lbl, 1)
        
        # Süre
        duration = result.get('duration', '')
        if duration:
            dur_lbl = QLabel(duration)
            dur_lbl.setStyleSheet(f"""
                color: {_TEXT_TERTIARY};
                font-size: 10px;
                background: transparent;
            """)
            lay.addWidget(dur_lbl)
        
        # Oynat butonu
        play_btn = _NeonButton("▶ OYNAT", _CYAN)
        play_btn.setFixedSize(90, 32)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,255,0.15);
                border: 1px solid {_CYAN};
                border-radius: 16px;
                color: {_CYAN};
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(0,255,255,0.3);
            }}
        """)
        url = result.get('url', '')
        play_btn.clicked.connect(lambda: self._play_stream(url, title))
        lay.addWidget(play_btn)
        
        # Video butonu
        vid_btn = _NeonButton("📹 VİDEO", _MAGENTA)
        vid_btn.setFixedSize(90, 32)
        vid_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,0,255,0.15);
                border: 1px solid {_MAGENTA};
                border-radius: 16px;
                color: {_MAGENTA};
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(255,0,255,0.3);
            }}
        """)
        vid_btn.clicked.connect(lambda: self._watch_video_url(url, title))
        lay.addWidget(vid_btn)
        
        # İndirme butonu
        dl_btn = _NeonButton("⬇", _NEON_GREEN)
        dl_btn.setFixedSize(36, 32)
        dl_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(57,255,20,0.15);
                border: 1px solid {_NEON_GREEN};
                border-radius: 16px;
                color: {_NEON_GREEN};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: rgba(57,255,20,0.3);
            }}
        """)
        dl_btn.clicked.connect(lambda: self._download_result(result))
        lay.addWidget(dl_btn)
        
        self._results_layout.addWidget(card)

    def _refresh_library(self):
        """Kütüphaneyi yenile."""
        while self._lib_layout.count():
            item = self._lib_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        try:
            import os
            lib_dir = os.path.join(config.MODELS_DIR, "music_library")
            if not os.path.exists(lib_dir):
                os.makedirs(lib_dir, exist_ok=True)
                
            files = [f for f in os.listdir(lib_dir) if f.endswith('.mp3')]
            
            if not files:
                lbl = QLabel("İndirilen müzik yok")
                lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 11px; padding: 10px; background: transparent;")
                self._lib_layout.addWidget(lbl)
            else:
                for idx, fname in enumerate(sorted(files), 1):
                    self._add_library_item(idx, fname)
                    
            self._lib_layout.addStretch()
        except Exception as e:
            logger.error(f"Kütüphane yenileme hatası: {e}")

    def _add_library_item(self, num, filename):
        """Kütüphane öğesi ekle."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border-left: 3px solid {_CYAN_DIM};
                border-radius: 6px;
            }}
            QFrame:hover {{
                border-left-color: {_CYAN};
                background: {_CARD_HOVER};
            }}
        """)
        card.setFixedHeight(50)
        
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)
        
        # Numara — hexagonal badge
        num_lbl = QLabel(f"#{num:02X}")
        num_lbl.setFixedSize(38, 24)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setStyleSheet(f"""
            background: {_CYBER_SURFACE3};
            border: 1px solid {_CYAN};
            border-radius: 4px;
            color: {_CYAN};
            font-size: 10px;
            font-weight: 700;
            font-family: 'Courier';
        """)
        lay.addWidget(num_lbl)
        
        # Başlık
        title = filename[:-4]  # .mp3 çıkar
        if len(title) > 25:
            title = title[:25] + "..."
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            color: {_TEXT_PRIMARY};
            font-size: 11px;
            background: transparent;
        """)
        lay.addWidget(title_lbl, 1)
        
        # Oynat butonu
        play_btn = _NeonButton("▶", _CYAN)
        play_btn.setFixedSize(28, 28)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CYAN};
                border: none;
                border-radius: 14px;
                color: {_CYBER_BG};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {_MAGENTA};
            }}
        """)
        play_btn.clicked.connect(lambda: self._play_lib_track(filename))
        lay.addWidget(play_btn)
        
        self._lib_layout.addWidget(card)

    def _refresh_playlists(self):
        """Playlist'leri yenile."""
        while self._pl_layout.count():
            item = self._pl_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Mock playlists
        playlists = [
            {"name": "Favoriler", "count": 12},
            {"name": "Chill Vibes", "count": 8},
        ]
        
        for pl in playlists:
            self._add_playlist_item(pl)
        self._pl_layout.addStretch()

    def _add_playlist_item(self, playlist):
        """Playlist öğesi ekle."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border: 1px solid {_MAGENTA_DIM};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {_MAGENTA};
                background: {_CARD_HOVER};
            }}
        """)
        card.setFixedHeight(45)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)
        
        # İkon
        icon = QLabel("♪")
        icon.setStyleSheet(f"color: {_MAGENTA}; font-size: 18px; background: transparent;")
        lay.addWidget(icon)
        
        # Başlık
        name = playlist['name']
        title_lbl = QLabel(name)
        title_lbl.setStyleSheet(f"""
            color: {_TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 500;
            background: transparent;
        """)
        lay.addWidget(title_lbl, 1)
        
        # Sayı badge
        count = playlist['count']
        count_lbl = QLabel(str(count))
        count_lbl.setFixedSize(28, 20)
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_lbl.setStyleSheet(f"""
            background: {_MAGENTA_DIM};
            border-radius: 10px;
            color: {_MAGENTA};
            font-size: 10px;
            font-weight: 700;
        """)
        lay.addWidget(count_lbl)
        
        # Clicked event — mock
        card.mousePressEvent = lambda e: self._play_playlist(name)
        
        self._pl_layout.addWidget(card)

    def _play_lib_track(self, filename):
        """Kütüphaneden track oynat."""
        import os
        path = os.path.join(config.MODELS_DIR, "music_library", filename)
        if not os.path.exists(path):
            self._status_lbl.setText(f"⚠ Dosya bulunamadı: {filename}")
            return
            
        title = filename[:-4]
        self._play_stream(path, title)

    def _play_stream(self, url, title):
        """Stream oynat."""
        if not self._browser:
            self._status_lbl.setText("⚠ Tarayıcı başlatılmamış")
            return
            
        from voice_engine import YouTubeStreamResolver
        worker = YouTubeStreamResolver(url, title)
        worker.stream_ready.connect(self._on_stream_ready)
        worker.error.connect(lambda e: self._status_lbl.setText(f"⚠ {e}"))
        self._stream_worker = worker
        worker.start()
        self._status_lbl.setText(f"⏳ Stream hazırlanıyor: {title[:40]}...")

    def _on_stream_ready(self, stream_url, title):
        """Stream hazır."""
        if not self._browser or not hasattr(self._browser, '_music_player'):
            return
            
        player = self._browser._music_player
        player.setSource(QUrl(stream_url))
        player.play()
        
        self._playing_url = stream_url
        self._playing_title = title
        self._is_playing = True
        self._update_now_playing()
        self._spectrum.set_playing(True)
        self._play_btn.setText("⏸")
        
        # Glitch efekti tetikle
        if self._glitch_overlay:
            self._glitch_overlay.trigger_glitch()
        
        self._status_lbl.setText(f"▶ Oynatılıyor: {title[:50]}")

    def _play_playlist(self, name):
        """Playlist oynat — mock."""
        self._status_lbl.setText(f"▶ Playlist oynatılıyor: {name}")

    def _toggle_play(self):
        """Oynat/Duraklat toggle."""
        if not self._browser or not hasattr(self._browser, '_music_player'):
            return
            
        player = self._browser._music_player
        if self._is_playing:
            player.pause()
            self._is_playing = False
            self._play_btn.setText("▶")
            self._spectrum.set_playing(False)
        else:
            player.play()
            self._is_playing = True
            self._play_btn.setText("⏸")
            self._spectrum.set_playing(True)

    def _on_prev(self):
        """Önceki track — mock."""
        self._status_lbl.setText("⏮ Önceki track (henüz uygulanmadı)")

    def _on_next(self):
        """Sonraki track — mock."""
        self._status_lbl.setText("⏭ Sonraki track (henüz uygulanmadı)")

    def _on_vol_changed(self, value):
        """Ses seviyesi değişti."""
        if not self._browser or not hasattr(self._browser, '_music_audio'):
            return
        self._browser._music_audio.setVolume(value / 100.0)

    def _watch_video(self, result):
        """Sonuçtan video izle."""
        url = result.get('url', '')
        title = result.get('title', 'Video')
        self._watch_video_url(url, title)

    def _watch_video_url(self, url, title):
        """URL'den video izle."""
        if not url:
            return
            
        self._video_url = url
        self._video_title = title
        self._vid_title_lbl.setText(title[:60] + ('...' if len(title) > 60 else ''))
        self._status_lbl.setText(f"⏳ Video stream hazırlanıyor...")
        
        worker = _VideoStreamWorker(url, title)
        worker.stream_ready.connect(self._on_video_stream_ready)
        worker.error.connect(self._on_video_stream_error)
        self._stream_worker = worker
        worker.start()

    def _on_video_stream_ready(self, stream_url, title):
        """Video stream hazır."""
        self._video_player.setSource(QUrl(stream_url))
        self._video_player.play()
        self._stacked.setCurrentIndex(1)
        self._status_lbl.setText("")
        
        # Glitch efekti
        if self._glitch_overlay:
            self._glitch_overlay.trigger_glitch()

    def _on_video_stream_error(self, error):
        """Video stream hatası."""
        self._status_lbl.setText(f"⚠ Video hatası: {error}")

    def _on_video_state_changed(self, state):
        """Video oynatma durumu değişti."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._vid_play_btn.setText("⏸")
        else:
            self._vid_play_btn.setText("▶")

    def _vid_on_position_changed(self, pos):
        """Video pozisyon değişti."""
        self._video_position = pos
        if not self._video_seeking and self._video_duration > 0:
            val = int((pos / self._video_duration) * 1000)
            self._vid_seek_slider.setValue(val)
        self._vid_time_lbl.setText(self._fmt(pos))

    def _vid_on_duration_changed(self, dur):
        """Video süre değişti."""
        self._video_duration = dur
        self._vid_dur_lbl.setText(self._fmt(dur))

    def _vid_on_seek_end(self):
        """Video seek bitti."""
        self._video_seeking = False
        val = self._vid_seek_slider.value()
        pos = int((val / 1000.0) * self._video_duration)
        self._video_player.setPosition(pos)

    def _vid_seek_rel(self, delta_ms):
        """Video relative seek."""
        new_pos = self._video_position + delta_ms
        new_pos = max(0, min(new_pos, self._video_duration))
        self._video_player.setPosition(new_pos)

    def _vid_toggle_play(self):
        """Video oynat/duraklat."""
        state = self._video_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._video_player.pause()
        else:
            self._video_player.play()

    def _vid_set_speed(self, idx):
        """Video hızı ayarla."""
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        self._video_player.setPlaybackRate(speeds[idx])

    def _vid_toggle_fullscreen(self):
        """Tam ekrana geç."""
        self._video_player.setVideoOutput(self._fullscreen_window.video_widget())
        self._fullscreen_window.showFullScreen()

    def _exit_fullscreen(self):
        """Tam ekrandan çık."""
        self._video_player.setVideoOutput(self._video_widget)

    def _close_video(self):
        """Video'yu kapat."""
        self._video_player.stop()
        self._stacked.setCurrentIndex(0)

    def _open_video_in_browser(self):
        """Video'yu tarayıcıda aç."""
        if self._video_url:
            self.open_in_browser.emit(self._video_url)

    def _download_url(self):
        """URL'den indir."""
        url = self._url_input.text().strip()
        if not url:
            return
        self._do_download(url, "İndirilen Müzik")

    def _download_result(self, result):
        """Sonuçtan indir."""
        url = result.get('url', '')
        title = result.get('title', 'Müzik')
        if url:
            self._do_download(url, title)

    def _do_download(self, url, title):
        """İndirmeyi başlat."""
        from voice_engine import MusicLibraryDownloader
        worker = MusicLibraryDownloader(url, title)
        worker.download_complete.connect(self._on_download_done)
        worker.error.connect(lambda e: self._status_lbl.setText(f"⚠ İndirme hatası: {e}"))
        self._download_worker = worker
        worker.start()
        self._status_lbl.setText(f"⬇ İndiriliyor: {title[:40]}...")

    def _on_download_done(self, filename):
        """İndirme tamamlandı."""
        self._status_lbl.setText(f"✅ İndirildi: {filename}")
        self._refresh_library()

    def _update_now_playing(self):
        """Now playing bilgisini güncelle."""
        if self._playing_title:
            self._np_title.setText(self._playing_title[:50] + ('...' if len(self._playing_title) > 50 else ''))
            # Cyan renk aktif
            self._np_title.setStyleSheet(f"""
                color: {_CYAN};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            """)
        else:
            self._np_title.setText("Şarkı seçilmedi")
            self._np_title.setStyleSheet(f"""
                color: {_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            """)

    def _update_progress(self):
        """Progress bar güncelle."""
        if not self._browser or not hasattr(self._browser, '_music_player'):
            return
            
        player = self._browser._music_player
        pos = player.position()
        dur = player.duration()
        
        self._current_position = pos
        self._current_duration = dur
        
        if not self._seeking and dur > 0:
            val = int((pos / dur) * 1000)
            self._prog_slider.setValue(val)
            
        self._np_time.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    def _on_seek_start(self):
        """Seek başladı."""
        self._seeking = True

    def _on_seek_end(self):
        """Seek bitti."""
        self._seeking = False
        if not self._browser or not hasattr(self._browser, '_music_player'):
            return
        val = self._prog_slider.value()
        pos = int((val / 1000.0) * self._current_duration)
        self._browser._music_player.setPosition(pos)

    def _fmt(self, ms):
        """Milisaniyeyi MM:SS formatına çevir."""
        s = int(ms / 1000)
        m = s // 60
        s = s % 60
        return f"{m}:{s:02d}"

    def showEvent(self, event):
        """Widget gösterildiğinde."""
        super().showEvent(event)
        # Matrix rain'i yeniden başlat
        if self._matrix_rain:
            self._matrix_rain._init_columns()
        # Glitch overlay'i resize
        if self._glitch_overlay:
            self._glitch_overlay.setGeometry(self.rect())

    def resizeEvent(self, event):
        """Widget resize edildiğinde."""
        super().resizeEvent(event)
        # Matrix rain'i resize
        if self._matrix_rain:
            self._matrix_rain.setGeometry(self.rect())
            self._matrix_rain._init_columns()
        # Glitch overlay'i resize
        if self._glitch_overlay:
            self._glitch_overlay.setGeometry(self.rect())

    def _load_trends(self):
        """Trend müzikleri yükle."""
        self._clear_results()
        self._stacked.setCurrentIndex(0)
        from voice_engine import YouTubeTrendWorker
        self._status_lbl.setText("🔥 Trend müzikler yükleniyor...")
        worker = YouTubeTrendWorker()
        worker.results_ready.connect(self._on_search_results)
        worker.error.connect(lambda e: self._status_lbl.setText(f"⚠ {e}"))
        self._search_worker = worker
        worker.start()
