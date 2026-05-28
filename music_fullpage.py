"""
Visionary Navigator — Tam Sayfa Müzik Sayfası
Spotify tabanlı koyu tema, yeşil vurgu rengi.
YouTube'dan arama, indirme, streaming, gömülü video izleme.
Video ve arama sonuçları birlikte görünebilir (QSplitter).
Soft waveform visualizer.
Tüm UI metinleri ve yorumlar Türkçe'dir.
"""

import logging
import os
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
#  VISIONARY MUSIC — RENK PALETİ (stitch tasarım sistemi ile uyumlu)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_BG = "#131313"                         # background / surface-dim
_BG_SECONDARY = "#1c1b1b"               # surface-container-low
_SURFACE = "#201f1f"                    # surface-container
_SURFACE2 = "#2a2a2a"                   # surface-container-high
_SURFACE3 = "#353534"                   # surface-container-highest
_ACCENT = "#00ff41"                     # primary-container (neon yeşil)
_ACCENT_LIGHT = "#72ff70"               # primary-fixed
_ACCENT_DIM = "#00e639"                 # primary-fixed-dim
_ACCENT_WARM = "#FF9A3C"                # turuncu (indirme)
_ACCENT_ROSE = "#E91429"                # kırmızı (izle)
_TEXT_PRIMARY = "#e5e2e1"               # on-surface
_TEXT_SECONDARY = "#b9ccb2"             # on-surface-variant
_TEXT_TERTIARY = "#84967e"              # outline
_GLASS_BG = "rgba(18,18,18,0.6)"        # glass-panel arka plan
_GLASS_BORDER = "rgba(0,255,65,0.2)"    # neon yeşil sınır (glass-popout)
_CARD_BG = "rgba(18,18,18,0.6)"         # kart arka planı
_CARD_HOVER = "rgba(0,255,65,0.07)"     # hover kart
_GRADIENT_START = "#00e639"             # primary-fixed-dim
_GRADIENT_END = "#007117"               # on-primary-container


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SOFT WAVE WIDGET — Yumuşak dalga görselleştiricisi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _SoftWaveWidget(QWidget):
    """
    Minimalist yumuşak dalga görselleştiricisi.
    Müzik çalarken daha büyük, durduğunda gentle idle animasyon.
    4 katmanlı translucent sine dalgaları - mavi-gri renk şeması.
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
        
        # Neon yeşil dalga renk şeması (Visionary Music)
        colors = [
            QColor(0, 255, 65, 50),     # primary-container neon
            QColor(114, 255, 112, 60),  # primary-fixed
            QColor(0, 230, 57, 38),     # primary-fixed-dim
            QColor(0, 113, 23, 45)      # on-primary-container deep
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
#  AMBIANCE PULSE OVERLAY — Radyal gradyan pulse efekti
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _AmbiancePulseOverlay(QWidget):
    """
    Radyal gradient ile subtle pulse efekti (şarkı değişiminde).
    Hafif mavi ton.
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
        gradient.setColorAt(0.0, QColor(0, 255, 65, int(self._opacity * 70)))
        gradient.setColorAt(0.5, QColor(0, 230, 57, int(self._opacity * 25)))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, w, h)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AESTHETIC BUTTON — Gradient hover glow efektli buton
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _AestheticButton(QPushButton):
    """
    Hover'da mavi glow efekti olan estetik buton.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._glow_effect = None
        self.setStyleSheet(f"""
            QPushButton {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 9999px;
                padding: 10px 24px;
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
            self._glow_effect.setColor(QColor(0, 255, 65, 0))
            self._glow_effect.setBlurRadius(26)
            self._glow_effect.setOffset(0, 0)
            self.setGraphicsEffect(self._glow_effect)
            
    def enterEvent(self, event):
        self._ensure_glow()
        if self._glow_effect:
            self._glow_effect.setColor(QColor(0, 255, 65, 180))
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if self._glow_effect:
            self._glow_effect.setColor(QColor(0, 255, 65, 0))
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
        self._pending_video_url = ""
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
        self._refresh_playlists()
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

    def paintEvent(self, event):
        """Arka plan: Visionary Music subtle grid + ambient neon glow blobs."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Subtle grid (40px, rgba(255,255,255,0.03))
        pen = QPen(QColor(255, 255, 255, 8))
        pen.setWidth(1)
        painter.setPen(pen)
        for x in range(0, self.width() + 40, 40):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height() + 40, 40):
            painter.drawLine(0, y, self.width(), y)

        # Ambient glow — sağ üst (neon yeşil)
        painter.setPen(Qt.PenStyle.NoPen)
        grad1 = QRadialGradient(self.width() - 60, -80, 520)
        grad1.setColorAt(0.0, QColor(0, 255, 65, 13))
        grad1.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad1))
        painter.drawRect(self.rect())

        # Ambient glow — sol alt (ikincil yeşil)
        grad2 = QRadialGradient(int(self.width() * 0.2), int(self.height()), 380)
        grad2.setColorAt(0.0, QColor(114, 254, 143, 13))
        grad2.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad2))
        painter.drawRect(self.rect())

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
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {_SURFACE3};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        
        self._results_widget = QWidget()
        self._results_widget.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 20)
        self._results_layout.setSpacing(0)
        self._results_layout.addStretch()
        self._results_scroll.setWidget(self._results_widget)

        # Section header (bölüm başlığı + sütun başlıkları) + results scroll sarmalı
        results_outer = QWidget()
        results_outer.setStyleSheet("background: transparent;")
        ro_layout = QVBoxLayout(results_outer)
        ro_layout.setContentsMargins(0, 0, 0, 0)
        ro_layout.setSpacing(0)

        self._section_header = self._build_section_header()
        ro_layout.addWidget(self._section_header)
        ro_layout.addWidget(self._results_scroll, 1)

        self._content_splitter.addWidget(results_outer)
        
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
        """Sidebar (280px genişlik) — Visionary Music tasarım sistemi."""
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: rgba(18,18,18,0.7);
                border-right: 1px solid rgba(255,255,255,0.1);
            }}
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 24, 0, 24)
        layout.setSpacing(0)
        
        # ── Logo alanı ──────────────────────────────────────────
        logo_frame = QFrame()
        logo_frame.setStyleSheet("background: transparent;")
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(24, 0, 24, 0)
        logo_layout.setSpacing(2)
        
        logo_title = QLabel("Visionary")
        logo_title.setStyleSheet(f"""
            QLabel {{
                color: {_ACCENT};
                font-size: 24px;
                font-weight: 800;
                letter-spacing: -0.5px;
                background: transparent;
            }}
        """)
        logo_layout.addWidget(logo_title)
        
        logo_sub = QLabel("MUSIC SYSTEM")
        logo_sub.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 3px;
                background: transparent;
            }}
        """)
        logo_layout.addWidget(logo_sub)
        layout.addWidget(logo_frame)
        layout.addSpacing(24)
        
        # ── Nav menü ────────────────────────────────────────────
        nav_items = [
            ("🏠", "Keşfet", self._load_trends),
            ("📚", "Kütüphane", self._refresh_library),
        ]
        
        self._btn_kesfet = self._create_sidebar_nav_btn("🏠", "Keşfet", active=True)
        self._btn_kesfet.clicked.connect(self._load_trends)
        layout.addWidget(self._btn_kesfet)
        
        self._btn_library = self._create_sidebar_nav_btn("📚", "Kütüphane")
        self._btn_library.clicked.connect(self._refresh_library)
        layout.addWidget(self._btn_library)
        
        layout.addSpacing(20)
        
        # ── Kütüphane listesi başlığı ───────────────────────────
        lib_header = QFrame()
        lib_header.setStyleSheet("background: transparent;")
        lib_h_layout = QHBoxLayout(lib_header)
        lib_h_layout.setContentsMargins(24, 0, 16, 0)
        lib_h_layout.setSpacing(0)
        
        lib_label = QLabel("KÜTÜPHANENİZ")
        lib_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.5px;
                background: transparent;
            }}
        """)
        lib_h_layout.addWidget(lib_label)
        lib_h_layout.addStretch()
        layout.addWidget(lib_header)
        layout.addSpacing(8)
        
        self._library_scroll = QScrollArea()
        self._library_scroll.setWidgetResizable(True)
        self._library_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 2px; }
        """)
        self._library_widget = QWidget()
        self._library_widget.setStyleSheet("background: transparent;")
        self._library_layout = QVBoxLayout(self._library_widget)
        self._library_layout.setContentsMargins(0, 0, 0, 0)
        self._library_layout.setSpacing(2)
        self._library_layout.addStretch()
        self._library_scroll.setWidget(self._library_widget)
        layout.addWidget(self._library_scroll, 1)
        
        layout.addSpacing(12)
        
        # ── Playlist başlığı ────────────────────────────────────
        pl_header = QFrame()
        pl_header.setStyleSheet("background: transparent;")
        pl_h_layout = QHBoxLayout(pl_header)
        pl_h_layout.setContentsMargins(24, 0, 16, 0)
        pl_h_layout.setSpacing(0)
        
        pl_label = QLabel("PLAYLISTLER")
        pl_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.5px;
                background: transparent;
            }}
        """)
        pl_h_layout.addWidget(pl_label)
        pl_h_layout.addStretch()
        layout.addWidget(pl_header)
        layout.addSpacing(8)
        
        self._playlist_scroll = QScrollArea()
        self._playlist_scroll.setWidgetResizable(True)
        self._playlist_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 2px; }
        """)
        self._playlist_widget = QWidget()
        self._playlist_widget.setStyleSheet("background: transparent;")
        self._playlist_layout = QVBoxLayout(self._playlist_widget)
        self._playlist_layout.setContentsMargins(0, 0, 0, 0)
        self._playlist_layout.setSpacing(2)
        self._playlist_layout.addStretch()
        self._playlist_scroll.setWidget(self._playlist_widget)
        layout.addWidget(self._playlist_scroll, 1)
        
        layout.addSpacing(16)
        
        # ── Yeni Playlist butonu ─────────────────────────────────
        new_pl_btn = QPushButton("+ Yeni Playlist")
        new_pl_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_ACCENT};
                border: 1px solid rgba(0,255,65,0.4);
                border-radius: 9999px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 600;
                margin: 0 24px;
            }}
            QPushButton:hover {{
                background: rgba(0,255,65,0.08);
                border: 1px solid {_ACCENT};
            }}
        """)
        layout.addWidget(new_pl_btn)

        # ── Profil alanı (sidebar alt) ────────────────────────
        layout.addSpacing(14)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.07); border: none;")
        layout.addWidget(sep)

        layout.addSpacing(12)

        profile_row = QFrame()
        profile_row.setStyleSheet("background: transparent;")
        pr_layout = QHBoxLayout(profile_row)
        pr_layout.setContentsMargins(24, 0, 16, 0)
        pr_layout.setSpacing(12)

        avatar = QLabel("VN")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            QLabel {{
                background: {_SURFACE3};
                color: {_TEXT_PRIMARY};
                border-radius: 17px;
                font-size: 11px;
                font-weight: 800;
                border: 1px solid rgba(255,255,255,0.1);
            }}
        """)
        pr_layout.addWidget(avatar)

        user_col = QVBoxLayout()
        user_col.setSpacing(1)
        user_name_lbl = QLabel("Visionary")
        user_name_lbl.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; background: transparent;")
        user_col.addWidget(user_name_lbl)
        user_badge_lbl = QLabel("Pro Member")
        user_badge_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 10px; background: transparent;")
        user_col.addWidget(user_badge_lbl)
        pr_layout.addLayout(user_col, 1)

        layout.addWidget(profile_row)

        return sidebar
        
    def _create_sidebar_nav_btn(self, icon: str, text: str, active: bool = False) -> QPushButton:
        """Sidebar nav button — Visionary Music stili."""
        btn = QPushButton(f"  {icon}  {text}")
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0,255,65,0.05);
                    color: {_ACCENT};
                    border: none;
                    border-left: 3px solid {_ACCENT};
                    padding: 12px 20px;
                    text-align: left;
                    font-size: 15px;
                    font-weight: 700;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {_TEXT_SECONDARY};
                    border: none;
                    border-left: 3px solid transparent;
                    padding: 12px 20px;
                    text-align: left;
                    font-size: 15px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.04);
                    color: {_TEXT_PRIMARY};
                }}
            """)
        return btn
        
    def _build_section_header(self) -> QWidget:
        """Bölüm başlığı: dinamik title + sütun başlıkları (# | BAŞLIK | SÜRE)."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(10)

        # Başlık + TÜMÜNÜ GÖR satırı
        title_row = QHBoxLayout()
        self._section_title_label = QLabel("Trend Şarkılar")
        self._section_title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 22px;
                font-weight: 700;
                letter-spacing: -0.3px;
                background: transparent;
            }}
        """)
        title_row.addWidget(self._section_title_label)
        title_row.addStretch()

        view_all_lbl = QLabel("TÜMÜNÜ GÖR")
        view_all_lbl.setStyleSheet(f"""
            QLabel {{
                color: {_ACCENT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }}
        """)
        title_row.addWidget(view_all_lbl)
        layout.addLayout(title_row)

        # Sütun başlıkları satırı
        col_row = QHBoxLayout()
        col_row.setSpacing(14)
        col_row.setContentsMargins(20, 0, 16, 0)

        def mk_col(text, fixed_w=None):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"""
                QLabel {{
                    color: {_TEXT_TERTIARY};
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 1.2px;
                    background: transparent;
                }}
            """)
            if fixed_w:
                lbl.setFixedWidth(fixed_w)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl

        col_row.addWidget(mk_col("#", 28))
        col_row.addWidget(mk_col("BAŞLIK"), 1)
        col_row.addWidget(mk_col("⏱", 80))
        layout.addLayout(col_row)

        return frame

    def _build_search_header(self) -> QWidget:
        """Arama header — Visionary Music browse/keşfet başlığı."""
        header = QFrame()
        header.setFixedHeight(190)
        header.setStyleSheet(f"""
            QFrame {{
                background: rgba(18,18,18,0.6);
                border-bottom: 1px solid rgba(255,255,255,0.08);
            }}
        """)
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(32, 20, 32, 16)
        layout.setSpacing(14)
        
        # Başlık satırı
        title_row = QHBoxLayout()
        title = QLabel("Keşfet")
        title.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 32px;
                font-weight: 800;
                letter-spacing: -0.5px;
                background: transparent;
            }}
        """)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)
        
        # Arama satırı
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Şarkı, sanatçı veya video ara...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.07);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 9999px;
                padding: 12px 22px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0,255,65,0.4);
                background: rgba(255,255,255,0.1);
            }}
            QLineEdit::placeholder {{
                color: {_TEXT_TERTIARY};
            }}
        """)
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input, 1)
        
        self._search_btn = QPushButton("Ara")
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #003907;
                border: none;
                border-radius: 9999px;
                padding: 12px 28px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        self._search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self._search_btn)
        
        layout.addLayout(search_row)
        
        # URL satırı
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("YouTube / video linki yapıştır...")
        self._url_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.04);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 9999px;
                padding: 9px 18px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(0,255,65,0.3);
            }}
        """)
        self._url_input.returnPressed.connect(self._watch_url)
        url_row.addWidget(self._url_input, 1)
        
        _pill_btn_base = f"""
            border-radius: 9999px; padding: 9px 16px; font-size: 12px;
            font-weight: 700; border: none;
        """
        
        self._watch_url_btn = QPushButton("▶ İzle")
        self._watch_url_btn.setStyleSheet(f"QPushButton {{ background: {_ACCENT_ROSE}; color: white; {_pill_btn_base} }} QPushButton:hover {{ background: #c41222; }}")
        self._watch_url_btn.clicked.connect(self._watch_url)
        url_row.addWidget(self._watch_url_btn)

        self._play_url_btn = QPushButton("♪ Dinle")
        self._play_url_btn.setStyleSheet(f"QPushButton {{ background: {_ACCENT}; color: #003907; {_pill_btn_base} }} QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}")
        self._play_url_btn.clicked.connect(self._play_url_stream)
        url_row.addWidget(self._play_url_btn)

        self._download_btn = QPushButton("⬇ İndir")
        self._download_btn.setStyleSheet(f"QPushButton {{ background: {_ACCENT_WARM}; color: white; {_pill_btn_base} }} QPushButton:hover {{ background: #FFB060; }}")
        self._download_btn.clicked.connect(self._download_url)
        url_row.addWidget(self._download_btn)
        
        layout.addLayout(url_row)
        
        return header
        
    def _build_now_playing_bar(self) -> QWidget:
        """Alt now playing bar — Visionary Music tasarım sistemi (stitch referansı)."""
        bar = QFrame()
        bar.setFixedHeight(96)
        bar.setStyleSheet(f"""
            QFrame {{
                background: rgba(13,13,13,0.95);
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
        """)
        
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        
        # ── Progress bar (en üstte, ince) ───────────────────────
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setFixedHeight(4)
        self._progress_slider.setStyleSheet(f"""
            QSlider {{
                margin: 0;
                padding: 0;
            }}
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.15);
                height: 4px;
                border-radius: 0;
            }}
            QSlider::handle:horizontal {{
                background: {_ACCENT};
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {_ACCENT};
                border-radius: 0;
            }}
        """)
        self._progress_slider.sliderPressed.connect(self._on_seek_start)
        self._progress_slider.sliderReleased.connect(self._on_seek_end)
        outer.addWidget(self._progress_slider)
        
        # ── Ana kontrol satırı ───────────────────────────────────
        main_row = QHBoxLayout()
        main_row.setContentsMargins(24, 0, 24, 0)
        main_row.setSpacing(0)
        
        # Sol: Şarkı bilgisi (albüm thumb + başlık + süre)
        left_section = QHBoxLayout()
        left_section.setSpacing(12)
        left_section.setContentsMargins(0, 0, 0, 0)
        
        # Albüm thumbnail yeri (placeholder kutu)
        self._thumb_frame = QLabel("♫")
        self._thumb_frame.setFixedSize(56, 56)
        self._thumb_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_frame.setStyleSheet(f"""
            QLabel {{
                background: {_SURFACE2};
                color: {_ACCENT};
                border-radius: 8px;
                font-size: 22px;
            }}
        """)
        left_section.addWidget(self._thumb_frame)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel("Şarkı seçilmedi")
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }}
        """)
        info_col.addWidget(self._title_label)

        self._artist_label = QLabel("Visionary Music")
        self._artist_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                font-family: 'Space Mono', monospace;
                background: transparent;
            }}
        """)
        info_col.addWidget(self._artist_label)
        
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 11px;
                background: transparent;
            }}
        """)
        info_col.addWidget(self._time_label)
        left_section.addLayout(info_col)
        left_section.addStretch()

        # Beğen butonu (left section sağına)
        like_btn = QPushButton("♡")
        like_btn.setFixedSize(30, 30)
        like_btn.setToolTip("Beğen")
        like_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_TEXT_TERTIARY};
                border: none;
                border-radius: 15px;
                font-size: 15px;
            }}
            QPushButton:hover {{
                color: {_ACCENT};
            }}
        """)
        left_section.addWidget(like_btn)

        main_row.addLayout(left_section, 1)
        
        # Orta: Kontroller (shuffle, prev, play, next, repeat)
        center_section = QHBoxLayout()
        center_section.setSpacing(8)
        center_section.setContentsMargins(0, 0, 0, 0)
        center_section.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        
        self._shuffle_btn = self._create_player_icon_btn("⇄", accent=False)
        center_section.addWidget(self._shuffle_btn)
        
        self._prev_btn = self._create_player_icon_btn("⏮")
        self._prev_btn.clicked.connect(self._on_prev)
        center_section.addWidget(self._prev_btn)
        
        # Ana play butonu — neon yeşil daire (glow hover)
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(48, 48)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #003907;
                border: none;
                border-radius: 24px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
            QPushButton:pressed {{
                background: {_ACCENT_DIM};
            }}
        """)
        self._play_btn.clicked.connect(self._toggle_play)
        center_section.addWidget(self._play_btn)
        
        self._next_btn = self._create_player_icon_btn("⏭")
        self._next_btn.clicked.connect(self._on_next)
        center_section.addWidget(self._next_btn)
        
        self._repeat_btn = self._create_player_icon_btn("↺", accent=False)
        center_section.addWidget(self._repeat_btn)
        
        main_row.addLayout(center_section, 1)
        
        # Sağ: Dalga + ses
        right_section = QHBoxLayout()
        right_section.setSpacing(12)
        right_section.setContentsMargins(0, 0, 0, 0)
        right_section.addStretch()
        
        self._wave_widget = _SoftWaveWidget()
        self._wave_widget.setFixedSize(80, 32)
        right_section.addWidget(self._wave_widget)
        
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 14px; background: transparent;")
        right_section.addWidget(vol_icon)
        
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.2);
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {_ACCENT};
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {_ACCENT};
                border-radius: 2px;
            }}
        """)
        self._volume_slider.valueChanged.connect(self._on_vol_changed)
        right_section.addWidget(self._volume_slider)
        
        main_row.addLayout(right_section, 1)
        
        outer.addLayout(main_row, 1)
        
        return bar
        
    def _create_player_icon_btn(self, icon: str, accent: bool = True) -> QPushButton:
        """Player kontrol icon butonu."""
        btn = QPushButton(icon)
        btn.setFixedSize(36, 36)
        if accent:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {_TEXT_PRIMARY};
                    border: none;
                    border-radius: 18px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    color: {_ACCENT};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {_TEXT_TERTIARY};
                    border: none;
                    border-radius: 18px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    color: {_TEXT_SECONDARY};
                }}
            """)
        return btn
        
    def _build_video_page(self) -> QWidget:
        """Video container (başta gizli, video oynarken göster)."""
        container = QFrame()
        container.setObjectName("videoDeck")
        container.setStyleSheet(f"""
            QFrame#videoDeck {{
                background: transparent;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(14)
        
        # Video header
        header = QFrame()
        header.setObjectName("videoHero")
        header.setStyleSheet(f"""
            QFrame#videoHero {{
                background: {_SURFACE};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 14px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        eyebrow = QLabel("VIDEO SUITE")
        eyebrow.setStyleSheet(f"""
            QLabel {{
                color: rgba(241, 245, 249, 0.62);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.6px;
            }}
        """)
        title_col.addWidget(eyebrow)

        self._video_title_label = QLabel("Video salonu hazır")
        self._video_title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 22px;
                font-weight: 700;
            }}
        """)
        title_col.addWidget(self._video_title_label)

        self._video_meta_label = QLabel("Bir video seçtiğinizde oynatıcı, kalite bilgisi ve hızlı kontroller burada görünür.")
        self._video_meta_label.setWordWrap(True)
        self._video_meta_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 12px;
                padding-right: 12px;
            }}
        """)
        title_col.addWidget(self._video_meta_label)

        header_layout.addLayout(title_col, 1)

        side_col = QVBoxLayout()
        side_col.setSpacing(10)
        side_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._video_status_badge = QLabel()
        self._video_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_status_badge.setMinimumWidth(104)
        side_col.addWidget(self._video_status_badge, 0, Qt.AlignmentFlag.AlignRight)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        pill_button = f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.14);
                border: 1px solid rgba(255,255,255,0.16);
            }}
            QPushButton:disabled {{
                color: rgba(241,245,249,0.35);
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.04);
            }}
        """
        
        # Back button
        self._video_back_btn = QPushButton("Kapat")
        self._video_back_btn.setStyleSheet(pill_button)
        self._video_back_btn.clicked.connect(self._close_video)
        actions.addWidget(self._video_back_btn)
        
        # Minimize button
        self._video_minimize_btn = QPushButton("Küçült")
        self._video_minimize_btn.setStyleSheet(pill_button)
        self._video_minimize_btn.clicked.connect(self._minimize_video)
        actions.addWidget(self._video_minimize_btn)
        
        self._video_browser_btn = QPushButton("Tarayıcıda İzle")
        self._video_browser_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, x2:1,
                    stop:0 {_GRADIENT_START}, stop:1 {_GRADIENT_END});
                color: {_TEXT_PRIMARY};
                border: none;
                border-radius: 14px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
            QPushButton:disabled {{
                color: rgba(241,245,249,0.35);
                background: rgba(255,255,255,0.08);
            }}
        """)
        self._video_browser_btn.clicked.connect(self._open_video_in_browser)
        self._video_browser_btn.setEnabled(False)
        actions.addWidget(self._video_browser_btn)

        side_col.addLayout(actions)
        header_layout.addLayout(side_col)
        
        layout.addWidget(header)

        self._video_stage = QFrame()
        self._video_stage.setObjectName("videoStage")
        self._video_stage.setStyleSheet(f"""
            QFrame#videoStage {{
                background: #0A0A0A;
                border: 1px solid {_GLASS_BORDER};
                border-radius: 16px;
            }}
        """)
        stage_layout = QVBoxLayout(self._video_stage)
        stage_layout.setContentsMargins(10, 10, 10, 10)
        stage_layout.setSpacing(0)
        self._video_widget.setMinimumHeight(320)
        self._video_widget.setStyleSheet("background: #05070C; border-radius: 18px;")
        stage_layout.addWidget(self._video_widget, 1)
        
        layout.addWidget(self._video_stage, 1)
        
        # Video control bar (frosted glass)
        control_bar = QFrame()
        control_bar.setObjectName("videoControls")
        control_bar.setStyleSheet(f"""
            QFrame#videoControls {{
                background: {_GLASS_BG};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 14px;
            }}
        """)
        control_layout = QVBoxLayout(control_bar)
        control_layout.setContentsMargins(18, 14, 18, 14)
        control_layout.setSpacing(10)
        
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
                color: white;
                border: none;
                border-radius: 9999px;
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
                border-radius: 9999px;
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

        self._set_video_panel_state(
            "BEKLEMEDE",
            "Bir video acildiginda oynatma kontrolleri ve kalite bilgisi burada guncellenir.",
            "idle",
        )
        
        return container

    def _set_video_panel_state(self, status: str, detail: str, tone: str = "idle") -> None:
        """Video panelinin durum rozetini ve alt bilgisini guncelle."""
        palette = {
            "idle": ("rgba(148,163,184,0.16)", "rgba(148,163,184,0.22)", "#CBD5E1"),
            "loading": ("rgba(245,158,11,0.16)", "rgba(245,158,11,0.30)", "#FCD34D"),
            "live": ("rgba(16,185,129,0.16)", "rgba(16,185,129,0.28)", "#6EE7B7"),
            "error": ("rgba(244,63,94,0.16)", "rgba(244,63,94,0.28)", "#FDA4AF"),
        }
        bg, border, color = palette.get(tone, palette["idle"])
        self._video_status_badge.setText(status)
        self._video_status_badge.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
        """)
        self._video_meta_label.setText(detail)
        
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
        if hasattr(self, "_section_title_label"):
            self._section_title_label.setText(f"Arama Sonuçları  ({len(items)} sonuç)")
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
        """Sonuç kartı ekle — Visionary Music track-row stili."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            QFrame:hover {{
                background: rgba(255,255,255,0.04);
            }}
        """)
        
        card_layout = QHBoxLayout(row)
        card_layout.setContentsMargins(20, 10, 16, 10)
        card_layout.setSpacing(14)
        
        # Numara rozeti
        idx = self._results_layout.count()
        badge = QLabel(str(idx))
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 12px;
                background: transparent;
                font-weight: 600;
            }}
        """)
        card_layout.addWidget(badge)
        
        # Başlık + süre
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        title_label = QLabel(item["title"])
        title_label.setWordWrap(False)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        info_layout.addWidget(title_label)
        
        duration_label = QLabel(self._fmt(item.get("duration", 0)))
        duration_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 11px;
                background: transparent;
            }}
        """)
        info_layout.addWidget(duration_label)
        
        card_layout.addLayout(info_layout, 1)
        
        # Sağ: aksiyonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(32, 32)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #003907;
                border: none;
                border-radius: 16px;
                font-size: 12px;
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
        video_btn.setFixedSize(32, 32)
        video_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {_TEXT_SECONDARY};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_ROSE};
                color: {_ACCENT_ROSE};
            }}
        """)
        video_btn.setToolTip("Video İzle")
        video_btn.clicked.connect(lambda: self._watch_video_url(item["url"]))
        btn_layout.addWidget(video_btn)
        
        download_btn = QPushButton("⬇")
        download_btn.setFixedSize(32, 32)
        download_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {_TEXT_SECONDARY};
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {_ACCENT_WARM};
                color: {_ACCENT_WARM};
            }}
        """)
        download_btn.setToolTip("İndir")
        download_btn.clicked.connect(lambda: self._download_result(item["url"]))
        btn_layout.addWidget(download_btn)
        
        card_layout.addLayout(btn_layout)
        
        self._results_layout.insertWidget(self._results_layout.count() - 1, row)
        
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
        """Kütüphane öğesi ekle — Visionary Music track-row stili."""
        idx = len(self._library_tracks)
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }}
            QFrame:hover {{
                background: rgba(255,255,255,0.04);
            }}
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(24, 8, 16, 8)
        layout.setSpacing(12)
        
        # Numara (hover'da play ikonu gibi görünür)
        num_lbl = QLabel(str(idx))
        num_lbl.setFixedWidth(24)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_TERTIARY};
                font-size: 12px;
                background: transparent;
            }}
        """)
        layout.addWidget(num_lbl)
        
        # Başlık
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        title = QLabel(name)
        title.setWordWrap(False)
        title.setToolTip(filename)
        title.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
        """)
        layout.addWidget(title, 1)
        
        # Play butonu
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(28, 28)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #003907;
                border: none;
                border-radius: 14px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        play_btn.clicked.connect(lambda: self._play_lib_track(filename))
        layout.addWidget(play_btn)
        
        self._library_layout.insertWidget(self._library_layout.count() - 1, row)
        
    def _refresh_playlists(self):
        """Playlist yenile (playlists.json'dan yükle)."""
        import json
        playlists_path = os.path.join(config.BASE_DIR, "music", "playlists.json")
        try:
            if not os.path.isfile(playlists_path):
                return
            with open(playlists_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                names = list(data.keys())
            elif isinstance(data, list):
                names = [p.get('name', str(i)) for i, p in enumerate(data) if isinstance(p, dict)]
            else:
                return
            self._playlists = names
            for name in names:
                self._add_playlist_item(name)
        except Exception as e:
            logger.warning(f"Playlist yüklenemedi: {e}")
        
    def _add_playlist_item(self, name: str):
        """Playlist öğesi ekle — Visionary Music kart stili."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }}
            QFrame:hover {{
                background: rgba(255,255,255,0.04);
            }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(24, 10, 16, 10)
        layout.setSpacing(12)
        
        icon_lbl = QLabel("📁")
        icon_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 14px; background: transparent;")
        layout.addWidget(icon_lbl)
        
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
        """)
        layout.addWidget(name_lbl, 1)
        
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(26, 26)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #003907;
                border: none;
                border-radius: 13px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {_ACCENT_LIGHT};
            }}
        """)
        play_btn.clicked.connect(lambda: self._play_playlist(name))
        layout.addWidget(play_btn)
        
        self._playlist_layout.insertWidget(self._playlist_layout.count() - 1, row)
        
    # ─────────────────────────────────────────────────────────────
    #  PLAYBACK
    # ─────────────────────────────────────────────────────────────
    def _play_lib_track(self, filename: str):
        """Kütüphaneden dosya oynat."""
        path = os.path.join(config.MUSIC_DIR, filename)
        if not os.path.isfile(path):
            logger.error(f"Dosya bulunamadı: {path}")
            return
        # Prev/next navigasyonu için liste ve indeksi güncelle
        if not self._current_playlist or filename not in self._current_playlist:
            self._current_playlist = list(self._library_tracks)
        try:
            self._current_idx = self._current_playlist.index(filename)
        except ValueError:
            self._current_idx = 0
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
        """Playlist oynat."""
        import json
        playlists_path = os.path.join(config.BASE_DIR, "music", "playlists.json")
        try:
            if not os.path.isfile(playlists_path):
                logger.warning(f"Playlist dosyası bulunamadı: {playlists_path}")
                return
            with open(playlists_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tracks: list = []
            if isinstance(data, dict) and name in data:
                raw = data[name]
                tracks = raw if isinstance(raw, list) else []
            elif isinstance(data, list):
                for p in data:
                    if isinstance(p, dict) and p.get('name') == name:
                        tracks = p.get('tracks', [])
                        break
            filenames = [t if isinstance(t, str) else t.get('filename', '') for t in tracks]
            filenames = [f for f in filenames if f]
            if not filenames:
                logger.warning(f"Playlist boş veya bulunamadı: {name}")
                return
            self._current_playlist = filenames
            self._current_idx = 0
            self._play_lib_track(filenames[0])
        except Exception as e:
            logger.warning(f"Playlist oynatma hatası: {e}")
        
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
        """Önceki parça."""
        if self._current_idx > 0:
            self._current_idx -= 1
            if self._current_playlist:
                self._play_lib_track(self._current_playlist[self._current_idx])

    def _on_next(self):
        """Sonraki parça."""
        if self._current_idx < len(self._current_playlist) - 1:
            self._current_idx += 1
            self._play_lib_track(self._current_playlist[self._current_idx])
            
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
        self._pending_video_url = url
        self._current_url = url
        self._video_container.show()
        self._video_title_label.setText("Video hazirlaniyor...")
        self._video_browser_btn.setEnabled(True)
        self._set_video_panel_state(
            "HAZIRLANIYOR",
            "Kaynak adresi cozuluyor. Akis hazir oldugunda oynatma otomatik baslayacak.",
            "loading",
        )
        self._stream_worker = _StreamWorker(url, is_video=True)
        self._stream_worker.stream_ready.connect(self._on_video_stream_ready)
        self._stream_worker.stream_error.connect(self._on_video_stream_error)
        self._stream_worker.start()
        
    def _on_video_stream_ready(self, title: str, url: str, fmt: str):
        """Video stream hazır - video container'ı göster."""
        self._video_player.stop()
        self._video_player.setSource(QUrl(url))
        self._current_title = title
        self._current_url = self._pending_video_url or url
        self._is_video_mode = True
        self._video_title_label.setText(title)
        self._set_video_panel_state(
            "CANLI",
            f"{fmt} hazir. Isterseniz videoyu tarayicida orijinal sayfasinda da acabilirsiniz.",
            "live",
        )
        
        # Video container'ı göster (QSplitter üzerinde)
        self._video_container.show()
        
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()
        self._pending_video_url = ""
        
    def _on_video_stream_error(self, error: str):
        """Video stream hatası."""
        logger.error(f"Video stream hatası: {error}")
        self._video_container.show()
        self._video_title_label.setText("Video acilamadi")
        self._set_video_panel_state(
            "HATA",
            f"Akis acilamadi: {error[:140]}",
            "error",
        )
        self._video_browser_btn.setEnabled(bool(self._current_url))
        
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
            self._video_stage.layout().addWidget(self._video_widget)
            
    def _close_video(self):
        """Video'yu kapat (container'ı gizle)."""
        self._video_player.stop()
        self._video_container.hide()
        self._is_video_mode = False
        self._pending_video_url = ""
        self._current_url = ""
        self._video_browser_btn.setEnabled(False)
        self._video_title_label.setText("Video salonu hazır")
        self._set_video_panel_state(
            "BEKLEMEDE",
            "Bir video acildiginda oynatma kontrolleri ve kalite bilgisi burada guncellenir.",
            "idle",
        )
        
    def _open_video_in_browser(self):
        """Video'yu tarayıcıda aç."""
        if self._current_url and self._current_url.startswith(("http://", "https://")) and self._browser:
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
        title = self._current_title or "Şarkı seçilmedi"
        fm = self._title_label.fontMetrics()
        elided = fm.elidedText(title, Qt.TextElideMode.ElideRight, 380)
        self._title_label.setText(elided)
        self._title_label.setToolTip(title)
        
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
        if hasattr(self, "_section_title_label"):
            self._section_title_label.setText("Trend Şarkılar")
        self._clear_results()
        trends = [
            {"title": "Lofi Hip Hop Radio - Beats to Relax/Study", "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk", "duration": 0},
            {"title": "Synthwave Radio - Beats to Chill/Game", "url": "https://www.youtube.com/watch?v=4xDzrJKXOOY", "duration": 0},
            {"title": "Chillhop Radio - Jazzy & Lo-fi Hip Hop", "url": "https://www.youtube.com/watch?v=5yx6BWlEVcY", "duration": 0},
        ]
        for item in trends:
            self._add_result_item(item)
