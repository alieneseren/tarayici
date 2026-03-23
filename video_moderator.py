"""
Visionary Navigator — Video İçerik Moderasyonu
Gemini Vision API ile periyodik kare analizi.
Uygunsuz içerik algılama + uyarı + blur overlay.
"""

import base64
import logging
from io import BytesIO
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QBuffer
from PyQt6.QtGui import QColor, QPixmap, QImage

from settings_manager import SettingsManager

logger = logging.getLogger("VideoMod")
logger.setLevel(logging.INFO)

# Video platformu domain'leri
VIDEO_DOMAINS = [
    "youtube.com", "youtu.be", "netflix.com", "disneyplus.com",
    "primevideo.com", "hbomax.com", "twitch.tv", "dailymotion.com",
    "vimeo.com", "puhutv.com", "blutv.com", "exxen.com", "gain.tv",
    "mubi.com", "tabii.com",
]

ANALYSIS_INTERVAL_MS = 8000  # 8 saniye


class _FrameAnalyzer(QThread):
    """Kareyi Gemini Vision API'ye gönderip analiz eder."""

    result = pyqtSignal(bool, str)   # (is_unsafe, explanation)
    error = pyqtSignal(str)

    def __init__(self, image_base64: str, api_key: str):
        super().__init__()
        self._image_b64 = image_base64
        self._api_key = api_key

    def run(self):
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)

            prompt = (
                "Bu bir web tarayıcı ekran görüntüsüdür. "
                "Görselde şiddet, cinsel içerik, çıplaklık veya +18 yetişkin içerik var mı? "
                "Cevabını JSON formatında ver: {\"unsafe\": true/false, \"reason\": \"açıklama\"} "
                "Eğer içerik uygunsuz değilse reason boş bırak."
            )

            image_bytes = base64.b64decode(self._image_b64)

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                ],
                config={"temperature": 0.1, "max_output_tokens": 256}
            )

            if response and response.text:
                import json
                text = response.text.strip()
                # JSON bloğunu çıkar
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                try:
                    data = json.loads(text)
                    is_unsafe = data.get("unsafe", False)
                    reason = data.get("reason", "")
                    self.result.emit(bool(is_unsafe), str(reason))
                except json.JSONDecodeError:
                    # JSON parse edilemezse güvenli say
                    self.result.emit(False, "")
            else:
                self.result.emit(False, "")

        except Exception as e:
            logger.error(f"Kare analiz hatası: {e}")
            self.error.emit(str(e)[:80])


class VideoModerator(QWidget):
    """Video içerik moderasyon paneli — floating island."""

    mod_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoModPanel")
        self.setFixedSize(320, 180)
        self._settings = SettingsManager()
        self._is_monitoring = False
        self._last_status = "idle"
        self._analyzer: Optional[_FrameAnalyzer] = None
        self._web_view = None  # Aktif QWebEngineView referansı

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._capture_and_analyze)

        self._setup_ui()

    def set_web_view(self, view) -> None:
        """Aktif sekmenin QWebEngineView'ını ayarla."""
        self._web_view = view

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QWidget#videoModPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1A1225, stop:1 #0E0A18);
                border: 1px solid rgba(255,82,82,0.15);
                border-radius: 16px;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # Başlık
        header = QHBoxLayout()
        icon = QLabel("🛡️")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("VİDEO MODERASYON")
        title.setStyleSheet("""
            font-size: 11px; font-weight: 800; color: #FF5252;
            letter-spacing: 2px;
        """)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #565670; font-size: 12px;
            }
            QPushButton:hover { color: #FF5252; }
        """)
        close_btn.clicked.connect(self._close)

        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        lay.addLayout(header)

        # Durum göstergesi
        self._status_label = QLabel("Hazır — Taramayı başlatın")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("""
            font-size: 12px; color: #8E8EA0; padding: 4px 0;
            line-height: 1.4;
        """)
        lay.addWidget(self._status_label)

        # Kontrol butonları
        btn_row = QHBoxLayout()

        self._toggle_btn = QPushButton("▶ Başlat")
        self._toggle_btn.setFixedHeight(34)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,82,82,0.12);
                border: 1px solid rgba(255,82,82,0.3);
                border-radius: 8px; color: #FF5252;
                font-size: 12px; font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: rgba(255,82,82,0.2);
                border-color: rgba(255,82,82,0.5);
            }
        """)
        self._toggle_btn.clicked.connect(self._toggle_monitoring)
        btn_row.addWidget(self._toggle_btn, 1)
        lay.addLayout(btn_row)

        lay.addStretch()

    def _toggle_monitoring(self) -> None:
        if self._is_monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        if not self._settings.has_gemini():
            self._status_label.setText("⚠️ Gemini API anahtarı gerekli.\nAyarlar → API anahtarı girin.")
            self._status_label.setStyleSheet("font-size: 12px; color: #FF5252; padding: 4px 0;")
            return

        self._is_monitoring = True
        self._toggle_btn.setText("⏹ Durdur")
        self._status_label.setText("🔍 Tarama aktif — kareler analiz ediliyor...")
        self._status_label.setStyleSheet("font-size: 12px; color: #00E676; padding: 4px 0;")
        self._timer.start(ANALYSIS_INTERVAL_MS)
        logger.info("Video moderasyon başlatıldı")

    def _stop_monitoring(self) -> None:
        self._is_monitoring = False
        self._timer.stop()
        self._toggle_btn.setText("▶ Başlat")
        self._status_label.setText("Tarama durduruldu.")
        self._status_label.setStyleSheet("font-size: 12px; color: #8E8EA0; padding: 4px 0;")
        logger.info("Video moderasyon durduruldu")

    def _capture_and_analyze(self) -> None:
        """Aktif sekmeden kare yakala ve Gemini'ye gönder."""
        if not self._web_view or not self._settings.has_gemini():
            return

        if self._analyzer and self._analyzer.isRunning():
            return  # Önceki analiz devam ediyor

        try:
            # Ekran görüntüsü al
            pixmap = self._web_view.grab()
            if pixmap.isNull():
                return

            # Küçült (API'ye büyük resim göndermemek için)
            scaled = pixmap.scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio)

            # Base64'e çevir
            buffer = QBuffer()
            buffer.open(QBuffer.OpenModeFlag.ReadWrite)
            scaled.save(buffer, "PNG")
            image_bytes = buffer.data().data()
            buffer.close()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # Analiz thread'ini başlat
            self._analyzer = _FrameAnalyzer(image_b64, self._settings.gemini_api_key)
            self._analyzer.result.connect(self._on_analysis_result)
            self._analyzer.error.connect(self._on_analysis_error)
            self._analyzer.start()

        except Exception as e:
            logger.error(f"Kare yakalama hatası: {e}")

    def _on_analysis_result(self, is_unsafe: bool, reason: str) -> None:
        if is_unsafe:
            self._status_label.setText(f"🚨 Uygunsuz içerik algılandı!\n{reason}")
            self._status_label.setStyleSheet("font-size: 12px; color: #FF5252; padding: 4px 0; font-weight: 600;")

            # Blur overlay enjekte et
            if self._web_view:
                self._web_view.page().runJavaScript("""
                    (function() {
                        let overlay = document.getElementById('visionary-blur-overlay');
                        if (!overlay) {
                            overlay = document.createElement('div');
                            overlay.id = 'visionary-blur-overlay';
                            overlay.style.cssText = `
                                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                                background: rgba(0,0,0,0.85); backdrop-filter: blur(30px);
                                z-index: 999999; display: flex; align-items: center;
                                justify-content: center; flex-direction: column;
                            `;
                            overlay.innerHTML = `
                                <div style="color:#FF5252;font-size:48px;margin-bottom:16px">🛡️</div>
                                <div style="color:#FFF;font-size:20px;font-weight:700;margin-bottom:8px">
                                    Uygunsuz İçerik Algılandı</div>
                                <div style="color:#888;font-size:14px;margin-bottom:24px">
                                    Bu sayfa hassas içerik barındırıyor olabilir.</div>
                                <button onclick="this.parentElement.remove()"
                                    style="background:#FF5252;color:#FFF;border:none;
                                    border-radius:8px;padding:12px 32px;font-size:14px;
                                    font-weight:600;cursor:pointer">Yine de Göster</button>
                            `;
                            document.body.appendChild(overlay);
                        }
                    })();
                """)
        else:
            self._status_label.setText("✅ İçerik güvenli — tarama devam ediyor")
            self._status_label.setStyleSheet("font-size: 12px; color: #00E676; padding: 4px 0;")

    def _on_analysis_error(self, msg: str) -> None:
        self._status_label.setText(f"⚠️ Analiz hatası: {msg[:50]}")
        self._status_label.setStyleSheet("font-size: 12px; color: #FFB300; padding: 4px 0;")

    def _close(self) -> None:
        self._stop_monitoring()
        self.hide()
        self.mod_closed.emit()
