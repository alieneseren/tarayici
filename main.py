"""
Visionary Navigator — Ana Giriş Noktası
Uygulamayı başlatır, splash ekranını gösterir ve ana pencereyi açar.
"""

import sys
import os
import signal
import logging

# ─── Loglama yapılandırması ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)-18s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")


def ensure_directories():
    """Gerekli dizinlerin var olmasını sağlar."""
    import config
    dirs = [
        config.MODELS_DIR,
        config.ASSETS_DIR,
        config.ICONS_DIR,
        config.MUSIC_DIR,
        os.path.join(config.BASE_DIR, "screenshots"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def create_splash(app):
    """Başlangıç yükleme ekranını oluşturur."""
    from PyQt6.QtWidgets import QSplashScreen, QLabel
    from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont, QLinearGradient
    from PyQt6.QtCore import Qt

    # Splash ekran boyutu
    width, height = 480, 300

    pixmap = QPixmap(width, height)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Arka plan gradient
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#0D0D0D"))
    gradient.setColorAt(0.5, QColor("#1A1A2E"))
    gradient.setColorAt(1.0, QColor("#16213E"))
    painter.fillRect(0, 0, width, height, gradient)

    # Üst accent çizgisi
    accent_gradient = QLinearGradient(0, 0, width, 0)
    accent_gradient.setColorAt(0.0, QColor("#6C63FF"))
    accent_gradient.setColorAt(1.0, QColor("#00D9FF"))
    painter.fillRect(0, 0, width, 3, accent_gradient)

    # Uygulama adı
    painter.setPen(QColor("#E8E8E8"))
    title_font = QFont(".AppleSystemUIFont", 28, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(0, 80, width, 50, Qt.AlignmentFlag.AlignCenter, "🧭 Visionary Navigator")

    # Alt başlık
    painter.setPen(QColor("#6C63FF"))
    subtitle_font = QFont(".AppleSystemUIFont", 13, QFont.Weight.Normal)
    painter.setFont(subtitle_font)
    painter.drawText(0, 130, width, 30, Qt.AlignmentFlag.AlignCenter, "Yapay Zeka Destekli Masaüstü Tarayıcı")

    # Versiyon
    painter.setPen(QColor("#6B6B80"))
    ver_font = QFont(".AppleSystemUIFont", 10)
    painter.setFont(ver_font)
    painter.drawText(0, 170, width, 20, Qt.AlignmentFlag.AlignCenter, "v1.0.0 — AI + AR + Web")

    # Yükleniyor
    painter.setPen(QColor("#00D9FF"))
    loading_font = QFont(".AppleSystemUIFont", 11)
    painter.setFont(loading_font)
    painter.drawText(0, 240, width, 20, Qt.AlignmentFlag.AlignCenter, "Yükleniyor...")

    # Alt accent çizgisi
    painter.fillRect(0, height - 3, width, 3, accent_gradient)

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    return splash


def main():
    """Ana uygulama döngüsü."""
    logger.info("=" * 60)
    logger.info("  Visionary Navigator başlatılıyor...")
    logger.info("=" * 60)

    # Dizinleri oluştur
    ensure_directories()

    # QtWebEngine ayarları — process başlamadan ÖNCE yapılmalı
    base_flags = "--disable-gpu-compositing --use-gl=angle --disable-features=SkiaGraphite"
    
    # Tor modu aktifse proxy flag'i ekle
    try:
        from privacy_engine import is_tor_mode_enabled, get_tor_chromium_flags
        if is_tor_mode_enabled():
            tor_flags = get_tor_chromium_flags()
            if tor_flags:
                base_flags = f"{base_flags} {tor_flags}"
                logger.info("Tor modu aktif, proxy ayarlandı.")
    except Exception as e:
        logger.warning(f"Tor durumu kontrol edilemedi: {e}")
    
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", base_flags)

    # KRİTİK: QtWebEngineWidgets, QApplication oluşturulmadan ÖNCE import edilmeli
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # Yüksek DPI desteği
    app = QApplication(sys.argv)
    app.setApplicationName("Visionary Navigator")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Visionary")

    # Ctrl+C ile güvenli kapanma (traceback önleme)
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Splash ekranı göster
    splash = create_splash(app)

    # Ana pencereyi oluştur
    from browser_core import VisionaryBrowser
    browser = VisionaryBrowser()

    # Splash'ı kapat ve pencereyi göster
    splash.finish(browser)
    browser.show()
    
    # Pencereyi ön plana getir ve aktif yap
    browser.raise_()
    browser.activateWindow()

    logger.info("Uygulama hazır.")

    # Hoşgeldin selamlaması (ayarlarda aktifse)
    from PyQt6.QtCore import QTimer
    def _play_welcome():
        try:
            from settings_manager import SettingsManager
            settings = SettingsManager()
            if settings.get("welcome_enabled", True) and settings.tts_enabled:
                from voice_engine import WelcomeGreeting
                browser._welcome = WelcomeGreeting(
                    music_url=settings.music_url,
                    voice=settings.tts_voice,
                    music_start_sec=settings.get("music_start_sec", 0)
                )
                browser._welcome.play()
                logger.info("Hoşgeldin selamlaması çalınıyor.")
        except Exception as e:
            logger.warning(f"Hoşgeldin hatası: {e}")

    QTimer.singleShot(2000, _play_welcome)

    # Uygulama döngüsünü başlat
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
