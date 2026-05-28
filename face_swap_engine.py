"""
Visionary Navigator — Face Swap Engine
InsightFace + InSwapper tabanlı yüz değiştirme motoru.
E-ticaret sitelerindeki manken fotoğraflarına kullanıcı yüzü giydirme.

Deepfake projesinden (~/ deepfake/src/ai_engine.py) çekirdek pipeline sadeleştirilerek
tarayıcıya entegre edilmiştir.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import config

logger = logging.getLogger("FaceSwapEngine")
logger.setLevel(logging.INFO)

# ─── Model yolları ─────────────────────────────────────────────────
MODELS_DIR = Path(config.BASE_DIR) / "models"
INSIGHTFACE_ROOT = MODELS_DIR / "insightface_models"  # symlink → deepfake/models/models
INSWAPPER_PATH = MODELS_DIR / "inswapper_128.onnx"
GFPGAN_PATH = MODELS_DIR / "GFPGANv1.4.pth"

# InsightFace ayarları
INSIGHTFACE_MODEL_NAME = "buffalo_l"
DET_SIZE = (640, 640)
DET_THRESH = 0.35
FACE_DETECTION_THRESHOLD = 0.4

# ONNX providers — Apple Silicon: CoreML + CPU
ONNX_PROVIDERS = ["CoreMLExecutionProvider", "CPUExecutionProvider"]

# Otomatik boşaltma (5 dakika inaktivite)
IDLE_TIMEOUT_SEC = 300


@dataclass
class DetectedFace:
    """Algılanan yüz bilgisi konteyner'ı."""
    id: int
    bbox: np.ndarray          # [x1, y1, x2, y2]
    kps: np.ndarray           # 5 landmark
    embedding: np.ndarray     # Yüz gömme vektörü
    det_score: float          # Algılama güven skoru
    thumbnail: Optional[Image.Image] = None

    def get_center(self) -> Tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2
        )

    def get_area(self) -> float:
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])


class FaceSwapEngine:
    """
    InsightFace + InSwapper tabanlı yüz değiştirme motoru.
    Singleton pattern — tek bir global instance üzerinden çalışır.
    Lazy-load: modeller ilk kullanımda yüklenir.
    Auto-unload: belirli süre inaktivite sonrası bellek serbest bırakılır.
    """

    _instance: Optional["FaceSwapEngine"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._face_analyzer = None
        self._face_swapper = None
        self._face_enhancer = None
        self._next_face_id = 0
        self._last_used = 0.0
        self._idle_timer: Optional[threading.Timer] = None
        self._initialized = True
        logger.info("FaceSwapEngine oluşturuldu (lazy-load).")

    # ─── Modelleri Yükleme ────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._face_analyzer is not None and self._face_swapper is not None

    def _touch(self):
        """Son kullanım zamanını güncelle ve idle timer'ı resetle."""
        self._last_used = time.time()
        if self._idle_timer:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(IDLE_TIMEOUT_SEC, self._auto_unload)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _auto_unload(self):
        """İnaktivite sonrası otomatik bellek serbest bırakma."""
        elapsed = time.time() - self._last_used
        if elapsed >= IDLE_TIMEOUT_SEC:
            logger.info(f"FaceSwap {int(elapsed)}s inaktif — modeller boşaltılıyor.")
            self.unload()

    def _ensure_analyzer(self) -> None:
        """InsightFace FaceAnalysis'i lazy-load et."""
        if self._face_analyzer is not None:
            return

        if not INSIGHTFACE_ROOT.exists():
            raise RuntimeError(
                f"InsightFace modelleri bulunamadı: {INSIGHTFACE_ROOT}\n"
                "Lütfen deepfake projesinin model dosyalarını kontrol edin."
            )

        import insightface
        from insightface.app import FaceAnalysis

        logger.info("🔄 InsightFace yükleniyor...")

        self._face_analyzer = FaceAnalysis(
            name=INSIGHTFACE_MODEL_NAME,
            root=str(INSIGHTFACE_ROOT.parent),  # parent = models/insightface_models/..
            providers=ONNX_PROVIDERS,
        )
        self._face_analyzer.prepare(
            ctx_id=0,
            det_size=DET_SIZE,
            det_thresh=DET_THRESH,
        )
        logger.info("✅ InsightFace yüklendi.")

    def _ensure_swapper(self) -> None:
        """InSwapper modelini lazy-load et."""
        if self._face_swapper is not None:
            return

        if not INSWAPPER_PATH.exists():
            raise RuntimeError(
                f"InSwapper modeli bulunamadı: {INSWAPPER_PATH}\n"
                "Lütfen deepfake projesinin model dosyalarını kontrol edin."
            )

        import insightface

        logger.info("🔄 InSwapper yükleniyor...")
        self._face_swapper = insightface.model_zoo.get_model(
            str(INSWAPPER_PATH),
            providers=ONNX_PROVIDERS,
        )
        logger.info("✅ InSwapper yüklendi.")

    def _ensure_enhancer(self) -> None:
        """GFPGAN face enhancer'ı lazy-load et (opsiyonel)."""
        if self._face_enhancer is not None:
            return

        if not GFPGAN_PATH.exists():
            logger.warning("GFPGAN modeli bulunamadı — enhancement devre dışı.")
            return

        try:
            from gfpgan import GFPGANer
            import torch

            device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
            logger.info(f"🔄 GFPGAN yükleniyor (device: {device})...")

            self._face_enhancer = GFPGANer(
                model_path=str(GFPGAN_PATH),
                upscale=2,
                arch="clean",
                channel_multiplier=2,
                device=device,
            )
            logger.info("✅ GFPGAN yüklendi.")
        except Exception as e:
            logger.warning(f"GFPGAN yüklenemedi: {e}")

    # ─── Yüz Algılama ─────────────────────────────────────────────

    def detect_faces(
        self,
        image: np.ndarray,
        generate_thumbnails: bool = True
    ) -> List[DetectedFace]:
        """
        Görüntüdeki yüzleri algılar.

        Args:
            image: BGR numpy array
            generate_thumbnails: Küçük yüz görseli üret

        Returns:
            DetectedFace listesi
        """
        self._ensure_analyzer()
        self._touch()

        faces = self._face_analyzer.get(image)
        detected = []

        for face in faces:
            if face.det_score < FACE_DETECTION_THRESHOLD:
                continue

            thumbnail = None
            if generate_thumbnails:
                thumbnail = self._create_thumbnail(image, face.bbox)

            detected.append(DetectedFace(
                id=self._next_face_id,
                bbox=face.bbox,
                kps=face.kps,
                embedding=face.embedding,
                det_score=face.det_score,
                thumbnail=thumbnail,
            ))
            self._next_face_id += 1

        return detected

    def _create_thumbnail(
        self, image: np.ndarray, bbox: np.ndarray, size: Tuple[int, int] = (120, 120)
    ) -> Image.Image:
        """Yüz bounding box'ından kırpılmış küçük görsel üretir."""
        x1, y1, x2, y2 = map(int, bbox)
        padding = int((x2 - x1) * 0.25)
        h, w = image.shape[:2]

        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(w, x2 + padding)
        y2 = min(h, y2 + padding)

        crop = image[y1:y2, x1:x2]
        crop = cv2.resize(crop, size)
        return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

    # ─── Yüz Değiştirme ───────────────────────────────────────────

    def swap_face(
        self,
        target_image: np.ndarray,
        source_face: DetectedFace,
        target_face: DetectedFace,
        blend: bool = True,
    ) -> np.ndarray:
        """
        Hedef görüntüdeki bir yüzü kaynak yüzle değiştirir.

        Args:
            target_image: BGR hedef görüntü
            source_face: Giydirmek istenen yüz (kullanıcı)
            target_face: Değiştirilecek yüz (manken)
            blend: Kenar yumuşatma + renk eşleme uygula

        Returns:
            Yüzü değiştirilmiş görüntü
        """
        self._ensure_swapper()
        self._touch()

        import insightface

        source_obj = insightface.app.common.Face(
            bbox=source_face.bbox,
            kps=source_face.kps,
            det_score=source_face.det_score,
            embedding=source_face.embedding,
        )
        target_obj = insightface.app.common.Face(
            bbox=target_face.bbox,
            kps=target_face.kps,
            det_score=target_face.det_score,
            embedding=target_face.embedding,
        )

        result = self._face_swapper.get(
            target_image, target_obj, source_obj, paste_back=True
        )

        if blend:
            try:
                result = self._apply_improved_blend(
                    original=target_image,
                    swapped=result,
                    face_bbox=target_face.bbox,
                    face_kps=target_face.kps,
                )
            except Exception as e:
                logger.warning(f"Blend hatası: {e}")

        return result

    # ─── Tek Adım API ──────────────────────────────────────────────

    def swap_in_product_photo(
        self,
        product_image: np.ndarray,
        user_photo: np.ndarray,
        enhance: bool = False,
    ) -> Optional[np.ndarray]:
        """
        Manken fotoğrafındaki yüzü kullanıcının yüzüyle değiştirir.

        Args:
            product_image: E-ticaret ürün fotoğrafı (BGR)
            user_photo: Kullanıcının fotoğrafı (BGR)
            enhance: GFPGAN ile kalite artır

        Returns:
            Sonuç görüntüsü veya None
        """
        self._touch()

        # 1. Mankendeki yüzleri algıla
        target_faces = self.detect_faces(product_image, generate_thumbnails=False)
        if not target_faces:
            logger.warning("Ürün fotoğrafında yüz algılanamadı.")
            return None

        # En büyük yüzü hedef al (manken genelde ana figürdür)
        target_face = max(target_faces, key=lambda f: f.get_area())

        # 2. Kullanıcı fotoğrafındaki yüzü algıla
        source_faces = self.detect_faces(user_photo, generate_thumbnails=False)
        if not source_faces:
            logger.warning("Kullanıcı fotoğrafında yüz algılanamadı.")
            return None

        # En yüksek güvenli yüzü kaynak al
        source_face = max(source_faces, key=lambda f: f.det_score)

        # 3. Yüz değiştir
        result = self.swap_face(product_image, source_face, target_face, blend=True)

        # 4. Kalite artırma (opsiyonel)
        if enhance:
            result = self.enhance_face(result)

        logger.info("✅ Yüz değiştirme tamamlandı.")
        return result

    # ─── Kalite Artırma ────────────────────────────────────────────

    def enhance_face(self, image: np.ndarray) -> np.ndarray:
        """GFPGAN ile yüz kalitesini artırır."""
        self._ensure_enhancer()

        if self._face_enhancer is None:
            return image

        try:
            _, _, output = self._face_enhancer.enhance(
                image,
                has_aligned=False,
                only_center_face=False,
                paste_back=True,
                weight=0.95,
            )
            return output if output is not None else image
        except Exception as e:
            logger.warning(f"Enhancement hatası: {e}")
            return image

    # ─── Blend + Renk Eşleme (Deepfake projesinden) ───────────────

    def _apply_improved_blend(
        self,
        original: np.ndarray,
        swapped: np.ndarray,
        face_bbox: np.ndarray,
        face_kps: np.ndarray,
    ) -> np.ndarray:
        """
        Gelişmiş kenar yumuşatma + renk eşleme.
        Deepfake projesinin ai_engine.py _apply_improved_blend fonksiyonundan.
        """
        h, w = original.shape[:2]

        # Yüz maskesi oluştur
        mask = self._create_face_mask(h, w, face_bbox, face_kps)

        # Renk eşleme
        swapped_matched = self._match_color(original, swapped, mask)

        # Çok aşamalı Gaussian blur — pürüzsüz kenarlar
        blur1 = cv2.GaussianBlur(mask, (31, 31), 11)
        blur2 = cv2.GaussianBlur(mask, (21, 21), 7)
        blur3 = cv2.GaussianBlur(mask, (11, 11), 3)

        mask_final = (blur1 * 0.2 + blur2 * 0.3 + blur3 * 0.5).astype(np.uint8)
        mask_3d = mask_final[:, :, np.newaxis].astype(np.float32) / 255.0

        result = (
            swapped_matched.astype(np.float32) * mask_3d
            + original.astype(np.float32) * (1 - mask_3d)
        ).astype(np.uint8)

        return result

    def _create_face_mask(
        self,
        height: int,
        width: int,
        face_bbox: np.ndarray,
        face_kps: np.ndarray,
    ) -> np.ndarray:
        """Yüz bölgesi için eliptik maske oluşturur."""
        mask = np.zeros((height, width), dtype=np.uint8)
        x1, y1, x2, y2 = map(int, face_bbox)

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)

        if face_kps is not None and len(face_kps) >= 5:
            kps = face_kps.astype(np.int32)
            cx = int(np.mean(kps[:, 0]))
            cy = int(np.mean(kps[:, 1]))

            kp_spread_x = np.max(kps[:, 0]) - np.min(kps[:, 0])
            kp_spread_y = np.max(kps[:, 1]) - np.min(kps[:, 1])
            bbox_w = x2 - x1
            bbox_h = y2 - y1

            rx = int(max(kp_spread_x, bbox_w * 0.5) * 1.1)
            ry = int(max(kp_spread_y, bbox_h * 0.5) * 1.3)

            cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
        else:
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            rx = int((x2 - x1) * 0.55)
            ry = int((y2 - y1) * 0.55)
            cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)

        return mask

    def _match_color(
        self,
        original: np.ndarray,
        swapped: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        """
        LAB renk uzayında renk transferi.
        'Yapıştırılmış' görünümü azaltır.
        """
        original_lab = cv2.cvtColor(original, cv2.COLOR_BGR2LAB).astype(np.float32)
        swapped_lab = cv2.cvtColor(swapped, cv2.COLOR_BGR2LAB).astype(np.float32)

        mask_bool = mask > 128
        if not np.any(mask_bool):
            return swapped

        for i in range(3):
            orig_ch = original_lab[:, :, i]
            swap_ch = swapped_lab[:, :, i]

            orig_mean = np.mean(orig_ch[mask_bool])
            orig_std = np.std(orig_ch[mask_bool]) + 1e-6
            swap_mean = np.mean(swap_ch[mask_bool])
            swap_std = np.std(swap_ch[mask_bool]) + 1e-6

            swap_ch[mask_bool] = (
                (swap_ch[mask_bool] - swap_mean) * (orig_std / swap_std) + orig_mean
            )
            swapped_lab[:, :, i] = swap_ch

        swapped_lab = np.clip(swapped_lab, 0, 255).astype(np.uint8)
        return cv2.cvtColor(swapped_lab, cv2.COLOR_LAB2BGR)

    # ─── Bellek Yönetimi ───────────────────────────────────────────

    def unload(self) -> None:
        """Tüm modelleri bellekten kaldır."""
        if self._idle_timer:
            self._idle_timer.cancel()
            self._idle_timer = None

        self._face_analyzer = None
        self._face_swapper = None
        self._face_enhancer = None
        self._next_face_id = 0

        # Garbage collection
        import gc
        gc.collect()

        logger.info("🧹 FaceSwap modelleri boşaltıldı.")

    def get_memory_mb(self) -> float:
        """Tahmini bellek kullanımı (MB)."""
        mb = 0.0
        if self._face_analyzer is not None:
            mb += 350  # InsightFace ~350 MB
        if self._face_swapper is not None:
            mb += 530  # InSwapper ~530 MB
        if self._face_enhancer is not None:
            mb += 350  # GFPGAN ~350 MB
        return mb
