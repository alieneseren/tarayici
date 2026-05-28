"""
Visionary Navigator — Face Swap Preview Panel
Yüz değiştirme sonuçlarını gösteren premium glassmorphism UI.
Before/After slider, kaydetme ve tekrar deneme butonları.
"""

import logging
import os
import time
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
)
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QGraphicsDropShadowEffect, QFileDialog,
    QGraphicsOpacityEffect, QSizePolicy,
)

import config

logger = logging.getLogger("FaceSwapPreview")


class FaceSwapWorker(QThread):
    """Arka planda yüz değiştirme işlemi."""

    progress = pyqtSignal(str)     # Durum mesajı
    finished = pyqtSignal(object)  # Sonuç np.ndarray veya None
    error = pyqtSignal(str)

    def __init__(self, product_image: np.ndarray, user_photo_path: str):
        super().__init__()
        self._product_image = product_image
        self._user_photo_path = user_photo_path

    def run(self):
        try:
            self.progress.emit("🔍 Yüzler algılanıyor...")

            from face_swap_engine import FaceSwapEngine
            engine = FaceSwapEngine()

            # Kullanıcı fotoğrafını yükle
            user_photo = cv2.imread(self._user_photo_path)
            if user_photo is None:
                self.error.emit("Fotoğrafınız yüklenemedi.")
                return

            self.progress.emit("🎭 Yüz değiştiriliyor...")

            result = engine.swap_in_product_photo(
                product_image=self._product_image,
                user_photo=user_photo,
                enhance=False,
            )

            if result is None:
                self.error.emit("Fotoğraflarda yüz algılanamadı.")
                return

            self.progress.emit("✅ Tamamlandı!")
            self.finished.emit(result)

        except Exception as e:
            logger.error(f"FaceSwap hatası: {e}", exc_info=True)
            self.error.emit(f"İşlem hatası: {str(e)[:100]}")


class FaceSwapPreview(QWidget):
    """
    Yüz değiştirme sonucunu gösteren premium overlay panel.
    Before/After karşılaştırma, kaydetme, tekrar deneme.
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("faceSwapPreview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._original_image: Optional[np.ndarray] = None
        self._result_image: Optional[np.ndarray] = None
        self._worker: Optional[FaceSwapWorker] = None
        self._slider_value = 100  # 0=orijinal, 100=sonuç

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            #faceSwapPreview {
                background: rgba(10, 10, 16, 0.97);
                border: 1px solid rgba(108, 99, 255, 0.15);
                border-radius: 20px;
            }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Header ───────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(108,99,255,0.08), stop:1 rgba(0,217,255,0.05));
                border-bottom: 1px solid rgba(108,99,255,0.12);
                border-radius: 20px 20px 0 0;
            }
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 16, 0)

        icon = QLabel("🎭")
        icon.setStyleSheet("font-size: 20px;")

        title = QLabel("Yüz Değiştirme")
        title.setStyleSheet("""
            font-size: 14px; font-weight: 700; color: #FFFFFF;
            letter-spacing: 1px;
        """)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px; color: #8E8EA0; font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255,82,82,0.15);
                border-color: rgba(255,82,82,0.3); color: #FF5252;
            }
        """)
        close_btn.clicked.connect(self._close)

        h_lay.addWidget(icon)
        h_lay.addWidget(title)
        h_lay.addStretch()
        h_lay.addWidget(close_btn)

        # ── Image Display ────────────────────────────────────────
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(300)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._image_label.setStyleSheet("""
            QLabel {
                background: #0A0A0F;
                border: none;
                color: #565670;
                font-size: 13px;
            }
        """)

        # ── Status / Loading ─────────────────────────────────────
        self._status = QLabel()
        self._status.setFixedHeight(28)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("""
            color: #6C63FF; font-size: 12px; font-weight: 600;
            letter-spacing: 0.5px;
        """)

        # ── Before/After Slider ──────────────────────────────────
        slider_container = QFrame()
        slider_container.setFixedHeight(46)
        slider_container.setStyleSheet("background: transparent;")
        sl = QHBoxLayout(slider_container)
        sl.setContentsMargins(24, 0, 24, 0)

        lbl_before = QLabel("Orijinal")
        lbl_before.setStyleSheet("color: #565670; font-size: 11px; font-weight: 600;")
        lbl_after = QLabel("Sonuç")
        lbl_after.setStyleSheet("color: #00E676; font-size: 11px; font-weight: 600;")

        self._compare_slider = QSlider(Qt.Orientation.Horizontal)
        self._compare_slider.setRange(0, 100)
        self._compare_slider.setValue(100)
        self._compare_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: rgba(255,255,255,0.08);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 18px; height: 18px; margin: -7px 0;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #00D9FF);
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(108,99,255,0.3); border-radius: 2px;
            }
        """)
        self._compare_slider.valueChanged.connect(self._on_slider_changed)

        sl.addWidget(lbl_before)
        sl.addWidget(self._compare_slider, 1)
        sl.addWidget(lbl_after)

        # ── Action Buttons ───────────────────────────────────────
        btn_bar = QFrame()
        btn_bar.setFixedHeight(64)
        btn_bar.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.02);
                border-top: 1px solid rgba(108,99,255,0.08);
                border-radius: 0 0 20px 20px;
            }
        """)
        b_lay = QHBoxLayout(btn_bar)
        b_lay.setContentsMargins(20, 0, 20, 0)
        b_lay.setSpacing(10)

        self._save_btn = self._action_btn("💾 Kaydet", "#6C63FF")
        self._save_btn.clicked.connect(self._save_result)

        self._retry_btn = self._action_btn("🔄 Farklı Fotoğraf", "#00D9FF")
        self._retry_btn.clicked.connect(self._retry)

        self._enhance_btn = self._action_btn("✨ Kalite Artır", "#00E676")
        self._enhance_btn.clicked.connect(self._enhance)

        b_lay.addWidget(self._save_btn)
        b_lay.addWidget(self._retry_btn)
        b_lay.addWidget(self._enhance_btn)

        # Birleştir
        main.addWidget(header)
        main.addWidget(self._image_label, 1)
        main.addWidget(self._status)
        main.addWidget(slider_container)
        main.addWidget(btn_bar)

        # Başlangıçta aksiyonları gizle
        slider_container.hide()
        btn_bar.hide()
        self._slider_container = slider_container
        self._btn_bar = btn_bar

    def _action_btn(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color}18;
                border: 1px solid {color}40;
                border-radius: 10px;
                color: {color};
                font-size: 12px; font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: {color}30;
                border-color: {color}80;
            }}
        """)
        return btn

    # ─── Public API ───────────────────────────────────────────────

    def start_swap(self, product_image: np.ndarray, user_photo_path: str):
        """Yüz değiştirme işlemini başlat."""
        self._original_image = product_image.copy()
        self._display_image(product_image)
        self._status.setText("⏳ İşleniyor...")
        self._status.setStyleSheet(
            "color: #6C63FF; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;"
        )

        # Loading animasyonu
        self._loading_dots = 0
        self._loading_timer = QTimer()
        self._loading_timer.setInterval(400)
        self._loading_timer.timeout.connect(self._animate_loading)
        self._loading_timer.start()

        self._worker = FaceSwapWorker(product_image, user_photo_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _animate_loading(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = "." * self._loading_dots
        base = self._status.text().rstrip(".")
        self._status.setText(f"{base}{dots}")

    def _on_progress(self, msg: str):
        self._status.setText(msg)

    def _on_finished(self, result: np.ndarray):
        if hasattr(self, '_loading_timer'):
            self._loading_timer.stop()

        self._result_image = result
        self._display_image(result)
        self._status.setText("✅ Yüz değiştirme tamamlandı!")
        self._status.setStyleSheet(
            "color: #00E676; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;"
        )

        # Aksiyonları göster
        self._slider_container.show()
        self._btn_bar.show()
        self._compare_slider.setValue(100)

    def _on_error(self, msg: str):
        if hasattr(self, '_loading_timer'):
            self._loading_timer.stop()

        self._status.setText(f"❌ {msg}")
        self._status.setStyleSheet(
            "color: #FF5252; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;"
        )
        self._image_label.setText(f"⚠️ {msg}")

    def _on_slider_changed(self, value: int):
        """Before/After slider: 0=orijinal, 100=sonuç."""
        if self._original_image is None or self._result_image is None:
            return

        alpha = value / 100.0
        blended = cv2.addWeighted(
            self._result_image, alpha,
            self._original_image, 1 - alpha,
            0,
        )
        self._display_image(blended)

    # ─── Display ──────────────────────────────────────────────────

    def _display_image(self, image: np.ndarray):
        """BGR numpy array'i QLabel'a sığdırarak gösterir."""
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)

        # Label boyutuna sığdır
        label_w = max(self._image_label.width(), 300)
        label_h = max(self._image_label.height(), 300)
        pixmap = QPixmap.fromImage(q_img).scaled(
            label_w, label_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._image_label.setPixmap(pixmap)

    # ─── Aksiyonlar ───────────────────────────────────────────────

    def _save_result(self):
        if self._result_image is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Sonucu Kaydet",
            os.path.expanduser(f"~/Desktop/face_swap_{int(time.time())}.jpg"),
            "Images (*.jpg *.png)",
        )
        if path:
            cv2.imwrite(path, self._result_image)
            self._status.setText(f"💾 Kaydedildi: {os.path.basename(path)}")

    def _retry(self):
        """Farklı fotoğrafla tekrar dene."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Fotoğrafınızı Seçin", "",
            "Images (*.jpg *.jpeg *.png *.webp *.heic)",
        )
        if path and self._original_image is not None:
            # Aksiyonları gizle, yeniden başlat
            self._slider_container.hide()
            self._btn_bar.hide()
            self.start_swap(self._original_image, path)

    def _enhance(self):
        """GFPGAN ile kalite artır."""
        if self._result_image is None:
            return

        self._status.setText("✨ Kalite artırılıyor...")

        class _EnhanceWorker(QThread):
            done = pyqtSignal(object)
            err = pyqtSignal(str)

            def __init__(self, img):
                super().__init__()
                self._img = img

            def run(self):
                try:
                    from face_swap_engine import FaceSwapEngine
                    engine = FaceSwapEngine()
                    result = engine.enhance_face(self._img)
                    self.done.emit(result)
                except Exception as e:
                    self.err.emit(str(e))

        w = _EnhanceWorker(self._result_image)
        w.done.connect(lambda r: (
            setattr(self, '_result_image', r),
            self._display_image(r),
            self._status.setText("✨ Kalite artırıldı!"),
        ))
        w.err.connect(lambda e: self._status.setText(f"⚠️ {e[:60]}"))
        w.start()
        self._enhance_worker = w

    def _close(self):
        self._slider_container.hide()
        self._btn_bar.hide()
        self.hide()
        self.closed.emit()

        # Worker'ı durdur
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
