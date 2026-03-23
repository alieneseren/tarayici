"""
Visionary Navigator — Yapılandırma Sabitleri
Tüm uygulama genelinde kullanılan sabitler ve varsayılan değerler.
"""

import os

# ─── Uygulama Bilgileri ────────────────────────────────────────────
APP_NAME = "Visionary Navigator"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Yapay Zeka Destekli Masaüstü Tarayıcı"

# ─── Dosya Yolları ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(BASE_DIR, "js")
STYLES_DIR = os.path.join(BASE_DIR, "styles")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
MODELS_DIR = os.path.join(BASE_DIR, "models")
MUSIC_DIR = os.path.join(BASE_DIR, "music")

# ─── LLM Yapılandırması ───────────────────────────────────────────
LLM_MODEL_PATH = os.path.join(MODELS_DIR, "model.gguf")  # Kullanıcı kendi modelini koyacak
LLM_CONTEXT_LENGTH = 4096  # Hibrit AI: ağır işler Gemini'ye yönlendirilir
LLM_MAX_TOKENS = 1024
LLM_TEMPERATURE = 0.7
LLM_GPU_LAYERS = -1  # -1 = Apple Silicon Metal GPU auto-offload
LLM_THREADS = 4
LLM_IDLE_TIMEOUT_SEC = 600  # 10 dakika — gereksiz yeniden yüklemeyi önler

# ─── YOLO Yapılandırması ──────────────────────────────────────────
YOLO_MODEL_NAME = "yolov8n.pt"  # Nano model — hız öncelikli
YOLO_CONFIDENCE_THRESHOLD = 0.5

# ─── MediaPipe Yapılandırması ──────────────────────────────────────
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

# ─── Kamera Yapılandırması ────────────────────────────────────────
CAMERA_INDEX = 0
CAMERA_FPS = 30
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
AR_LOW_FPS = 15  # LLM aktifken düşük FPS modu

# ─── UI Renk Paleti ───────────────────────────────────────────────
COLORS = {
    "bg_primary": "#0D0D0D",
    "bg_secondary": "#1A1A2E",
    "bg_tertiary": "#16213E",
    "accent_primary": "#6C63FF",
    "accent_secondary": "#00D9FF",
    "accent_gradient_start": "#6C63FF",
    "accent_gradient_end": "#00D9FF",
    "text_primary": "#E8E8E8",
    "text_secondary": "#A0A0B0",
    "text_muted": "#6B6B80",
    "border": "#2A2A40",
    "success": "#00E676",
    "warning": "#FFB300",
    "error": "#FF5252",
    "sidebar_bg": "rgba(26, 26, 46, 0.85)",
}

# ─── UI Boyutları ──────────────────────────────────────────────────
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
SIDEBAR_WIDTH = 380
TAB_HEIGHT = 32
TOOLBAR_HEIGHT = 40
ANIMATION_DURATION_MS = 250

# ─── AI Prompt Şablonları ─────────────────────────────────────────
REVIEW_ANALYSIS_PROMPT = """E-ticaret ürün verilerini, müşteri yorumlarını ve soru-cevap bölümünü analiz et.
Aşağıdaki 4 başlığı kullanarak kısa ve net bir özet oluştur. Başka hiçbir açıklama yazma.
Eğer yorum yoksa, ARTILAR ve EKSİLER kısımlarına madde ekleme, sadece "Kullanıcı deneyimi bulunmuyor." yaz.
Eğer soru-cevap verisi yoksa, o bölümü "Soru-cevap verisi bulunamadı." olarak bırak.
Asla bana verdiğim şablon metnini veya parantezleri kopyalama.

💡 ARTILAR
(Var olan olumlu özellikleri listele)

⚠️ EKSİLER
(Var olan olumsuz özellikleri listele)

❓ SORU-CEVAP ÖZETİ
(Sıkça sorulan soruları ve cevaplarını özetle)

🎯 PROFESYONEL DEĞERLENDİRME
(Satıcı ve ürün hakkında objektif, 2 cümlelik nihai karar)

Müşteri Yorumları & Veriler:
{product_data}
"""

# ─── Desteklenen E-ticaret Siteleri ──────────────────────────────
SUPPORTED_SITES = {
    "trendyol": {
        "domain": "trendyol.com",
        "review_selector": ".pr-rnr-com-w",
        "seller_selector": ".merchant-box",
        "product_image_selector": "img.detail-section-img",
    },
    "hepsiburada": {
        "domain": "hepsiburada.com",
        "review_selector": ".hermes-ReviewCard",
        "seller_selector": ".merchant-info",
        "product_image_selector": "img.product-image",
    },
}

# ─── Finansal Zekâ Modülü ──────────────────────────────────────────
FINANCE_CACHE_DIR = os.path.join(BASE_DIR, "models", "finance_cache")
FINANCE_HISTORY_YEARS = 5          # Tarihsel veri çekme süresi (yıl)
FINANCE_LOOKBACK_WINDOW = 60       # LSTM kayan pencere boyutu
FINANCE_FORECAST_DAYS = 14         # Tahmin ufku (gün)
FINANCE_LSTM_EPOCHS = 25           # LSTM eğitim epoch sayısı
FINANCE_MONTE_CARLO_RUNS = 50      # Güven aralığı simülasyonu

# Finans sitesi domain'leri — otomatik tarama tetikleme
FINANCE_DOMAINS = [
    'finance.yahoo.com', 'google.com/finance', 'investing.com',
    'bloomberg.com', 'tradingview.com', 'bigpara.hurriyet.com',
    'marketwatch.com', 'cnbc.com', 'reuters.com',
    'finans.mynet.com', 'borsaistanbul.com',
]

# ─── Varsayılan Ana Sayfa ─────────────────────────────────────────
DEFAULT_HOME_URL = "https://www.google.com"
NEW_TAB_URL = "about:blank"
