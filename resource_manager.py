"""
Visionary Navigator — Akıllı Kaynak Yöneticisi
LLM, YOLO ve MediaPipe modellerinin bellek-verimli yaşam döngüsünü yönetir.
Lazy-load, otomatik unload ve RAM izleme sağlar.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any

import psutil

import config

# ─── Loglama ayarları ──────────────────────────────────────────────
logger = logging.getLogger("ResourceManager")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(handler)


class SmartResourceManager:
    """
    Akıllı Kaynak Yöneticisi — Singleton deseni.
    Modelleri talep anında yükler, belirli süre kullanılmadığında bellekten kaldırır.
    Thread-safe erişim sağlar.
    """

    _instance: Optional["SmartResourceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SmartResourceManager":
        """Singleton: Tek bir örnek oluşturulmasını garanti eder."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """İlk oluşturmada kaynakları başlat."""
        if self._initialized:
            return
        self._initialized = True

        # Model referansları
        self._llm_model = None
        self._yolo_model = None
        self._mediapipe_pose = None
        self._mediapipe_face_mesh = None

        # Son kullanım zamanları
        self._llm_last_used: float = 0
        self._vision_last_used: float = 0

        # Kilit nesneleri — thread-safe erişim
        self._llm_lock = threading.Lock()
        self._vision_lock = threading.Lock()

        # Otomatik temizleme zamanlayıcısı
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()

        logger.info("Akıllı Kaynak Yöneticisi başlatıldı.")

    # ─── LLM Yönetimi ─────────────────────────────────────────────

    def load_llm(self) -> Any:
        """
        LLM modelini lazy-load ile yükler.
        Zaten yüklüyse mevcut referansı döndürür.
        """
        with self._llm_lock:
            if self._llm_model is not None:
                self._llm_last_used = time.time()
                return self._llm_model

            try:
                import os
                if not os.path.exists(config.LLM_MODEL_PATH):
                    logger.warning(
                        f"LLM model dosyası bulunamadı: {config.LLM_MODEL_PATH}. "
                        "Lütfen 'models/' klasörüne bir GGUF dosyası yerleştirin."
                    )
                    return None

                logger.info("LLM modeli yükleniyor... Bu biraz zaman alabilir.")
                from llama_cpp import Llama

                self._llm_model = Llama(
                    model_path=config.LLM_MODEL_PATH,
                    n_ctx=config.LLM_CONTEXT_LENGTH,
                    n_gpu_layers=config.LLM_GPU_LAYERS,
                    n_threads=config.LLM_THREADS,
                    verbose=False,
                )
                self._llm_last_used = time.time()

                logger.info("LLM modeli başarıyla yüklendi.")
                return self._llm_model

            except ImportError:
                logger.error("llama-cpp-python paketi yüklü değil. 'pip install llama-cpp-python' ile yükleyin.")
                return None
            except Exception as e:
                logger.error(f"LLM yükleme hatası: {e}")
                return None

    def unload_llm(self) -> None:
        """LLM modelini bellekten kaldırır."""
        with self._llm_lock:
            if self._llm_model is not None:
                del self._llm_model
                self._llm_model = None
                logger.info("LLM modeli bellekten kaldırıldı.")

    @property
    def is_llm_loaded(self) -> bool:
        """LLM modelinin yüklü olup olmadığını kontrol eder."""
        return self._llm_model is not None

    # ─── Görüntü İşleme (Vision) Yönetimi ─────────────────────────

    def load_vision(self) -> Dict[str, Any]:
        """
        YOLO ve MediaPipe modellerini yükler.
        Sözlük olarak döndürür: {"yolo": model, "pose": pose, "face_mesh": face_mesh}
        """
        with self._vision_lock:
            if self._yolo_model is not None:
                self._vision_last_used = time.time()
                return self._get_vision_dict()

            try:
                logger.info("Vision modülleri yükleniyor...")

                # YOLO yükleme
                try:
                    from ultralytics import YOLO
                    self._yolo_model = YOLO(config.YOLO_MODEL_NAME)
                    logger.info("YOLOv8 modeli yüklendi.")
                except Exception as e:
                    logger.warning(f"YOLO yükleme hatası (AR devam edecek): {e}")
                    self._yolo_model = None

                # MediaPipe Pose yükleme
                try:
                    import mediapipe as mp
                    self._mediapipe_pose = mp.solutions.pose.Pose(
                        static_image_mode=False,
                        model_complexity=1,
                        min_detection_confidence=config.MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
                        min_tracking_confidence=config.MEDIAPIPE_MIN_TRACKING_CONFIDENCE,
                    )
                    self._mediapipe_face_mesh = mp.solutions.face_mesh.FaceMesh(
                        static_image_mode=False,
                        max_num_faces=1,
                        min_detection_confidence=config.MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
                        min_tracking_confidence=config.MEDIAPIPE_MIN_TRACKING_CONFIDENCE,
                    )
                    logger.info("MediaPipe modülleri yüklendi.")
                except Exception as e:
                    logger.warning(f"MediaPipe yükleme hatası: {e}")
                    self._mediapipe_pose = None
                    self._mediapipe_face_mesh = None

                self._vision_last_used = time.time()
                return self._get_vision_dict()

            except Exception as e:
                logger.error(f"Vision yükleme hatası: {e}")
                return self._get_vision_dict()

    def unload_vision(self) -> None:
        """Vision modellerini bellekten kaldırır."""
        with self._vision_lock:
            if self._mediapipe_pose is not None:
                self._mediapipe_pose.close()
                self._mediapipe_pose = None
            if self._mediapipe_face_mesh is not None:
                self._mediapipe_face_mesh.close()
                self._mediapipe_face_mesh = None
            if self._yolo_model is not None:
                del self._yolo_model
                self._yolo_model = None
            logger.info("Vision modülleri bellekten kaldırıldı.")

    @property
    def is_vision_loaded(self) -> bool:
        """Vision modellerinin yüklü olup olmadığını kontrol eder."""
        return self._yolo_model is not None or self._mediapipe_pose is not None

    def _get_vision_dict(self) -> Dict[str, Any]:
        """Vision modellerini sözlük olarak döndürür."""
        return {
            "yolo": self._yolo_model,
            "pose": self._mediapipe_pose,
            "face_mesh": self._mediapipe_face_mesh,
        }

    # ─── Bellek İzleme ─────────────────────────────────────────────

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Mevcut bellek kullanım istatistiklerini döndürür.
        Dönen sözlük: ram_used_mb, ram_total_mb, ram_percent, loaded_models
        """
        process = psutil.Process()
        mem_info = process.memory_info()
        system_mem = psutil.virtual_memory()

        loaded_models = []
        if self.is_llm_loaded:
            loaded_models.append("LLM")
        if self._yolo_model is not None:
            loaded_models.append("YOLO")
        if self._mediapipe_pose is not None:
            loaded_models.append("MediaPipe Pose")
        if self._mediapipe_face_mesh is not None:
            loaded_models.append("MediaPipe FaceMesh")

        return {
            "process_ram_mb": round(mem_info.rss / (1024 * 1024), 1),
            "system_ram_used_mb": round(system_mem.used / (1024 * 1024), 1),
            "system_ram_total_mb": round(system_mem.total / (1024 * 1024), 1),
            "system_ram_percent": system_mem.percent,
            "loaded_models": loaded_models,
        }

    # ─── Otomatik Temizleme ────────────────────────────────────────

    def _start_cleanup_timer(self) -> None:
        """Periyodik temizleme zamanlayıcısını başlatır (30 saniyede bir kontrol)."""
        self._cleanup_timer = threading.Timer(120.0, self._auto_cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _auto_cleanup(self) -> None:
        """
        Kullanılmayan modelleri otomatik olarak bellekten kaldırır.
        LLM: config.LLM_IDLE_TIMEOUT_SEC sonra kaldırılır.
        """
        current_time = time.time()

        # LLM inaktivite kontrolü
        if (self.is_llm_loaded and
                (current_time - self._llm_last_used) > config.LLM_IDLE_TIMEOUT_SEC):
            logger.info(
                f"LLM {config.LLM_IDLE_TIMEOUT_SEC}s boyunca kullanılmadı — bellekten kaldırılıyor."
            )
            self.unload_llm()

        # Zamanlayıcıyı tekrar başlat
        self._start_cleanup_timer()

    # ─── Temizlik ──────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Tüm kaynakları serbest bırakır ve zamanlayıcıyı iptal eder."""
        logger.info("Kaynak yöneticisi kapatılıyor...")
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        self.unload_llm()
        self.unload_vision()
        logger.info("Tüm kaynaklar serbest bırakıldı.")
