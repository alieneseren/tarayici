"""
Visionary Navigator — Gesture Controller
MediaPipe Hands ile el hareketi takibi + yüz tanıma.
İşaret parmağı → fare hareketi, yumruk → tıklama, avuç → scroll, V işareti → sağ tık.
"""

import logging
import math
import os
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import (
    QThread, pyqtSignal, Qt, QTimer, QPoint, QSize
)
from PyQt6.QtGui import QImage, QPixmap, QCursor, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QGraphicsDropShadowEffect
)

import config

logger = logging.getLogger("GestureController")
logger.setLevel(logging.INFO)


# ─── El landmark indeksleri ────────────────────────────────────────
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_MCP = 9
RING_TIP = 16
RING_MCP = 13
PINKY_TIP = 20
PINKY_MCP = 17


def _distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _finger_is_up(landmarks: dict, tip_idx: int, mcp_idx: int) -> bool:
    """Parmak yukarıda mı kontrol et (tip, MCP'den yukarıda ise)."""
    tip = landmarks.get(tip_idx)
    mcp = landmarks.get(mcp_idx)
    if tip and mcp:
        return tip[1] < mcp[1]  # y ekseni — küçük = yukarıda
    return False


class GestureEngine(QThread):
    """
    MediaPipe Hands ile el hareketi algılama.
    QCamera (PyQt6 Multimedia) kullanır — macOS uyumlu.
    """

    # Sinyaller
    frame_ready = pyqtSignal(QImage)
    gesture_detected = pyqtSignal(str, int, int)  # (gesture_name, x, y)
    face_detected = pyqtSignal(bool)               # yüz bulundu/kayboldu
    emotion_detected = pyqtSignal(str)             # "mutlu", "nötr", "normal"
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._hand_landmarker = None
        self._face_detector = None
        self._screen_w = 0
        self._screen_h = 0
        self._smoothing = 0.35  # Fare yumuşatma katsayısı
        self._prev_x = 0
        self._prev_y = 0
        self._click_cooldown = 0.0
        self._last_gesture = ""

    def _init_mediapipe(self) -> bool:
        """MediaPipe modellerini yükle."""
        try:
            import mediapipe as mp

            # Hand Landmarker
            hand_model = os.path.join(config.MODELS_DIR, "hand_landmarker.task")
            if os.path.exists(hand_model):
                base = mp.tasks.BaseOptions(model_asset_path=hand_model)
                opts = mp.tasks.vision.HandLandmarkerOptions(
                    base_options=base,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_hands=1,
                    min_hand_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(opts)
                logger.info("HandLandmarker yüklendi.")
            else:
                self.error_occurred.emit("hand_landmarker.task bulunamadı")
                return False

            # Face Detector (yüz tanıma için)
            face_model = os.path.join(config.MODELS_DIR, "face_landmarker.task")
            if os.path.exists(face_model):
                base_f = mp.tasks.BaseOptions(model_asset_path=face_model)
                face_opts = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=base_f,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                )
                self._face_detector = mp.tasks.vision.FaceLandmarker.create_from_options(face_opts)
                logger.info("FaceLandmarker (gesture) yüklendi.")

            return True
        except Exception as e:
            self.error_occurred.emit(f"MediaPipe hatası: {e}")
            return False

    def _detect_hand(self, frame: np.ndarray) -> Optional[dict]:
        """El landmark'larını algıla."""
        if self._hand_landmarker is None:
            return None
        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._hand_landmarker.detect(mp_image)

            if not result.hand_landmarks or len(result.hand_landmarks) == 0:
                return None

            hand = result.hand_landmarks[0]
            h, w = frame.shape[:2]
            landmarks = {}
            for idx, lm in enumerate(hand):
                landmarks[idx] = (int(lm.x * w), int(lm.y * h))
            return landmarks
        except Exception as e:
            logger.warning(f"El algılama hatası: {e}")
            return None

    def _detect_face(self, frame: np.ndarray) -> bool:
        """Yüz var mı kontrol et."""
        if self._face_detector is None:
            return False
        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._face_detector.detect(mp_image)
            return bool(result.face_landmarks and len(result.face_landmarks) > 0)
        except Exception:
            return False

    def _detect_emotion(self, frame: np.ndarray) -> Optional[str]:
        """
        Yüz landmark'larından duygu durumu algıla.
        MediaPipe FaceLandmarker 478 landmark döndürür.
        Dudak köşeleri + kaş yüksekliği + ağız açıklığı ile duygu tahmini:
          - mutlu: dudak köşeleri yukarı (gülümseme)
          - normal: dudak köşeleri aşağı veya kaşlar çatık
          - nötr: ikisi arasında
        """
        if self._face_detector is None:
            return None
        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._face_detector.detect(mp_image)

            if not result.face_landmarks or len(result.face_landmarks) == 0:
                return None

            lm = result.face_landmarks[0]
            h, w = frame.shape[:2]

            # Anahtar landmark'lar (MediaPipe FaceMesh 478 nokta)
            # Dudak köşeleri: 61 (sol), 291 (sağ)
            # Üst dudak ortası: 13, Alt dudak ortası: 14
            # Burun ucu: 1
            # Sol kaş iç: 66, Sağ kaş iç: 296
            # Sol göz alt: 145, Sağ göz alt: 374
            # Alın ortası: 10

            def pt(idx):
                return (lm[idx].x * w, lm[idx].y * h)

            mouth_left = pt(61)
            mouth_right = pt(291)
            upper_lip = pt(13)
            lower_lip = pt(14)
            nose_tip = pt(1)

            # Ağız genişliği (referans mesafe)
            mouth_width = _distance(mouth_left, mouth_right)
            if mouth_width < 1:
                return "nötr"

            # ── Gülümseme skoru ──
            # Dudak köşelerinin orta noktası vs üst/alt dudak hizası
            mouth_center_y = (upper_lip[1] + lower_lip[1]) / 2
            left_corner_y = mouth_left[1]
            right_corner_y = mouth_right[1]
            avg_corner_y = (left_corner_y + right_corner_y) / 2

            # Köşeler merkeze göre ne kadar yukarıda? (negatif = yukarıda = gülümseme)
            smile_ratio = (mouth_center_y - avg_corner_y) / mouth_width

            # ── Ağız açıklığı (şaşkınlık/gülme) ──
            mouth_open = _distance(upper_lip, lower_lip) / mouth_width

            # ── Duygu sınıflandırma ──
            # smile_ratio > 0.05 → dudak köşeleri yukarda → mutlu
            # smile_ratio < -0.02 → dudak köşeleri aşağıda → normal (üzgün/ciddi)
            # arasında → nötr
            if smile_ratio > 0.04 or (smile_ratio > 0.02 and mouth_open > 0.15):
                emotion = "mutlu"
            elif smile_ratio < -0.02:
                emotion = "normal"
            else:
                emotion = "nötr"

            return emotion

        except Exception as e:
            logger.warning(f"Duygu algılama hatası: {e}")
            return None

    def _classify_gesture(self, lm: dict) -> Tuple[str, int, int]:
        """El landmark'larından jest sınıflandır."""
        index_up = _finger_is_up(lm, INDEX_TIP, INDEX_MCP)
        middle_up = _finger_is_up(lm, MIDDLE_TIP, MIDDLE_MCP)
        ring_up = _finger_is_up(lm, RING_TIP, RING_MCP)
        pinky_up = _finger_is_up(lm, PINKY_TIP, PINKY_MCP)

        # Başparmak-işaret mesafesi (tıklama tespiti)
        thumb_index_dist = _distance(lm[THUMB_TIP], lm[INDEX_TIP])
        wrist_mcp_dist = _distance(lm[WRIST], lm[INDEX_MCP])
        pinch_threshold = wrist_mcp_dist * 0.35

        ix, iy = lm[INDEX_TIP]

        # 1) İşaret parmağı + orta parmak yukarı (V işareti) → sağ tık
        if index_up and middle_up and not ring_up and not pinky_up:
            return ("right_click", ix, iy)

        # 2) Sadece işaret parmağı yukarı → fare hareketi
        if index_up and not middle_up and not ring_up and not pinky_up:
            return ("move", ix, iy)

        # 3) Başparmak + işaret yakın (pinch) → sol tıklama
        if thumb_index_dist < pinch_threshold:
            return ("click", ix, iy)

        # 4) Tüm parmaklar yukarı (avuç açık) → scroll modu
        if index_up and middle_up and ring_up and pinky_up:
            return ("scroll", ix, iy)

        # 5) Tüm parmaklar kapalı (yumruk) → hiçbir şey yapma (durakla)
        if not index_up and not middle_up and not ring_up and not pinky_up:
            return ("fist", ix, iy)

        return ("unknown", ix, iy)

    def run(self) -> None:
        """Kamera döngüsü — QCamera yerine cv2 (daha az overhead)."""
        self._running = True

        if not self._init_mediapipe():
            return

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self._screen_w = geo.width()
            self._screen_h = geo.height()
        else:
            self._screen_w = 1440
            self._screen_h = 900

        # Kamera aç
        cap = None
        for idx in [0, 1]:
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
                if cap and cap.isOpened():
                    break
                if cap:
                    cap.release()
                    cap = None
            except Exception:
                cap = None

        if cap is None or not cap.isOpened():
            self.error_occurred.emit("Kamera açılamadı — izinleri kontrol edin.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Warm-up
        for _ in range(15):
            ret, _ = cap.read()
            if ret:
                break
            time.sleep(0.1)

        self.status_update.emit("✋ El takibi aktif")
        face_check_counter = 0
        face_visible = False

        while self._running:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)  # Ayna
            h, w = frame.shape[:2]

            # El algılama
            landmarks = self._detect_hand(frame)

            if landmarks:
                gesture, gx, gy = self._classify_gesture(landmarks)

                # Kamera koordinatını ekran koordinatına dönüştür
                sx = int((gx / w) * self._screen_w)
                sy = int((gy / h) * self._screen_h)

                # Yumuşatma
                sx = int(self._prev_x + (sx - self._prev_x) * self._smoothing)
                sy = int(self._prev_y + (sy - self._prev_y) * self._smoothing)
                self._prev_x = sx
                self._prev_y = sy

                if gesture != self._last_gesture:
                    self._last_gesture = gesture

                self.gesture_detected.emit(gesture, sx, sy)

                # Debug çizimi
                self._draw_hand(frame, landmarks, gesture)
            else:
                self._last_gesture = ""

            # Yüz + duygu algılama (her 15 karede bir — performans)
            face_check_counter += 1
            if face_check_counter % 15 == 0:
                has_face = self._detect_face(frame)
                if has_face != face_visible:
                    face_visible = has_face
                    self.face_detected.emit(has_face)

                # Duygu algılama
                if has_face:
                    emotion = self._detect_emotion(frame)
                    if emotion:
                        self._current_emotion = emotion
                        self.emotion_detected.emit(emotion)

            # Duygu etiketini frame'e çiz
            if hasattr(self, '_current_emotion') and self._current_emotion:
                emo_display = {
                    "mutlu": ("😊 Mutlu", (0, 230, 118)),
                    "nötr": ("😐 Nötr", (180, 180, 200)),
                    "normal": ("😶 Normal", (255, 193, 7)),
                }
                emo_text, emo_color = emo_display.get(self._current_emotion, ("❓", (150, 150, 150)))
                cv2.putText(frame, emo_text, (w - 160, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, emo_color, 2)

            # QImage'a çevir ve gönder
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            q_img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            self.frame_ready.emit(q_img.copy())

            time.sleep(1.0 / 30)  # ~30 FPS

        cap.release()
        logger.info("Gesture kamera kapatıldı.")

    def _draw_hand(self, frame: np.ndarray, lm: dict, gesture: str) -> None:
        """Debug: El landmark'larını ve jesti kareye çiz."""
        # Landmarkları çiz
        for idx, (x, y) in lm.items():
            color = (108, 99, 255) if idx in (INDEX_TIP, THUMB_TIP) else (0, 200, 200)
            cv2.circle(frame, (x, y), 4, color, -1)

        # Bağlantılar
        connections = [
            (WRIST, INDEX_MCP), (INDEX_MCP, INDEX_TIP),
            (WRIST, MIDDLE_MCP), (MIDDLE_MCP, MIDDLE_TIP),
            (WRIST, RING_MCP), (RING_MCP, RING_TIP),
            (WRIST, PINKY_MCP), (PINKY_MCP, PINKY_TIP),
            (WRIST, THUMB_TIP),
        ]
        for a, b in connections:
            if a in lm and b in lm:
                cv2.line(frame, lm[a], lm[b], (60, 60, 100), 1)

        # Jest adı
        gesture_names = {
            "move": "🖱️ Fare",
            "click": "👆 Tıkla",
            "right_click": "✌️ Sağ Tık",
            "scroll": "🖐️ Scroll",
            "fist": "✊ Duraklat",
            "unknown": "❓",
        }
        label = gesture_names.get(gesture, gesture)
        cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 230, 118), 2)

    def stop(self) -> None:
        self._running = False
        self.wait(3000)


class GestureWidget(QWidget):
    """
    Kamera önizleme + jest kontrolü küçük yüzen widget.
    Sol alt köşede müzik FAB'ının üstünde gösterilir.
    """

    gesture_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gestureWidget")
        self.setFixedSize(280, 230)
        self._engine: Optional[GestureEngine] = None
        self._mouse_control_active = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Kart çerçevesi
        self.setStyleSheet("""
            QWidget#gestureWidget {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #14142A, stop:1 #0F0F1E);
                border: 1px solid rgba(0,217,255,0.15);
                border-radius: 14px;
            }
        """)

        # Başlık
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet("background: transparent; border-bottom: 1px solid rgba(255,255,255,0.05);")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 0, 8, 0)

        title = QLabel("✋ Jest Kontrol")
        title.setStyleSheet("color: #00D9FF; font-size: 12px; font-weight: 700; letter-spacing: 0.5px;")

        self._status = QLabel("Kapalı")
        self._status.setStyleSheet("color: #565670; font-size: 10px;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #565670; font-size: 12px;
            }
            QPushButton:hover { color: #FF5252; }
        """)
        close_btn.clicked.connect(self.stop_gesture)

        h_lay.addWidget(title)
        h_lay.addStretch()
        h_lay.addWidget(self._status)
        h_lay.addWidget(close_btn)
        layout.addWidget(header)

        # Kamera önizleme
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background: #0A0A12; border: none; color: #3A3A50; font-size: 11px;")
        self._preview.setText("📷 Kamera kapalı")
        layout.addWidget(self._preview, 1)

        # Alt kontroller
        bottom = QFrame()
        bottom.setFixedHeight(34)
        bottom.setStyleSheet("background: transparent; border-top: 1px solid rgba(255,255,255,0.05);")
        b_lay = QHBoxLayout(bottom)
        b_lay.setContentsMargins(10, 0, 10, 0)

        self._toggle_btn = QPushButton("🖱️ Fare Aktif")
        self._toggle_btn.setFixedHeight(24)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,217,255,0.1); border: 1px solid rgba(0,217,255,0.2);
                border-radius: 6px; color: #00D9FF; font-size: 10px; font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover { background: rgba(0,217,255,0.2); }
        """)
        self._toggle_btn.clicked.connect(self._toggle_mouse)

        self._gesture_label = QLabel("")
        self._gesture_label.setStyleSheet("color: #8E8EA0; font-size: 10px;")

        self._emotion_label = QLabel("")
        self._emotion_label.setStyleSheet("color: #565670; font-size: 10px; font-weight: 600;")

        b_lay.addWidget(self._toggle_btn)
        b_lay.addStretch()
        b_lay.addWidget(self._emotion_label)
        b_lay.addSpacing(6)
        b_lay.addWidget(self._gesture_label)
        layout.addWidget(bottom)

    def start_gesture(self) -> None:
        """Kamerayı başlat ve jest algılamaya başla."""
        if self._engine and self._engine.isRunning():
            return

        self._status.setText("⏳ Başlatılıyor...")
        self._status.setStyleSheet("color: #FFD740; font-size: 10px;")

        self._engine = GestureEngine()
        self._engine.frame_ready.connect(self._on_frame)
        self._engine.gesture_detected.connect(self._on_gesture)
        self._engine.face_detected.connect(self._on_face)
        self._engine.emotion_detected.connect(self._on_emotion)
        self._engine.status_update.connect(self._on_status)
        self._engine.error_occurred.connect(self._on_error)
        self._engine.start()

    def stop_gesture(self) -> None:
        """Kamerayı kapat."""
        if self._engine:
            self._engine.stop()
            self._engine = None

        self._preview.clear()
        self._preview.setText("📷 Kamera kapalı")
        self._status.setText("Kapalı")
        self._status.setStyleSheet("color: #565670; font-size: 10px;")
        self.gesture_closed.emit()

    def _on_frame(self, q_img: QImage) -> None:
        """Kamera karesini önizlemede göster."""
        pixmap = QPixmap.fromImage(q_img)
        scaled = pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self._preview.setPixmap(scaled)

    def _on_gesture(self, gesture: str, sx: int, sy: int) -> None:
        """Jest algılandı — fare hareketini uygula."""
        gesture_icons = {
            "move": "🖱️ Fare",
            "click": "👆 Tıkla",
            "right_click": "✌️ Sağ Tık",
            "scroll": "🖐️ Scroll",
            "fist": "✊ Duraklat",
        }
        self._gesture_label.setText(gesture_icons.get(gesture, ""))

        if not self._mouse_control_active:
            return

        if gesture == "move":
            QCursor.setPos(sx, sy)

        elif gesture == "click":
            QCursor.setPos(sx, sy)
            # Programatik tıklama — platform bağımlı
            self._simulate_click(sx, sy, "left")

        elif gesture == "right_click":
            QCursor.setPos(sx, sy)
            self._simulate_click(sx, sy, "right")

    def _simulate_click(self, x: int, y: int, button: str = "left") -> None:
        """macOS'ta programatik tıklama."""
        try:
            import subprocess
            if button == "left":
                script = f'''
                tell application "System Events"
                    click at {{{x}, {y}}}
                end tell
                '''
            else:
                # Sağ tık için Quartz kullan
                script = f'''
                do shell script "python3 -c \\"
import Quartz
evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, ({x},{y}), Quartz.kCGMouseButtonRight)
Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
evt2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, ({x},{y}), Quartz.kCGMouseButtonRight)
Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt2)
\\""
                '''
            subprocess.Popen(['osascript', '-e', script],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning(f"Tıklama simülasyonu hatası: {e}")

    def _on_face(self, detected: bool) -> None:
        """Yüz algılandı/kayboldu."""
        if detected:
            self._status.setText("👤 Yüz algılandı")
            self._status.setStyleSheet("color: #00E676; font-size: 10px;")
        else:
            self._status.setText("✋ El takibi")
            self._status.setStyleSheet("color: #00D9FF; font-size: 10px;")
            self._emotion_label.setText("")

    def _on_emotion(self, emotion: str) -> None:
        """Duygu durumu algılandı."""
        emo_map = {
            "mutlu": ("😊 Mutlu", "#00E676"),
            "nötr": ("😐 Nötr", "#B0B0C0"),
            "normal": ("😶 Normal", "#FFD740"),
        }
        text, color = emo_map.get(emotion, ("❓", "#565670"))
        self._emotion_label.setText(text)
        self._emotion_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600;")

    def _on_status(self, msg: str) -> None:
        self._status.setText(msg)
        self._status.setStyleSheet("color: #00D9FF; font-size: 10px;")

    def _on_error(self, msg: str) -> None:
        self._preview.setText(f"⚠️ {msg}")
        self._status.setText("Hata")
        self._status.setStyleSheet("color: #FF5252; font-size: 10px;")

    def _toggle_mouse(self) -> None:
        """Fare kontrolünü aç/kapat."""
        self._mouse_control_active = not self._mouse_control_active
        if self._mouse_control_active:
            self._toggle_btn.setText("🖱️ Fare Aktif")
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,217,255,0.1); border: 1px solid rgba(0,217,255,0.2);
                    border-radius: 6px; color: #00D9FF; font-size: 10px; font-weight: 600;
                    padding: 0 10px;
                }
                QPushButton:hover { background: rgba(0,217,255,0.2); }
            """)
        else:
            self._toggle_btn.setText("🖱️ Fare Kapalı")
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 6px; color: #565670; font-size: 10px; font-weight: 600;
                    padding: 0 10px;
                }
                QPushButton:hover { background: rgba(255,255,255,0.08); }
            """)

    def is_active(self) -> bool:
        return self._engine is not None and self._engine.isRunning()
