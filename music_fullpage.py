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
    QGraphicsDropShadowEffect, QSplitter, QComboBox, QStackedWidget
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
#  TRENDING WORKER — YouTube'dan canlı trending müzik çeker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _TrendingWorker(QThread):
    """yt-dlp ile YouTube'dan trending müzik çeker."""
    trending_ready = pyqtSignal(list)   # list[dict{title,url,thumbnail,duration,view_count}]

    _GENRE_QUERIES = {
        "lofi":     "lofi hip hop relax study chill beats",
        "techno":   "techno electronic dark music mix",
        "synthwave":"synthwave retrowave 80s mix",
        "hiphop":   "hip hop rap türkçe 2025",
        "global":   "trending music 2025 popular",
        "kesfet":   "trending music 2025 charts",
    }

    def __init__(self, genre: str = "global", max_results: int = 20):
        super().__init__()
        self.genre = genre
        self.max_results = max_results

    def run(self):
        import subprocess, json
        query_text = self._GENRE_QUERIES.get(self.genre, self.genre)
        query = f"ytsearch{self.max_results}:{query_text}"
        try:
            cmd = [
                "yt-dlp", query,
                "--dump-json", "--skip-download", "--no-playlist",
                "--match-filter", "duration > 60",
                "--user-agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            items = []
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    try:
                        d = json.loads(line)
                        thumb = d.get("thumbnail") or ""
                        # thumbnail listesi varsa en küçüğünü seç (hızlı yükle)
                        if not thumb and d.get("thumbnails"):
                            thumbs = sorted(
                                d["thumbnails"],
                                key=lambda t: t.get("width", 9999)
                            )
                            thumb = thumbs[0].get("url", "")
                        items.append({
                            "title":      d.get("title", ""),
                            "url":        d.get("webpage_url", ""),
                            "thumbnail":  thumb,
                            "duration":   d.get("duration") or 0,
                            "view_count": d.get("view_count") or 0,
                            "uploader":   d.get("uploader") or d.get("channel", ""),
                        })
                    except Exception:
                        pass
            self.trending_ready.emit(items)
        except Exception as e:
            self.trending_ready.emit([])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THUMBNAIL WORKER — URL'den küçük resim indirir
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _ThumbnailWorker(QThread):
    """Verilen URL'den thumbnail PNG verisini indirir."""
    done = pyqtSignal(object, bytes)   # (QLabel, data)

    def __init__(self, label, url: str):
        super().__init__()
        self._label = label
        self._url = url

    def run(self):
        try:
            import urllib.request
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = urllib.request.urlopen(req, timeout=8).read()
            self.done.emit(self._label, data)
        except Exception:
            self.done.emit(self._label, b"")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FULLSCREEN VIDEO WINDOW — Tam ekran sinema modu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _FullScreenVideoWindow(QWidget):
    """
    Tam ekran sinema modu — tam_ekran tasarım.
    Hover'da alt kontrol çubuğu + üst başlık belirir, 3 sn sonra kaybolur.
    """
    closed = pyqtSignal()

    def __init__(
        self,
        video_widget: QVideoWidget,
        player: "QMediaPlayer | None" = None,
        title: str = "",
        artist: str = "",
        on_prev=None,
        on_next=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet("background: #000000;")
        self.setMouseTracking(True)

        self._video_widget = video_widget
        self._player = player
        self._on_prev_cb = on_prev
        self._on_next_cb = on_next
        self._is_seeking = False
        self._fs_duration = 0

        # Video widget tam ekranı doldurur
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._video_widget)

        # ── Üst overlay: başlık + sanatçı ──────────────────────
        self._top_overlay = QFrame(self)
        self._top_overlay.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0,0,0,0.78), stop:1 transparent
                );
                border: none;
            }
        """)
        top_inner = QHBoxLayout(self._top_overlay)
        top_inner.setContentsMargins(28, 24, 28, 32)
        top_col = QVBoxLayout()
        top_col.setSpacing(4)
        self._fs_title_lbl = QLabel(title or "Video")
        self._fs_title_lbl.setStyleSheet(
            "color: #ffffff; font-size: 22px; font-weight: 700; background: transparent;"
        )
        self._fs_artist_lbl = QLabel(artist or "")
        self._fs_artist_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 13px; background: transparent;"
        )
        top_col.addWidget(self._fs_title_lbl)
        top_col.addWidget(self._fs_artist_lbl)
        top_inner.addLayout(top_col, 1)

        # ── Alt overlay: progress + kontroller ─────────────────
        self._bot_overlay = QFrame(self)
        self._bot_overlay.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 transparent, stop:1 rgba(0,0,0,0.88)
                );
                border: none;
            }
        """)
        bot_inner = QVBoxLayout(self._bot_overlay)
        bot_inner.setContentsMargins(24, 32, 24, 24)
        bot_inner.setSpacing(10)

        # İlerleme çubuğu
        self._fs_progress = QSlider(Qt.Orientation.Horizontal)
        self._fs_progress.setRange(0, 1000)
        self._fs_progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.18);
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {_ACCENT};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                width: 14px; height: 14px;
                border-radius: 7px;
                margin: -5px 0;
            }}
        """)
        self._fs_progress.sliderPressed.connect(lambda: setattr(self, "_is_seeking", True))
        self._fs_progress.sliderReleased.connect(self._fs_seek_end)
        bot_inner.addWidget(self._fs_progress)

        # Frosted-glass kontrol satırı
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("""
            QFrame {
                background: rgba(20,20,20,0.65);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
            }
        """)
        ctrl_hl = QHBoxLayout(ctrl_frame)
        ctrl_hl.setContentsMargins(20, 6, 20, 6)
        ctrl_hl.setSpacing(0)

        _icon_btn = f"""
            QPushButton {{
                background: transparent; border: none;
                color: rgba(255,255,255,0.75); font-size: 20px;
            }}
            QPushButton:hover {{ color: #ffffff; }}
        """

        # SOL — ses + zaman
        left_w = QWidget()
        left_hl = QHBoxLayout(left_w)
        left_hl.setContentsMargins(0, 0, 0, 0)
        left_hl.setSpacing(8)

        vol_btn = QPushButton("🔊")
        vol_btn.setFixedSize(34, 34)
        vol_btn.setStyleSheet(_icon_btn)

        self._fs_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._fs_vol_slider.setFixedWidth(72)
        self._fs_vol_slider.setRange(0, 100)
        self._fs_vol_slider.setValue(70)
        self._fs_vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255,255,255,0.18); height: 3px; border-radius: 2px;
            }
            QSlider::sub-page:horizontal { background: #ffffff; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #ffffff; width: 10px; height: 10px;
                border-radius: 5px; margin: -4px 0;
            }
        """)
        if self._player:
            ao = self._player.audioOutput()
            if ao:
                self._fs_vol_slider.setValue(int(ao.volume() * 100))
        self._fs_vol_slider.valueChanged.connect(self._fs_set_volume)

        self._fs_time_lbl = QLabel("0:00 / 0:00")
        self._fs_time_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.60); font-size: 12px; "
            "font-family: monospace; background: transparent;"
        )
        left_hl.addWidget(vol_btn)
        left_hl.addWidget(self._fs_vol_slider)
        left_hl.addSpacing(10)
        left_hl.addWidget(self._fs_time_lbl)
        left_hl.addStretch()

        # MERKEZ — önceki / oynat / sonraki
        center_w = QWidget()
        center_hl = QHBoxLayout(center_w)
        center_hl.setContentsMargins(0, 0, 0, 0)
        center_hl.setSpacing(16)
        center_hl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(38, 38)
        prev_btn.setStyleSheet(_icon_btn)
        prev_btn.clicked.connect(self._fs_prev)

        self._fs_play_btn = QPushButton("⏸")
        self._fs_play_btn.setFixedSize(56, 56)
        self._fs_play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT}; color: #000000;
                border: none; border-radius: 28px;
                font-size: 22px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}
            QPushButton:pressed {{ background: {_ACCENT}; }}
        """)
        self._fs_play_btn.clicked.connect(self._fs_toggle_play)

        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(38, 38)
        next_btn.setStyleSheet(_icon_btn)
        next_btn.clicked.connect(self._fs_next)

        center_hl.addWidget(prev_btn)
        center_hl.addWidget(self._fs_play_btn)
        center_hl.addWidget(next_btn)

        # SAĞ — çıkış
        right_w = QWidget()
        right_hl = QHBoxLayout(right_w)
        right_hl.setContentsMargins(0, 0, 0, 0)
        right_hl.setSpacing(8)
        right_hl.addStretch()

        exit_btn = QPushButton("⛶")
        exit_btn.setFixedSize(36, 36)
        exit_btn.setToolTip("Tam ekrandan çık (Esc)")
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.80);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px; font-size: 18px;
            }}
            QPushButton:hover {{
                background: {_ACCENT}; color: #000;
                border-color: {_ACCENT};
            }}
        """)
        exit_btn.clicked.connect(self.close)
        right_hl.addWidget(exit_btn)

        ctrl_hl.addWidget(left_w, 1)
        ctrl_hl.addWidget(center_w, 1)
        ctrl_hl.addWidget(right_w, 1)
        bot_inner.addWidget(ctrl_frame)

        # Idle timer — 3 sn hareketsizlikte kontroller gizlenir
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._hide_controls)

        # Player sinyalleri
        if self._player:
            self._player.positionChanged.connect(self._fs_on_position)
            self._player.durationChanged.connect(self._fs_on_duration)
            self._player.playbackStateChanged.connect(self._fs_on_state)

        self._show_controls()
        self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._top_overlay.setGeometry(0, 0, w, 120)
        self._bot_overlay.setGeometry(0, h - 160, w, 160)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space:
            self._fs_toggle_play()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._show_controls()

    def _show_controls(self):
        self._top_overlay.show()
        self._bot_overlay.show()
        self._top_overlay.raise_()
        self._bot_overlay.raise_()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._idle_timer.start(3000)

    def _hide_controls(self):
        self._top_overlay.hide()
        self._bot_overlay.hide()
        self.setCursor(Qt.CursorShape.BlankCursor)

    def _fs_toggle_play(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _fs_prev(self):
        if self._on_prev_cb:
            self._on_prev_cb()

    def _fs_next(self):
        if self._on_next_cb:
            self._on_next_cb()

    def _fs_set_volume(self, val: int):
        if self._player:
            ao = self._player.audioOutput()
            if ao:
                ao.setVolume(val / 100.0)

    def _fs_seek_end(self):
        self._is_seeking = False
        if self._player and self._fs_duration > 0:
            pos = int(self._fs_progress.value() * self._fs_duration / 1000)
            self._player.setPosition(pos)

    def _fs_on_position(self, pos: int):
        if not self._is_seeking and self._fs_duration > 0:
            self._fs_progress.setValue(int(pos * 1000 / self._fs_duration))

        def _fmt(ms):
            s = ms // 1000
            return f"{s // 60}:{s % 60:02d}"

        self._fs_time_lbl.setText(f"{_fmt(pos)} / {_fmt(self._fs_duration)}")

    def _fs_on_duration(self, dur: int):
        self._fs_duration = dur

    def _fs_on_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._fs_play_btn.setText("⏸")
        else:
            self._fs_play_btn.setText("▶")

    def closeEvent(self, event):
        if self._player:
            try:
                self._player.positionChanged.disconnect(self._fs_on_position)
                self._player.durationChanged.disconnect(self._fs_on_duration)
                self._player.playbackStateChanged.disconnect(self._fs_on_state)
            except Exception:
                pass
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
    track_changed   = pyqtSignal(str, str, int)   # (title, url, index)
    
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
        self._search_worker    = None
        self._stream_worker    = None
        self._download_worker  = None
        self._trend_worker     = None
        self._thumbnail_workers: list = []
        self._trending_items: list = []
        # Kategori worker'ları {genre_key: _TrendingWorker}
        self._cat_workers: dict = {}
        
        # Timers
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        
        self._glow_timer = None
        
        self._setup_ui()
        self._refresh_library()
        self._refresh_playlists()
        # Canlı trending — 500ms sonra başlat (UI render tamamlansın)
        QTimer.singleShot(500, self._load_live_trends)
        
    def set_browser(self, browser):
        """Tarayıcı referansını ayarla."""
        self._browser = browser

    def notify_external_playback(self, title: str, url: str, index: int) -> None:
        """
        Dışarıdaki bir player (welcome/mini player) şarkı çaldığında
        Now Playing bar'ı ve wave animasyonunu güncelle.
        Kendi video_player'ında kaynak varsa güncelleme yapma.
        """
        if not self._video_player.source().isEmpty():
            return  # Kendi player'ı aktif — müdahale etme
        self._current_title = title
        self._current_url = url
        # Now playing bar başlığını güncelle
        fm = self._title_label.fontMetrics()
        elided = fm.elidedText(title, Qt.TextElideMode.ElideRight, 380)
        self._title_label.setText(elided)
        self._title_label.setToolTip(title)
        # Play butonu ve dalga animasyonu
        self._play_btn.setText("⏸")
        self._wave_widget.set_playing(True)


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
    # ═══════════════════════════════════════════════════════════════
    #  UI KURULUM  ─  3 sayfalı Visionary Music mimarisi
    # ═══════════════════════════════════════════════════════════════

    def _setup_ui(self):
        """Ana UI layout — 3 sayfalı Visionary Music."""
        self.setStyleSheet(f"background: {_BG};")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (önce kur — _nav_btns listesini oluşturur)
        self._sidebar = self._build_sidebar()
        main_layout.addWidget(self._sidebar)

        # Sağ: sayfa container + now playing bar
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # QStackedWidget — 3 sayfa
        self._pages = QStackedWidget()
        self._pages.setStyleSheet("background: transparent;")

        self._ana_sayfa_page = self._build_ana_sayfa_page()   # 0
        self._pages.addWidget(self._ana_sayfa_page)

        self._kesfet_page = self._build_kesfet_page()          # 1
        self._pages.addWidget(self._kesfet_page)

        self._kutuphane_page = self._build_kutuphane_page()    # 2
        self._pages.addWidget(self._kutuphane_page)

        # Video izleme sayfası — ayrı tam sayfa (index 3)
        self._video_page = self._build_video_page()              # 3
        self._pages.addWidget(self._video_page)
        # Geriye dönük uyumluluk: _video_container alias'ı
        self._video_container = self._video_page

        right_layout.addWidget(self._pages, 1)

        # Now playing bar (her sayfada görünür)
        self._now_playing_bar = self._build_now_playing_bar()
        right_layout.addWidget(self._now_playing_bar)

        main_layout.addWidget(right_widget, 1)

        # Ambiance pulse overlay
        self._pulse_overlay = _AmbiancePulseOverlay(self)
        self._pulse_overlay.setGeometry(self.rect())
        self._pulse_overlay.lower()

        # Başlangıç sayfası: Ana Sayfa (index 0)
        self._nav_to_page(0, 0)

    # ───────────────────────────────────────────────────────────────
    #  SIDEBAR  —  navigasyon odaklı (library/playlist'ler Kütüphane'de)
    # ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        """Sidebar (280px) — Visionary Music nav sistemi."""
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: rgba(19,19,19,0.98);
                border-right: 1px solid rgba(255,255,255,0.08);
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(0)

        # ── Logo ───────────────────────────────────────────────
        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_row = QHBoxLayout(logo_w)
        logo_row.setContentsMargins(20, 0, 20, 16)
        logo_row.setSpacing(12)

        logo_circle = QLabel("V")
        logo_circle.setFixedSize(40, 40)
        logo_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_circle.setStyleSheet(f"""
            QLabel {{
                background: {_SURFACE2};
                color: {_ACCENT};
                border-radius: 20px;
                font-size: 16px;
                font-weight: 900;
                border: 1px solid rgba(0,255,65,0.35);
            }}
        """)
        logo_row.addWidget(logo_circle)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        t1 = QLabel("Visionary")
        t1.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: 800; background: transparent;")
        t2 = QLabel("MUSIC SYSTEM")
        t2.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 9px; font-weight: 700; letter-spacing: 2px; background: transparent;")
        txt_col.addWidget(t1)
        txt_col.addWidget(t2)
        logo_row.addLayout(txt_col, 1)
        layout.addWidget(logo_w)

        # ── Nav butonları ──────────────────────────────────────
        self._nav_btns: list = []
        nav_data = [
            ("🏠", "Ana Sayfa",   0),
            ("🔍", "Keşfet",      1),
            ("📚", "Kütüphane",   2),
            ("♡",  "Beğenilenler",2),
        ]
        for btn_i, (icon, label, page_idx) in enumerate(nav_data):
            btn = QPushButton(f"  {icon}   {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._set_nav_btn_active(btn, False)   # başta hepsi pasif
            btn.clicked.connect(
                lambda checked=False, pi=page_idx, bi=btn_i: self._nav_to_page(pi, bi)
            )
            self._nav_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # ── Yeni Playlist ─────────────────────────────────────
        new_pl = QPushButton("+ Yeni Playlist")
        new_pl.setCursor(Qt.CursorShape.PointingHandCursor)
        new_pl.clicked.connect(self._create_playlist_dialog)
        new_pl.setStyleSheet(f"""
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
        layout.addWidget(new_pl)
        layout.addSpacing(14)

        # ── Ayraç ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.07); border: none;")
        layout.addWidget(sep)
        layout.addSpacing(12)

        # ── Profil alanı ──────────────────────────────────────
        prof_w = QWidget()
        prof_w.setStyleSheet("background: transparent;")
        prof_row = QHBoxLayout(prof_w)
        prof_row.setContentsMargins(20, 0, 20, 20)
        prof_row.setSpacing(12)

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
        prof_row.addWidget(avatar)

        ucol = QVBoxLayout()
        ucol.setSpacing(1)
        uname = QLabel("Visionary")
        uname.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; background: transparent;")
        ubadge = QLabel("Pro Member")
        ubadge.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 10px; background: transparent;")
        ucol.addWidget(uname)
        ucol.addWidget(ubadge)
        prof_row.addLayout(ucol, 1)
        layout.addWidget(prof_w)

        return sidebar

    def _create_sidebar_nav_btn(self, icon: str, text: str, active: bool = False) -> QPushButton:
        """Sidebar nav button — geriye dönük uyumluluk için korundu."""
        btn = QPushButton(f"  {icon}  {text}")
        self._set_nav_btn_active(btn, active)
        return btn

    # ───────────────────────────────────────────────────────────────
    #  NAVİGASYON  —  sayfa geçişi + buton aktif/pasif
    # ───────────────────────────────────────────────────────────────

    def _nav_to_page(self, page_idx: int, btn_idx: int = -1):
        """Sayfaya geç + sidebar buton durumunu güncelle."""
        self._pages.setCurrentIndex(page_idx)
        # Video sayfası (3) için hiçbir nav butonu aktif olmaz
        if page_idx >= 3:
            for btn in self._nav_btns:
                self._set_nav_btn_active(btn, False)
            return
        # btn_idx belirtilmediyse sayfa_idx = buton_idx (0→0, 1→1, 2→2)
        effective = btn_idx if btn_idx >= 0 else page_idx
        for i, btn in enumerate(self._nav_btns):
            self._set_nav_btn_active(btn, i == effective)

    def _set_nav_btn_active(self, btn: QPushButton, active: bool):
        """Sidebar nav butonuna aktif/pasif stili uygula."""
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0,255,65,0.07);
                    color: {_ACCENT};
                    border: none;
                    border-left: 3px solid {_ACCENT};
                    padding: 12px 20px;
                    text-align: left;
                    font-size: 14px;
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
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.04);
                    color: {_TEXT_PRIMARY};
                }}
            """)

    # ───────────────────────────────────────────────────────────────
    #  ANA SAYFA  —  Hero + kategoriler + trend şarkılar
    # ───────────────────────────────────────────────────────────────

    def _build_ana_sayfa_page(self) -> QWidget:
        """Ana Sayfa (index 0) — canlı hero + kategoriler + trending."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {_SURFACE3}; border-radius: 4px; }}
            QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(28, 20, 28, 32)
        lay.setSpacing(24)

        # ── Üst arama çubuğu → Keşfet'e yönlendirip arama yapar ──
        sf = QFrame()
        sf.setFixedHeight(44)
        sf.setStyleSheet(f"""
            QFrame {{
                background: rgba(42,42,42,0.9);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 22px;
            }}
        """)
        sf_lay = QHBoxLayout(sf)
        sf_lay.setContentsMargins(16, 0, 8, 0)
        sf_lay.setSpacing(8)
        sch_icon = QLabel("🔍")
        sch_icon.setStyleSheet(f"color: {_TEXT_TERTIARY}; background: transparent; font-size: 14px;")
        sf_lay.addWidget(sch_icon)
        self._home_search_input = QLineEdit()
        self._home_search_input.setPlaceholderText("Şarkı, sanatçı veya albüm ara…")
        self._home_search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                color: {_TEXT_PRIMARY}; font-size: 14px;
            }}
        """)
        self._home_search_input.returnPressed.connect(self._home_search_submit)
        sf_lay.addWidget(self._home_search_input, 1)
        sch_btn = QPushButton("Ara")
        sch_btn.setFixedHeight(30)
        sch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT}; color: #003907; border: none;
                border-radius: 15px; font-size: 12px; font-weight: 700;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}
        """)
        sch_btn.clicked.connect(self._home_search_submit)
        sf_lay.addWidget(sch_btn)
        lay.addWidget(sf)

        # ── İnline arama sonuçları (başta gizli) ──────────────────
        self._home_results_frame = QWidget()
        self._home_results_frame.setStyleSheet("background: transparent;")
        hrf_lay = QVBoxLayout(self._home_results_frame)
        hrf_lay.setContentsMargins(0, 12, 0, 0)
        hrf_lay.setSpacing(8)

        hrf_hdr = QHBoxLayout()
        self._home_res_title_lbl = QLabel("Sonuçlar")
        self._home_res_title_lbl.setStyleSheet(
            f"color:{_TEXT_PRIMARY}; font-size:18px; font-weight:700; background:transparent;"
        )
        hrf_hdr.addWidget(self._home_res_title_lbl, 1)
        hrf_clear_btn = QPushButton("✕ Kapat")
        hrf_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hrf_clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_TEXT_TERTIARY};border:none;font-size:12px;}}"
            f"QPushButton:hover{{color:{_ACCENT};}}"
        )
        hrf_clear_btn.clicked.connect(self._home_results_clear)
        hrf_hdr.addWidget(hrf_clear_btn)
        hrf_lay.addLayout(hrf_hdr)

        self._home_res_items = QWidget()
        self._home_res_items.setStyleSheet("background: transparent;")
        self._home_res_items_layout = QVBoxLayout(self._home_res_items)
        self._home_res_items_layout.setContentsMargins(0, 0, 0, 0)
        self._home_res_items_layout.setSpacing(2)
        self._home_res_items_layout.addStretch()
        hrf_lay.addWidget(self._home_res_items)

        self._home_results_frame.hide()
        lay.addWidget(self._home_results_frame)

        # ── Hero kartı (canlı trending #1 ile doldurulur) ─────────
        hero = QFrame()
        hero.setFixedHeight(300)
        hero.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a2b1a, stop:0.55 #161e16, stop:1 {_BG});
                border: 1px solid rgba(0,255,65,0.18);
                border-radius: 22px;
            }}
        """)
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(44, 36, 36, 36)
        hero_lay.setSpacing(24)

        lc = QVBoxLayout()
        lc.setSpacing(10)

        self._hero_badge = QLabel("  ● Yükleniyor…  ")
        self._hero_badge.setFixedHeight(24)
        self._hero_badge.setMaximumWidth(220)
        self._hero_badge.setStyleSheet(f"""
            QLabel {{
                color: {_ACCENT};
                background: rgba(0,255,65,0.12);
                border: 1px solid rgba(0,255,65,0.3);
                border-radius: 12px; font-size: 10px; font-weight: 700;
                letter-spacing: 1px; padding: 0 4px;
            }}
        """)
        lc.addWidget(self._hero_badge)

        self._hero_title = QLabel("—")
        self._hero_title.setWordWrap(True)
        self._hero_title.setMaximumWidth(520)
        self._hero_title.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY}; font-size: 36px; font-weight: 800;
                letter-spacing: -1px; background: transparent;
            }}
        """)
        lc.addWidget(self._hero_title)

        self._hero_sub = QLabel("Trending verisi yükleniyor…")
        self._hero_sub.setWordWrap(True)
        self._hero_sub.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 13px; background: transparent;")
        lc.addWidget(self._hero_sub)
        lc.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._hero_play_btn = QPushButton("▶  Oynat")
        self._hero_play_btn.setFixedHeight(42)
        self._hero_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hero_play_btn.setEnabled(False)
        self._hero_play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT}; color: #003907; border: none;
                border-radius: 21px; font-size: 14px; font-weight: 700;
                padding: 0 28px;
            }}
            QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}
            QPushButton:disabled {{ background: rgba(0,255,65,0.3); color: rgba(0,57,7,0.5); }}
        """)
        btn_row.addWidget(self._hero_play_btn)

        self._hero_watch_btn = QPushButton("📹  İzle")
        self._hero_watch_btn.setFixedHeight(42)
        self._hero_watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hero_watch_btn.setEnabled(False)
        self._hero_watch_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 21px; font-size: 14px; font-weight: 600;
                padding: 0 24px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); }}
            QPushButton:disabled {{ color: rgba(229,226,225,0.4); }}
        """)
        btn_row.addWidget(self._hero_watch_btn)
        btn_row.addStretch()
        lc.addLayout(btn_row)
        lc.addStretch()
        hero_lay.addLayout(lc, 3)

        # Thumbnail
        self._hero_thumb = QLabel()
        self._hero_thumb.setFixedSize(210, 210)
        self._hero_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero_thumb.setText("♫")
        self._hero_thumb.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2a3a2a, stop:1 #1a2a1a);
                border: 1px solid rgba(0,255,65,0.2);
                border-radius: 16px;
                color: {_ACCENT}; font-size: 72px;
            }}
        """)
        hero_lay.addWidget(self._hero_thumb)
        lay.addWidget(hero)

        # ── Kategoriler ────────────────────────────────────────────
        cat_hdr = QHBoxLayout()
        c_title = QLabel("Kategoriler")
        c_title.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 20px; font-weight: 700; background: transparent;")
        cat_hdr.addWidget(c_title)
        cat_hdr.addStretch()
        lay.addLayout(cat_hdr)

        cats_row = QHBoxLayout()
        cats_row.setSpacing(12)
        self._category_close_fns = []  # accordion için tüm kartların kapatma fonksiyonları
        for cat_name, genre_key, cat_bg in [
            ("Lo-fi Beats",    "lofi",     "#161e1e"),
            ("Techno / EDM",   "techno",   "#181826"),
            ("Synthwave",      "synthwave","#261818"),
            ("Hip-Hop / Rap",  "hiphop",   "#1e1a0e"),
        ]:
            cats_row.addWidget(self._build_category_card(cat_name, genre_key, cat_bg), 1)
        lay.addLayout(cats_row)

        # ── Trend Şarkılar (canlı) ─────────────────────────────────
        tr_hdr = QHBoxLayout()
        tr_l = QLabel("Trend Şarkılar")
        tr_l.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 20px; font-weight: 700; background: transparent;")
        tr_hdr.addWidget(tr_l)
        tr_hdr.addStretch()
        tr_btn = QPushButton("Keşfet'te Gör →")
        tr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tr_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {_ACCENT};
                border: none; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ color: {_ACCENT_LIGHT}; }}
        """)
        tr_btn.clicked.connect(lambda: self._nav_to_page(1, 1))
        tr_hdr.addWidget(tr_btn)
        lay.addLayout(tr_hdr)

        # Yükleniyor placeholder
        self._home_trend_loading = QLabel("⏳  Trend şarkılar yükleniyor…")
        self._home_trend_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._home_trend_loading.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 13px; background: transparent; padding: 20px;")
        lay.addWidget(self._home_trend_loading)

        self._home_trends_widget = QWidget()
        self._home_trends_widget.setStyleSheet("background: transparent;")
        self._home_trends_layout = QVBoxLayout(self._home_trends_widget)
        self._home_trends_layout.setContentsMargins(0, 0, 0, 0)
        self._home_trends_layout.setSpacing(4)
        self._home_trends_widget.hide()
        lay.addWidget(self._home_trends_widget)

        lay.addStretch()
        page.setWidget(content)
        return page

    def _build_category_card(self, name: str, genre_key: str, bg: str) -> QFrame:
        """Açılır-kapanır kategori kartı."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 14px;
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # Başlık satırı
        hdr = QFrame()
        hdr.setFixedHeight(54)
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.setStyleSheet("QFrame { background: transparent; border: none; }")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(14, 0, 14, 0)
        hdr_lay.setSpacing(10)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent;")
        expand_btn = QPushButton("▼")
        expand_btn.setFixedSize(24, 24)
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {_TEXT_TERTIARY};
                border: none; font-size: 10px;
            }}
            QPushButton:hover {{ color: {_ACCENT}; }}
        """)
        hdr_lay.addWidget(name_lbl, 1)
        hdr_lay.addWidget(expand_btn)
        card_lay.addWidget(hdr)

        # İçerik paneli (başta gizli)
        content_panel = QWidget()
        content_panel.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(8, 0, 8, 8)
        content_layout.setSpacing(2)
        loading_lbl = QLabel("  ⏳ Yükleniyor…")
        loading_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 11px; background: transparent; padding: 8px;")
        content_layout.addWidget(loading_lbl)
        content_panel.hide()
        card_lay.addWidget(content_panel)

        def toggle():
            will_open = content_panel.isHidden()
            # Tüm kartları kapat (accordion)
            for fn in getattr(self, '_category_close_fns', []):
                fn()
            # Bu kart kapalıysa aç
            if will_open:
                content_panel.show()
                expand_btn.setText("▲")
                card.setStyleSheet(f"""
                    QFrame {{
                        background: {bg};
                        border: 1px solid rgba(0,255,65,0.3);
                        border-radius: 14px;
                    }}
                """)
                # İlk açılışta yükle
                if not getattr(content_panel, "_loaded", False):
                    content_panel._loaded = True
                    self._load_category(genre_key, content_layout, loading_lbl)

        def close_fn():
            if not content_panel.isHidden():
                content_panel.hide()
                expand_btn.setText("▼")
                card.setStyleSheet(f"""
                    QFrame {{
                        background: {bg};
                        border: 1px solid rgba(255,255,255,0.07);
                        border-radius: 14px;
                    }}
                """)

        if hasattr(self, '_category_close_fns'):
            self._category_close_fns.append(close_fn)

        expand_btn.clicked.connect(toggle)
        hdr.mousePressEvent = lambda e: toggle()
        return card


    # ───────────────────────────────────────────────────────────────
    #  KEŞFET  —  arama + video + sonuçlar (mevcut işlevsellik)
    # ───────────────────────────────────────────────────────────────

    def _build_kesfet_page(self) -> QWidget:
        """Keşfet sayfası (index 1) — arama çubuğu + sonuçlar (video artık ayrı sayfa)."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # Arama başlığı
        page_layout.addWidget(self._build_search_header())

        # Sonuçlar scroll (direkt, splitter yok)
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {_SURFACE3}; border-radius: 4px; }}
            QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._results_widget = QWidget()
        self._results_widget.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 20)
        self._results_layout.setSpacing(0)
        self._results_layout.addStretch()
        self._results_scroll.setWidget(self._results_widget)

        results_outer = QWidget()
        results_outer.setStyleSheet("background: transparent;")
        ro_layout = QVBoxLayout(results_outer)
        ro_layout.setContentsMargins(0, 0, 0, 0)
        ro_layout.setSpacing(0)

        # _section_title_label burada oluşur (_build_section_header içinde)
        self._section_header = self._build_section_header()
        ro_layout.addWidget(self._section_header)
        ro_layout.addWidget(self._results_scroll, 1)

        # content_splitter alias (eski referanslar için)
        self._content_splitter = results_outer

        page_layout.addWidget(results_outer, 1)
        return page

    # ───────────────────────────────────────────────────────────────
    #  KÜTÜPHANEfullpage  —  track tablosu + koleksiyonlar
    # ───────────────────────────────────────────────────────────────

    def _build_kutuphane_page(self) -> QWidget:
        """Kütüphane sayfası (index 2) — track listesi + playlist koleksiyonu."""
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {_SURFACE3}; border-radius: 4px; }}
            QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 32)
        layout.setSpacing(24)

        # ── Son Aktivite başlığı ──────────────────────────────
        act_hdr = QHBoxLayout()
        act_t = QLabel("Son Aktivite")
        act_t.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 20px; font-weight: 700; background: transparent;")
        act_hdr.addWidget(act_t)
        act_hdr.addStretch()
        act_all = QPushButton("TÜMÜNÜ GÖR")
        act_all.setCursor(Qt.CursorShape.PointingHandCursor)
        act_all.setStyleSheet(
            f"QPushButton{{color:{_ACCENT};background:transparent;border:none;"
            f"font-size:10px;font-weight:700;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{_ACCENT_LIGHT};}}"
        )
        act_all.clicked.connect(
            lambda: self._library_scroll.setMaximumHeight(16777215)
        )
        act_hdr.addWidget(act_all)
        layout.addLayout(act_hdr)

        # Cam panel — track tablosu
        tt = QFrame()
        tt.setStyleSheet(f"""
            QFrame {{
                background: rgba(18,18,18,0.6);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 16px;
            }}
        """)
        tt_layout = QVBoxLayout(tt)
        tt_layout.setContentsMargins(0, 0, 0, 0)
        tt_layout.setSpacing(0)

        # Sütun başlıkları
        ch = QFrame()
        ch.setFixedHeight(40)
        ch.setStyleSheet(
            "QFrame { background: transparent; border-bottom: 1px solid rgba(255,255,255,0.07);"
            " border-top-left-radius: 16px; border-top-right-radius: 16px; }"
        )
        ch_layout = QHBoxLayout(ch)
        ch_layout.setContentsMargins(24, 0, 24, 0)
        ch_layout.setSpacing(12)
        for txt, fixed_w in [("#", 28), ("BAŞLIK", 0), ("⏱", 60)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"color: {_TEXT_TERTIARY}; font-size: 11px; font-weight: 700;"
                " letter-spacing: 1px; background: transparent;"
            )
            if fixed_w:
                lbl.setFixedWidth(fixed_w)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ch_layout.addWidget(lbl, 0 if fixed_w else 1)
        tt_layout.addWidget(ch)

        # Kütüphane scroll (_add_library_item buraya ekler)
        self._library_scroll = QScrollArea()
        self._library_scroll.setWidgetResizable(True)
        self._library_scroll.setMaximumHeight(400)
        self._library_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #353534; border-radius: 3px; }
        """)
        self._library_widget = QWidget()
        self._library_widget.setStyleSheet("background: transparent;")
        self._library_layout = QVBoxLayout(self._library_widget)
        self._library_layout.setContentsMargins(0, 4, 0, 4)
        self._library_layout.setSpacing(2)
        self._library_layout.addStretch()
        self._library_scroll.setWidget(self._library_widget)
        tt_layout.addWidget(self._library_scroll)
        layout.addWidget(tt)

        # ── Koleksiyonlar başlığı ────────────────────────────
        col_hdr = QHBoxLayout()
        col_t = QLabel("Koleksiyonlar")
        col_t.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 20px; font-weight: 700; background: transparent;")
        col_hdr.addWidget(col_t)
        col_hdr.addStretch()
        layout.addLayout(col_hdr)

        # Cam panel — playlist kartları
        pc = QFrame()
        pc.setStyleSheet(f"""
            QFrame {{
                background: rgba(18,18,18,0.6);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 16px;
            }}
        """)
        pc_layout = QVBoxLayout(pc)
        pc_layout.setContentsMargins(0, 0, 0, 8)
        pc_layout.setSpacing(0)

        # Playlist öğeleri (_add_playlist_item buraya ekler)
        self._playlist_widget = QWidget()
        self._playlist_widget.setStyleSheet("background: transparent;")
        self._playlist_layout = QVBoxLayout(self._playlist_widget)
        self._playlist_layout.setContentsMargins(0, 0, 0, 0)
        self._playlist_layout.setSpacing(2)
        self._playlist_layout.addStretch()
        pc_layout.addWidget(self._playlist_widget)
        layout.addWidget(pc)

        layout.addStretch()
        page.setWidget(content)
        return page


    # ───────────────────────────────────────────────────────────────
    #  CANLÜ TRENDING & THUMBNAIL & KATEGORİ YÜKLEME
    # ───────────────────────────────────────────────────────────────

    def _home_search_submit(self):
        """Ana sayfa arama → Keşfet sayfasına yönlendir ve orada ara."""
        q = self._home_search_input.text().strip()
        if not q:
            return
        # Keşfet sayfasına geç
        self._nav_to_page(1, 1)
        # Keşfet arama kutusuna sorguyu aktar ve aramayı tetikle
        if hasattr(self, '_search_input'):
            self._search_input.setText(q)
        self._do_search()

    def _on_home_search_results(self, items: list, query: str = ""):
        """Ana sayfa inline arama sonuçları geldi."""
        if hasattr(self, "_home_res_title_lbl"):
            self._home_res_title_lbl.setText(f"Arama Sonuçları  ({len(items)} sonuç)")
        if not hasattr(self, "_home_res_items_layout"):
            return
        # Önceki sonuçları temizle
        while self._home_res_items_layout.count() > 1:
            child = self._home_res_items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for item in items:
            self._add_result_item(item, target_layout=self._home_res_items_layout)

    def _home_results_clear(self, clear_input: bool = True):
        """Ana sayfa arama sonuçlarını kapat."""
        if hasattr(self, "_home_results_frame"):
            self._home_results_frame.hide()
        if hasattr(self, "_home_res_items_layout"):
            while self._home_res_items_layout.count() > 1:
                child = self._home_res_items_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        if clear_input and hasattr(self, "_home_search_input"):
            self._home_search_input.clear()

    def _load_live_trends(self):
        """YouTube'dan canlı trending verisi çek (global + Keşfet)."""
        if self._trend_worker and self._trend_worker.isRunning():
            return
        self._trend_worker = _TrendingWorker("global", 12)
        self._trend_worker.trending_ready.connect(self._on_global_trending_ready)
        self._trend_worker.start()
        # Keşfet için de ayrı worker
        kt = _TrendingWorker("kesfet", 20)
        kt.trending_ready.connect(self._on_kesfet_trending_ready)
        kt.start()
        self._cat_workers["kesfet_load"] = kt

    def _on_global_trending_ready(self, items: list):
        """Global trending hazır → Ana Sayfa hero + trend listesi güncelle."""
        self._trending_items = items
        if not items:
            if hasattr(self, "_home_trend_loading"):
                self._home_trend_loading.setText("⚠️  Trending verisi alınamadı.")
            return

        # Hero: #1 şarkı
        top = items[0]
        self._hero_title.setText(top["title"])
        self._hero_badge.setText(f"  ● #{1} Trending  ")
        sub = top.get("uploader", "YouTube Müzik")
        views = top.get("view_count", 0)
        if views:
            sub += f"  ·  {views:,} görüntüleme"
        self._hero_sub.setText(sub)
        # Butonları etkinleştir
        self._hero_play_btn.setEnabled(True)
        self._hero_watch_btn.setEnabled(True)
        hero_url = top["url"]
        try:
            self._hero_play_btn.clicked.disconnect()
        except TypeError:
            pass
        self._hero_play_btn.clicked.connect(lambda: self._play_stream(hero_url))
        try:
            self._hero_watch_btn.clicked.disconnect()
        except TypeError:
            pass
        self._hero_watch_btn.clicked.connect(lambda: self._watch_video_url(hero_url))
        # Thumbnail yükle
        if top.get("thumbnail"):
            self._fetch_thumbnail(self._hero_thumb, top["thumbnail"], size=(210, 210))

        # Trend listesi (1-10)
        if hasattr(self, "_home_trend_loading"):
            self._home_trend_loading.hide()
        if hasattr(self, "_home_trends_layout"):
            self._home_trends_widget.show()
            # Temizle
            while self._home_trends_layout.count():
                ch = self._home_trends_layout.takeAt(0)
                if ch.widget():
                    ch.widget().deleteLater()
            for i, item in enumerate(items[:10]):
                self._add_home_trend_row(item, self._home_trends_layout, i + 1)
        # Up Next listesini de doldur
        self._refresh_up_next()

    def _on_kesfet_trending_ready(self, items: list):
        """Keşfet trending hazır → results alanına yükle (sadece henüz boşsa)."""
        if not items:
            return
        # Yalnızca sonuç listesi henüz boşsa (kullanıcı arama yapmamışsa) doldur
        if self._results_layout.count() <= 1:
            if hasattr(self, "_section_title_label"):
                self._section_title_label.setText("Trend Şarkılar")
            self._clear_results()
            for item in items[:15]:
                self._add_result_item(item)

    def _add_home_trend_row(self, item: dict, layout: "QVBoxLayout", idx: int):
        """Ana Sayfa trend satırı (thumbnail + başlık + oynat/izle/indir)."""
        row = QFrame()
        row.setFixedHeight(62)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"""
            QFrame {{
                background: rgba(18,18,18,0.7);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
            }}
            QFrame:hover {{
                background: rgba(0,255,65,0.05);
                border: 1px solid rgba(0,255,65,0.2);
            }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(12, 0, 10, 0)
        rl.setSpacing(10)

        # Numara
        num = QLabel(str(idx))
        num.setFixedWidth(22)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 12px; background: transparent; font-weight: 700;")
        rl.addWidget(num)

        # Thumbnail
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(42, 42)
        thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_lbl.setText("♫")
        thumb_lbl.setStyleSheet(f"background: {_SURFACE2}; border-radius: 6px; color: {_ACCENT}; font-size: 14px; border: none;")
        rl.addWidget(thumb_lbl)
        if item.get("thumbnail"):
            self._fetch_thumbnail(thumb_lbl, item["thumbnail"], size=(42, 42))

        # Başlık + yazar
        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        t_lbl = QLabel(item["title"])
        t_lbl.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 12px; font-weight: 600; background: transparent;")
        info_col.addWidget(t_lbl)
        if item.get("uploader"):
            a_lbl = QLabel(item["uploader"])
            a_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 10px; background: transparent;")
            info_col.addWidget(a_lbl)
        rl.addLayout(info_col, 1)

        # Butonlar
        url = item["url"]
        for icon, tip, fn in [
            ("▶", "Dinle",  lambda u=url: self._play_stream(u)),
            ("📹", "İzle",  lambda u=url: self._watch_video_url(u)),
            ("⬇", "İndir", lambda u=url: self._download_track(u)),
        ]:
            b = QPushButton(icon)
            b.setFixedSize(28, 28)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {_SURFACE2}; color: {_TEXT_PRIMARY};
                    border: none; border-radius: 14px; font-size: 11px;
                }}
                QPushButton:hover {{ background: {_ACCENT}; color: #003907; }}
            """)
            b.clicked.connect(fn)
            rl.addWidget(b)

        layout.addWidget(row)

    def _load_category(self, genre_key: str, container_layout: "QVBoxLayout",
                       loading_lbl: "QLabel"):
        """Kategori worker başlat."""
        w = _TrendingWorker(genre_key, 10)
        w.trending_ready.connect(
            lambda items, cl=container_layout, ll=loading_lbl:
                self._on_category_ready(items, cl, ll)
        )
        w.start()
        self._cat_workers[genre_key] = w

    def _on_category_ready(self, items: list, container_layout: "QVBoxLayout",
                           loading_lbl: "QLabel"):
        """Kategori sonuçları hazır — listeye ekle."""
        loading_lbl.hide()
        for i, item in enumerate(items[:10]):
            row = QFrame()
            row.setFixedHeight(48)
            row.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border-bottom: 1px solid rgba(255,255,255,0.04);
                    border-radius: 0;
                }}
                QFrame:hover {{ background: rgba(0,255,65,0.04); }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 0, 8, 0)
            rl.setSpacing(8)

            num = QLabel(str(i + 1))
            num.setFixedWidth(18)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 10px; background: transparent;")
            rl.addWidget(num)

            # Thumbnail (small)
            tl = QLabel()
            tl.setFixedSize(32, 32)
            tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tl.setText("♫")
            tl.setStyleSheet(f"background: {_SURFACE2}; border-radius: 5px; color: {_ACCENT}; font-size: 10px; border: none;")
            rl.addWidget(tl)
            if item.get("thumbnail"):
                self._fetch_thumbnail(tl, item["thumbnail"], size=(32, 32))

            t = QLabel(item["title"])
            t.setStyleSheet(f"color: {_TEXT_PRIMARY}; font-size: 11px; font-weight: 500; background: transparent;")
            rl.addWidget(t, 1)

            url = item["url"]
            for icon, tip, fn in [
                ("▶", "Dinle", lambda u=url: self._play_stream(u)),
                ("📹", "İzle", lambda u=url: self._watch_video_url(u)),
                ("⬇", "İndir", lambda u=url: self._download_track(u)),
            ]:
                b = QPushButton(icon)
                b.setFixedSize(24, 24)
                b.setToolTip(tip)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {_SURFACE2}; color: {_TEXT_PRIMARY};
                        border: none; border-radius: 12px; font-size: 9px;
                    }}
                    QPushButton:hover {{ background: {_ACCENT}; color: #003907; }}
                """)
                b.clicked.connect(fn)
                rl.addWidget(b)

            container_layout.addWidget(row)

    def _fetch_thumbnail(self, label: "QLabel", url: str, size=(42, 42)):
        """Thumbnail'ı arkaplanda indir ve label'a yükle."""
        if not url:
            return
        w = _ThumbnailWorker(label, url)
        w.done.connect(lambda lbl, data, s=size: self._on_thumbnail_ready(lbl, data, s))
        w.start()
        self._thumbnail_workers.append(w)
        # Liste büyümesin (tamamlanan temizle)
        self._thumbnail_workers = [x for x in self._thumbnail_workers if x.isRunning()]
        self._thumbnail_workers.append(w)

    def _on_thumbnail_ready(self, label: "QLabel", data: bytes, size=(42, 42)):
        """Thumbnail verisi hazır → QPixmap olarak yükle."""
        if not data:
            return
        from PyQt6.QtGui import QPixmap
        pix = QPixmap()
        pix.loadFromData(data)
        if pix.isNull():
            return
        pix = pix.scaled(
            size[0], size[1],
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Ortalanmış kırp
        if pix.width() > size[0] or pix.height() > size[1]:
            x = (pix.width()  - size[0]) // 2
            y = (pix.height() - size[1]) // 2
            pix = pix.copy(x, y, size[0], size[1])
        label.setText("")
        label.setPixmap(pix)
        label.setStyleSheet(
            f"border-radius: {size[0] // 6}px; background: transparent; border: none;"
        )

    def _download_track(self, url: str):
        """Hızlı indirme — _DownloadWorker ile MP3 indir."""
        if self._download_worker and self._download_worker.isRunning():
            return
        self._download_worker = _DownloadWorker(url, config.MUSIC_DIR)
        self._download_worker.download_done.connect(self._on_download_done)
        self._download_worker.start()

    def _create_playlist_dialog(self):
        """Yeni playlist oluşturma dialogu."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Yeni Playlist", "Playlist adı:",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        import json, os
        path = os.path.join(config.BASE_DIR, "music", "playlists.json")
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                pass
        if name in data:
            return  # zaten var
        data[name] = []
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Playlist sayfasına geç ve listesi yenile
        self._nav_to_page(2, 2)
        # Yeni öğe ekle (duplicate olmadan)
        self._add_playlist_item(name)


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
        header.setFixedHeight(120)
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
        
        # Arama satırı — Ana Sayfa ile aynı pill tasarım
        sf = QFrame()
        sf.setFixedHeight(44)
        sf.setStyleSheet(f"""
            QFrame {{
                background: rgba(42,42,42,0.9);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 22px;
            }}
        """)
        sf_lay = QHBoxLayout(sf)
        sf_lay.setContentsMargins(16, 0, 8, 0)
        sf_lay.setSpacing(8)
        sch_icon = QLabel("🔍")
        sch_icon.setStyleSheet(f"color: {_TEXT_TERTIARY}; background: transparent; font-size: 14px;")
        sf_lay.addWidget(sch_icon)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Şarkı, sanatçı veya video ara…")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none;
                color: {_TEXT_PRIMARY}; font-size: 14px;
            }}
        """)
        self._search_input.returnPressed.connect(self._do_search)
        sf_lay.addWidget(self._search_input, 1)

        self._search_btn = QPushButton("Ara")
        self._search_btn.setFixedHeight(30)
        self._search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT}; color: #003907; border: none;
                border-radius: 15px; font-size: 12px; font-weight: 700;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}
        """)
        self._search_btn.clicked.connect(self._do_search)
        sf_lay.addWidget(self._search_btn)

        layout.addWidget(sf)

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
        """Video izleme sayfası — stitch 'Video Watch' tasarımı (8/12 + 4/12)."""
        # ── Shared button style helpers ──
        _pill = f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                padding: 6px 11px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.14);
                border-color: rgba(255,255,255,0.22);
            }}
            QPushButton:disabled {{
                color: rgba(229,226,225,0.30);
                background: rgba(255,255,255,0.03);
                border-color: rgba(255,255,255,0.05);
            }}
        """

        container = QFrame()
        container.setObjectName("videoDeck")
        container.setStyleSheet("QFrame#videoDeck { background: transparent; border: none; }")

        root = QHBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ════════════════════════════════════════════════════════
        # LEFT COLUMN — video player + metadata
        # ════════════════════════════════════════════════════════
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 5px; background: transparent; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.12); border-radius: 3px;
            }
        """)

        left_widget = QFrame()
        left_widget.setStyleSheet("background: transparent; border: none;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 16, 12, 20)
        left_layout.setSpacing(14)

        # ── 1. Ambient glow wrapper + video stage ──
        glow_frame = QFrame()
        glow_frame.setObjectName("videoGlow")
        glow_frame.setStyleSheet("""
            QFrame#videoGlow {
                background: rgba(0,255,65,0.05);
                border: 1px solid rgba(0,255,65,0.20);
                border-radius: 16px;
            }
        """)
        glow_vl = QVBoxLayout(glow_frame)
        glow_vl.setContentsMargins(0, 0, 0, 0)
        glow_vl.setSpacing(0)

        self._video_stage = QFrame()
        self._video_stage.setObjectName("videoStage")
        self._video_stage.setStyleSheet("""
            QFrame#videoStage {
                background: #000000;
                border-radius: 14px;
            }
        """)
        stage_vl = QVBoxLayout(self._video_stage)
        stage_vl.setContentsMargins(0, 0, 0, 0)
        stage_vl.setSpacing(0)
        self._video_widget.setMinimumHeight(360)
        self._video_widget.setStyleSheet("background: #000000;")
        stage_vl.addWidget(self._video_widget, 1)

        glow_vl.addWidget(self._video_stage)
        left_layout.addWidget(glow_frame, 1)

        # ── 2. Control bar ──
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("vidCtrl")
        ctrl_frame.setStyleSheet(f"""
            QFrame#vidCtrl {{
                background: rgba(18,18,18,0.88);
                border: 1px solid rgba(0,255,65,0.14);
                border-radius: 12px;
            }}
        """)
        ctrl_vl = QVBoxLayout(ctrl_frame)
        ctrl_vl.setContentsMargins(16, 10, 16, 10)
        ctrl_vl.setSpacing(8)

        # Seek slider
        self._vid_progress = QSlider(Qt.Orientation.Horizontal)
        self._vid_progress.setRange(0, 1000)
        self._vid_progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.10);
                height: 5px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {_TEXT_PRIMARY};
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -5px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {_ACCENT};
                border-radius: 3px;
            }}
        """)
        self._vid_progress.sliderPressed.connect(lambda: setattr(self, "_is_seeking", True))
        self._vid_progress.sliderReleased.connect(self._vid_on_seek_end)
        ctrl_vl.addWidget(self._vid_progress)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._vid_play_btn = QPushButton("▶")
        self._vid_play_btn.setFixedSize(40, 40)
        self._vid_play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #000;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {_ACCENT_LIGHT}; }}
        """)
        self._vid_play_btn.clicked.connect(self._vid_toggle_play)
        btn_row.addWidget(self._vid_play_btn)

        self._vid_back_btn = QPushButton("⏪ -10s")
        self._vid_back_btn.setStyleSheet(_pill)
        self._vid_back_btn.clicked.connect(lambda: self._vid_seek_rel(-10000))
        btn_row.addWidget(self._vid_back_btn)

        self._vid_fwd_btn = QPushButton("+10s ⏩")
        self._vid_fwd_btn.setStyleSheet(_pill)
        self._vid_fwd_btn.clicked.connect(lambda: self._vid_seek_rel(10000))
        btn_row.addWidget(self._vid_fwd_btn)

        self._vid_time_label = QLabel("0:00 / 0:00")
        self._vid_time_label.setStyleSheet(f"color: {_TEXT_SECONDARY}; font-size: 12px;")
        btn_row.addWidget(self._vid_time_label)

        btn_row.addStretch()

        self._vid_speed_combo = QComboBox()
        self._vid_speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self._vid_speed_combo.setCurrentIndex(2)
        self._vid_speed_combo.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255,255,255,0.07);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {_SURFACE2};
                color: {_TEXT_PRIMARY};
                selection-background-color: {_ACCENT};
            }}
        """)
        self._vid_speed_combo.currentTextChanged.connect(self._vid_set_speed)
        btn_row.addWidget(self._vid_speed_combo)

        self._vid_fullscreen_btn = QPushButton("⛶ Tam Ekran")
        self._vid_fullscreen_btn.setStyleSheet(_pill)
        self._vid_fullscreen_btn.clicked.connect(self._vid_toggle_fullscreen)
        btn_row.addWidget(self._vid_fullscreen_btn)

        # Status badge (compact, inline)
        self._video_status_badge = QLabel("BEKLEMEDE")
        self._video_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_status_badge.setMinimumWidth(90)
        self._video_status_badge.setStyleSheet("""
            QLabel {
                background: rgba(148,163,184,0.16);
                color: #CBD5E1;
                border: 1px solid rgba(148,163,184,0.22);
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }
        """)
        btn_row.addWidget(self._video_status_badge)

        self._video_browser_btn = QPushButton("🌐 Tarayıcıda")
        self._video_browser_btn.setEnabled(False)
        self._video_browser_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,65,0.10);
                color: {_ACCENT};
                border: 1px solid rgba(0,255,65,0.28);
                border-radius: 8px;
                padding: 6px 11px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(0,255,65,0.20); }}
            QPushButton:disabled {{
                color: rgba(0,255,65,0.30);
                background: rgba(0,255,65,0.04);
                border-color: rgba(0,255,65,0.08);
            }}
        """)
        self._video_browser_btn.clicked.connect(self._open_video_in_browser)
        btn_row.addWidget(self._video_browser_btn)

        self._video_minimize_btn = QPushButton("⬇ Küçült")
        self._video_minimize_btn.setStyleSheet(_pill)
        self._video_minimize_btn.clicked.connect(self._minimize_video)
        btn_row.addWidget(self._video_minimize_btn)

        self._video_back_btn = QPushButton("✕ Kapat")
        self._video_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                padding: 6px 11px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(220,50,50,0.22);
                border-color: rgba(220,50,50,0.40);
            }}
        """)
        self._video_back_btn.clicked.connect(self._close_video)
        btn_row.addWidget(self._video_back_btn)

        ctrl_vl.addLayout(btn_row)
        left_layout.addWidget(ctrl_frame)

        # ── 3. Title + meta ──
        title_frame = QFrame()
        title_frame.setStyleSheet("background: transparent; border: none;")
        title_fl = QVBoxLayout(title_frame)
        title_fl.setContentsMargins(4, 0, 4, 0)
        title_fl.setSpacing(5)

        self._video_title_label = QLabel("Video hazır bekleniyor")
        self._video_title_label.setWordWrap(True)
        self._video_title_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_PRIMARY};
                font-size: 20px;
                font-weight: 700;
                letter-spacing: -0.3px;
            }}
        """)
        title_fl.addWidget(self._video_title_label)

        self._video_meta_label = QLabel("Bir video seçildiğinde bilgiler burada görünür.")
        self._video_meta_label.setWordWrap(True)
        self._video_meta_label.setStyleSheet(
            f"color: {_TEXT_SECONDARY}; font-size: 13px;"
        )
        title_fl.addWidget(self._video_meta_label)
        left_layout.addWidget(title_frame)

        # ── 4. Channel row + action buttons ──
        ch_frame = QFrame()
        ch_frame.setStyleSheet("background: transparent; border: none;")
        ch_hl = QHBoxLayout(ch_frame)
        ch_hl.setContentsMargins(4, 0, 4, 0)
        ch_hl.setSpacing(12)

        ch_avatar = QLabel("♪")
        ch_avatar.setFixedSize(44, 44)
        ch_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ch_avatar.setStyleSheet(f"""
            QLabel {{
                background: {_SURFACE2};
                border: 2px solid rgba(0,255,65,0.28);
                border-radius: 22px;
                color: {_TEXT_SECONDARY};
                font-size: 20px;
            }}
        """)
        ch_hl.addWidget(ch_avatar)

        ch_info_vl = QVBoxLayout()
        ch_info_vl.setSpacing(1)
        self._vid_channel_label = QLabel("YouTube")
        self._vid_channel_label.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        ch_info_vl.addWidget(self._vid_channel_label)
        ch_src_label = QLabel("youtube.com")
        ch_src_label.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 11px;")
        ch_info_vl.addWidget(ch_src_label)
        ch_hl.addLayout(ch_info_vl)

        ch_hl.addStretch()

        _action_btn_ss = f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {_TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.12);
                border-color: rgba(255,255,255,0.22);
            }}
        """
        for icon_lbl in [("👍", "Beğen"), ("🔗", "Paylaş"), ("⬇", "İndir")]:
            ab = QPushButton(f"{icon_lbl[0]}  {icon_lbl[1]}")
            ab.setStyleSheet(_action_btn_ss)
            ch_hl.addWidget(ab)

        left_layout.addWidget(ch_frame)

        # ── 5. Glassmorphic description ──
        desc_frame = QFrame()
        desc_frame.setObjectName("vidDesc")
        desc_frame.setStyleSheet("""
            QFrame#vidDesc {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px;
            }
        """)
        desc_vl = QVBoxLayout(desc_frame)
        desc_vl.setContentsMargins(16, 12, 16, 12)
        desc_vl.setSpacing(6)

        self._video_desc_label = QLabel("Video açıklaması yüklenecek…")
        self._video_desc_label.setWordWrap(True)
        self._video_desc_label.setStyleSheet(
            f"color: {_TEXT_TERTIARY}; font-size: 13px; line-height: 1.5;"
        )
        desc_vl.addWidget(self._video_desc_label)
        left_layout.addWidget(desc_frame)

        left_layout.addStretch()
        left_scroll.setWidget(left_widget)
        left_scroll.setMinimumWidth(320)
        root.addWidget(left_scroll, 63)

        # ════════════════════════════════════════════════════════
        # RIGHT COLUMN — Sıradaki / Up Next
        # ════════════════════════════════════════════════════════
        right_frame = QFrame()
        right_frame.setObjectName("upNextPanel")
        right_frame.setMaximumWidth(320)
        right_frame.setStyleSheet(f"""
            QFrame#upNextPanel {{
                background: rgba(255,255,255,0.02);
                border-left: 1px solid rgba(255,255,255,0.07);
            }}
        """)
        right_vl = QVBoxLayout(right_frame)
        right_vl.setContentsMargins(14, 16, 14, 16)
        right_vl.setSpacing(10)

        # Header
        rh = QHBoxLayout()
        rh_title = QLabel("Sıradaki")
        rh_title.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; font-size: 15px; font-weight: 700;"
        )
        rh.addWidget(rh_title)
        rh.addStretch()
        ap_lbl = QLabel("Otomatik Oynat")
        ap_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 11px;")
        rh.addWidget(ap_lbl)
        ap_dot = QLabel("●")
        ap_dot.setStyleSheet(f"color: {_ACCENT}; font-size: 11px;")
        rh.addWidget(ap_dot)
        right_vl.addLayout(rh)

        # Scroll list
        up_next_scroll = QScrollArea()
        up_next_scroll.setWidgetResizable(True)
        up_next_scroll.setFrameShape(QFrame.Shape.NoFrame)
        up_next_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        up_next_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.10); border-radius: 2px;
            }
        """)

        up_next_widget = QFrame()
        up_next_widget.setStyleSheet("background: transparent; border: none;")
        self._up_next_layout = QVBoxLayout(up_next_widget)
        self._up_next_layout.setContentsMargins(0, 0, 0, 0)
        self._up_next_layout.setSpacing(2)

        # Placeholder
        ph = QLabel("Trending yükleniyor…")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 12px; padding: 20px 0;")
        self._up_next_layout.addWidget(ph)
        self._up_next_layout.addStretch()

        up_next_scroll.setWidget(up_next_widget)
        right_vl.addWidget(up_next_scroll, 1)

        root.addWidget(right_frame, 37)

        # Player signals
        self._video_player.positionChanged.connect(self._vid_on_position_changed)
        self._video_player.durationChanged.connect(self._vid_on_duration_changed)
        self._video_player.playbackStateChanged.connect(self._on_video_state_changed)
        self._video_player.mediaStatusChanged.connect(self._on_media_status_changed)

        self._set_video_panel_state(
            "BEKLEMEDE",
            "Bir video seçildiğinde oynatma başlar.",
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

    # ── Up Next helpers ──────────────────────────────────────────
    def _refresh_up_next(self) -> None:
        """_up_next_layout'u _trending_items ile doldur."""
        if not hasattr(self, "_up_next_layout"):
            return
        items = getattr(self, "_trending_items", [])
        if not items:
            return
        # Temizle (stretch hariç)
        while self._up_next_layout.count() > 1:
            item = self._up_next_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, it in enumerate(items[:12]):
            card = self._build_up_next_card(it, i)
            self._up_next_layout.insertWidget(self._up_next_layout.count() - 1, card)

    def _build_up_next_card(self, item: dict, idx: int) -> QFrame:
        """160px thumbnail + başlık + kanal satırı (stitch 'Up Next' kartı)."""
        url = item.get("url", "")
        title = item.get("title", "—")
        uploader = item.get("uploader", "")
        views = item.get("view_count", 0)
        views_str = f"{views:,} görüntüleme" if views else ""

        card = QFrame()
        card.setFixedHeight(72)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: rgba(255,255,255,0.05);
            }}
        """)
        hl = QHBoxLayout(card)
        hl.setContentsMargins(6, 5, 6, 5)
        hl.setSpacing(10)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(114, 64)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(f"""
            QLabel {{
                background: {_SURFACE2};
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 6px;
                color: {_TEXT_TERTIARY};
                font-size: 20px;
            }}
        """)
        thumb.setText("▶")
        if item.get("thumbnail"):
            self._fetch_thumbnail(thumb, item["thumbnail"], size=(114, 64))
        hl.addWidget(thumb)

        # Duration badge (overlay not possible in QLabel easily, skip)

        # Text
        info = QVBoxLayout()
        info.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setWordWrap(False)
        t_lbl.setMaximumWidth(180)
        t_lbl.setStyleSheet(
            f"color: {_TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
        )
        # Truncate with elide
        metrics = t_lbl.fontMetrics()
        t_lbl.setText(metrics.elidedText(title, Qt.TextElideMode.ElideRight, 178))
        info.addWidget(t_lbl)

        if uploader:
            ch_lbl = QLabel(uploader)
            ch_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 11px;")
            info.addWidget(ch_lbl)
        if views_str:
            v_lbl = QLabel(views_str)
            v_lbl.setStyleSheet(f"color: {_TEXT_TERTIARY}; font-size: 10px; opacity: 0.7;")
            info.addWidget(v_lbl)

        hl.addLayout(info, 1)

        # Click → watch
        if url:
            card.mousePressEvent = lambda e, u=url: self._watch_video_url(u)  # type: ignore[assignment]

        return card

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
        """Video görünümünü küçült — ses çalmaya devam eder, Keşfet'e döner."""
        self._nav_to_page(1, 1)
        
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
                
    def _add_result_item(self, item: dict, target_layout=None):
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
        
        # Thumbnail + numara
        idx = self._results_layout.count()
        thumb_lbl_r = QLabel()
        thumb_lbl_r.setFixedSize(42, 42)
        thumb_lbl_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_lbl_r.setText(str(idx))
        thumb_lbl_r.setStyleSheet(
            f"background: {_SURFACE2}; border-radius: 6px; color: {_TEXT_TERTIARY};"
            " font-size: 11px; font-weight: 700; border: none;"
        )
        card_layout.addWidget(thumb_lbl_r)
        if item.get("thumbnail"):
            self._fetch_thumbnail(thumb_lbl_r, item["thumbnail"], size=(42, 42))

        badge = QLabel(str(idx))
        badge.setFixedSize(28, 28)
        badge.hide()   # thumbnail varken gizle
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
        
        target = target_layout if target_layout is not None else self._results_layout
        target.insertWidget(target.count() - 1, row)

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
        
        # Butonlar: Play + (video dosyasıysa) İzle + Sil
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(28, 28)
        play_btn.setToolTip("Dinle")
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        # Video dosyası mı?
        _VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v",
                       ".ts", ".mpeg", ".mpg", ".wmv", ".flv", ".3gp")
        if filename.lower().endswith(_VIDEO_EXTS):
            watch_btn = QPushButton("�")
            watch_btn.setFixedSize(28, 28)
            watch_btn.setToolTip("Büyük Ekranda İzle (Video Sayfası)")
            watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            watch_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(233,20,41,0.7);
                    color: #fff; border: none;
                    border-radius: 14px; font-size: 11px;
                }}
                QPushButton:hover {{ background: {_ACCENT_ROSE}; }}
            """)
            import os as _os
            fpath = _os.path.join(config.MUSIC_DIR, filename)
            watch_btn.clicked.connect(
                lambda checked=False, p=fpath: self._play_local_video(p)
            )
            layout.addWidget(watch_btn)

        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("Sil")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {_TEXT_TERTIARY};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{ color: {_ACCENT_ROSE}; }}
        """)
        del_btn.clicked.connect(lambda checked=False, fn=filename: self._delete_lib_track(fn))
        layout.addWidget(del_btn)

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
        # Önce mevcut medyayı durdur
        self._video_player.stop()
        if self._stream_worker:
            self._stream_worker.quit()
            self._stream_worker.wait()
        self._pending_video_url = url
        self._current_url = url
        # Video sayfasına (index 3) geç
        self._nav_to_page(3)
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
        # Kanal label'ını güncelle (uploader bilgisi pending URL'den eşleştir)
        if hasattr(self, "_vid_channel_label"):
            matched = next(
                (it for it in getattr(self, "_trending_items", [])
                 if it.get("title", "") == title),
                None,
            )
            if matched and matched.get("uploader"):
                self._vid_channel_label.setText(matched["uploader"])
        self._set_video_panel_state(
            "CANLI",
            f"{fmt} hazır. İsterseniz videoyu tarayıcıda orijinal sayfasında da açabilirsiniz.",
            "live",
        )
        self._nav_to_page(3)  # Video sayfasına geç
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()
        self._pending_video_url = ""
        
    def _on_video_stream_error(self, error: str):
        """Video stream hatası."""
        logger.error(f"Video stream hatası: {error}")
        self._nav_to_page(3)  # Video sayfasında hata mesajını göster
        self._video_title_label.setText("Video açılamadı")
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

    def _on_media_status_changed(self, status):
        """Medya durumu değişti — parça bitiminde otomatik sonrakine geç."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._current_playlist:
                self._on_next()
                
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
            self._fullscreen_window = _FullScreenVideoWindow(
                self._video_widget,
                player=self._video_player,
                title=self._current_title,
                on_prev=self._on_prev,
                on_next=self._on_next,
            )
            self._fullscreen_window.closed.connect(self._exit_fullscreen)
            
    def _exit_fullscreen(self):
        """Tam ekrandan çık."""
        if self._fullscreen_window:
            self._fullscreen_window.close()
            self._fullscreen_window = None
            # Video widget'ı tekrar container'a ekle
            self._video_stage.layout().addWidget(self._video_widget)
            
    def _close_video(self):
        """Video'yu kapat — Keşfet sayfasına dön."""
        self._video_player.stop()
        self._is_video_mode = False
        self._pending_video_url = ""
        self._current_url = ""
        self._video_browser_btn.setEnabled(False)
        self._video_title_label.setText("Video hazır bekleniyor")
        self._set_video_panel_state("BEKLEMEDE", "Bir video seçildiğinde oynatma başlar.", "idle")
        # Keşfet sayfasına dön
        self._nav_to_page(1, 1)
        
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
        """Now playing bilgisini güncelle + track_changed sinyali yayınla."""
        title = self._current_title or "Şarkı seçilmedi"
        fm = self._title_label.fontMetrics()
        elided = fm.elidedText(title, Qt.TextElideMode.ElideRight, 380)
        self._title_label.setText(elided)
        self._title_label.setToolTip(title)
        # Mini player senkronizasyonu
        try:
            self.track_changed.emit(
                title,
                self._current_url or "",
                self._current_idx if self._current_idx >= 0 else 0,
            )
        except Exception:
            pass
        
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
    def _play_local_video(self, filepath: str):
        """Yerel video dosyasını video oynatıcıda oynat."""
        import os
        if not os.path.isfile(filepath):
            return
        self._video_player.stop()
        name = os.path.basename(filepath)
        self._video_title_label.setText(name)
        self._set_video_panel_state("OYNATILIYOR", f"Yerel dosya: {name}", "live")
        self._video_player.setSource(QUrl.fromLocalFile(filepath))
        self._current_title = name
        self._current_url = filepath
        self._is_video_mode = True
        self._nav_to_page(3)  # Video sayfasına geç
        self._video_player.play()
        self._update_now_playing()
        self._start_glow_pulse()

    def _delete_lib_track(self, filename: str):
        """Kütüphane dosyasını sil (onay sorar)."""
        from PyQt6.QtWidgets import QMessageBox
        import os
        path = os.path.join(config.MUSIC_DIR, filename)
        reply = QMessageBox.question(
            self, "Dosyayı Sil",
            f'"{filename}" silinsin mi?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
            except Exception:
                pass
            self._refresh_library()


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
        """Trend şarkılar yükle — canlı veya önbellek."""
        if self._trending_items:
            # Zaten yüklendi
            if hasattr(self, "_section_title_label"):
                self._section_title_label.setText("Trend Şarkılar")
            self._clear_results()
            for item in self._trending_items[:15]:
                self._add_result_item(item)
        else:
            # Henüz yüklenmedi → boş placeholder
            if hasattr(self, "_section_title_label"):
                self._section_title_label.setText("Trend Şarkılar  (yükleniyor…)")
            self._clear_results()
