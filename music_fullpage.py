"""
Visionary Navigator — Tam Sayfa Müzik Sayfası [PREMIUM DARK ELEGANT]
Sofistike koyu tema, glassmorphism, violet-rose gradient vurguları.
YouTube'dan arama, indirme, streaming, gömülü video izleme.
Video ve arama sonuçları birlikte görünebilir (QSplitter).
Soft waveform visualizer, ambiance pulse effects.
Tüm UI metinleri ve yorumlar Türkçe'dir.
"""

import logging
import random
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl, QThread, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QBrush, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QSizePolicy, QSlider,
    QGraphicsDropShadowEffect, QSplitter, QComboBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

import config

logger = logging.getLogger("MusicFullPage")
logger.setLevel(logging.INFO)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PREMIUM DARK ELEGANT RENK PALETİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_BG = "#0F0F14"                    # Koyu lacivert-siyah
_BG_SECONDARY = "#161621"          # İkincil arkaplan
_SURFACE = "#1C1C2E"               # Panel yüzeyi
_SURFACE2 = "#232338"              # Hover yüzeyi
_SURFACE3 = "#2A2A42"              # Kart yüzeyi
_ACCENT = "#8B5CF6"                # Mor vurgu (Violet)
_ACCENT_LIGHT = "#A78BFA"          # Açık mor
_ACCENT_WARM = "#F59E0B"           # Amber/altın vurgu
_ACCENT_ROSE = "#EC4899"           # Rose/pembe vurgu
_TEXT_PRIMARY = "#F1F5F9"          # Beyaz-mavi
_TEXT_SECONDARY = "#94A3B8"        # Gri-mavi
_TEXT_TERTIARY = "#64748B"         # Koyu gri-mavi
_GLASS_BG = "rgba(28,28,46,0.92)"  # Cam arkaplan
_GLASS_BORDER = "rgba(139,92,246,0.2)"  # Mor cam border
_CARD_BG = "rgba(35,35,56,0.6)"
_CARD_HOVER = "rgba(139,92,246,0.08)"
_GRADIENT_START = "#8B5CF6"        # Gradient başlangıç
_GRADIENT_END = "#EC4899"          # Gradient bitiş


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SOFT WAVE WIDGET — Yumuşak dalga görselleştiricisi (Violet-Rose)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _SoftWaveWidget(QWidget):
    """
    Minimalist yumuşak dalga görselleştiricisi.
    Müzik çalarken daha büyük, durduğunda gentle idle animasyon.
    4 katmanlı translucent sine dalgaları - violet/rose gradyan renkleri.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet("background: transparent;")
        
        self._num_waves = 4
        self._wave_offsets = [0, 0.3, 0.6, 0.9]
        self._wave_heights = np.array([0.3, 0.3, 0.3, 0.3])
        self._target_heights = np.array([0.3, 0.3, 0.3, 0.3])
        self._is_playing = False
        self._time = 0
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
        
    def set_playing(self, playing: bool):
        self._is_playing = playing
        
    def _animate(self):
        self._time += 0.05
        
        if self._is_playing:
            self._target_heights = np.array([0.6, 0.5, 0.55, 0.5])
        else:
            self._target_heights = np.array([0.25, 0.2, 0.22, 0.2])
            
        self._wave_heights += (self._target_heights - self._wave_heights) * 0.1
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        
        width = self.width()
        height = self.height()
        
        # Violet-rose gradyan renk şeması
        colors = [
            QColor(139, 92, 246, 40),   # Violet
            QColor(167, 139, 250, 50),  # Light violet
            QColor(236, 72, 153, 45),   # Rose
            QColor(139, 92, 246, 35)    # Violet
        ]
        
        for idx in range(self._num_waves):
            painter.setBrush(QBrush(colors[idx]))
            path = QPainterPath()
            
            wave_h = self._wave_heights[idx]
            freq = 2.0 + idx * 0.3
            offset = self._wave_offsets[idx]
            
            points = []
            for x in range(width + 1):
                norm_x = x / width
                y_val = np.sin((norm_x * freq + self._time + offset) * 2 * np.pi)
                y = int(height / 2 + y_val * wave_h * height / 2)
                points.append((x, y))
                
            if points:
                path.moveTo(points[0][0], points[0][1])
                for x, y in points[1:]:
                    path.lineTo(x, y)
                path.lineTo(width, height)
                path.lineTo(0, height)
                path.closeSubpath()
                painter.drawPath(path)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AMBIANCE PULSE OVERLAY — Radyal gradyan pulse efekti (violet-rose)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _AmbiancePulseOverlay(QWidget):
    """
    Radyal gradient ile subtle pulse efekti (şarkı değişiminde).
    Violet-rose renkler.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")
        self._opacity = 0.0
        
    def pulse(self):
        """Pulse animasyonu başlat."""
        self._opacity = 0.6
        QTimer.singleShot(1200, lambda: self._fade_out())
        
    def _fade_out(self):
        self._opacity = 0.0
        self.update()
        
    def paintEvent(self, event):
        if self._opacity <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_x = int(w / 2)
        center_y = int(h / 2)
        radius = int(max(w, h) * 0.6)
        
        gradient = QRadialGradient(center_x, center_y, radius)
        gradient.setColorAt(0.0, QColor(139, 92, 246, int(self._opacity * 100)))
        gradient.setColorAt(0.5, QColor(236, 72, 153, int(self._opacity * 50)))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, w, h)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AESTHETIC BUTTON — Gradient hover glow efektli buton
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _AestheticButton(QPushButton):
    """
    Hover'da violet glow efekti olan estetik buton.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._glow_effect = None
        self.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 12px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
                border: 1px solid {_ACCENT};
            }}
            QPushButton:pressed {{
                background: {_SURFACE};
            }}
        """)
        
    def _ensure_glow(self):
        if self._glow_effect is None:
            self._glow_effect = QGraphicsDropShadowEffect()
            self._glow_effect.setColor(QColor(139, 92, 246, 0))
            self._glow_effect.setBlurRadius(20)
            self._glow_effect.setOffset(0, 0)
            self.setGraphicsEffect(self._glow_effect)
            
    def enterEvent(self, event):
        self._ensure_glow()
        if self._glow_effect:
            self._glow_effect.setColor(QColor(139, 92, 246, 150))
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if self._glow_effect:
            self._glow_effect.setColor(QColor(139, 92, 246, 0))
        super().leaveEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STREAM WORKER — Arka plan iş parçacığı (yt-dlp çağırır)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _StreamWorker(QThread):
    """yt-dlp ile stream URL çeker (ses veya video)."""
    stream_ready = pyqtSignal(str, str, str)  # (title, url, format_note)
    stream_error = pyqtSignal(str)
    
    def __init__(self, query: str, is_video=False):
        super().__init__()
        self.query = query
        self.is_video = is_video
        
    def run(self):
        import subprocess, json
        try:
            if self.is_video:
                # Video+Audio birleşik format (QMediaPlayer uyumlu mp4)
                cmd = [
                    "yt-dlp", 
                    "-f", "best[ext=mp4][height<=720]/bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[height<=720]",
                    "--get-url", "--get-title", "--no-playlist",
                    "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "--extractor-args", "youtube:player_client=android",
                    self.query
                ]
            else:
                cmd = [
                    "yt-dlp", "-f", "bestaudio/best", "--get-url", "--get-title",
                    "--no-playlist",
                    "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "--extractor-args", "youtube:player_client=android",
                    self.query
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                title = lines[0]
                url = lines[1]
                fmt = "Video 720p" if self.is_video else "Audio"
                self.stream_ready.emit(title, url, fmt)
            else:
                self.stream_error.emit("Stream URL alınamadı")
        except Exception as e:
            self.stream_error.emit(str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SEARCH WORKER — YouTube arama worker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _SearchWorker(QThread):
    """yt-dlp ytsearch ile arama."""
    results_ready = pyqtSignal(list)
    search_error = pyqtSignal(str)
    
    def __init__(self, query: str, max_results=20):
        super().__init__()
        self.query = query
        self.max_results = max_results
        
    def run(self):
        import subprocess, json
        try:
            cmd = [
                "yt-dlp", f"ytsearch{self.max_results}:{self.query}",
                "--dump-json", "--no-playlist", "--skip-download"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            lines = result.stdout.strip().split("\n")
            items = []
            for line in lines:
                if line:
                    try:
                        data = json.loads(line)
                        items.append({
                            "title": data.get("title", ""),
                            "url": data.get("webpage_url", ""),
                            "duration": data.get("duration", 0)
                        })
                    except:
                        pass
            self.results_ready.emit(items)
        except Exception as e:
            self.search_error.emit(str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DOWNLOAD WORKER — İndirme worker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _DownloadWorker(QThread):
    """yt-dlp ile ses dosyası indirir."""
    download_done = pyqtSignal(str, str)  # (filename, error_msg)
    
    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        
    def run(self):
        import subprocess, os
        try:
            output_template = os.path.join(self.output_dir, "%(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-f", "bestaudio/best", "-x", "--audio-format", "mp3",
                "-o", output_template, self.url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                self.download_done.emit("", "")
            else:
                self.download_done.emit("", result.stderr)
        except Exception as e:
            self.download_done.emit("", str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FULLSCREEN VIDEO WINDOW — Tam ekran video penceresi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _FullScreenVideoWindow(QWidget):
    """
    Tam ekran video penceresi (frosted glass overlay bar).
    """
    closed = pyqtSignal()
    
    def __init__(self, video_widget: QVideoWidget, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(f"background: #000000;")
        self.showFullScreen()
        
        self._video_widget = video_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Overlay bar (frosted glass)
        overlay = QFrame()
        overlay.setFixedHeight(60)
        overlay.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-bottom: 1px solid {_ACCENT};
            }}
        """)
        overlay_layout = QHBoxLayout(overlay)
        overlay_layout.setContentsMargins(20, 10, 20, 10)
        
        exit_btn = QPushButton("✕ Çık")
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        exit_btn.clicked.connect(self.close)
        
        overlay_layout.addWidget(exit_btn)
        overlay_layout.addStretch()
        
        layout.addWidget(overlay)
        layout.addWidget(self._video_widget, 1)
        
    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MUSIC FULL PAGE — Ana sayfa widget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MusicFullPage(QWidget):
    """
    Tam sayfa müzik arayüzü.
    - QSplitter: Video (üst) + Arama sonuçları (alt) birlikte görünür
    - Sidebar: Kütüphane, playlist, navigasyon
    - Arama header: Keşfet, search bar, URL download
    - Now playing bar: Player kontrolü, progress
    - Video player: QMediaPlayer, gömülü video
    """
    
    _is_music_fullpage = True
    open_in_browser = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser = None
        
        # Player
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.7)
        
        # Video player
        self._video_widget = QVideoWidget()
        self._video_player = QMediaPlayer()
        self._video_player.setAudioOutput(self._audio_output)
        self._video_player.setVideoOutput(self._video_widget)
        
        # State
        self._current_title = ""
        self._current_url = ""
        self._current_duration = 0
        self._current_position = 0
        self._is_seeking = False
        self._is_video_mode = False
        self._video_duration = 0
        self._video_position = 0
        self._fullscreen_window = None
        
        # Library & playlist
        self._library_tracks = []
        self._playlists = []
        self._current_playlist = []
        self._current_idx = -1
        
        # Workers
        self._search_worker = None
        self._stream_worker = None
        self._download_worker = None
        
        # Timers
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        
        self._glow_timer = None
        
        self._setup_ui()
        self._refresh_library()
        self._load_trends()
        
    def set_browser(self, browser):
        """Tarayıcı referansını ayarla."""
        self._browser = browser
        
    def cleanup(self):
        """Cleanup kaynaklar."""
        if self._video_player:
            self._video_player.stop()
        if self._progress_timer:
            self._progress_timer.stop()
        if self._glow_timer:
            self._glow_timer.stop()
        if self._search_worker:
            self._search_worker.quit()
            self._search_worker.wait()
        if self._stream_worker:
            self._stream_worker.quit()
            self._stream_worker.wait()
        if self._download_worker:
            self._download_worker.quit()
            self._download_worker.wait()
            
    # ─────────────────────────────────────────────────────────────
    #  UI SETUP
    # ─────────────────────────────────────────────────────────────
    def _setup_ui(self):
        """Ana UI layout."""
        self.setStyleSheet(f"background: {_BG};")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar (280px)
        self._sidebar = self._build_sidebar()
        main_layout.addWidget(self._sidebar)
        
        # Right: Ana içerik
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Search header
        self._search_header = self._build_search_header()
        right_layout.addWidget(self._search_header)
        
        # Video + Sonuçlar splitter (dikey)
        self._content_splitter = QSplitter(Qt.Orientation.Vertical)
        self._content_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {_GLASS_BORDER};
                height: 2px;
            }}
        """)
        
        # Üst: Video alanı (başta gizli)
        self._video_container = self._build_video_page()
        self._video_container.hide()
        self._content_splitter.addWidget(self._video_container)
        
        # Alt: Arama sonuçları (her zaman görünür)
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)
        
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(20, 20, 20, 20)
        self._results_layout.setSpacing(12)
        self._results_layout.addStretch()
        self._results_scroll.setWidget(self._results_widget)
        self._content_splitter.addWidget(self._results_scroll)
        
        # Splitter oranları
        self._content_splitter.setStretchFactor(0, 2)  # Video
        self._content_splitter.setStretchFactor(1, 1)  # Results
        
        right_layout.addWidget(self._content_splitter, 1)
        
        # Now playing bar
        self._now_playing_bar = self._build_now_playing_bar()
        right_layout.addWidget(self._now_playing_bar)
        
        main_layout.addWidget(right_widget, 1)
        
        # Ambiance pulse overlay
        self._pulse_overlay = _AmbiancePulseOverlay(self)
        self._pulse_overlay.setGeometry(self.rect())
        self._pulse_overlay.lower()
        
    def _build_sidebar(self) -> QWidget:
        """Sidebar (280px genişlik, koyu yüzey)."""
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {_SURFACE};
                border-right: 1px solid {_GLASS_BORDER};
            }}
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(20)
        
        # Logo: "♫ Visionary Music" gradient text effect
        logo = QLabel("♫ Visionary Music")
        logo.setStyleSheet(f"""
            QLabel {{
                color: {_ACCENT};
                font-size: 22px;
                font-weight: 700;
                background: transparent;
            }}
        """)
        layout.addWidget(logo)
        
        # Gradient underline separator
        sep1 = QFrame()
        sep1.setFixedHeight(2)
        sep1.setStyleSheet(f"""
            background: qlineargradient(x1:0, x2:1,
                stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
        """)
        layout.addWidget(sep1)
        
        # Nav buttons (pill-shaped)
        nav_frame = QFrame()
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 10, 0, 10)
        nav_layout.setSpacing(10)
        
        self._btn_kesfet = self._create_nav_button("🎵 Keşfet")
        self._btn_kesfet.clicked.connect(lambda: self._load_trends())
        nav_layout.addWidget(self._btn_kesfet)
        
        self._btn_library = self._create_nav_button("📚 Kütüphane")
        self._btn_library.clicked.connect(lambda: self._refresh_library())
        nav_layout.addWidget(self._btn_library)
        
        layout.addWidget(nav_frame)
        
        # Library section
        lib_label = QLabel("KÜTÜPHANENİZ")
        lib_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
        """)
        layout.addWidget(lib_label)
        
        self._library_scroll = QScrollArea()
        self._library_scroll.setWidgetResizable(True)
        self._library_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        self._library_widget = QWidget()
        self._library_layout = QVBoxLayout(self._library_widget)
        self._library_layout.setContentsMargins(0, 0, 0, 0)
        self._library_layout.setSpacing(8)
        self._library_layout.addStretch()
        self._library_scroll.setWidget(self._library_widget)
        layout.addWidget(self._library_scroll, 1)
        
        # Playlist section
        pl_label = QLabel("PLAYLISTLER")
        pl_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
        """)
        layout.addWidget(pl_label)
        
        self._playlist_scroll = QScrollArea()
        self._playlist_scroll.setWidgetResizable(True)
        self._playlist_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        self._playlist_widget = QWidget()
        self._playlist_layout = QVBoxLayout(self._playlist_widget)
        self._playlist_layout.setContentsMargins(0, 0, 0, 0)
        self._playlist_layout.setSpacing(8)
        self._playlist_layout.addStretch()
        self._playlist_scroll.setWidget(self._playlist_widget)
        layout.addWidget(self._playlist_scroll, 1)
        
        return sidebar
        
    def _create_nav_button(self, text: str) -> QPushButton:
        """Pill-shaped nav button with hover glow."""
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 24px;
                padding: 12px 20px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
                border: 1px solid {_ACCENT};
            }}
        """)
        return btn
        
    def _build_search_header(self) -> QWidget:
        """Arama header (glass panel)."""
        header = QFrame()
        header.setFixedHeight(180)
        header.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-bottom: 1px solid {_GLASS_BORDER};
            }}
        """)
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(16)
        
        # Title: "Keşfet"
        title = QLabel("Keşfet")
        title.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 28px;
                font-weight: 700;
            }}
        """)
        layout.addWidget(title)
        
        # Search bar + button
        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Şarkı, sanatçı veya video ara...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 24px;
                padding: 14px 24px;
                font-size: 15px;
            }}
            QLineEdit:focus {{
                border: 1px solid {_ACCENT};
            }}
        """)
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input, 1)
        
        self._search_btn = QPushButton("🔍 Ara")
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 24px;
                padding: 14px 32px;
                font-size: 15px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self._search_btn)
        
        layout.addLayout(search_row)
        
        # URL video/player row
        url_row = QHBoxLayout()
        url_row.setSpacing(12)
        
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("YouTube / video linki yapıştır (indirmeden izle veya dinle)...")
        self._url_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 20px;
                padding: 10px 20px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {_ACCENT_WARM};
            }}
        """)
        self._url_input.returnPressed.connect(self._watch_url)
        url_row.addWidget(self._url_input, 1)
        
        self._watch_url_btn = QPushButton("▶ İzle")
        self._watch_url_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT_ROSE};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 20px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: #F472B6;
            }}
        """)
        self._watch_url_btn.clicked.connect(self._watch_url)
        url_row.addWidget(self._watch_url_btn)

        self._play_url_btn = QPushButton("♪ Dinle")
        self._play_url_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 20px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._play_url_btn.clicked.connect(self._play_url_stream)
        url_row.addWidget(self._play_url_btn)

        self._download_btn = QPushButton("⬇ İndir")
        self._download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT_WARM};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 20px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #FBBF24;
            }}
        """)
        self._download_btn.clicked.connect(self._download_url)
        url_row.addWidget(self._download_btn)
        
        layout.addLayout(url_row)
        
        return header
        
    def _build_now_playing_bar(self) -> QWidget:
        """Alt now playing bar (frosted glass)."""
        bar = QFrame()
        bar.setFixedHeight(120)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-top: 1px solid {_GLASS_BORDER};
            }}
        """)
        
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(6)
        
        # Wave visualizer (sabit yükseklik)
        self._wave_widget = _SoftWaveWidget()
        self._wave_widget.setFixedHeight(24)
        layout.addWidget(self._wave_widget)
        
        # Controls row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(16)
        
        # Large circular play button (gradient bg)
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(48, 48)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 24px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._play_btn.clicked.connect(self._toggle_play)
        controls_row.addWidget(self._play_btn)
        
        # Prev button
        self._prev_btn = self._create_nav_icon_button("⏮")
        self._prev_btn.clicked.connect(self._on_prev)
        controls_row.addWidget(self._prev_btn)
        
        # Next button
        self._next_btn = self._create_nav_icon_button("⏭")
        self._next_btn.clicked.connect(self._on_next)
        controls_row.addWidget(self._next_btn)
        
        # Title + time
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self._title_label = QLabel("Şarkı seçilmedi")
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        info_layout.addWidget(self._title_label)
        
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 12px;
            }}
        """)
        info_layout.addWidget(self._time_label)
        
        controls_row.addLayout(info_layout, 1)
        
        # Volume
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 16px;")
        controls_row.addWidget(vol_icon)
        
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setFixedWidth(100)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_SURFACE2};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {_ACCENT};
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                border-radius: 3px;
            }}
        """)
        self._volume_slider.valueChanged.connect(self._on_vol_changed)
        controls_row.addWidget(self._volume_slider)
        
        layout.addLayout(controls_row)
        
        # Thin gradient progress bar
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_SURFACE2};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {_TEXT_PRIMARY};
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                border-radius: 2px;
            }}
        """)
        self._progress_slider.sliderPressed.connect(self._on_seek_start)
        self._progress_slider.sliderReleased.connect(self._on_seek_end)
        layout.addWidget(self._progress_slider)
        
        return bar
        
    def _build_video_page(self) -> QWidget:
        """Video container (başta gizli, video oynarken göster)."""
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: #000000;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video header
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-bottom: 1px solid {_GLASS_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)
        
        # Back button
        self._video_back_btn = QPushButton("⬅ Geri")
        self._video_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
            }}
        """)
        self._video_back_btn.clicked.connect(self._close_video)
        header_layout.addWidget(self._video_back_btn)
        
        # Minimize button
        self._video_minimize_btn = QPushButton("📐 Küçült")
        self._video_minimize_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
            }}
        """)
        self._video_minimize_btn.clicked.connect(self._minimize_video)
        header_layout.addWidget(self._video_minimize_btn)
        
        self._video_title_label = QLabel("Video")
        self._video_title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        header_layout.addWidget(self._video_title_label, 1)
        
        self._video_browser_btn = QPushButton("🌐 Tarayıcıda Aç")
        self._video_browser_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._video_browser_btn.clicked.connect(self._open_video_in_browser)
        header_layout.addWidget(self._video_browser_btn)
        
        layout.addWidget(header)
        
        # Video widget
        layout.addWidget(self._video_widget, 1)
        
        # Video control bar (frosted glass)
        control_bar = QFrame()
        control_bar.setFixedHeight(70)
        control_bar.setStyleSheet(f"""
            QFrame {{
                background: {_GLASS_BG};
                border-top: 1px solid {_GLASS_BORDER};
            }}
        """)
        control_layout = QVBoxLayout(control_bar)
        control_layout.setContentsMargins(16, 8, 16, 8)
        control_layout.setSpacing(8)
        
        # Seek bar
        self._vid_progress = QSlider(Qt.Orientation.Horizontal)
        self._vid_progress.setRange(0, 1000)
        self._vid_progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {_SURFACE2};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {_TEXT_PRIMARY};
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                border-radius: 3px;
            }}
        """)
        self._vid_progress.sliderPressed.connect(lambda: setattr(self, "_is_seeking", True))
        self._vid_progress.sliderReleased.connect(self._vid_on_seek_end)
        control_layout.addWidget(self._vid_progress)
        
        # Buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        
        self._vid_play_btn = QPushButton("▶")
        self._vid_play_btn.setFixedSize(40, 40)
        self._vid_play_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._vid_play_btn.clicked.connect(self._vid_toggle_play)
        buttons_row.addWidget(self._vid_play_btn)
        
        self._vid_back_btn = QPushButton("⏪ -10s")
        self._vid_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
            }}
        """)
        self._vid_back_btn.clicked.connect(lambda: self._vid_seek_rel(-10000))
        buttons_row.addWidget(self._vid_back_btn)
        
        self._vid_fwd_btn = QPushButton("+10s ⏩")
        self._vid_fwd_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
            }}
        """)
        self._vid_fwd_btn.clicked.connect(lambda: self._vid_seek_rel(10000))
        buttons_row.addWidget(self._vid_fwd_btn)
        
        self._vid_time_label = QLabel("0:00 / 0:00")
        self._vid_time_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 13px;
            }}
        """)
        buttons_row.addWidget(self._vid_time_label)
        
        buttons_row.addStretch()
        
        self._vid_speed_combo = QComboBox()
        self._vid_speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self._vid_speed_combo.setCurrentIndex(2)
        self._vid_speed_combo.setStyleSheet(f"""
            QComboBox {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                selection-background-color: {_ACCENT};
            }}
        """)
        self._vid_speed_combo.currentTextChanged.connect(self._vid_set_speed)
        buttons_row.addWidget(self._vid_speed_combo)
        
        self._vid_fullscreen_btn = QPushButton("⛶ Tam Ekran")
        self._vid_fullscreen_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
            }}
        """)
        self._vid_fullscreen_btn.clicked.connect(self._vid_toggle_fullscreen)
        buttons_row.addWidget(self._vid_fullscreen_btn)
        
        control_layout.addLayout(buttons_row)
        
        layout.addWidget(control_bar)
        
        # Video player signals
        self._video_player.positionChanged.connect(self._vid_on_position_changed)
        self._video_player.durationChanged.connect(self._vid_on_duration_changed)
        self._video_player.playbackStateChanged.connect(self._on_video_state_changed)
        
        return container
        
    def _create_nav_icon_button(self, icon: str) -> QPushButton:
        """Icon-only circular button."""
        btn = QPushButton(icon)
        btn.setFixedSize(40, 40)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 20px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
                border: 1px solid {_ACCENT};
            }}
        """)
        return btn
        
    def _minimize_video(self):
        """Video alanını küçült (gizle) ama ses çalmaya devam et."""
        self._video_container.hide()
        
    # ─────────────────────────────────────────────────────────────
    #  GLOW PULSE (Arka plan pulse efekti)
    # ─────────────────────────────────────────────────────────────
    def _start_glow_pulse(self):
        """Pulse overlay efekti başlat."""
        if self._pulse_overlay:
            self._pulse_overlay.pulse()
            
    # ─────────────────────────────────────────────────────────────
    #  SEARCH
    # ─────────────────────────────────────────────────────────────
    def _do_search(self):
        """Arama yap."""
        query = self._search_input.text().strip()
        if not query:
            return
        self._clear_results()
        if self._search_worker:
            self._search_worker.quit()
            self._search_worker.wait()
        self._search_worker = _SearchWorker(query, max_results=20)
        self._search_worker.results_ready.connect(self._on_search_results)
        self._search_worker.search_error.connect(lambda e: logger.error(f"Arama hatası: {e}"))
        self._search_worker.start()
        
    def _on_search_results(self, items: list):
        """Arama sonuçları geldi."""
        self._clear_results()
        for item in items:
            self._add_result_item(item)
            
    def _clear_results(self):
        """Sonuç listesini temizle."""
        while self._results_layout.count() > 1:
            child = self._results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def _add_result_item(self, item: dict):
        """Sonuç kartı ekle (clean glass card)."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                background: {_CARD_HOVER};
                border: 1px solid {_ACCENT};
            }}
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(16)
        
        # Left: Badge (number)
        idx = self._results_layout.count()
        badge = QLabel(str(idx))
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
            }}
        """)
        card_layout.addWidget(badge)
        
        # Center: Title + duration
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        title_label = QLabel(item["title"])
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        info_layout.addWidget(title_label)
        
        duration_label = QLabel(self._fmt(item.get("duration", 0)))
        duration_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 12px;
            }}
        """)
        info_layout.addWidget(duration_label)
        
        card_layout.addLayout(info_layout, 1)
        
        # Right: Icon buttons (play, video, download)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(36, 36)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        play_btn.setToolTip("Oynat")
        play_btn.clicked.connect(lambda: self._play_stream(item["url"]))
        btn_layout.addWidget(play_btn)
        
        video_btn = QPushButton("📹")
        video_btn.setFixedSize(36, 36)
        video_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
                border: 1px solid {_ACCENT_ROSE};
            }}
        """)
        video_btn.setToolTip("Video İzle")
        video_btn.clicked.connect(lambda: self._watch_video_url(item["url"]))
        btn_layout.addWidget(video_btn)
        
        download_btn = QPushButton("⬇")
        download_btn.setFixedSize(36, 36)
        download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {_SURFACE3};
                border: 1px solid {_ACCENT_WARM};
            }}
        """)
        download_btn.setToolTip("İndir")
        download_btn.clicked.connect(lambda: self._download_result(item["url"]))
        btn_layout.addWidget(download_btn)
        
        card_layout.addLayout(btn_layout)
        
        self._results_layout.insertWidget(self._results_layout.count() - 1, card)
        
    # ─────────────────────────────────────────────────────────────
    #  LIBRARY
    # ─────────────────────────────────────────────────────────────
    def _refresh_library(self):
        """Kütüphanedeki müzik dosyalarını tara (config.MUSIC_DIR)."""
        import os
        
        # Clear
        while self._library_layout.count() > 1:
            child = self._library_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self._library_tracks = []
        
        # BUG FIX: config.MUSIC_DIR kullan
        music_dir = config.MUSIC_DIR
        if not os.path.isdir(music_dir):
            logger.warning(f"Müzik dizini bulunamadı: {music_dir}")
            return
            
        files = os.listdir(music_dir)
        for fname in sorted(files):
            if fname.endswith((".mp3", ".wav", ".m4a", ".flac")):
                self._library_tracks.append(fname)
                self._add_library_item(fname)
                
    def _add_library_item(self, filename: str):
        """Kütüphane öğesi ekle (album-art-style badge)."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: {_CARD_HOVER};
                border: 1px solid {_ACCENT};
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # Badge
        idx = len(self._library_tracks)
        badge = QLabel(str(idx))
        badge.setFixedSize(32, 32)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }}
        """)
        layout.addWidget(badge)
        
        # Title
        title = QLabel(filename)
        title.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        layout.addWidget(title, 1)
        
        # Play button
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(28, 28)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        play_btn.clicked.connect(lambda: self._play_lib_track(filename))
        layout.addWidget(play_btn)
        
        self._library_layout.insertWidget(self._library_layout.count() - 1, card)
        
    def _refresh_playlists(self):
        """Playlist yenile (placeholder)."""
        pass
        
    def _add_playlist_item(self, name: str):
        """Playlist öğesi ekle."""
        btn = QPushButton(f"📁 {name}")
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_CARD_BG};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {_CARD_HOVER};
                border: 1px solid {_ACCENT};
            }}
        """)
        btn.clicked.connect(lambda: self._play_playlist(name))
        self._playlist_layout.insertWidget(self._playlist_layout.count() - 1, btn)
        
    # ─────────────────────────────────────────────────────────────
    #  PLAYBACK
    # ─────────────────────────────────────────────────────────────
    def _play_lib_track(self, filename: str):
        """Kütüphaneden dosya oynat (BUG FIX: config.MUSIC_DIR)."""
        import os
        # BUG FIX: config.MUSIC_DIR kullan
        path = os.path.join(config.MUSIC_DIR, filename)
        if not os.path.isfile(path):
            logger.error(f"Dosya bulunamadı: {path}")
            return
        self._video_player.stop()
        self._video_player.setSource(QUrl.fromLocalFile(path))
        self._current_title = filename
        self._current_url = path
        self._is_video_mode = False
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()
        
    def _play_stream(self, url: str):
        """YouTube stream oynat (ses)."""
        if self._stream_worker:
            self._stream_worker.quit()
            self._stream_worker.wait()
        self._stream_worker = _StreamWorker(url, is_video=False)
        self._stream_worker.stream_ready.connect(self._on_stream_ready)
        self._stream_worker.stream_error.connect(lambda e: logger.error(f"Stream hatası: {e}"))
        self._stream_worker.start()
        
    def _on_stream_ready(self, title: str, url: str, fmt: str):
        """Stream hazır."""
        self._video_player.stop()
        self._video_player.setSource(QUrl(url))
        self._current_title = title
        self._current_url = url
        self._is_video_mode = False
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()
        
    def _play_playlist(self, name: str):
        """Playlist oynat (placeholder)."""
        pass
        
    def _toggle_play(self):
        """Oynat/duraklat."""
        source = self._video_player.source()
        if source.isEmpty():
            logger.warning("Oynatılacak medya kaynağı yok.")
            return

        state = self._video_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._video_player.pause()
        else:
            # Parça bittiyse yeniden oynatırken başa sar.
            duration = self._video_player.duration()
            position = self._video_player.position()
            if (
                state == QMediaPlayer.PlaybackState.StoppedState
                and duration > 0
                and position >= max(0, duration - 500)
            ):
                self._video_player.setPosition(0)
            self._video_player.play()
            
    def _on_prev(self):
        """Önceki parça (playlist varsa)."""
        if self._current_idx > 0:
            self._current_idx -= 1
            # TODO: play track
            
    def _on_next(self):
        """Sonraki parça (playlist varsa)."""
        if self._current_idx < len(self._current_playlist) - 1:
            self._current_idx += 1
            # TODO: play track
            
    def _on_vol_changed(self, value: int):
        """Ses seviyesi değişti."""
        self._audio_output.setVolume(value / 100.0)
        
    # ─────────────────────────────────────────────────────────────
    #  VIDEO
    # ─────────────────────────────────────────────────────────────
    def _watch_video(self, url: str):
        """Video izle (deprecated: use _watch_video_url)."""
        self._watch_video_url(url)
        
    def _watch_video_url(self, url: str):
        """YouTube video URL'den video izle."""
        if self._stream_worker:
            self._stream_worker.quit()
            self._stream_worker.wait()
        self._stream_worker = _StreamWorker(url, is_video=True)
        self._stream_worker.stream_ready.connect(self._on_video_stream_ready)
        self._stream_worker.stream_error.connect(self._on_video_stream_error)
        self._stream_worker.start()
        
    def _on_video_stream_ready(self, title: str, url: str, fmt: str):
        """Video stream hazır - video container'ı göster."""
        self._video_player.stop()
        self._video_player.setSource(QUrl(url))
        self._current_title = title
        self._current_url = url
        self._is_video_mode = True
        self._video_title_label.setText(title)
        
        # Video container'ı göster (QSplitter üzerinde)
        self._video_container.show()
        
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()
        
    def _on_video_stream_error(self, error: str):
        """Video stream hatası."""
        logger.error(f"Video stream hatası: {error}")
        
    def _on_video_state_changed(self, state):
        """Video oynatma durumu değişti."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
            self._vid_play_btn.setText("⏸")
            self._wave_widget.set_playing(True)
            self._progress_timer.start(100)
        else:
            self._play_btn.setText("▶")
            self._vid_play_btn.setText("▶")
            self._wave_widget.set_playing(False)
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._progress_timer.stop()
                
    def _vid_on_position_changed(self, pos: int):
        """Video pozisyon değişti."""
        self._video_position = pos
        if not self._is_seeking and self._video_duration > 0:
            self._vid_progress.setValue(int(pos * 1000 / self._video_duration))
        self._vid_time_label.setText(f"{self._fmt(pos // 1000)} / {self._fmt(self._video_duration // 1000)}")
        
    def _vid_on_duration_changed(self, dur: int):
        """Video toplam süre değişti."""
        self._video_duration = dur
        
    def _vid_on_seek_end(self):
        """Video seek serbest bırakıldı."""
        self._is_seeking = False
        if self._video_duration > 0:
            pos = int(self._vid_progress.value() * self._video_duration / 1000)
            self._video_player.setPosition(pos)
            
    def _vid_seek_rel(self, delta_ms: int):
        """Video relative seek."""
        new_pos = self._video_player.position() + delta_ms
        new_pos = max(0, min(new_pos, self._video_duration))
        self._video_player.setPosition(new_pos)
        
    def _vid_toggle_play(self):
        """Video oynat/duraklat."""
        self._toggle_play()
        
    def _vid_set_speed(self, speed_text: str):
        """Video hızını ayarla."""
        speed = float(speed_text.replace("x", ""))
        self._video_player.setPlaybackRate(speed)
        
    def _vid_toggle_fullscreen(self):
        """Tam ekran aç/kapat."""
        if self._fullscreen_window:
            self._exit_fullscreen()
        else:
            self._fullscreen_window = _FullScreenVideoWindow(self._video_widget)
            self._fullscreen_window.closed.connect(self._exit_fullscreen)
            
    def _exit_fullscreen(self):
        """Tam ekrandan çık."""
        if self._fullscreen_window:
            self._fullscreen_window.close()
            self._fullscreen_window = None
            # Video widget'ı tekrar container'a ekle
            self._video_container.layout().addWidget(self._video_widget)
            
    def _close_video(self):
        """Video'yu kapat (container'ı gizle)."""
        self._video_player.stop()
        self._video_container.hide()
        self._is_video_mode = False
        
    def _open_video_in_browser(self):
        """Video'yu tarayıcıda aç."""
        if self._current_url and self._browser:
            self.open_in_browser.emit(self._current_url)
            
    # ─────────────────────────────────────────────────────────────
    #  DOWNLOAD
    # ─────────────────────────────────────────────────────────────
    def _download_url(self):
        """URL'den indir."""
        url = self._url_input.text().strip()
        if not url:
            return
        self._do_download(url)

    def _watch_url(self):
        """Yapıştırılan URL'yi indirmeden video olarak oynat."""
        url = self._url_input.text().strip()
        if not url:
            return
        self._watch_video_url(url)

    def _play_url_stream(self):
        """Yapıştırılan URL'yi indirmeden ses olarak oynat."""
        url = self._url_input.text().strip()
        if not url:
            return
        self._play_stream(url)
        
    def _download_result(self, url: str):
        """Arama sonucundan indir."""
        self._do_download(url)
        
    def _do_download(self, url: str):
        """İndirme başlat."""
        import os
        if self._download_worker:
            self._download_worker.quit()
            self._download_worker.wait()
        output_dir = config.MUSIC_DIR
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        self._download_worker = _DownloadWorker(url, output_dir)
        self._download_worker.download_done.connect(self._on_download_done)
        self._download_worker.start()
        logger.info("İndirme başladı...")
        
    def _on_download_done(self, filename: str, error: str):
        """İndirme tamamlandı."""
        if error:
            logger.error(f"İndirme hatası: {error}")
        else:
            logger.info("İndirme tamamlandı!")
            self._refresh_library()
            
    # ─────────────────────────────────────────────────────────────
    #  NOW PLAYING
    # ─────────────────────────────────────────────────────────────
    def _update_now_playing(self):
        """Now playing bilgisini güncelle."""
        self._title_label.setText(self._current_title or "Şarkı seçilmedi")
        
    def _update_progress(self):
        """Progress bar güncelle."""
        if self._is_seeking:
            return
        dur = self._video_player.duration()
        pos = self._video_player.position()
        if dur > 0:
            self._progress_slider.setValue(int(pos * 1000 / dur))
        self._time_label.setText(f"{self._fmt(pos // 1000)} / {self._fmt(dur // 1000)}")
        
    def _on_seek_start(self):
        """Seek başladı."""
        self._is_seeking = True
        
    def _on_seek_end(self):
        """Seek bitti."""
        self._is_seeking = False
        dur = self._video_player.duration()
        if dur > 0:
            pos = int(self._progress_slider.value() * dur / 1000)
            self._video_player.setPosition(pos)
            
    def _fmt(self, seconds: int) -> str:
        """Saniyeyi MM:SS formatına çevir."""
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"
        
    # ─────────────────────────────────────────────────────────────
    #  EVENTS
    # ─────────────────────────────────────────────────────────────
    def showEvent(self, event):
        """Widget gösterildiğinde."""
        super().showEvent(event)
        if self._pulse_overlay:
            self._pulse_overlay.setGeometry(self.rect())
            
    def resizeEvent(self, event):
        """Resize olayı."""
        super().resizeEvent(event)
        if self._pulse_overlay:
            self._pulse_overlay.setGeometry(self.rect())
            
    # ─────────────────────────────────────────────────────────────
    #  TRENDS
    # ─────────────────────────────────────────────────────────────
    def _load_trends(self):
        """Trend şarkılar yükle (örnek listesi)."""
        self._clear_results()
        trends = [
            {"title": "Lofi Hip Hop Radio - Beats to Relax/Study", "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk", "duration": 0},
            {"title": "Synthwave Radio - Beats to Chill/Game", "url": "https://www.youtube.com/watch?v=4xDzrJKXOOY", "duration": 0},
            {"title": "Chillhop Radio - Jazzy & Lo-fi Hip Hop", "url": "https://www.youtube.com/watch?v=5yx6BWlEVcY", "duration": 0},
        ]
        for item in trends:
            self._add_result_item(item)
