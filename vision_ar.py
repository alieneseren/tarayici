"""
Visionary Navigator — Görüntü İşleme & AR Modülü
MediaPipe ile poz/yüz takibi, YOLOv8 ile nesne doğrulama ve
perspektif dönüşüm ile sanal deneme (Virtual Try-On) sağlar.
"""

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)

import config
from resource_manager import SmartResourceManager

# ─── Loglama ───────────────────────────────────────────────────────
logger = logging.getLogger("VisionAR")
logger.setLevel(logging.INFO)


class PoseTracker:
    """
    MediaPipe Tasks API ile vücut ve yüz landmark'larını çıkarır.
    PoseLandmarker: omuz/kalça noktaları.
    FaceLandmarker: göz/alın noktaları.
    """

    # Pose landmark indeksleri
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24

    # Face landmark indeksleri (FaceLandmarker - 478 nokta)
    LEFT_EYE_OUTER = 33
    RIGHT_EYE_OUTER = 263
    NOSE_TIP = 1
    FOREHEAD = 10

    def __init__(self):
        self._pose_landmarker = None
        self._face_landmarker = None
        self._initialized = False

    def initialize(self, vision_models: dict = None) -> None:
        """MediaPipe Tasks modellerini yükler."""
        if self._initialized:
            return

        import os
        import mediapipe as mp

        models_dir = os.path.join(config.BASE_DIR, "models")

        # PoseLandmarker
        pose_model = os.path.join(models_dir, "pose_landmarker_lite.task")
        if os.path.exists(pose_model):
            try:
                base_opts = mp.tasks.BaseOptions(model_asset_path=pose_model)
                pose_opts = mp.tasks.vision.PoseLandmarkerOptions(
                    base_options=base_opts,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_poses=1,
                    min_pose_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._pose_landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(pose_opts)
                logger.info("PoseLandmarker yüklendi.")
            except Exception as e:
                logger.warning(f"PoseLandmarker yükleme hatası: {e}")
        else:
            logger.warning(f"Pose model bulunamadı: {pose_model}")

        # FaceLandmarker
        face_model = os.path.join(models_dir, "face_landmarker.task")
        if os.path.exists(face_model):
            try:
                base_opts = mp.tasks.BaseOptions(model_asset_path=face_model)
                face_opts = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=base_opts,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._face_landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(face_opts)
                logger.info("FaceLandmarker yüklendi.")
            except Exception as e:
                logger.warning(f"FaceLandmarker yükleme hatası: {e}")
        else:
            logger.warning(f"Face model bulunamadı: {face_model}")

        self._initialized = True

    def get_body_landmarks(self, frame: np.ndarray) -> Optional[dict]:
        """Vücut noktalarını çıkarır: omuz ve kalça piksel koordinatları."""
        if self._pose_landmarker is None:
            return None

        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._pose_landmarker.detect(mp_image)

            if not result.pose_landmarks or len(result.pose_landmarks) == 0:
                return None

            landmarks = result.pose_landmarks[0]
            h, w = frame.shape[:2]

            def to_px(idx):
                lm = landmarks[idx]
                return (int(lm.x * w), int(lm.y * h), lm.visibility)

            ls = to_px(self.LEFT_SHOULDER)
            rs = to_px(self.RIGHT_SHOULDER)
            lh = to_px(self.LEFT_HIP)
            rh = to_px(self.RIGHT_HIP)

            min_vis = min(ls[2], rs[2], lh[2], rh[2])
            if min_vis < 0.4:
                return None

            return {
                "left_shoulder": (ls[0], ls[1]),
                "right_shoulder": (rs[0], rs[1]),
                "left_hip": (lh[0], lh[1]),
                "right_hip": (rh[0], rh[1]),
                "confidence": round(min_vis, 2),
            }
        except Exception as e:
            logger.warning(f"Pose detection hatası: {e}")
            return None

    def get_face_landmarks(self, frame: np.ndarray) -> Optional[dict]:
        """Yüz noktalarını çıkarır: göz, burun, alın koordinatları."""
        if self._face_landmarker is None:
            return None

        try:
            import mediapipe as mp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._face_landmarker.detect(mp_image)

            if not result.face_landmarks or len(result.face_landmarks) == 0:
                return None

            face = result.face_landmarks[0]
            h, w = frame.shape[:2]

            def to_px(idx):
                lm = face[idx]
                return (int(lm.x * w), int(lm.y * h))

            return {
                "left_eye": to_px(self.LEFT_EYE_OUTER),
                "right_eye": to_px(self.RIGHT_EYE_OUTER),
                "nose_tip": to_px(self.NOSE_TIP),
                "forehead": to_px(self.FOREHEAD),
            }
        except Exception as e:
            logger.warning(f"Face detection hatası: {e}")
            return None


class ObjectVerifier:
    """
    YOLOv8 ile ürün sınıfı doğrulaması yapar.
    Kıyafet olarak algılanabilecek COCO sınıflarını filtreler.
    """

    # Kıyafet ile ilişkilendirilebilecek COCO sınıfları (yaklaşık eşleşme)
    CLOTHING_CLASSES = {"person", "tie", "backpack", "handbag", "suitcase"}

    def __init__(self):
        self._yolo = None

    def initialize(self, vision_models: dict) -> None:
        """YOLO modelini ata."""
        self._yolo = vision_models.get("yolo")

    def verify_person_in_frame(self, frame: np.ndarray) -> bool:
        """Karedeki insan varlığını doğrular."""
        if self._yolo is None:
            return True  # YOLO yoksa varsayılan olarak kabul et

        try:
            results = self._yolo(frame, verbose=False, conf=config.YOLO_CONFIDENCE_THRESHOLD)
            for r in results:
                for box in r.boxes:
                    cls_name = r.names[int(box.cls[0])]
                    if cls_name == "person":
                        return True
            return False
        except Exception as e:
            logger.warning(f"YOLO doğrulama hatası: {e}")
            return True


class ProductOverlay:
    """
    Ürün görselini vücut landmark'larına göre perspektif dönüşüm ile bindiren sınıf.
    cv2.warpPerspective + alpha blending kullanır.
    """

    @staticmethod
    def warp_product_on_body(
        frame: np.ndarray,
        product_image: np.ndarray,
        body_landmarks: dict,
        padding_factor: float = 0.12
    ) -> np.ndarray:
        """
        Ürün görselini omuz-kalça dörtgenine perspektif dönüşümle bindirir.

        Argümanlar:
            frame: Kamera karesi (BGR)
            product_image: Ürün görseli (BGRA veya BGR)
            body_landmarks: PoseTracker'dan gelen nokta sözlüğü
            padding_factor: Omuz genişliğine göre yatay dolgu oranı

        Döndürür:
            Overlay uygulanmış kare (BGR)
        """
        h, w = frame.shape[:2]

        # Hedef noktaları al
        ls = body_landmarks["left_shoulder"]
        rs = body_landmarks["right_shoulder"]
        lh = body_landmarks["left_hip"]
        rh = body_landmarks["right_hip"]

        # Omuz genişliğine göre yatay dolgu ekle (daha doğal görünüm)
        shoulder_width = abs(rs[0] - ls[0])
        pad = int(shoulder_width * padding_factor)

        dst_points = np.float32([
            [rs[0] - pad, rs[1]],         # Sağ omuz (sol üst)
            [ls[0] + pad, ls[1]],         # Sol omuz (sağ üst)
            [lh[0] + pad, lh[1]],         # Sol kalça (sağ alt)
            [rh[0] - pad, rh[1]],         # Sağ kalça (sol alt)
        ])

        # Kaynak noktaları (ürün görselinin köşeleri)
        ph, pw = product_image.shape[:2]
        src_points = np.float32([
            [0, 0],
            [pw, 0],
            [pw, ph],
            [0, ph],
        ])

        # Perspektif dönüşüm matrisi
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)

        # Alpha kanalı kontrolü
        if product_image.shape[2] == 4:
            # BGRA — alfa kanalı var
            bgr = product_image[:, :, :3]
            alpha = product_image[:, :, 3]
        else:
            # BGR — opak
            bgr = product_image
            alpha = np.ones((ph, pw), dtype=np.uint8) * 255

        # Görseli warp et
        warped_bgr = cv2.warpPerspective(bgr, matrix, (w, h))
        warped_alpha = cv2.warpPerspective(alpha, matrix, (w, h))

        # Alpha maskeleme ile birleştir
        alpha_mask = warped_alpha.astype(float) / 255.0
        alpha_mask = np.stack([alpha_mask] * 3, axis=-1)

        # Birleştirme
        result = frame.astype(float)
        overlay = warped_bgr.astype(float)
        result = result * (1 - alpha_mask) + overlay * alpha_mask
        result = result.astype(np.uint8)

        return result

    @staticmethod
    def warp_accessory_on_face(
        frame: np.ndarray,
        accessory_image: np.ndarray,
        face_landmarks: dict
    ) -> np.ndarray:
        """
        Aksesuar (gözlük/şapka) görselini yüz landmark'larına göre afin dönüşüm ile bindirir.
        """
        h, w = frame.shape[:2]

        le = face_landmarks["left_eye"]
        re = face_landmarks["right_eye"]

        # Gözlük genişliği = göz arası mesafenin 2 katı
        eye_dist = np.sqrt((le[0] - re[0])**2 + (le[1] - re[1])**2)
        accessory_width = int(eye_dist * 2.2)

        if accessory_width < 20:
            return frame

        # Ölçeklendirme
        ah, aw = accessory_image.shape[:2]
        scale = accessory_width / aw
        new_h = int(ah * scale)
        resized = cv2.resize(accessory_image, (accessory_width, new_h))

        # Merkez noktası (iki göz arası)
        center_x = (le[0] + re[0]) // 2
        center_y = (le[1] + re[1]) // 2

        # Açı hesapla (göz çizgisi eğimi)
        angle = np.degrees(np.arctan2(le[1] - re[1], le[0] - re[0]))

        # Döndürme matrisi
        rot_matrix = cv2.getRotationMatrix2D(
            (accessory_width // 2, new_h // 2), angle, 1.0
        )

        rotated = cv2.warpAffine(resized, rot_matrix, (accessory_width, new_h))

        # Yerleştirme koordinatları
        x1 = center_x - accessory_width // 2
        y1 = center_y - new_h // 2
        x2 = x1 + accessory_width
        y2 = y1 + new_h

        # Sınır kontrolü
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return frame

        # Alpha kanalı ile bindirme
        roi_w = x2 - x1
        roi_h = y2 - y1
        rotated_cropped = rotated[:roi_h, :roi_w]

        if rotated_cropped.shape[2] == 4:
            alpha = rotated_cropped[:, :, 3].astype(float) / 255.0
            alpha = np.stack([alpha] * 3, axis=-1)
            bgr = rotated_cropped[:, :, :3]
        else:
            alpha = np.ones((roi_h, roi_w, 3), dtype=float)
            bgr = rotated_cropped

        result = frame.copy()
        roi = result[y1:y2, x1:x2].astype(float)
        blended = roi * (1 - alpha) + bgr.astype(float) * alpha
        result[y1:y2, x1:x2] = blended.astype(np.uint8)

        return result


class CameraThread(QThread):
    """
    Kamera yakalama ve AR overlay döngüsünü ayrı thread'de çalıştırır.
    İşlenmiş kareleri sinyal olarak UI'ya gönderir.
    """

    # İşlenmiş kareyi QImage olarak gönderen sinyal
    frame_ready = pyqtSignal(QImage)
    # AR durum bilgisi (FPS, güven skoru, insan algılandı mı)
    status_update = pyqtSignal(dict)
    # Hata mesajı
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._mutex = QMutex()

        # AR bileşenleri
        self._pose_tracker = PoseTracker()
        self._object_verifier = ObjectVerifier()
        self._product_overlay = ProductOverlay()

        # Ürün görseli
        self._product_image: Optional[np.ndarray] = None
        self._overlay_mode = "body"  # "body" veya "face"

    def set_product_image(self, image_path_or_array) -> bool:
        """
        Deneme yapılacak ürün görselini ayarlar.
        Argüman: dosya yolu (str) veya numpy dizisi.
        """
        try:
            if isinstance(image_path_or_array, str):
                img = cv2.imread(image_path_or_array, cv2.IMREAD_UNCHANGED)
            elif isinstance(image_path_or_array, np.ndarray):
                img = image_path_or_array
            else:
                return False

            if img is None:
                return False

            self._product_image = img
            logger.info(f"Ürün görseli ayarlandı: {img.shape}")
            return True

        except Exception as e:
            logger.error(f"Ürün görseli yükleme hatası: {e}")
            return False

    def set_overlay_mode(self, mode: str) -> None:
        """Overlay modunu ayarlar: 'body' veya 'face'."""
        self._overlay_mode = mode

    def run(self) -> None:
        """Kamera yakalama ve AR döngüsü — ayrı thread'de çalışır."""
        self._running = True
        resource_manager = SmartResourceManager()

        # Vision modellerini yükle (başarısız olursa sadece kamera gösterilir)
        try:
            vision_models = resource_manager.load_vision()
            self._pose_tracker.initialize(vision_models)
            self._object_verifier.initialize(vision_models)
            logger.info("Vision modülleri yüklendi.")
        except Exception as e:
            logger.warning(f"Vision modülleri yüklenemedi (salt kamera modu): {e}")

        # Kamera açma — birden fazla backend dene
        cap = None

        # 1. AVFoundation dene (Mac için en uyumlu)
        for i in [config.CAMERA_INDEX, 0, 1]:
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
                if cap is not None and cap.isOpened():
                    logger.info(f"Kamera index {i} açıldı (AVFoundation).")
                    break
                elif cap is not None:
                    cap.release()
                    cap = None
            except Exception:
                cap = None

        # 2. AVFoundation başarısızsa CAP_ANY dene
        if cap is None or not cap.isOpened():
            for i in [0, 1]:
                try:
                    cap = cv2.VideoCapture(i)
                    if cap is not None and cap.isOpened():
                        logger.info(f"Kamera index {i} açıldı (ANY).")
                        break
                    elif cap is not None:
                        cap.release()
                        cap = None
                except Exception:
                    cap = None

        if cap is None or not cap.isOpened():
            self.error_occurred.emit("Kamera açılamadı! Sistem Ayarları → Gizlilik → Kamera'dan Terminal'e izin verin ve uygulamayı yeniden başlatın.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        # macOS AVFoundation warm-up: 3 saniyeye kadar bekle
        warmup_ok = False
        for _ in range(30):  # 30 x 100ms = 3 saniye
            ret, frame = cap.read()
            if ret and frame is not None:
                warmup_ok = True
                break
            time.sleep(0.1)

        if not warmup_ok:
            self.error_occurred.emit("Kamera açıldı fakat görüntü alınamıyor. Terminal'i CMD+Q ile tamamen kapatıp yeniden açın.")
            cap.release()
            return

        logger.info("Kamera başlatıldı — AR döngüsü çalışıyor.")
        frame_count = 0
        fps_start = time.time()

        while self._running:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)  # Ayna efekti
            frame_count += 1
            display_frame = frame.copy()

            try:
                # Ürün görseli varsa overlay uygula
                if self._product_image is not None:
                    if self._overlay_mode == "body":
                        body = self._pose_tracker.get_body_landmarks(frame)
                        if body:
                            # İnsan doğrulaması (her 10 karede bir — performans)
                            is_person = True
                            if frame_count % 10 == 0:
                                is_person = self._object_verifier.verify_person_in_frame(frame)

                            if is_person:
                                display_frame = self._product_overlay.warp_product_on_body(
                                    display_frame, self._product_image, body
                                )

                            # Poz güven skoru göster
                            cv2.putText(
                                display_frame,
                                f"Poz Guven: {body['confidence']:.0%}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 217, 255), 2
                            )
                        else:
                            cv2.putText(
                                display_frame,
                                "Vücut algılanamıyor — kameraya dönün",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0, 100, 255), 2
                            )

                    elif self._overlay_mode == "face":
                        face = self._pose_tracker.get_face_landmarks(frame)
                        if face:
                            display_frame = self._product_overlay.warp_accessory_on_face(
                                display_frame, self._product_image, face
                            )
                else:
                    # Ürün görseli yok — sadece poz iskeletini çiz
                    body = self._pose_tracker.get_body_landmarks(frame)
                    if body:
                        for key, point in body.items():
                            if key != "confidence" and isinstance(point, tuple):
                                cv2.circle(display_frame, point, 6, (108, 99, 255), -1)
                                cv2.circle(display_frame, point, 8, (0, 217, 255), 2)

                # FPS hesapla
                elapsed = time.time() - fps_start
                if elapsed > 0:
                    fps = frame_count / elapsed
                else:
                    fps = 0

                # FPS göster
                cv2.putText(
                    display_frame,
                    f"FPS: {fps:.1f}",
                    (display_frame.shape[1] - 120, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 230, 118), 2
                )

                # FPS sayacını sıfırla (her 30 karede)
                if frame_count >= 30:
                    frame_count = 0
                    fps_start = time.time()

            except Exception as e:
                logger.warning(f"AR kare işleme hatası: {e}")

            # BGR → RGB → QImage dönüşümü
            rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.frame_ready.emit(q_img.copy())

            # Hedef FPS'e göre bekle
            target_delay = 1.0 / config.CAMERA_FPS
            time.sleep(max(0, target_delay - 0.005))

        # Temizlik
        cap.release()
        logger.info("Kamera kapatıldı.")

    def stop(self) -> None:
        """Kamera döngüsünü durdurur."""
        self._running = False
        self.wait(3000)  # Maksimum 3 saniye bekle


class ARWidget(QWidget):
    """
    AR kamera çıktısını gösteren UI bileşeni.
    Kamera beslemesini, kontrol butonlarını ve durum bilgisini içerir.
    """

    # AR kapatıldığında sinyal
    ar_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("arWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #111118; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08);")
        self.setFixedWidth(420)
        self._camera_thread: Optional[CameraThread] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Arayüz bileşenlerini oluşturur."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Üst bilgi çubuğu ──────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 16, 16)

        title = QLabel("AR Deneme")
        title.setStyleSheet("""
            color: #FFFFFF; 
            font-weight: 500; 
            font-size: 14px;
            letter-spacing: 0.5px;
        """)

        self._status_label = QLabel("Bekliyor")
        self._status_label.setObjectName("arStatus")
        self._status_label.setStyleSheet("color: #8E8EA0; font-size: 12px;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8E8EA0;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        close_btn.clicked.connect(self.close_ar)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self._status_label)
        header_layout.addWidget(close_btn)

        # ── Kamera görüntüsü ──────────────────────────────────────
        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                min-height: 360px;
                color: #8E8EA0;
            }
        """)
        self._video_label.setText("Kamera başlatılıyor...")

        # ── Alt kontrol çubuğu ────────────────────────────────────
        controls = QFrame()
        controls.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                padding: 12px 20px;
            }
        """)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self._mode_btn = QPushButton("Kıyafet / Aksesuar")
        self._mode_btn.setObjectName("accentButton")
        self._mode_btn.clicked.connect(self._toggle_mode)

        self._capture_btn = QPushButton("Ekran Görüntüsü")
        self._capture_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8E8EA0;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #ECECF1;
            }
        """)
        self._capture_btn.clicked.connect(self._capture_screenshot)

        controls_layout.addWidget(self._mode_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self._capture_btn)

        # Düzeni birleştir
        layout.addWidget(header)
        layout.addWidget(self._video_label, 1)
        layout.addWidget(controls)

        self._current_mode = "body"
        self._ar_starting = False  # Re-entry kilidi
        self._camera_permission_cached = None  # İzin sonucunu bir kez cache'le
        self._qt_camera = None
        self._capture_session = None
        self._video_sink = None
        self._product_image = None
        self._product_category = "clothing"  # Varsayılan
        self._pose_tracker = PoseTracker()
        self._tracker_initialized = False
        self._frame_count = 0
        self._cached_body = None
        self._cached_face = None
        self._overlay_logged = False

    def _request_camera_permission(self) -> bool:
        """macOS'ta kamera iznini Swift ile kontrol eder ve ister. Sonucu cache'ler."""
        # Daha önce kontrol edildiyse tekrar Swift derlemeye gerek yok
        if self._camera_permission_cached is not None:
            return self._camera_permission_cached

        import subprocess
        try:
            result = subprocess.run(
                ['swift', '-e', '''
import AVFoundation
import Foundation
let sema = DispatchSemaphore(value: 0)
let status = AVCaptureDevice.authorizationStatus(for: .video)
if status == .notDetermined {
    AVCaptureDevice.requestAccess(for: .video) { granted in
        print(granted ? "granted" : "denied")
        sema.signal()
    }
    sema.wait()
} else if status == .authorized {
    print("granted")
} else {
    print("denied")
}
'''],
                capture_output=True, text=True, timeout=30
            )
            self._camera_permission_cached = 'granted' in result.stdout
            return self._camera_permission_cached
        except Exception as e:
            logger.warning(f"Kamera izni kontrolü başarısız: {e}")
            self._camera_permission_cached = True  # Başarısızsa devam et
            return True

    def start_ar(self, product_image=None, category: str = "clothing") -> None:
        """AR modülünü başlatır — PyQt6 QCamera ile macOS uyumlu."""
        # Re-entry koruması
        if self._ar_starting:
            return
        self._ar_starting = True

        # Önceki kamera oturumunu temizle (sinyal tetiklemeden)
        self._stop_camera_silently()

        # macOS kamera iznini kontrol et/iste
        if not self._request_camera_permission():
            self._video_label.setText(
                "🔒 Kamera erişimi reddedildi\n\n"
                "1. macOS → Sistem Ayarları → Gizlilik ve Güvenlik → Kamera\n"
                "2. Terminal'i listede bulun ve anahtarı açın\n"
                "3. Uygulamayı yeniden başlatın"
            )
            self._status_label.setText("🔒 İzin yok")
            self._status_label.setStyleSheet("color: #FF5252; font-size: 12px;")
            self._ar_starting = False
            return

        try:
            from PyQt6.QtMultimedia import (
                QCamera, QMediaDevices, QMediaCaptureSession, QVideoSink
            )
        except ImportError:
            self._on_error("PyQt6-Multimedia bulunamadı. pip install PyQt6-Multimedia")
            self._ar_starting = False
            return

        # Kamera cihazlarını bul
        devices = QMediaDevices.videoInputs()
        if not devices:
            self._on_error(
                "Kamera bulunamadı!\n\n"
                "macOS → Sistem Ayarları → Gizlilik ve Güvenlik → Kamera\n"
                "bölümünden Terminal'e izin verin."
            )
            self._ar_starting = False
            return

        camera_device = devices[0]
        logger.info(f"QCamera başlatılıyor: {camera_device.description()}")

        # QCamera oluştur
        self._qt_camera = QCamera(camera_device)
        self._qt_camera.errorOccurred.connect(self._on_camera_error)

        # Capture Session + Video Sink
        self._capture_session = QMediaCaptureSession()
        self._video_sink = QVideoSink()
        self._capture_session.setCamera(self._qt_camera)
        self._capture_session.setVideoSink(self._video_sink)
        self._video_sink.videoFrameChanged.connect(self._on_qt_frame)

        # Ürün görseli ve kategori
        self._product_image = product_image
        self._product_category = category

        # MediaPipe tracker'ı başlat (lazy, kendi modellerini yükler)
        if product_image is not None and not self._tracker_initialized:
            try:
                self._pose_tracker.initialize()
                self._tracker_initialized = True
                logger.info("MediaPipe tracker başlatıldı.")
            except Exception as e:
                logger.warning(f"MediaPipe başlatılamadı: {e}")

        # Kamerayı başlat
        self._qt_camera.start()

        # Kamera aktif mi kontrol et
        if self._qt_camera.isActive():
            self._status_label.setText("● Aktif")
            self._status_label.setStyleSheet("color: #00E676; font-size: 12px; font-weight: 600;")
        else:
            self._status_label.setText("⏳ Kamera izni bekleniyor...")
            self._status_label.setStyleSheet("color: #FFD740; font-size: 12px;")
            self._video_label.setText(
                "📷 Kamera izni gerekli\n\n"
                "macOS Sistem Ayarları → Gizlilik ve Güvenlik → Kamera\n"
                "bölümünden Terminal'e izin verin,\n"
                "ardından uygulamayı yeniden başlatın."
            )

        self._ar_starting = False

    def _on_camera_error(self, error, error_string) -> None:
        """QCamera hata sinyali."""
        logger.error(f"QCamera hatası: {error_string}")
        if "not granted" in error_string.lower() or "access" in error_string.lower():
            self._video_label.setText(
                "🔒 Kamera erişimi reddedildi\n\n"
                "1. macOS → Sistem Ayarları → Gizlilik ve Güvenlik → Kamera\n"
                "2. Terminal'i (veya VSCode) listede bulun\n"
                "3. Yanındaki anahtarı açın\n"
                "4. Uygulamayı yeniden başlatın"
            )
            self._status_label.setText("🔒 İzin yok")
            self._status_label.setStyleSheet("color: #FF5252; font-size: 12px;")
        else:
            self._on_error(f"Kamera hatası: {error_string}")

    def _on_qt_frame(self, frame) -> None:
        """QVideoSink'den gelen her kareyi işler ve gösterir."""
        q_image = frame.toImage()
        if q_image.isNull():
            return

        q_image = q_image.convertToFormat(QImage.Format.Format_RGB888)
        q_image = q_image.mirrored(True, False)

        # Ürün görseli varsa body-tracked overlay yap
        if self._product_image is not None:
            self._frame_count += 1
            try:
                # İlk 30 karede her karede tespit, sonra her 3'te bir
                if self._frame_count <= 30:
                    detect_this_frame = True
                else:
                    detect_this_frame = (self._frame_count % 3 == 0)
                q_image = self._apply_product_overlay(q_image, detect_this_frame)
            except Exception as e:
                # Her 60 karede bir hata logla (spam önle)
                if self._frame_count % 60 <= 1:
                    logger.warning(f"Overlay hatası [frame {self._frame_count}]: {e}")
                    import traceback
                    traceback.print_exc()

        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self._video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self._video_label.setPixmap(scaled)

    def _qimage_to_cv(self, q_image: QImage) -> np.ndarray:
        """QImage (RGB888) → OpenCV BGR numpy array."""
        w, h = q_image.width(), q_image.height()
        ptr = q_image.bits()
        ptr.setsize(h * w * 3)
        rgb = np.array(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def _cv_to_qimage(self, frame: np.ndarray) -> QImage:
        """OpenCV BGR numpy array → QImage (RGB888)."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        result = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        return result.copy()

    def _overlay_with_alpha(self, bg: np.ndarray, overlay: np.ndarray, x: int, y: int) -> np.ndarray:
        """BGRA overlay'ı BGR background'a alpha blending ile bindirme."""
        oh, ow = overlay.shape[:2]
        bh, bw = bg.shape[:2]

        # Sınır kontrolü
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(bw, x + ow), min(bh, y + oh)
        ox1, oy1 = x1 - x, y1 - y
        ox2, oy2 = ox1 + (x2 - x1), oy1 + (y2 - y1)

        if x2 <= x1 or y2 <= y1:
            return bg

        crop = overlay[oy1:oy2, ox1:ox2]
        if crop.shape[2] == 4:
            alpha = crop[:, :, 3:4].astype(np.float32) / 255.0
            fg = crop[:, :, :3].astype(np.float32)
            roi = bg[y1:y2, x1:x2].astype(np.float32)
            bg[y1:y2, x1:x2] = (fg * alpha + roi * (1.0 - alpha)).astype(np.uint8)
        else:
            bg[y1:y2, x1:x2] = crop

        return bg

    def _apply_product_overlay(self, q_image: QImage, detect: bool = True) -> QImage:
        """Ürün görselini body/face tracking ile kişiye giydirme."""
        frame = self._qimage_to_cv(q_image)
        product = self._product_image
        category = self._product_category

        # Landmark tespiti
        if detect:
            h, w = frame.shape[:2]

            # Yüz tespiti — full çözünürlükte (640px minimum)
            detect_w = max(640, min(w, 960))
            detect_scale = detect_w / max(w, 1)
            detect_frame = cv2.resize(frame, (detect_w, int(h * detect_scale)),
                                       interpolation=cv2.INTER_AREA) if detect_w != w else frame

            face = self._pose_tracker.get_face_landmarks(detect_frame)
            if face:
                sf = w / detect_w
                face_scaled = {
                    k: (int(v[0] * sf), int(v[1] * sf))
                    for k, v in face.items()
                }
                self._cached_face = face_scaled

                # Yüzden vücut pozisyonunu tahmin et (webcam'de oturan kişi)
                le = face_scaled["left_eye"]
                re = face_scaled["right_eye"]
                nose = face_scaled["nose_tip"]
                forehead = face_scaled["forehead"]

                # Yüz genişliği ve yüksekliği
                face_w = abs(le[0] - re[0])
                face_h = abs(forehead[1] - nose[1])
                face_cx = (le[0] + re[0]) // 2
                chin_y = nose[1] + int(face_h * 0.6)

                # Omuz tahmin: yüz genişliğinin ~3x'i, çeneden biraz aşağı
                shoulder_w = int(face_w * 3.0)
                shoulder_y = chin_y + int(face_h * 0.4)
                hip_y = chin_y + int(face_h * 2.5)

                self._cached_body = {
                    "left_shoulder": (face_cx + shoulder_w // 2, shoulder_y),
                    "right_shoulder": (face_cx - shoulder_w // 2, shoulder_y),
                    "left_hip": (face_cx + int(shoulder_w * 0.45), hip_y),
                    "right_hip": (face_cx - int(shoulder_w * 0.45), hip_y),
                    "confidence": 0.8,
                }
            else:
                # Yüz bulunamadıysa PoseLandmarker dene
                body = self._pose_tracker.get_body_landmarks(detect_frame)
                if body:
                    sf = w / detect_w
                    self._cached_body = {
                        k: (int(v[0] * sf), int(v[1] * sf)) if isinstance(v, tuple) else v
                        for k, v in body.items()
                    }

            # Periyodik loglama
            if self._frame_count % 30 == 0:
                logger.info(
                    f"AR detection [frame {self._frame_count}]: "
                    f"face={'✓' if self._cached_face else '✗'}, "
                    f"body={'✓' if self._cached_body else '✗'}"
                )

        # Overlay uygula
        if category == "clothing":
            frame = self._overlay_clothing(frame, product)
        elif category == "eyewear":
            frame = self._overlay_eyewear(frame, product)
        elif category == "headwear":
            frame = self._overlay_headwear(frame, product)
        else:
            frame = self._overlay_clothing(frame, product)

        # İlk 60 karede landmark debug noktaları çiz
        if self._frame_count <= 60 and self._cached_body:
            for key in ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]:
                pt = self._cached_body.get(key)
                if pt:
                    cv2.circle(frame, pt, 6, (0, 255, 0), -1)
        if self._frame_count <= 60 and self._cached_face:
            for key in ["left_eye", "right_eye", "nose_tip", "forehead"]:
                pt = self._cached_face.get(key)
                if pt:
                    cv2.circle(frame, pt, 4, (0, 255, 255), -1)

        result = self._cv_to_qimage(frame)
        return result

    def _overlay_clothing(self, frame: np.ndarray, product: np.ndarray) -> np.ndarray:
        """Kıyafeti omuz-kalça arasına perspektif dönüşümle bindirme."""
        landmarks = self._cached_body

        if landmarks is None:
            return self._static_overlay(frame, product, 0.45, 0.15)

        ls = landmarks["left_shoulder"]
        rs = landmarks["right_shoulder"]
        lh = landmarks["left_hip"]
        rh = landmarks["right_hip"]

        # Omuz genişliğini %20 genişlet (kıyafetin omuzu aşması için)
        shoulder_w = abs(ls[0] - rs[0])
        pad = int(shoulder_w * 0.2)

        # Hedef dörtgen (saat yönünde: sol-üst, sağ-üst, sağ-alt, sol-alt)
        # Ayna efektinden dolayı left/right yer değiştirebilir
        dst_pts = np.float32([
            [rs[0] - pad, rs[1] - int(shoulder_w * 0.1)],  # Sağ omuz (üst)
            [ls[0] + pad, ls[1] - int(shoulder_w * 0.1)],  # Sol omuz (üst)
            [lh[0] + pad, lh[1] + int(shoulder_w * 0.05)],  # Sol kalça (alt)
            [rh[0] - pad, rh[1] + int(shoulder_w * 0.05)],  # Sağ kalça (alt)
        ])

        # Kaynak dörtgen (ürün görselinin köşeleri)
        ph, pw = product.shape[:2]
        src_pts = np.float32([
            [0, 0],
            [pw, 0],
            [pw, ph],
            [0, ph],
        ])

        # Perspektif dönüşüm matrisi
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        h, w = frame.shape[:2]

        if product.shape[2] == 4:
            # BGRA — Şeffaf ürün
            warped = cv2.warpPerspective(product, M, (w, h),
                                         flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_CONSTANT,
                                         borderValue=(0, 0, 0, 0))
            frame = self._overlay_with_alpha(frame, warped, 0, 0)
        else:
            # BGR — Opak ürün
            warped = cv2.warpPerspective(product, M, (w, h),
                                         flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_CONSTANT,
                                         borderValue=(0, 0, 0))
            mask = cv2.warpPerspective(
                np.ones((ph, pw), dtype=np.uint8) * 255, M, (w, h),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
            )
            mask_3ch = cv2.merge([mask, mask, mask])
            frame = np.where(mask_3ch > 128, warped, frame)

        return frame

    def _overlay_eyewear(self, frame: np.ndarray, product: np.ndarray) -> np.ndarray:
        """Gözlüğü göz hizasına yerleştirme."""
        face = self._cached_face

        if face is None:
            return self._static_overlay(frame, product, 0.3, 0.25)

        le = face["left_eye"]
        re = face["right_eye"]

        # Gözler arası mesafe
        eye_dist = int(np.sqrt((le[0] - re[0])**2 + (le[1] - re[1])**2))
        target_w = int(eye_dist * 2.2)  # Gözlük gözlerden biraz geniş

        # Boyutlandır
        ph, pw = product.shape[:2]
        scale = target_w / max(pw, 1)
        target_h = int(ph * scale)
        resized = cv2.resize(product, (target_w, target_h), interpolation=cv2.INTER_AREA)

        # Merkez (iki göz arası orta nokta)
        cx = (le[0] + re[0]) // 2
        cy = (le[1] + re[1]) // 2

        x = cx - target_w // 2
        y = cy - target_h // 2

        # Açı hesabı (gözler eğikse döndür)
        angle = np.degrees(np.arctan2(re[1] - le[1], re[0] - le[0]))
        if abs(angle) > 2:
            M_rot = cv2.getRotationMatrix2D((target_w // 2, target_h // 2), -angle, 1.0)
            resized = cv2.warpAffine(resized, M_rot, (target_w, target_h),
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(0, 0, 0, 0) if resized.shape[2] == 4 else (0, 0, 0))

        frame = self._overlay_with_alpha(frame, resized, x, y)
        return frame

    def _overlay_headwear(self, frame: np.ndarray, product: np.ndarray) -> np.ndarray:
        """Şapkayı alın üzerine yerleştirme."""
        face = self._cached_face

        if face is None:
            return self._static_overlay(frame, product, 0.35, 0.05)

        le = face["left_eye"]
        re = face["right_eye"]
        forehead = face["forehead"]

        # Yüz genişliği
        face_w = int(np.sqrt((le[0] - re[0])**2 + (le[1] - re[1])**2) * 2.5)

        ph, pw = product.shape[:2]
        scale = face_w / max(pw, 1)
        target_h = int(ph * scale)
        resized = cv2.resize(product, (face_w, target_h), interpolation=cv2.INTER_AREA)

        cx = (le[0] + re[0]) // 2
        x = cx - face_w // 2
        y = forehead[1] - target_h

        frame = self._overlay_with_alpha(frame, resized, x, y)
        return frame

    def _static_overlay(self, frame: np.ndarray, product: np.ndarray, size_ratio: float, y_ratio: float) -> np.ndarray:
        """Body tracking yoksa statik merkez overlay."""
        h, w = frame.shape[:2]
        overlay_w = int(w * size_ratio)
        ph, pw = product.shape[:2]
        scale = overlay_w / max(pw, 1)
        overlay_h = int(ph * scale)
        resized = cv2.resize(product, (overlay_w, overlay_h), interpolation=cv2.INTER_AREA)
        x = (w - overlay_w) // 2
        y = int(h * y_ratio)
        frame = self._overlay_with_alpha(frame, resized, x, y)
        return frame

    def _stop_camera_silently(self) -> None:
        """Kamerayı kapat ama ar_closed sinyali GÖNDERME."""
        if self._qt_camera:
            try:
                self._qt_camera.errorOccurred.disconnect()
            except Exception:
                pass
            self._qt_camera.stop()
            self._qt_camera = None

        if self._video_sink:
            try:
                self._video_sink.videoFrameChanged.disconnect()
            except Exception:
                pass
            self._video_sink = None

        self._capture_session = None
        self._product_image = None

        # Eski CameraThread varsa temizle
        if self._camera_thread:
            self._camera_thread.stop()
            self._camera_thread.wait(3000)
            self._camera_thread = None

    def close_ar(self) -> None:
        """AR modülünü kapatır ve kaynakları serbest bırakır."""
        self._stop_camera_silently()

        self._video_label.clear()
        self._video_label.setText("📷 Kamera kapalı")
        self._status_label.setText("● Kapalı")
        self._status_label.setStyleSheet("color: #6B6B80; font-size: 12px;")
        self.ar_closed.emit()

    def _update_frame(self, q_image: QImage) -> None:
        """Kameradan gelen kareyi ekranda gösterir."""
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self._video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._video_label.setPixmap(scaled)

    def _on_error(self, error_msg: str) -> None:
        """Hata durumunda mesaj gösterir."""
        self._video_label.setText(f"⚠️ {error_msg}")
        self._status_label.setText("● Hata")
        self._status_label.setStyleSheet("color: #FF5252; font-size: 12px; font-weight: 600;")
        logger.error(f"AR hatası: {error_msg}")

    def _toggle_mode(self) -> None:
        """Kıyafet / Aksesuar modu arasında geçiş yapar."""
        if self._current_mode == "body":
            self._current_mode = "face"
            self._mode_btn.setText("🕶️ Aksesuar Modu")
        else:
            self._current_mode = "body"
            self._mode_btn.setText("👕 Kıyafet Modu")

        if self._camera_thread:
            self._camera_thread.set_overlay_mode(self._current_mode)

    def _capture_screenshot(self) -> None:
        """Mevcut AR karesinin ekran görüntüsünü Desktop'a kaydeder."""
        pixmap = self._video_label.pixmap()
        if pixmap:
            import os, subprocess
            save_dir = os.path.expanduser("~/Desktop/VisionaryAR")
            os.makedirs(save_dir, exist_ok=True)
            filename = os.path.join(save_dir, f"ar_capture_{int(time.time())}.png")
            pixmap.save(filename)
            logger.info(f"Ekran görüntüsü kaydedildi: {filename}")
            self._status_label.setText("📸 Masaüstüne kaydedildi!")
            self._status_label.setStyleSheet("color: #00E676; font-size: 12px; font-weight: 600;")

            # macOS bildirimi
            try:
                subprocess.Popen([
                    'osascript', '-e',
                    f'display notification "AR ekran görüntüsü masaüstüne kaydedildi" with title "Visionary Navigator" sound name "Glass"'
                ])
            except Exception:
                pass
