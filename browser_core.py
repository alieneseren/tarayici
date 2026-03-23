"""
Visionary Navigator — Tarayıcı Çekirdeği
PyQt6 + QtWebEngine tabanlı ana tarayıcı penceresi.
Sekmeli tarama, adres çubuğu, navigasyon araç çubuğu, AI kenar paneli ve AR modülü entegrasyonu.
"""

import json
import logging
import os
import sys
from typing import Optional
from urllib.parse import urlparse
import urllib.request

from PyQt6.QtCore import (
    Qt, QUrl, pyqtSlot, pyqtSignal, QObject, QSize, QTimer, QThread,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QIcon, QAction, QKeySequence, QFont, QFontDatabase, QPixmap, QColor
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QLineEdit, QStatusBar,
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
    QPushButton, QApplication, QSizePolicy, QFrame, QTabBar,
    QGraphicsDropShadowEffect, QSlider, QScrollArea, QInputDialog
)

import config
from ai_logic import AISidebar
from vision_ar import ARWidget
from gesture_controller import GestureWidget
from resource_manager import SmartResourceManager
from settings_manager import SettingsManager
from finance_ui import FinanceSidebar
from privacy_engine import PrivacyEngine, AdBlockerInterceptor, apply_tor_proxy_to_profile, remove_proxy
from visionary_search import VisionarySearchManager, VisionarySearchPage
from guardian_security import VisionaryGuardian, GuardianWarningPage
from ghost_sandbox import GhostManager, GhostTab, GhostNotification
from proxy_engine import (
    ProxyManager, ProxyConfig, ProxyType, ProxyStatus, 
    PROXY_COUNTRIES, get_chromium_proxy_args
)

# ─── Loglama ───────────────────────────────────────────────────────
logger = logging.getLogger("BrowserCore")
logger.setLevel(logging.INFO)


# ─── Sürüklenebilir YouTube Video Penceresi ───────────────────────
class _StreamFetchWorker(QObject):
    """yt_dlp ile arka planda stream URL alır — UI donmaz."""
    stream_ready = pyqtSignal(str, str)   # (stream_url, title)
    error        = pyqtSignal(str)

    def __init__(self, youtube_url: str):
        super().__init__()
        self._url = youtube_url

    def run(self):
        try:
            import yt_dlp
            opts = {
                'format': 'best[ext=mp4][height<=720]/bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[height<=720]',
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {'youtube': {'player_client': ['android']}},
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._url, download=False)
                title = info.get('title', '')
                # Doğrudan URL veya format listesinden al
                url = info.get('url', '')
                if not url:
                    fmts = info.get('formats', [])
                    # Video+audio birleşik mp4 olanı tercih et
                    for f in reversed(fmts):
                        if f.get('url') and f.get('ext') == 'mp4' and f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                            url = f['url']
                            break
                    # mp4 bulunamazsa herhangi birleşik format
                    if not url:
                        for f in reversed(fmts):
                            if f.get('url') and f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                                url = f['url']
                                break
                    if not url and fmts:
                        url = fmts[-1].get('url', '')
                if url:
                    self.stream_ready.emit(url, title)
                else:
                    self.error.emit("Stream URL alınamadı")
        except Exception as e:
            self.error.emit(str(e))


class _DraggableVideoFrame(QWidget):
    """
    Always-on-Top PiP video penceresi.
    Tarayıcı arka plana atılsa bile ekranda kalır.
    İki mod: sessiz (müzik ile senkron) veya sesli (video izleme).
    """
    # Müzik duraklatma/devam sinyalleri
    request_music_pause = pyqtSignal()
    request_music_resume = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(None)  # Top-level pencere (parent yok)
        self._parent_browser = parent
        self.setFixedSize(380, 260)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QWidget#pipWindow {
                background: #0A0A12;
                border: 1px solid rgba(29,185,84,0.35);
                border-radius: 14px;
            }
        """)
        self.setObjectName("pipWindow")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # ── Başlık çubuğu ───────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(6, 2, 2, 0)
        self._title_lbl = QLabel("🎬 Video")
        self._title_lbl.setStyleSheet(
            "color: #8E8EA0; font-size: 10px; font-weight: 600; background: transparent;"
        )
        self._title_lbl.setMaximumWidth(260)

        # Ses aç/kapa butonu
        self._sound_btn = QPushButton("🔇")
        self._sound_btn.setFixedSize(24, 24)
        self._sound_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sound_btn.setToolTip("Sesi aç (müzik duracak)")
        self._sound_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #5A5A70; font-size: 13px; }
            QPushButton:hover { color: #1DB954; }
        """)
        self._sound_btn.clicked.connect(self._toggle_sound)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none;
                          color: #5A5A70; font-size: 12px; }
            QPushButton:hover { color: #FF5252; }
        """)
        close_btn.clicked.connect(self._close_video)
        header.addWidget(self._title_lbl, 1)
        header.addWidget(self._sound_btn)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # ── Video alanı (QVideoWidget) ───────────────────────────
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: #000; border-radius: 8px;")
        layout.addWidget(self._video_widget, 1)

        # ── Yükleniyor / Hata etiketi ────────────────────────────
        self._status_lbl = QLabel("⏳ Stream URL alınıyor...")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "color: #6B7B72; font-size: 10px; font-family: 'Menlo', monospace; background: transparent;"
        )
        layout.addWidget(self._status_lbl)

        # ── QMediaPlayer ──────────────────────────────────────────
        self._player = QMediaPlayer()
        self._audio_out = QAudioOutput()
        self._audio_out.setVolume(0.0)
        self._audio_out.setMuted(True)
        self._player.setAudioOutput(self._audio_out)
        self._player.setVideoOutput(self._video_widget)

        # Ses modu: False = sessiz (müzik senkron), True = sesli (video izleme)
        self._sound_on = False

        self._fetch_thread = None
        self._fetch_worker = None
        self._drag_pos = None
        self.on_video_playing = None
        self.on_video_stopped = None

        self.hide()

    # ── Ses kontrolü ─────────────────────────────────────────────

    def _toggle_sound(self) -> None:
        """Video sesini aç/kapa. Ses açılınca müzik duraklar."""
        self._sound_on = not self._sound_on
        if self._sound_on:
            self._audio_out.setMuted(False)
            self._audio_out.setVolume(0.8)
            self._sound_btn.setText("🔊")
            self._sound_btn.setToolTip("Sesi kapat (müzik devam edecek)")
            self.request_music_pause.emit()
        else:
            self._audio_out.setMuted(True)
            self._audio_out.setVolume(0.0)
            self._sound_btn.setText("🔇")
            self._sound_btn.setToolTip("Sesi aç (müzik duracak)")
            self.request_music_resume.emit()

    def set_sound_mode(self, sound_on: bool) -> None:
        """Dışarıdan ses modunu ayarla."""
        self._sound_on = sound_on
        if sound_on:
            self._audio_out.setMuted(False)
            self._audio_out.setVolume(0.8)
            self._sound_btn.setText("🔊")
        else:
            self._audio_out.setMuted(True)
            self._audio_out.setVolume(0.0)
            self._sound_btn.setText("🔇")

    # ── Yükleme ─────────────────────────────────────────────────

    def load_video(self, youtube_url: str, title: str = ""):
        """YouTube URL'den stream URL al ve oynat."""
        if not youtube_url:
            return
        self._title_lbl.setText(f"🎬 {title[:30] if title else 'Video'}")
        self._status_lbl.setText("⏳ Stream URL alınıyor...")
        self._status_lbl.show()
        self._video_widget.hide()
        self.show()
        self.raise_()
        self._stop_fetch()

        self._fetch_thread = QThread()
        self._fetch_worker = _StreamFetchWorker(youtube_url)
        self._fetch_worker.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.stream_ready.connect(self._on_stream_ready)
        self._fetch_worker.error.connect(self._on_stream_error)
        self._fetch_worker.stream_ready.connect(self._fetch_thread.quit)
        self._fetch_worker.error.connect(self._fetch_thread.quit)
        self._fetch_thread.start()

    def _stop_fetch(self):
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait(1000)
        self._fetch_thread = None
        self._fetch_worker = None

    def _on_stream_ready(self, stream_url: str, title: str):
        """Stream URL hazır — QMediaPlayer ile oynat."""
        self._status_lbl.hide()
        self._video_widget.show()
        if title:
            self._title_lbl.setText(f"🎬 {title[:30]}")
        self._player.setSource(QUrl(stream_url))
        self._player.play()
        if callable(self.on_video_playing):
            self.on_video_playing(title or self._title_lbl.text())

    def _on_stream_error(self, err: str):
        self._status_lbl.setText(f"❌ {err[:50]}")
        self._video_widget.hide()

    # ── Kontroller ───────────────────────────────────────────────

    def _close_video(self):
        self._player.stop()
        self._stop_fetch()
        # Ses açıkken kapatılıyorsa müziği devam ettir
        if self._sound_on:
            self._sound_on = False
            self._audio_out.setMuted(True)
            self._audio_out.setVolume(0.0)
            self._sound_btn.setText("🔇")
            self.request_music_resume.emit()
        self.hide()
        if callable(self.on_video_stopped):
            self.on_video_stopped()

    def pause_video(self) -> None:
        self._player.pause()

    def resume_video(self) -> None:
        self._player.play()

    # ── Sürükleme (frameless pencere) ────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def paintEvent(self, event):
        """Yuvarlak köşeli arka plan çiz."""
        from PyQt6.QtGui import QPainter, QPainterPath, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.fillPath(path, QBrush(QColor("#0A0A12")))
        painter.setPen(QColor(29, 185, 84, 90))
        painter.drawPath(path)
        painter.end()


# ─── JavaScript Dosyalarını Yükle ──────────────────────────────────
def load_js_file(filename: str) -> str:
    """js/ klasöründen JavaScript dosyasını okur."""
    filepath = os.path.join(config.JS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"JS dosyası bulunamadı: {filepath}")
        return ""


# ─── QWebChannel Python Köprüsü ───────────────────────────────────
class WebBridge(QObject):
    """
    JavaScript → Python iletişim köprüsü.
    QWebChannel üzerinden DOM mesajlarını alır ve ilgili modüle yönlendirir.
    """

    def __init__(self, browser_window: "VisionaryBrowser"):
        super().__init__()
        self._browser = browser_window

    @pyqtSlot(str)
    def onDomMessage(self, message_json: str) -> None:
        """
        JavaScript'ten gelen DOM mesajını işler.
        Mesaj formatı: {"action": "try_on" | "review_data", "data": {...}}
        """
        try:
            msg = json.loads(message_json)
            action = msg.get("action", "")
            data = msg.get("data", {})

            logger.info(f"DOM mesajı alındı: action={action}")

            if action == "try_on":
                self._browser.handle_try_on(data)
            elif action == "review_data":
                self._browser.handle_review_data(data)
            elif action == "download_music":
                self._browser.handle_music_download(data)

        except json.JSONDecodeError as e:
            logger.error(f"DOM mesajı ayrıştırma hatası: {e}")


# ─── Özelleştirilmiş Web Sayfası ──────────────────────────────────
class BrowserPage(QWebEnginePage):
    """
    Özelleştirilmiş QWebEnginePage — JS enjeksiyonu ve WebChannel kurulumu.
    target=_blank linkleri yeni sekmede açar.
    Guardian güvenlik kontrolü entegrasyonu.
    """

    def __init__(self, profile: QWebEngineProfile, bridge: WebBridge, parent=None):
        super().__init__(profile, parent)
        self._bridge = bridge
        self._parent_view = parent  # QWebEngineView referansı
        self._setup_web_channel()
        self._inject_scripts()

    def _setup_web_channel(self) -> None:
        """QWebChannel kurulumu — Python-JS köprüsü."""
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self.setWebChannel(self._channel)
        
    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        """
        Navigasyon isteği öncesi Guardian güvenlik kontrolü.
        Tehlikeli siteler engellenir.
        """
        if not is_main_frame:
            return True  # Alt çerçeveleri atla
            
        # Ana pencereye referans al
        main_window = None
        if self._parent_view:
            main_window = self._parent_view.window()
            
        # Guardian kontrolü
        if main_window and hasattr(main_window, '_guardian'):
            guardian = main_window._guardian
            
            if guardian.is_enabled():
                url_str = url.toString()
                
                # Senkron kontrol (yerel kara liste + önbellek)
                is_safe, threat_type = guardian.check_url_sync(url_str)
                
                if not is_safe:
                    # URL engellendi — uyarı sayfası göster
                    logger.warning(f"Guardian engelledi (sync): {url_str}")
                    QTimer.singleShot(100, lambda: guardian.url_blocked.emit(url_str, threat_type))
                    return False
                    
                # Asenkron kontrol başlat (API taraması)
                if guardian.should_scan(url_str):
                    guardian.check_url_async(url_str)
                    
        return True  # Navigasyona izin ver

    def createWindow(self, window_type):
        """target=_blank ve window.open linklerini yeni sekmede açar."""
        if self._parent_view:
            main_window = self._parent_view.window()
            if hasattr(main_window, 'add_new_tab'):
                new_tab = main_window.add_new_tab()
                return new_tab.page()
        return super().createWindow(window_type)

    def _inject_scripts(self) -> None:
        """JavaScript dosyalarını sayfa yüklenmesinde otomatik enjekte eder."""
        scripts = self.scripts()

        # QWebChannel API'sini dosyadan yükle (dom_interceptor.js bunun üzerine çalışır)
        qwebchannel_api = load_js_file("qwebchannel.js")
        if qwebchannel_api:
            script0 = QWebEngineScript()
            script0.setName("QWebChannelAPI")
            script0.setSourceCode(qwebchannel_api)
            script0.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script0.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script0.setRunsOnSubFrames(False)
            scripts.insert(script0)

        # DOM Interceptor (ürün görseli algılama ve buton enjeksiyonu)
        interceptor_js = load_js_file("dom_interceptor.js")
        if interceptor_js:
            script1 = QWebEngineScript()
            script1.setName("VisionaryInterceptor")
            script1.setSourceCode(interceptor_js)
            script1.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script1.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script1.setRunsOnSubFrames(False)
            scripts.insert(script1)

        # Review Scraper (yorum kazıma)
        scraper_js = load_js_file("review_scraper.js")
        if scraper_js:
            script2 = QWebEngineScript()
            script2.setName("VisionaryScraper")
            script2.setSourceCode(scraper_js)
            script2.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script2.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script2.setRunsOnSubFrames(False)
            scripts.insert(script2)

        # YouTube Müzik İndirme Eklentisi
        yt_dl_js = load_js_file("youtube_downloader.js")
        if yt_dl_js:
            script3 = QWebEngineScript()
            script3.setName("VisionaryYTDownloader")
            script3.setSourceCode(yt_dl_js)
            script3.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script3.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script3.setRunsOnSubFrames(False)
            scripts.insert(script3)


# ─── Tarayıcı Sekmesi ─────────────────────────────────────────────
class BrowserTab(QWebEngineView):
    """
    Tek bir tarayıcı sekmesi — QWebEngineView tabanlı.
    """

    def __init__(self, bridge: WebBridge, parent=None, ad_blocker: AdBlockerInterceptor = None):
        super().__init__(parent)

        profile = QWebEngineProfile.defaultProfile()
        
        # Ad Blocker interceptor'ı profile'a ekle
        if ad_blocker:
            profile.setUrlRequestInterceptor(ad_blocker)
            
        self._page = BrowserPage(profile, bridge, self)
        self.setPage(self._page)

    def navigate_to(self, url: str) -> None:
        """Belirtilen URL'ye git. Protokol yoksa ekler."""
        if not url.startswith(("http://", "https://", "about:")):
            url = "https://" + url
        self.setUrl(QUrl(url))


# ─── Ana Tarayıcı Penceresi ───────────────────────────────────────
class VisionaryBrowser(QMainWindow):
    """
    Visionary Navigator — Ana uygulama penceresi.
    Sekmeli tarama, AI sidebar, AR modülü ve profesyonel koyu tema.
    """

    def __init__(self):
        super().__init__()

        # Kaynak yöneticisi
        self._resource_manager = SmartResourceManager()

        # Gizlilik Motoru (Ad Blocker + Tor)
        self._privacy_engine = PrivacyEngine(self)
        
        # Visionary Guardian (Güvenlik Taraması)
        self._guardian = VisionaryGuardian(self)
        self._guardian.url_blocked.connect(self._on_guardian_blocked)
        
        # Ghost Sandbox Manager (Hayalet Mod)
        self._ghost_manager = GhostManager(self)
        
        # Proxy Engine (Gelişmiş Proxy Yöneticisi)
        self._proxy_manager = ProxyManager(self)
        self._proxy_manager.proxy_connected.connect(self._on_proxy_connected)
        self._proxy_manager.proxy_disconnected.connect(self._on_proxy_disconnected)
        self._proxy_manager.proxy_failed.connect(self._on_proxy_error)
        self._proxy_manager.status_changed.connect(self._on_proxy_status_changed)
        
        # Visionary Meta-Search
        self._search_manager = VisionarySearchManager(self)

        # Python-JS köprüsü
        self._bridge = WebBridge(self)

        # UI bileşenleri
        self._ai_sidebar: Optional[AISidebar] = None
        self._ar_widget: Optional[ARWidget] = None
        self._finance_sidebar: Optional[FinanceSidebar] = None

        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._setup_shortcuts()
        self._setup_status_bar()

        # İlk sekmeyi aç
        self.add_new_tab(QUrl(config.DEFAULT_HOME_URL), "Ana Sayfa")

        # Bellek izleme zamanlayıcısı
        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._update_memory_display)
        self._memory_timer.start(5000)  # Her 5 saniyede güncelle

    def _setup_window(self) -> None:
        """Pencere özelliklerini ayarlar."""
        self.setWindowTitle(f"{config.APP_NAME} — {config.APP_DESCRIPTION}")
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.resize(1440, 900)

        # Pencereyi ekranın ortasına yerleştir
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - 1440) // 2
            y = (screen_geo.height() - 900) // 2
            self.move(x, y)

    def _setup_ui(self) -> None:
        """Tüm UI bileşenlerini oluşturur ve birleştirir."""
        # Ana merkez widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sol taraf: Araç çubuğu + Sekmeler ────────────────────
        browser_container = QWidget()
        browser_layout = QVBoxLayout(browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        # Navigasyon araç çubuğu
        self._toolbar = self._create_toolbar()
        browser_layout.addWidget(self._toolbar)

        # Sekme widget'ı
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.tabCloseRequested.connect(self.close_tab)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # Yeni sekme butonu — tab bar'ın üstünde, sekmelerin hemen sağında
        tab_bar = self._tab_widget.tabBar()
        self._new_tab_btn = QPushButton("+", tab_bar)
        self._new_tab_btn.setObjectName("newTabBtn")
        self._new_tab_btn.setFixedSize(28, 28)
        self._new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_tab_btn.setStyleSheet("""
            QPushButton {
                background: rgba(108, 99, 255, 0.12);
                color: #A79BFF;
                border: 1px solid rgba(108, 99, 255, 0.25);
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(108, 99, 255, 0.25);
                border-color: rgba(108, 99, 255, 0.5);
                color: #FFFFFF;
            }
        """)
        self._new_tab_btn.clicked.connect(lambda: self.add_new_tab())

        browser_layout.addWidget(self._tab_widget)

        # ── Ana Düzene Sadece Tarayıcıyı Ekle ─────────────────────
        main_layout.addWidget(browser_container, 1)

        # ── Sağ üst: AI Sidebar (Yüzen Ada) ───────────────────────
        self._ai_sidebar = AISidebar(central_widget)
        self._ai_sidebar.setFixedHeight(600)
        self._ai_sidebar.analysis_requested.connect(self._run_review_scraper)
        self._ai_sidebar.chat_requested.connect(self._handle_chat_request)
        self._ai_sidebar.fullscreen_requested.connect(self._open_ai_fullscreen)
        self._ai_sidebar.hide()
        
        shadow_ai = QGraphicsDropShadowEffect()
        shadow_ai.setBlurRadius(50)
        shadow_ai.setColor(QColor(0, 0, 0, 180))
        shadow_ai.setOffset(0, 12)
        self._ai_sidebar.setGraphicsEffect(shadow_ai)

        # ── Alt sağ: AR Widget (Yüzen Ada) ────────────────────────
        self._ar_container = QWidget(central_widget)
        self._ar_container.hide()
        ar_layout = QVBoxLayout(self._ar_container)
        ar_layout.setContentsMargins(0, 0, 0, 0)
        
        self._ar_widget = ARWidget(self._ar_container)
        self._ar_widget.ar_closed.connect(self._on_ar_closed)
        self._ar_widget.hide()
        ar_layout.addWidget(self._ar_widget)

        shadow_ar = QGraphicsDropShadowEffect()
        shadow_ar.setBlurRadius(50)
        shadow_ar.setColor(QColor(0, 0, 0, 180))
        shadow_ar.setOffset(0, 12)
        self._ar_container.setGraphicsEffect(shadow_ar)

        # ── Sol üst: Finans Sidebar (Yüzen Ada) ───────────────────
        self._finance_sidebar = FinanceSidebar(central_widget)
        self._finance_sidebar.setFixedHeight(700)
        self._finance_sidebar.analysis_requested.connect(self._on_finance_scan_requested)
        self._finance_sidebar.close_requested.connect(self._on_finance_closed)
        self._finance_sidebar.fullscreen_requested.connect(self._open_finance_fullscreen)
        self._finance_sidebar.hide()

        shadow_finance = QGraphicsDropShadowEffect()
        shadow_finance.setBlurRadius(50)
        shadow_finance.setColor(QColor(0, 255, 136, 80))
        shadow_finance.setOffset(0, 12)
        self._finance_sidebar.setGraphicsEffect(shadow_finance)

        # ── Sol alt: Müzik FAB (Yüzen Kontrol) ───────────────────
        self._music_fab = QPushButton("🎵", central_widget)
        self._music_fab.setFixedSize(52, 52)
        self._music_fab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._music_fab.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6C63FF, stop:1 #4B4BFF);
                border: none; border-radius: 26px;
                font-size: 22px; color: #FFFFFF;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7F77FF, stop:1 #5C5CFF);
            }
        """)
        shadow_fab = QGraphicsDropShadowEffect()
        shadow_fab.setBlurRadius(30)
        shadow_fab.setColor(QColor(108, 99, 255, 120))
        shadow_fab.setOffset(0, 6)
        self._music_fab.setGraphicsEffect(shadow_fab)
        self._music_fab.clicked.connect(self._toggle_music_panel)
        self._music_fab.raise_()

        # ── Gesture / Kamera Widget (sol alt — FAB'ın üstü) ──────
        self._gesture_widget = GestureWidget(central_widget)
        self._gesture_widget.gesture_closed.connect(self._on_gesture_closed)
        self._gesture_widget.hide()

        shadow_gesture = QGraphicsDropShadowEffect()
        shadow_gesture.setBlurRadius(40)
        shadow_gesture.setColor(QColor(0, 217, 255, 100))
        shadow_gesture.setOffset(0, 8)
        self._gesture_widget.setGraphicsEffect(shadow_gesture)

        # Müzik Panel (FAB'a tıklayınca açılır)
        self._music_panel = QFrame(central_widget)
        self._music_panel.setFixedSize(400, 680)
        self._music_panel.hide()
        self._music_panel.setStyleSheet("""
            QFrame#musicPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #121212, stop:0.5 #0e0e0e, stop:1 #0a0a0a);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
            }
        """)
        self._music_panel.setObjectName("musicPanel")

        shadow_panel = QGraphicsDropShadowEffect()
        shadow_panel.setBlurRadius(50)
        shadow_panel.setColor(QColor(0, 0, 0, 200))
        shadow_panel.setOffset(0, 10)
        self._music_panel.setGraphicsEffect(shadow_panel)

        self._setup_music_panel()

        # ── Mini Player (Küçültülmüş müzik kontrolü) ─────────
        self._mini_player = QFrame(central_widget)
        self._mini_player.setFixedSize(280, 52)
        self._mini_player.setObjectName("miniPlayer")
        self._mini_player.hide()
        self._mini_player.setStyleSheet("""
            QFrame#miniPlayer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #14142A, stop:1 #1A1A30);
                border: 1px solid rgba(108,99,255,0.25);
                border-radius: 26px;
            }
        """)
        shadow_mini = QGraphicsDropShadowEffect()
        shadow_mini.setBlurRadius(30)
        shadow_mini.setColor(QColor(108, 99, 255, 100))
        shadow_mini.setOffset(0, 4)
        self._mini_player.setGraphicsEffect(shadow_mini)
        self._setup_mini_player()

        # ── YouTube Video Penceresi (Always-on-Top PiP) ─────────
        self._yt_video_frame = _DraggableVideoFrame(self)
        self._yt_video_frame.request_music_pause.connect(self._pip_music_pause)
        self._yt_video_frame.request_music_resume.connect(self._pip_music_resume)
        self._yt_video_frame.hide()

        self.setCentralWidget(central_widget)

    def _setup_music_panel(self) -> None:
        """Müzik kontrol panelini oluşturur — Spotify benzeri tasarım."""
        from voice_engine import MusicLibrary, MusicLibraryDownloader, YouTubeSearchWorker, YouTubeTrendWorker, YouTubeStreamResolver

        self._music_library = MusicLibrary()
        self._music_library.scan_music_dir()
        self._music_downloader: Optional[MusicLibraryDownloader] = None
        self._yt_search_worker: Optional[YouTubeSearchWorker] = None
        self._yt_trend_worker: Optional[YouTubeTrendWorker] = None
        self._yt_stream_resolver: Optional[YouTubeStreamResolver] = None
        self._trend_loaded: bool = False

        _GREEN = "#1DB954"
        _TEXT = "#FFFFFF"
        _TEXT2 = "#B3B3B3"
        _CARD = "rgba(255,255,255,0.05)"

        _SCROLL_STYLE = """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 4px; margin: 0; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15); border-radius: 2px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(29,185,84,0.5); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """
        _INPUT_STYLE = """
            QLineEdit {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 20px; color: #FFFFFF;
                font-size: 12px; padding: 7px 14px;
            }
            QLineEdit:focus {
                border-color: #1DB954;
                background: rgba(29,185,84,0.07);
            }
        """

        layout = QVBoxLayout(self._music_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Üst Bölüm: Album Art + Track Info ────────────────
        top_section = QFrame()
        top_section.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                    stop:0 rgba(18,18,18,0), stop:0.3 rgba(29,185,84,0.12),
                    stop:1 rgba(29,185,84,0.35));
                border-radius: 20px 20px 0 0;
            }
        """)
        top_lay = QVBoxLayout(top_section)
        top_lay.setContentsMargins(20, 14, 20, 12)
        top_lay.setSpacing(10)

        # Header: başlık + kapat
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        hdr_lbl = QLabel("♫  MÜZIK")
        hdr_lbl.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {_GREEN}; "
                               "letter-spacing: 3px; background: transparent;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: rgba(255,255,255,0.3); font-size: 12px; }
            QPushButton:hover { color: #FF5252; }
        """)
        close_btn.clicked.connect(lambda: self._music_panel.hide())
        header_row.addWidget(hdr_lbl)
        header_row.addStretch()
        header_row.addWidget(close_btn)
        top_lay.addLayout(header_row)

        # Album Art placeholder
        art_outer = QHBoxLayout()
        art_outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._album_art_frame = QFrame()
        self._album_art_frame.setFixedSize(110, 110)
        self._album_art_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a28, stop:0.6 #0d1f14, stop:1 #1DB954);
                border-radius: 10px;
            }
        """)
        art_inner = QVBoxLayout(self._album_art_frame)
        art_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._album_art_lbl = QLabel("🎵")
        self._album_art_lbl.setStyleSheet("font-size: 40px; background: transparent;")
        self._album_art_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art_inner.addWidget(self._album_art_lbl)
        art_outer.addWidget(self._album_art_frame)
        top_lay.addLayout(art_outer)

        # Şarkı adı + YT butonu
        track_row = QHBoxLayout()
        track_row.setSpacing(8)
        track_col = QVBoxLayout()
        track_col.setSpacing(2)
        self._now_playing_lbl = QLabel("Şarkı seç")
        self._now_playing_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        self._now_playing_lbl.setMaximumWidth(250)
        self._now_source_lbl = QLabel("— Çalmıyor —")
        self._now_source_lbl.setStyleSheet(f"font-size: 11px; color: {_TEXT2}; background: transparent;")
        track_col.addWidget(self._now_playing_lbl)
        track_col.addWidget(self._now_source_lbl)
        track_row.addLayout(track_col, 1)

        # YouTube'da İzle butonu (URL olan şarkılarda görünür)
        self._yt_watch_btn = QPushButton("▶ YouTube")
        self._yt_watch_btn.setFixedSize(78, 26)
        self._yt_watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yt_watch_btn.setToolTip("Şu anki konumdan YouTube'da izle")
        self._yt_watch_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,30,30,0.15); border: 1px solid rgba(255,60,60,0.3);
                border-radius: 13px; font-size: 10px; font-weight: 700; color: #FF6060;
            }
            QPushButton:hover { background: rgba(255,30,30,0.3); color: #FF9090; }
        """)
        self._yt_watch_btn.clicked.connect(self._open_youtube_at_position)
        self._yt_watch_btn.hide()
        track_row.addWidget(self._yt_watch_btn)
        top_lay.addLayout(track_row)
        layout.addWidget(top_section)

        # ── Oynatma Kontrolleri ──────────────────────────────────────────
        ctrl_section = QFrame()
        ctrl_section.setStyleSheet("QFrame { background: transparent; }")
        ctrl_lay = QVBoxLayout(ctrl_section)
        ctrl_lay.setContentsMargins(20, 10, 20, 8)
        ctrl_lay.setSpacing(6)

        _SLIDER_STYLE = f"""
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.15); height: 4px;
                border-radius: 2px; border: none;
            }}
            QSlider::handle:horizontal {{
                background: {_TEXT}; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px; border: none;
            }}
            QSlider::handle:horizontal:hover {{ background: {_GREEN}; }}
            QSlider::sub-page:horizontal {{
                background: {_GREEN}; border-radius: 2px;
            }}
        """
        _TIME_STYLE = f"font-size: 10px; color: {_TEXT2}; background: transparent;"

        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setStyleSheet(_SLIDER_STYLE)
        self._progress_slider.setFixedHeight(16)
        self._progress_slider.sliderPressed.connect(self._on_progress_pressed)
        self._progress_slider.sliderReleased.connect(self._on_progress_released)
        self._seeking_by_user = False
        ctrl_lay.addWidget(self._progress_slider)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        self._time_current_lbl = QLabel("0:00")
        self._time_current_lbl.setStyleSheet(_TIME_STYLE)
        self._time_total_lbl = QLabel("0:00")
        self._time_total_lbl.setStyleSheet(_TIME_STYLE)
        self._time_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_row.addWidget(self._time_current_lbl)
        time_row.addStretch()
        time_row.addWidget(self._time_total_lbl)
        ctrl_lay.addLayout(time_row)

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(500)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start()

        # Kontrol butonları
        btn_row = QHBoxLayout()
        btn_row.setSpacing(0)

        _ghost_sm = f"""
            QPushButton {{ background: transparent; border: none; font-size: 14px;
                color: rgba(255,255,255,0.4); border-radius: 14px; padding: 2px; }}
            QPushButton:hover {{ color: {_TEXT}; }}
        """
        _ghost_active = f"""
            QPushButton {{ background: transparent; border: none; font-size: 14px;
                color: {_GREEN}; border-radius: 14px; padding: 2px; }}
            QPushButton:hover {{ color: #1ed760; }}
        """
        _ghost_lg = f"""
            QPushButton {{ background: transparent; border: none; font-size: 20px;
                color: rgba(255,255,255,0.75); border-radius: 20px; padding: 2px; }}
            QPushButton:hover {{ color: {_TEXT}; }}
        """

        self._shuffle_btn = QPushButton("🔀")
        self._shuffle_btn.setFixedSize(36, 36)
        self._shuffle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shuffle_btn.setToolTip("Karıştır")
        self._shuffle_btn.setStyleSheet(_ghost_sm)
        self._shuffle_btn.clicked.connect(self._toggle_shuffle)
        self._shuffle_mode = False

        prev_ctrl_btn = QPushButton("⏮")
        prev_ctrl_btn.setFixedSize(42, 42)
        prev_ctrl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_ctrl_btn.setStyleSheet(_ghost_lg)
        prev_ctrl_btn.clicked.connect(self._on_prev_track)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(56, 56)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_TEXT}; border: none; border-radius: 28px;
                font-size: 18px; color: #000000;
            }}
            QPushButton:hover {{ background: #E0E0E0; transform: scale(1.05); }}
            QPushButton:pressed {{ background: #C0C0C0; }}
        """)
        self._play_btn.clicked.connect(self._toggle_music_playback)

        next_ctrl_btn = QPushButton("⏭")
        next_ctrl_btn.setFixedSize(42, 42)
        next_ctrl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_ctrl_btn.setStyleSheet(_ghost_lg)
        next_ctrl_btn.clicked.connect(self._on_next_track)

        self._repeat_btn = QPushButton("🔁")
        self._repeat_btn.setFixedSize(36, 36)
        self._repeat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._repeat_btn.setToolTip("Tekrar: Kapalı")
        self._repeat_btn.setStyleSheet(_ghost_sm)
        self._repeat_btn.clicked.connect(self._toggle_repeat)
        self._repeat_mode = 0

        btn_row.addStretch()
        btn_row.addWidget(self._shuffle_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(prev_ctrl_btn)
        btn_row.addSpacing(2)
        btn_row.addWidget(self._play_btn)
        btn_row.addSpacing(2)
        btn_row.addWidget(next_ctrl_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(self._repeat_btn)
        btn_row.addStretch()
        ctrl_lay.addLayout(btn_row)

        # Ses seviyesi
        vol_row = QHBoxLayout()
        vol_row.setSpacing(8)
        vol_lo = QLabel("🔈")
        vol_lo.setStyleSheet(f"font-size: 11px; color: {_TEXT2}; background: transparent;")
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(25)
        self._vol_slider.setStyleSheet(_SLIDER_STYLE)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_hi = QLabel("🔊")
        vol_hi.setStyleSheet(f"font-size: 11px; color: {_TEXT2}; background: transparent;")
        vol_row.addWidget(vol_lo)
        vol_row.addWidget(self._vol_slider, 1)
        vol_row.addWidget(vol_hi)
        ctrl_lay.addLayout(vol_row)
        layout.addWidget(ctrl_section)

        # ── Ayırıcı ──────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; background: rgba(255,255,255,0.07); max-height: 1px;")
        layout.addWidget(sep)

        # ── Sekme Butonları ──────────────────────────────────
        tab_bar = QFrame()
        tab_bar.setStyleSheet("QFrame { background: transparent; }")
        tab_bar.setFixedHeight(44)
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(16, 6, 16, 6)
        tab_lay.setSpacing(4)

        self._tab_btn_style_active = f"""
            QPushButton {{
                background: rgba(255,255,255,0.12); border: none;
                border-radius: 15px; color: {_TEXT};
                font-size: 11px; font-weight: 700; padding: 4px 6px;
            }}
        """
        self._tab_btn_style_inactive = """
            QPushButton {
                background: transparent; border: none;
                border-radius: 15px; color: rgba(255,255,255,0.4);
                font-size: 11px; font-weight: 600; padding: 4px 6px;
            }
            QPushButton:hover { color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.05); }
        """

        self._yt_tab_btn = QPushButton("⚡ Keşfet")
        self._yt_tab_btn.setFixedHeight(30)
        self._yt_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yt_tab_btn.setCheckable(True)
        self._yt_tab_btn.setChecked(True)
        self._yt_tab_btn.clicked.connect(lambda: self._switch_music_tab("youtube"))
        self._yt_tab_btn.setStyleSheet(self._tab_btn_style_active)

        self._lib_tab_btn = QPushButton("📂 Kütüphane")
        self._lib_tab_btn.setFixedHeight(30)
        self._lib_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lib_tab_btn.setCheckable(True)
        self._lib_tab_btn.clicked.connect(lambda: self._switch_music_tab("library"))
        self._lib_tab_btn.setStyleSheet(self._tab_btn_style_inactive)

        self._pl_tab_btn = QPushButton("📋 Listeler")
        self._pl_tab_btn.setFixedHeight(30)
        self._pl_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pl_tab_btn.setCheckable(True)
        self._pl_tab_btn.clicked.connect(lambda: self._switch_music_tab("playlist"))
        self._pl_tab_btn.setStyleSheet(self._tab_btn_style_inactive)

        tab_lay.addWidget(self._yt_tab_btn, 1)
        tab_lay.addWidget(self._lib_tab_btn, 1)
        tab_lay.addWidget(self._pl_tab_btn, 1)
        layout.addWidget(tab_bar)

        # ── YouTube / Keşfet Sayfası ─────────────────────────
        self._yt_page = QWidget()
        self._yt_page.setStyleSheet("background: transparent;")
        yt_lay = QVBoxLayout(self._yt_page)
        yt_lay.setContentsMargins(12, 0, 12, 8)
        yt_lay.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._yt_search_input = QLineEdit()
        self._yt_search_input.setPlaceholderText("🔍  Şarkı veya sanatçı ara...")
        self._yt_search_input.setStyleSheet(_INPUT_STYLE)
        self._yt_search_input.setFixedHeight(36)
        self._yt_search_input.returnPressed.connect(self._do_youtube_search)

        search_btn = QPushButton("Ara")
        search_btn.setFixedSize(52, 36)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,60,60,0.18); border: 1px solid rgba(255,60,60,0.3);
                border-radius: 18px; font-size: 11px; font-weight: 700; color: #FF6666;
            }
            QPushButton:hover { background: rgba(255,60,60,0.32); color: #FF9999; }
        """)
        search_btn.clicked.connect(self._do_youtube_search)
        search_row.addWidget(self._yt_search_input, 1)
        search_row.addWidget(search_btn)
        yt_lay.addLayout(search_row)

        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self._yt_input = QLineEdit()
        self._yt_input.setPlaceholderText("↓  YouTube URL yapıştır → indir")
        self._yt_input.setStyleSheet(_INPUT_STYLE)
        self._yt_input.setFixedHeight(32)
        self._yt_input.returnPressed.connect(self._download_from_youtube)
        dl_btn = QPushButton("⬇")
        dl_btn.setFixedSize(40, 32)
        dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dl_btn.setStyleSheet("""
            QPushButton {
                background: rgba(29,185,84,0.15); border: 1px solid rgba(29,185,84,0.3);
                border-radius: 16px; font-size: 14px; color: #1DB954;
            }
            QPushButton:hover { background: rgba(29,185,84,0.3); color: #1ed760; }
        """)
        dl_btn.clicked.connect(self._download_from_youtube)
        url_row.addWidget(self._yt_input, 1)
        url_row.addWidget(dl_btn)
        yt_lay.addLayout(url_row)

        self._yt_search_status = QLabel("")
        self._yt_search_status.setStyleSheet(
            "color: rgba(29,185,84,0.8); font-size: 10px; padding: 0 2px; background: transparent;"
        )
        self._yt_search_status.setFixedHeight(14)
        yt_lay.addWidget(self._yt_search_status)

        yt_scroll = QScrollArea()
        yt_scroll.setWidgetResizable(True)
        yt_scroll.setStyleSheet(_SCROLL_STYLE)
        self._yt_results_container = QWidget()
        self._yt_results_container.setStyleSheet("background: transparent;")
        self._yt_results_layout = QVBoxLayout(self._yt_results_container)
        self._yt_results_layout.setContentsMargins(0, 0, 0, 0)
        self._yt_results_layout.setSpacing(3)
        self._yt_results_layout.addStretch()
        yt_scroll.setWidget(self._yt_results_container)
        yt_lay.addWidget(yt_scroll, 1)
        layout.addWidget(self._yt_page, 1)

        # ── Kütüphane Sayfası ────────────────────────────────
        self._lib_page = QWidget()
        self._lib_page.setStyleSheet("background: transparent;")
        lib_lay = QVBoxLayout(self._lib_page)
        lib_lay.setContentsMargins(12, 0, 12, 8)
        lib_lay.setSpacing(4)

        self._dl_status = QLabel("")
        self._dl_status.setStyleSheet(
            "color: rgba(29,185,84,0.8); font-size: 10px; padding: 0 2px; background: transparent;"
        )
        self._dl_status.setFixedHeight(14)
        lib_lay.addWidget(self._dl_status)

        lib_scroll = QScrollArea()
        lib_scroll.setWidgetResizable(True)
        lib_scroll.setStyleSheet(_SCROLL_STYLE)
        self._lib_container = QWidget()
        self._lib_container.setStyleSheet("background: transparent;")
        self._lib_layout = QVBoxLayout(self._lib_container)
        self._lib_layout.setContentsMargins(0, 0, 0, 0)
        self._lib_layout.setSpacing(2)
        self._lib_layout.addStretch()
        lib_scroll.setWidget(self._lib_container)
        lib_lay.addWidget(lib_scroll, 1)
        layout.addWidget(self._lib_page, 1)
        self._lib_page.hide()

        # ── Playlist Sayfası ─────────────────────────────────
        self._pl_page = QWidget()
        self._pl_page.setStyleSheet("background: transparent;")
        pl_lay = QVBoxLayout(self._pl_page)
        pl_lay.setContentsMargins(12, 0, 12, 8)
        pl_lay.setSpacing(6)

        new_pl_row = QHBoxLayout()
        new_pl_row.setSpacing(6)
        self._pl_name_input = QLineEdit()
        self._pl_name_input.setPlaceholderText("✨  Yeni liste adı, Enter...")
        self._pl_name_input.setStyleSheet(_INPUT_STYLE)
        self._pl_name_input.setFixedHeight(34)
        self._pl_name_input.returnPressed.connect(self._create_playlist)
        new_pl_btn = QPushButton("+")
        new_pl_btn.setFixedSize(34, 34)
        new_pl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_pl_btn.setStyleSheet("""
            QPushButton {
                background: rgba(29,185,84,0.2); border: 1px solid rgba(29,185,84,0.4);
                border-radius: 17px; font-size: 18px; color: #1DB954;
            }
            QPushButton:hover { background: rgba(29,185,84,0.4); color: #FFFFFF; }
        """)
        new_pl_btn.clicked.connect(self._create_playlist)
        new_pl_row.addWidget(self._pl_name_input, 1)
        new_pl_row.addWidget(new_pl_btn)
        pl_lay.addLayout(new_pl_row)

        pl_scroll = QScrollArea()
        pl_scroll.setWidgetResizable(True)
        pl_scroll.setStyleSheet(_SCROLL_STYLE)
        self._pl_container = QWidget()
        self._pl_container.setStyleSheet("background: transparent;")
        self._pl_layout = QVBoxLayout(self._pl_container)
        self._pl_layout.setContentsMargins(0, 0, 0, 0)
        self._pl_layout.setSpacing(6)
        self._pl_layout.addStretch()
        pl_scroll.setWidget(self._pl_container)
        pl_lay.addWidget(pl_scroll, 1)
        layout.addWidget(self._pl_page, 1)
        self._pl_page.hide()

        self._refresh_library_ui()

    # ── Müzik Panel Sekmeler ──────────────────────────────────

    def _setup_mini_player(self) -> None:
        """Mini player widget'ı — küçültülmüş durumda play/pause + şarkı adı."""
        layout = QHBoxLayout(self._mini_player)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Müzik ikonu — tıklanınca paneli aç
        expand_btn = QPushButton("🎵")
        expand_btn.setFixedSize(36, 36)
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet("""
            QPushButton {
                background: rgba(108,99,255,0.15); border: none;
                border-radius: 18px; font-size: 16px;
            }
            QPushButton:hover { background: rgba(108,99,255,0.3); }
        """)
        expand_btn.clicked.connect(self._expand_music_panel)

        # Şarkı adı
        self._mini_track_label = QLabel("♪ Müzik")
        self._mini_track_label.setStyleSheet("""
            color: #E0E0E8; font-size: 11px; font-weight: 500;
        """)
        self._mini_track_label.setFixedWidth(120)

        # Önceki buton
        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                font-size: 13px; color: #8E8EA0;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        prev_btn.clicked.connect(self._on_prev_track)

        # Play/Pause
        self._mini_play_btn = QPushButton("⏸")
        self._mini_play_btn.setFixedSize(32, 32)
        self._mini_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mini_play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #4B4BFF);
                border: none; border-radius: 16px;
                font-size: 13px; color: #FFFFFF;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #7F77FF, stop:1 #5C5CFF);
            }
        """)
        self._mini_play_btn.clicked.connect(self._toggle_music_playback)

        # Sonraki buton
        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(28, 28)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                font-size: 13px; color: #8E8EA0;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        next_btn.clicked.connect(self._on_next_track)

        layout.addWidget(expand_btn)
        layout.addWidget(self._mini_track_label, 1)
        layout.addWidget(prev_btn)
        layout.addWidget(self._mini_play_btn)
        layout.addWidget(next_btn)

    def _on_prev_track(self) -> None:
        """Önceki şarkıya geç."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome.play_prev_track()
            self._play_btn.setText("⏸")
            self._mini_play_btn.setText("⏸")

    def _on_next_track(self) -> None:
        """Sonraki şarkıya geç."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome.play_next_track()
            self._play_btn.setText("⏸")
            self._mini_play_btn.setText("⏸")

    def _on_track_changed(self, title: str, url: str, index: int) -> None:
        """Şarkı değiştiğinde UI güncellemesi."""
        display = title[:20] + "…" if len(title) > 20 else title
        self._mini_track_label.setText(f"♪ {display}")
        self._play_btn.setText("⏸")
        if hasattr(self, '_mini_play_btn'):
            self._mini_play_btn.setText("⏸")
        if hasattr(self, '_now_playing_lbl'):
            panel_display = title[:28] + "…" if len(title) > 28 else title
            self._now_playing_lbl.setText(panel_display)
        if hasattr(self, '_now_source_lbl'):
            source = "YouTube" if url else "Kütüphane"
            self._now_source_lbl.setText(f"♪  {source}")
        # YouTube'da İzle butonu — URL olan şarkılarda göster
        if hasattr(self, '_yt_watch_btn'):
            if url:
                self._yt_watch_btn.show()
            else:
                self._yt_watch_btn.hide()
        # Kütüphane listesini güncelle (çalan şarkıyı vurgula) — deferred
        QTimer.singleShot(50, self._refresh_library_ui)
        # YouTube video penceresi — URL varsa göster
        if url and hasattr(self, '_yt_video_frame'):
            try:
                self._yt_video_frame.load_video(url, title)
                # Top-level pencere: ekranın sağ alt köşesine konumlandır
                screen = QApplication.primaryScreen()
                if screen:
                    sg = screen.availableGeometry()
                    x = sg.right() - self._yt_video_frame.width() - 20
                    y = sg.bottom() - self._yt_video_frame.height() - 20
                    self._yt_video_frame.move(x, y)
            except Exception as e:
                logger.warning(f"YouTube video yükleme hatası: {e}")
        elif hasattr(self, '_yt_video_frame'):
            self._yt_video_frame.hide()

    def _open_youtube_at_position(self) -> None:
        """Şu an çalan şarkının YouTube URL'sini mevcut konumdan tarayıcıda aç."""
        welcome = getattr(self, '_welcome', None)
        if not welcome:
            return
        url = welcome.current_track_url
        if not url:
            return
        # Mevcut konumu saniyeye çevir
        pos_sec = max(0, welcome._music_player.position() // 1000)
        # Video ID çıkar
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        video_id = qs.get('v', [''])[0]
        if not video_id:
            # youtu.be/ID formatı
            video_id = parsed.path.lstrip('/')
        if not video_id:
            # Direkt URL'yi kullan
            yt_url = url
        else:
            yt_url = f"https://www.youtube.com/watch?v={video_id}&t={pos_sec}"
        tab = self._current_tab()
        if tab:
            tab.navigate_to(yt_url)
        self._music_panel.hide()

    # ─── Video ↔ Müzik Ses Senkronizasyonu ──────────────────────────────

    def _on_video_playing(self, title: str = "") -> None:
        """Video oynatılmaya başlandı — müzik zaten çalıyor, ses müzikten geliyor."""
        logger.debug(f"Video başladı (sessiz, ses müzikten): {title}")

    def _on_video_stopped(self) -> None:
        """Video durdu / kapatıldı."""
        logger.debug("Video durduruldu")

    def _pip_music_pause(self) -> None:
        """PiP'te video sesi açıldı — müziği duraklat."""
        welcome = getattr(self, '_welcome', None)
        if welcome and welcome.is_playing:
            welcome.pause_music()
            self._play_btn.setText("▶")
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText("▶")

    def _pip_music_resume(self) -> None:
        """PiP'te video sesi kapatıldı — müziği devam ettir."""
        welcome = getattr(self, '_welcome', None)
        if welcome and not welcome.is_playing:
            welcome.resume_music()
            self._play_btn.setText("⏸")
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText("⏸")

    def _auto_minimize_music(self) -> None:
        """Müzik paneli açıksa otomatik küçült — müzik çalıyorsa mini player göster."""
        if not getattr(self, '_music_panel', None):
            return
        if self._music_panel.isVisible():
            welcome = getattr(self, '_welcome', None)
            if welcome and welcome.is_playing:
                self._minimize_music_panel()
            else:
                self._music_panel.hide()

    def _minimize_music_panel(self) -> None:
        """Müzik panelini gizle ve mini player'ı göster."""
        if self._music_panel.isVisible():
            self._music_panel.hide()
        # Mini player pozisyonunu güncelle, sonra göster
        QTimer.singleShot(50, lambda: (
            self._update_mini_player_position(),
            self._mini_player.raise_(),
            self._mini_player.show(),
            self._music_fab.hide()
        ))

    def _expand_music_panel(self) -> None:
        """Mini player'ı gizle ve müzik panelini aç."""
        self._mini_player.hide()
        self._music_fab.show()
        self._update_music_fab_position()
        self._music_panel.raise_()
        self._music_panel.show()

    def _update_mini_player_position(self) -> None:
        """Mini player'ın konumunu güncelle — sol alt köşe."""
        sb_h = self.statusBar().height() if self.statusBar() else 0
        x = 20
        y = self.centralWidget().height() - 52 - sb_h - 16
        self._mini_player.move(x, y)

    def _switch_music_tab(self, tab: str) -> None:
        """YouTube / Kütüphane / Playlist sekmesi geçişi."""
        for page in (self._yt_page, self._lib_page, self._pl_page):
            page.hide()
        for btn in (self._yt_tab_btn, self._lib_tab_btn, self._pl_tab_btn):
            btn.setChecked(False)
            btn.setStyleSheet(self._tab_btn_style_inactive)

        if tab == "youtube":
            self._yt_page.show()
            self._yt_tab_btn.setChecked(True)
            self._yt_tab_btn.setStyleSheet(self._tab_btn_style_active)
            # İlk açılışta trend müzikleri otomatik listele
            if not self._trend_loaded:
                self._load_trend_music()
        elif tab == "library":
            self._lib_page.show()
            self._lib_tab_btn.setChecked(True)
            self._lib_tab_btn.setStyleSheet(self._tab_btn_style_active)
            self._refresh_library_ui()
        else:  # playlist
            self._pl_page.show()
            self._pl_tab_btn.setChecked(True)
            self._pl_tab_btn.setStyleSheet(self._tab_btn_style_active)
            self._refresh_playlist_ui()

    def _load_trend_music(self) -> None:
        """YouTube trend müziklerini otomatik yükle — Keşfet sekmesi açılınca çağrılır."""
        from voice_engine import YouTubeTrendWorker
        if (hasattr(self, '_yt_trend_worker') and self._yt_trend_worker
                and self._yt_trend_worker.isRunning()):
            return
        self._yt_search_status.setText("🔥 Trend müzikler yükleniyor...")
        self._yt_trend_worker = YouTubeTrendWorker()
        self._yt_trend_worker.results_ready.connect(self._on_trend_results)
        self._yt_trend_worker.error.connect(
            lambda e: self._yt_search_status.setText(f"⚠ {e}")
        )
        self._yt_trend_worker.start()

    def _on_trend_results(self, results: list) -> None:
        """Trend sonuçları geldi — Keşfet listesini güncelle."""
        self._trend_loaded = True
        self._yt_search_status.setText(f"🔥 {len(results)} trend müzik")
        self._on_youtube_results(results)

    # ── YouTube Arama ─────────────────────────────────────────

    def _do_youtube_search(self) -> None:
        """YouTube'da şarkı ara — panel içinde sonuç göster."""
        from voice_engine import YouTubeSearchWorker
        query = self._yt_search_input.text().strip()
        if not query:
            return

        self._yt_search_status.setText("🔍 Aranıyor...")

        # Önceki sonuçları temizle
        while self._yt_results_layout.count() > 1:
            item = self._yt_results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._yt_search_worker = YouTubeSearchWorker(query, max_results=8)
        self._yt_search_worker.results_ready.connect(self._on_youtube_results)
        self._yt_search_worker.error.connect(
            lambda err: self._yt_search_status.setText(f"❌ {err}")
        )
        self._yt_search_worker.start()

    def _on_youtube_results(self, results: list) -> None:
        """YouTube arama sonuçlarını listele."""
        # Önceki sonuçları temizle
        while self._yt_results_layout.count() > 1:
            item = self._yt_results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not results:
            self._yt_search_status.setText("Sonuç bulunamadı")
            return

        self._yt_search_status.setText(f"✅ {len(results)} sonuç bulundu")

        for idx, r in enumerate(results):
            item = QFrame()
            item.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.04);
                    border-radius: 10px;
                }
                QFrame:hover {
                    background: rgba(220,50,50,0.07);
                    border-color: rgba(255,80,80,0.18);
                }
            """)
            item_lay = QHBoxLayout(item)
            item_lay.setContentsMargins(8, 7, 8, 7)
            item_lay.setSpacing(7)

            # Sol: YT ikonu küçük
            yt_icon = QLabel("▶")
            yt_icon.setFixedSize(22, 22)
            yt_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            yt_icon.setStyleSheet("""
                color: rgba(255,80,80,0.5);
                font-size: 9px;
                background: rgba(255,80,80,0.07);
                border-radius: 11px;
            """)

            # Bilgi
            info_lay = QVBoxLayout()
            info_lay.setSpacing(1)
            t_lbl = QLabel(r.get("title", "?")[:44])
            t_lbl.setStyleSheet("color: #D8D8E8; font-size: 11px; font-weight: 500; background: transparent;")
            t_lbl.setWordWrap(True)

            meta = f"{r.get('channel', '')[:22]}  •  {r.get('duration', '')}"
            m_lbl = QLabel(meta)
            m_lbl.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 10px; background: transparent;")

            info_lay.addWidget(t_lbl)
            info_lay.addWidget(m_lbl)

            btn_col = QVBoxLayout()
            btn_col.setSpacing(3)

            # Çal (streaming) butonu
            play_stream_btn = QPushButton("▶")
            play_stream_btn.setFixedSize(28, 28)
            play_stream_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_stream_btn.setToolTip("İndirmeden Dinle")
            play_stream_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,200,100,0.12);
                    border: 1px solid rgba(0,200,100,0.22);
                    border-radius: 8px; font-size: 10px; color: #44CC88;
                }
                QPushButton:hover {
                    background: rgba(0,200,100,0.28);
                    border-color: rgba(0,200,100,0.5);
                    color: #FFFFFF;
                }
            """)
            stream_url = r.get("url", "")
            stream_title = r.get("title", "")
            play_stream_btn.clicked.connect(
                lambda _, u=stream_url, ti=stream_title: self._play_youtube_stream(u, ti)
            )

            # İndir butonu
            dl_btn = QPushButton("⬇")
            dl_btn.setFixedSize(28, 28)
            dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dl_btn.setToolTip("Kütüphaneye İndir")
            dl_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(108,99,255,0.12);
                    border: 1px solid rgba(108,99,255,0.22);
                    border-radius: 8px; font-size: 12px; color: #9890FF;
                }
                QPushButton:hover {
                    background: rgba(108,99,255,0.28);
                    border-color: rgba(108,99,255,0.5);
                    color: #FFFFFF;
                }
            """)
            url = r.get("url", "")
            dl_btn.clicked.connect(lambda _, u=url: self._download_search_result(u))

            btn_col.addWidget(play_stream_btn)
            btn_col.addWidget(dl_btn)

            item_lay.addWidget(yt_icon)
            item_lay.addLayout(info_lay, 1)
            item_lay.addLayout(btn_col)
            self._yt_results_layout.insertWidget(idx, item)

    def _download_search_result(self, url: str) -> None:
        """Arama sonucundan şarkı indir — URL'yi de kaydet."""
        from voice_engine import MusicLibraryDownloader
        if not url:
            return

        # Kütüphane sekmesine geç ve durumu göster
        self._switch_music_tab("library")
        self._dl_status.setText("⏳ Hazırlanıyor...")

        self._pending_download_url = url  # URL'yi sakla, indirme bitince kütüphaneye eklenecek

        self._music_downloader = MusicLibraryDownloader(url)
        self._music_downloader.progress.connect(
            lambda msg: self._dl_status.setText(msg)
        )
        self._music_downloader.finished.connect(self._on_download_finished)
        self._music_downloader.error.connect(
            lambda err: self._dl_status.setText(f"❌ {err[:50]}")
        )
        self._music_downloader.start()

    def _refresh_library_ui(self) -> None:
        """Kütüphane listesini yenile."""
        while self._lib_layout.count() > 1:
            item = self._lib_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tracks = self._music_library.tracks
        if not tracks:
            empty = QLabel("📭  Henüz şarkı yok\n\nYouTube'dan indir veya URL yapıştır")
            empty.setStyleSheet("color: rgba(255,255,255,0.2); font-size: 11px; padding: 20px;"
                                "text-align: center; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lib_layout.insertWidget(0, empty)
            return

        # Şu an çalan şarkının index'ini bul
        current_idx = -1
        welcome = getattr(self, '_welcome', None)
        if welcome:
            current_idx = welcome.current_track_index

        for idx, track in enumerate(tracks):
            is_playing = (idx == current_idx)
            item = QFrame()
            item.setObjectName(f"lib_track_{idx}")
            item.setStyleSheet(f"""
                QFrame {{
                    background: {'rgba(29,185,84,0.12)' if is_playing else 'rgba(255,255,255,0.03)'};
                    border: 1px solid {'rgba(29,185,84,0.35)' if is_playing else 'rgba(255,255,255,0.04)'};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    background: {'rgba(29,185,84,0.18)' if is_playing else 'rgba(255,255,255,0.07)'};
                }}
            """)
            item_lay = QHBoxLayout(item)
            item_lay.setContentsMargins(10, 7, 8, 7)
            item_lay.setSpacing(8)

            # Numara veya şu an çalıyor ikonu
            num_lbl = QLabel("♪" if is_playing else f"{idx+1}")
            num_lbl.setFixedWidth(18)
            num_lbl.setStyleSheet(f"color: {'#1DB954' if is_playing else 'rgba(255,255,255,0.2)'}; "
                                   "font-size: 11px; font-weight: 700; background: transparent;")
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Çal butonu
            play_btn = QPushButton("▶")
            play_btn.setFixedSize(28, 28)
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(29,185,84,0.25)' if is_playing else 'rgba(255,255,255,0.07)'};
                    border: none; border-radius: 14px;
                    font-size: 11px; color: {'#1DB954' if is_playing else '#B3B3B3'};
                }}
                QPushButton:hover {{ background: rgba(29,185,84,0.4); color: #FFFFFF; }}
            """)
            track_idx = idx
            play_btn.clicked.connect(lambda _, i=track_idx: self._play_library_track_by_index(i))

            title_lbl = QLabel(track.get("title", "Bilinmeyen")[:34])
            title_lbl.setStyleSheet(f"color: {'#FFFFFF' if is_playing else '#D8D8E8'}; "
                                     "font-size: 11px; font-weight: 500; background: transparent;")

            # Listeye ekle
            add_pl_btn = QPushButton("＋")
            add_pl_btn.setFixedSize(22, 22)
            add_pl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_pl_btn.setToolTip("Playlist'e ekle")
            add_pl_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; font-size: 13px; color: rgba(255,255,255,0.2); }
                QPushButton:hover { color: #1DB954; }
            """)
            add_pl_btn.clicked.connect(lambda _, i=track_idx, b=add_pl_btn: self._show_add_to_playlist_menu(i, b))

            # Sil
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; font-size: 9px; color: rgba(255,255,255,0.1); }
                QPushButton:hover { color: #FF5252; }
            """)
            del_btn.clicked.connect(lambda _, i=track_idx: self._delete_library_track(i))

            item_lay.addWidget(num_lbl)
            item_lay.addWidget(play_btn)
            item_lay.addWidget(title_lbl, 1)
            item_lay.addWidget(add_pl_btn)
            item_lay.addWidget(del_btn)
            self._lib_layout.insertWidget(idx, item)

    def _toggle_music_panel(self) -> None:
        """Müzik panelini aç/kapat."""
        if self._music_panel.isVisible():
            self._music_panel.hide()
            # Müzik çalıyorsa mini player göster
            welcome = getattr(self, '_welcome', None)
            if welcome and welcome.is_playing:
                self._minimize_music_panel()
        else:
            self._mini_player.hide()
            self._music_fab.show()
            self._update_music_fab_position()
            self._music_panel.raise_()
            self._music_panel.show()

    def _toggle_music_playback(self) -> None:
        """Aktif müzik ve videoyu eşzamanlı durdur/başlat."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            playing = welcome.toggle_music()
            icon = "⏸" if playing else "▶"
            self._play_btn.setText(icon)
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText(icon)
            # Video frame'i de senkronize et
            if hasattr(self, '_yt_video_frame') and self._yt_video_frame.isVisible():
                if playing:
                    self._yt_video_frame.resume_video()
                else:
                    self._yt_video_frame.pause_video()
        else:
            self._play_btn.setText("▶")
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText("▶")

    def _seek_forward(self) -> None:
        """Müziği 10 saniye ileri sar."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome.seek_forward(10)

    def _seek_backward(self) -> None:
        """Müziği 10 saniye geri sar."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome.seek_backward(10)

    @staticmethod
    def _format_ms(ms: int) -> str:
        """Milisaniyeyi m:ss formatına çevirir."""
        if ms <= 0:
            return "0:00"
        total_sec = ms // 1000
        m, s = divmod(total_sec, 60)
        return f"{m}:{s:02d}"

    def _update_progress(self) -> None:
        """Progress slider ve zaman etiketlerini güncelle."""
        welcome = getattr(self, '_welcome', None)
        if not welcome:
            return
        player = welcome._music_player
        pos = player.position()
        dur = player.duration()
        if not self._seeking_by_user and dur > 0:
            self._progress_slider.setValue(int(pos * 1000 / dur))
        self._time_current_lbl.setText(self._format_ms(pos))
        self._time_total_lbl.setText(self._format_ms(dur))

    def _on_progress_pressed(self) -> None:
        self._seeking_by_user = True

    def _on_progress_released(self) -> None:
        """Kullanıcı progress slider'ı bıraktığında seek yap."""
        self._seeking_by_user = False
        welcome = getattr(self, '_welcome', None)
        if not welcome:
            return
        dur = welcome._music_player.duration()
        if dur > 0:
            new_pos = int(self._progress_slider.value() * dur / 1000)
            welcome._music_player.setPosition(new_pos)

    def _toggle_shuffle(self) -> None:
        """Karıştır modunu aç/kapat."""
        self._shuffle_mode = not self._shuffle_mode
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome._shuffle_mode = self._shuffle_mode
        _on = """
            QPushButton {
                background: rgba(108,99,255,0.2); border: none;
                font-size: 13px; color: #A79BFF; border-radius: 12px;
            }
            QPushButton:hover { color: #C8C0FF; background: rgba(108,99,255,0.35); }
        """
        _off = """
            QPushButton {
                background: transparent; border: none;
                font-size: 13px; color: rgba(255,255,255,0.25); border-radius: 12px;
            }
            QPushButton:hover { color: rgba(255,255,255,0.7); background: rgba(255,255,255,0.05); }
        """
        self._shuffle_btn.setStyleSheet(_on if self._shuffle_mode else _off)
        self._shuffle_btn.setToolTip("Karıştır: Açık" if self._shuffle_mode else "Karıştır: Kapalı")

    def _toggle_repeat(self) -> None:
        """Tekrar modunu döngüle: kapalı → tümü → tek şarkı."""
        self._repeat_mode = (self._repeat_mode + 1) % 3
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome._repeat_mode = self._repeat_mode
        labels = {0: ("🔁", "Tekrar: Kapalı"), 1: ("🔁", "Tekrar: Tümü"), 2: ("🔂", "Tekrar: Tek Şarkı")}
        icon, tip = labels[self._repeat_mode]
        self._repeat_btn.setText(icon)
        self._repeat_btn.setToolTip(tip)
        _on = """
            QPushButton {
                background: rgba(108,99,255,0.2); border: none;
                font-size: 13px; color: #A79BFF; border-radius: 12px;
            }
            QPushButton:hover { color: #C8C0FF; background: rgba(108,99,255,0.35); }
        """
        _off = """
            QPushButton {
                background: transparent; border: none;
                font-size: 13px; color: rgba(255,255,255,0.25); border-radius: 12px;
            }
            QPushButton:hover { color: rgba(255,255,255,0.7); background: rgba(255,255,255,0.05); }
        """
        self._repeat_btn.setStyleSheet(_on if self._repeat_mode > 0 else _off)

    # ── Playlist yönetimi ────────────────────────────────────────

    def _create_playlist(self) -> None:
        """Yeni playlist oluştur."""
        name = self._pl_name_input.text().strip()
        if not name:
            return
        ok = self._music_library.create_playlist(name)
        self._pl_name_input.clear()
        if ok:
            self._refresh_playlist_ui()
        else:
            self._pl_name_input.setPlaceholderText("⚠️ Bu isim zaten var!")

    def _refresh_playlist_ui(self) -> None:
        """Playlist listesini yenile."""
        while self._pl_layout.count() > 1:
            item = self._pl_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        playlists = self._music_library.get_playlists()
        if not playlists:
            empty = QLabel("Henüz playlist yok")
            empty.setStyleSheet("color: #3A3A50; font-size: 12px; padding: 16px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pl_layout.insertWidget(0, empty)
            return

        for i, (pl_name, indices) in enumerate(playlists.items()):
            pl_frame = QFrame()
            pl_frame.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 10px;
                }
            """)
            pl_lay = QVBoxLayout(pl_frame)
            pl_lay.setContentsMargins(10, 8, 10, 8)
            pl_lay.setSpacing(4)

            # Playlist başlığı
            hdr = QHBoxLayout()
            name_lbl = QLabel(f"🎵 {pl_name}")
            name_lbl.setStyleSheet("color: #A79BFF; font-size: 12px; font-weight: 700;")
            cnt_lbl = QLabel(f"{len(indices)} şarkı")
            cnt_lbl.setStyleSheet("color: #565670; font-size: 10px;")

            # Playlist'i çal butonu
            play_pl_btn = QPushButton("▶ Çal")
            play_pl_btn.setFixedHeight(22)
            play_pl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_pl_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(108,99,255,0.2); border: 1px solid rgba(108,99,255,0.3);
                    border-radius: 6px; color: #A79BFF; font-size: 10px; font-weight: 600;
                    padding: 0 8px;
                }
                QPushButton:hover { background: rgba(108,99,255,0.35); color: #FFFFFF; }
            """)
            play_pl_btn.clicked.connect(lambda _, n=pl_name: self._play_playlist(n))

            # Sil butonu
            del_pl_btn = QPushButton("✕")
            del_pl_btn.setFixedSize(20, 20)
            del_pl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_pl_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; color: #3A3A50; font-size: 10px; }
                QPushButton:hover { color: #FF5252; }
            """)
            del_pl_btn.clicked.connect(lambda _, n=pl_name: self._delete_playlist(n))

            hdr.addWidget(name_lbl, 1)
            hdr.addWidget(cnt_lbl)
            hdr.addSpacing(4)
            hdr.addWidget(play_pl_btn)
            hdr.addWidget(del_pl_btn)
            pl_lay.addLayout(hdr)

            # Playlist içindeki şarkılar (max 3 göster)
            tracks = self._music_library.get_playlist_tracks(pl_name)
            for j, track in enumerate(tracks[:3]):
                t_row = QHBoxLayout()
                t_lbl = QLabel(f"  {j+1}. {track.get('title','?')[:28]}")
                t_lbl.setStyleSheet("color: #6B7B8A; font-size: 10px;")
                rm_btn = QPushButton("−")
                rm_btn.setFixedSize(16, 16)
                rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                rm_btn.setStyleSheet("""
                    QPushButton { background: transparent; border: none; color: #3A3A50; font-size: 11px; }
                    QPushButton:hover { color: #FF5252; }
                """)
                lib_idx = track.get("_lib_index", -1)
                rm_btn.clicked.connect(lambda _, n=pl_name, ti=lib_idx: self._remove_from_playlist(n, ti))
                t_row.addWidget(t_lbl, 1)
                t_row.addWidget(rm_btn)
                pl_lay.addLayout(t_row)

            if len(tracks) > 3:
                more = QLabel(f"  … +{len(tracks)-3} şarkı daha")
                more.setStyleSheet("color: #3A3A50; font-size: 10px; font-style: italic;")
                pl_lay.addWidget(more)

            self._pl_layout.insertWidget(i, pl_frame)

    def _play_playlist(self, playlist_name: str) -> None:
        """Playlist'i baştan çal."""
        tracks = self._music_library.get_playlist_tracks(playlist_name)
        if not tracks:
            return
        welcome = getattr(self, '_welcome', None)
        if welcome:
            first_idx = tracks[0].get("_lib_index", 0)
            welcome._play_track_at_index(first_idx)
            self._play_btn.setText("⏸")
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText("⏸")

    def _delete_playlist(self, name: str) -> None:
        self._music_library.delete_playlist(name)
        self._refresh_playlist_ui()

    def _remove_from_playlist(self, playlist_name: str, track_index: int) -> None:
        self._music_library.remove_from_playlist(playlist_name, track_index)
        self._refresh_playlist_ui()

    def _show_add_to_playlist_menu(self, track_index: int, btn: 'QPushButton') -> None:
        """Track için playlist seçim menüsü göster."""
        from PyQt6.QtWidgets import QMenu
        playlists = self._music_library.get_playlists()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #17172B;
                border: 1px solid rgba(108,99,255,0.25);
                border-radius: 10px;
                color: #D0D0E0;
                font-size: 12px;
                padding: 4px;
            }
            QMenu::item {
                padding: 7px 18px 7px 14px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: rgba(108,99,255,0.2);
                color: #C8C0FF;
            }
            QMenu::separator { height: 1px; background: rgba(255,255,255,0.06); margin: 3px 8px; }
        """)
        if not playlists:
            a = menu.addAction("Önce liste oluşturun →")
            a.setEnabled(False)
        else:
            for pl_name in playlists:
                # triggered lambda ile pl_name'i yakala — setData kullanmıyoruz
                action = menu.addAction(f"  {pl_name}")
                action.triggered.connect(
                    lambda checked=False, n=pl_name: self._add_track_to_playlist(track_index, n)
                )
        menu.addSeparator()
        new_action = menu.addAction("＋  Yeni liste oluştur")
        new_action.triggered.connect(lambda: self._switch_music_tab("playlist"))
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _add_track_to_playlist(self, track_index: int, playlist_name: str) -> None:
        """Track'i playlist'e ekle ve bildirim göster."""
        ok = self._music_library.add_to_playlist(playlist_name, track_index)
        if ok:
            self.statusBar().showMessage(f"✅ '{playlist_name}' listesine eklendi", 2500)
        else:
            self.statusBar().showMessage(f"ℹ️ Zaten '{playlist_name}' listesinde", 2000)

    def _on_volume_changed(self, value: int) -> None:
        """Ses seviyesini güncelle."""
        welcome = getattr(self, '_welcome', None)
        if welcome:
            welcome.set_volume(value / 100.0)

    def _download_from_youtube(self) -> None:
        """YouTube URL'den şarkı indir — URL'yi kütüphaneye kaydet."""
        from voice_engine import MusicLibraryDownloader
        url = self._yt_input.text().strip()
        if not url:
            return
        self._yt_input.clear()
        # Kütüphane sekmesine geç
        self._switch_music_tab("library")
        self._dl_status.setText("⏳ Hazırlanıyor...")

        self._pending_download_url = url  # URL'yi sakla

        self._music_downloader = MusicLibraryDownloader(url)
        self._music_downloader.progress.connect(
            lambda msg: self._dl_status.setText(msg)
        )
        self._music_downloader.finished.connect(self._on_download_finished)
        self._music_downloader.error.connect(
            lambda err: self._dl_status.setText(f"❌ {err[:50]}")
        )
        self._music_downloader.start()

    def _on_download_finished(self, title: str, path: str) -> None:
        """İndirme tamamlandı — kütüphaneye YouTube URL'siyle birlikte ekle."""
        url = getattr(self, '_pending_download_url', "")
        self._music_library.add_track(title, path, url)
        self._pending_download_url = ""
        self._dl_status.setText(f"✅ {title[:35]} eklendi!")
        self._refresh_library_ui()
        QTimer.singleShot(3000, lambda: self._dl_status.setText(""))

    def _open_youtube_music(self) -> None:
        """YouTube müzik panelinde arama input'una odaklan."""
        if not self._music_panel.isVisible():
            self._toggle_music_panel()
        self._switch_music_tab("youtube")
        self._yt_search_input.setFocus()

    def handle_music_download(self, data: dict) -> None:
        """
        YouTube sayfasındaki JS eklentisinden gelen müzik indirme isteği.
        JS -> WebBridge -> bu metot.
        """
        url = data.get("url", "")
        title = data.get("title", "Bilinmeyen")
        if not url:
            return

        logger.info(f"YouTube eklentisinden indirme isteği: {title[:40]}")
        self.statusBar().showMessage(f"⬇ İndiriliyor: {title[:40]}...", 5000)

        from voice_engine import MusicLibraryDownloader
        self._pending_download_url = url  # URL sakla
        self._music_downloader = MusicLibraryDownloader(url)
        self._music_downloader.progress.connect(
            lambda msg: self.statusBar().showMessage(f"🎧 {msg}", 3000)
        )
        self._music_downloader.finished.connect(
            lambda t, p: self._on_yt_plugin_download_done(t, p)
        )
        self._music_downloader.error.connect(
            lambda err: self.statusBar().showMessage(f"❌ İndirme hatası: {err[:50]}", 5000)
        )
        self._music_downloader.start()

    def _on_yt_plugin_download_done(self, title: str, path: str) -> None:
        """YouTube eklentisinden indirme tamamlandı."""
        url = getattr(self, '_pending_download_url', "")
        self._music_library.add_track(title, path, url)
        self._pending_download_url = ""
        self._refresh_library_ui()
        self.statusBar().showMessage(f"✅ {title[:40]} müzik kütüphanesine eklendi!", 5000)

    def _play_library_track(self, path: str) -> None:
        """Kütüphaneden bir şarkıyı çal — path'e göre."""
        if not getattr(self, '_welcome', None):
            from voice_engine import WelcomeGreeting
            self._welcome = WelcomeGreeting()
        welcome = self._welcome
        welcome.set_library(self._music_library)
        welcome.set_on_track_changed(self._on_track_changed)
        idx = self._music_library.find_index_by_path(path)
        if idx >= 0:
            self._play_library_track_by_index(idx)
        elif os.path.exists(path):
            welcome.play_library_track(path)
            self._play_btn.setText("⏸")
            if hasattr(self, '_mini_play_btn'):
                self._mini_play_btn.setText("⏸")

    def _play_library_track_by_index(self, index: int) -> None:
        """Kütüphaneden index'e göre şarkı çal."""
        # Debounce — hızlı art arda tıklamayı engelle
        now = getattr(self, '_last_play_time', 0)
        import time
        current = time.time()
        if current - now < 0.5:
            return
        self._last_play_time = current

        if not getattr(self, '_welcome', None):
            from voice_engine import WelcomeGreeting
            self._welcome = WelcomeGreeting()
        welcome = self._welcome
        if not welcome._music_library:
            welcome.set_library(self._music_library)
        welcome.set_on_track_changed(self._on_track_changed)
        welcome._play_track_at_index(index)
        self._play_btn.setText("⏸")
        if hasattr(self, '_mini_play_btn'):
            self._mini_play_btn.setText("⏸")
        if hasattr(self, '_mini_player') and not self._mini_player.isVisible():
            self._update_mini_player_position()
            self._mini_player.show()

    def _play_youtube_stream(self, yt_url: str, title: str = "") -> None:
        """YouTube URL'yi indirmeden stream olarak çal."""
        if not yt_url:
            return
        if not getattr(self, '_welcome', None):
            from voice_engine import WelcomeGreeting
            self._welcome = WelcomeGreeting()
        welcome = self._welcome
        welcome.set_on_track_changed(self._on_track_changed)

        # Status güncelle
        short = title[:30] + "…" if len(title) > 30 else title
        self._yt_search_status.setText(f"⏳ Çözümleniyor: {short}")

        from voice_engine import YouTubeStreamResolver
        if hasattr(self, '_yt_stream_resolver') and self._yt_stream_resolver:
            try:
                self._yt_stream_resolver.quit()
                self._yt_stream_resolver.wait(500)
            except Exception:
                pass

        self._yt_stream_resolver = YouTubeStreamResolver(yt_url, title)
        self._yt_stream_resolver.stream_ready.connect(
            lambda audio_url, t: (
                self._yt_search_status.setText(f"▶ {t[:35]}"),
                welcome.play_stream_url(audio_url, t),
                self._play_btn.setText("⏸"),
                self._mini_play_btn.setText("⏸") if hasattr(self, '_mini_play_btn') else None,
                self._mini_player.show() if hasattr(self, '_mini_player') else None,
            )
        )
        self._yt_stream_resolver.error.connect(
            lambda e: self._yt_search_status.setText(f"❌ {e}")
        )
        self._yt_stream_resolver.start()

    def _delete_library_track(self, index: int) -> None:
        """Kütüphaneden şarkı sil."""
        self._music_library.remove_track(index)
        self._refresh_library_ui()

    def _update_music_fab_position(self) -> None:
        """Müzik FAB ve panelin pozisyonunu güncelle."""
        sb_h = self.statusBar().height() if self.statusBar() else 0
        fab_x = 20
        fab_y = self.centralWidget().height() - 52 - sb_h - 16
        self._music_fab.move(fab_x, fab_y)
        # Panel, FAB'ın üstünde açılır
        panel_x = 20
        panel_y = fab_y - self._music_panel.height() - 8
        self._music_panel.move(panel_x, max(60, panel_y))

    def _update_new_tab_btn_pos(self) -> None:
        """+ butonunu tab bar'da son sekmenin hemen sağına konumlandır."""
        try:
            tab_bar = self._tab_widget.tabBar()
            count = tab_bar.count()
            if count == 0:
                self._new_tab_btn.move(4, 4)
                return
            last_rect = tab_bar.tabRect(count - 1)
            x = last_rect.right() + 6
            y = (tab_bar.height() - self._new_tab_btn.height()) // 2
            self._new_tab_btn.move(x, max(2, y))
            self._new_tab_btn.raise_()
        except Exception:
            pass

    def _create_toolbar(self) -> QToolBar:
        """Navigasyon araç çubuğunu oluşturur."""
        toolbar = QToolBar("Navigasyon")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setFixedHeight(config.TOOLBAR_HEIGHT)

        # Navigasyon butonları — Minimalist İkonlar
        icon_size = QSize(20, 20)

        back_btn = QPushButton()
        back_btn.setObjectName("toolbarBtn")
        back_btn.setIcon(QIcon(os.path.join(config.ICONS_DIR, "back.svg")))
        back_btn.setIconSize(icon_size)
        back_btn.setToolTip("Geri (Alt+Sol)")
        back_btn.setFixedSize(36, 32)
        back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(back_btn)

        forward_btn = QPushButton()
        forward_btn.setObjectName("toolbarBtn")
        forward_btn.setIcon(QIcon(os.path.join(config.ICONS_DIR, "forward.svg")))
        forward_btn.setIconSize(icon_size)
        forward_btn.setToolTip("İleri (Alt+Sağ)")
        forward_btn.setFixedSize(36, 32)
        forward_btn.clicked.connect(self._go_forward)
        toolbar.addWidget(forward_btn)

        reload_btn = QPushButton()
        reload_btn.setObjectName("toolbarBtn")
        reload_btn.setIcon(QIcon(os.path.join(config.ICONS_DIR, "refresh.svg")))
        reload_btn.setIconSize(icon_size)
        reload_btn.setToolTip("Yenile (F5)")
        reload_btn.setFixedSize(36, 32)
        reload_btn.clicked.connect(self._reload_page)
        toolbar.addWidget(reload_btn)

        home_btn = QPushButton()
        home_btn.setObjectName("toolbarBtn")
        home_btn.setIcon(QIcon(os.path.join(config.ICONS_DIR, "home.svg")))
        home_btn.setIconSize(icon_size)
        home_btn.setToolTip("Ana Sayfa")
        home_btn.setFixedSize(36, 32)
        home_btn.clicked.connect(self._go_home)
        toolbar.addWidget(home_btn)

        # Ayraç
        toolbar.addSeparator()

        # Adres çubuğu
        self._address_bar = QLineEdit()
        self._address_bar.setObjectName("addressBar")
        self._address_bar.setPlaceholderText("🔍 URL veya arama terimi girin...")
        self._address_bar.returnPressed.connect(self._navigate_to_url)
        self._address_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self._address_bar)

        # Ayraç
        toolbar.addSeparator()

        # ── "Özellikler" Açılır Menü ────────────────────────────
        from PyQt6.QtWidgets import QMenu
        features_btn = QPushButton("◆ Özellikler ▾")
        features_btn.setFixedSize(130, 32)
        features_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        features_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(108,99,255,0.18), stop:1 rgba(75,75,255,0.12));
                color: #A79BFF;
                border: 1px solid rgba(108, 99, 255, 0.3);
                border-radius: 8px;
                font-weight: 700; font-size: 12px;
                letter-spacing: 0.5px; padding: 0 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(108,99,255,0.3), stop:1 rgba(75,75,255,0.25));
                color: #FFFFFF;
                border-color: rgba(108, 99, 255, 0.6);
            }
            QPushButton::menu-indicator { image: none; width: 0; }
        """)

        features_menu = QMenu(features_btn)
        features_menu.setStyleSheet("""
            QMenu {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14142A, stop:1 #0E0E1A);
                border: 1px solid rgba(108,99,255,0.2);
                border-radius: 10px; padding: 6px 4px;
                color: #ECECF1; font-size: 13px;
            }
            QMenu::item {
                padding: 10px 20px 10px 16px;
                border-radius: 6px; margin: 2px 4px;
            }
            QMenu::item:selected {
                background: rgba(108,99,255,0.15);
                color: #FFFFFF;
            }
            QMenu::separator {
                height: 1px; margin: 4px 12px;
                background: rgba(255,255,255,0.06);
            }
        """)

        # AI
        features_menu.addAction("🧠  AI Sohbet", self._open_ai_fullscreen)
        features_menu.addAction("✨  Ürün Analizi", self._toggle_ai_sidebar)
        features_menu.addSeparator()

        # Finans
        features_menu.addAction("📈  Finans Paneli", self._toggle_finance_sidebar)
        features_menu.addAction("📊  Finans Terminali", self._open_finance_fullscreen)
        features_menu.addSeparator()

        # AR & Gesture
        features_menu.addAction("🥽  AR Sanal Deneme", self._toggle_ar_module)
        self._gesture_action = features_menu.addAction("✋  Jest Kontrolü", self._toggle_gesture)
        features_menu.addSeparator()

        # Müzik
        features_menu.addAction("🎵  Müzik Sayfası", self._open_music_fullscreen)
        features_menu.addSeparator()
        
        # Güvenlik & Gizlilik (kısayol ikonları toolbar'a taşındı)

        features_btn.setMenu(features_menu)
        toolbar.addWidget(features_btn)
        
        # Özellikler yanında hızlı erişim ikonları (sadece ikon + tooltip)
        toolbar.addSeparator()
        quick_btn_style = """
            QPushButton {
                background: transparent;
                color: #EDEDF2;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.10);
                border-color: rgba(255, 255, 255, 0.28);
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.16);
            }
            QPushButton:checked {
                background: rgba(108, 99, 255, 0.34);
                border-color: rgba(142, 132, 255, 0.78);
                color: #FFFFFF;
            }
        """
        
        self._guardian_btn = QPushButton("🛡️")
        self._guardian_btn.setFixedSize(34, 32)
        self._guardian_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._guardian_btn.setToolTip("Guardian: Aktif")
        self._guardian_btn.setCheckable(True)
        self._guardian_btn.setChecked(True)
        self._guardian_btn.setStyleSheet(quick_btn_style)
        self._guardian_btn.clicked.connect(self._toggle_guardian)
        toolbar.addWidget(self._guardian_btn)
        
        guardian_stats_btn = QPushButton("📊")
        guardian_stats_btn.setFixedSize(34, 32)
        guardian_stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        guardian_stats_btn.setToolTip("Guardian İstatistikleri")
        guardian_stats_btn.setStyleSheet(quick_btn_style)
        guardian_stats_btn.clicked.connect(self._show_guardian_stats)
        toolbar.addWidget(guardian_stats_btn)
        
        privacy_btn = QPushButton("🔒")
        privacy_btn.setFixedSize(34, 32)
        privacy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        privacy_btn.setToolTip("Gizlilik Kalkanı")
        privacy_btn.setStyleSheet(quick_btn_style)
        privacy_btn.clicked.connect(self._open_privacy_panel)
        toolbar.addWidget(privacy_btn)
        
        search_btn = QPushButton("🔍")
        search_btn.setFixedSize(34, 32)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setToolTip("Visionary Arama")
        search_btn.setStyleSheet(quick_btn_style)
        search_btn.clicked.connect(self._open_visionary_search)
        toolbar.addWidget(search_btn)
        
        self._tor_btn = QPushButton("🧅")
        self._tor_btn.setFixedSize(34, 32)
        self._tor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tor_btn.setToolTip("Tor Ağı: Kapalı")
        self._tor_btn.setCheckable(True)
        self._tor_btn.setChecked(False)
        self._tor_btn.setStyleSheet(quick_btn_style)
        self._tor_btn.clicked.connect(self._toggle_tor)
        toolbar.addWidget(self._tor_btn)
        
        # Ghost Mode butonu
        self._ghost_btn = QPushButton("👻")
        self._ghost_btn.setFixedSize(34, 32)
        self._ghost_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ghost_btn.setToolTip("Hayalet Mod: Pasif (yeni izole sekme aç)")
        self._ghost_btn.setCheckable(True)
        self._ghost_btn.setChecked(False)
        self._ghost_btn.setStyleSheet(
            quick_btn_style + """
            QPushButton:checked {
                background: rgba(230, 199, 194, 0.36);
                border-color: rgba(230, 199, 194, 0.90);
                color: #FFFFFF;
            }
            """
        )
        self._ghost_btn.clicked.connect(self._open_ghost_tab)
        toolbar.addWidget(self._ghost_btn)
        
        # Smart Proxy butonu (🌍 ülke seçimi)
        self._proxy_btn = QPushButton("🌍")
        self._proxy_btn.setFixedSize(34, 32)
        self._proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._proxy_btn.setToolTip("Akıllı Proxy: Kapalı (ülke seç)")
        self._proxy_btn.setCheckable(True)
        self._proxy_btn.setChecked(False)
        self._proxy_btn.setStyleSheet(
            quick_btn_style + """
            QPushButton:checked {
                background: rgba(34, 197, 94, 0.36);
                border-color: rgba(34, 197, 94, 0.90);
                color: #FFFFFF;
            }
            """
        )
        self._proxy_btn.clicked.connect(self._show_proxy_menu)
        toolbar.addWidget(self._proxy_btn)
        
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedSize(34, 32)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Ayarlar")
        settings_btn.setStyleSheet(quick_btn_style)
        settings_btn.clicked.connect(self._open_settings_tab)
        toolbar.addWidget(settings_btn)

        return toolbar

    def _apply_theme(self) -> None:
        """QSS tema dosyasını uygular."""
        theme_path = os.path.join(config.STYLES_DIR, "theme.qss")
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            logger.info("Tema başarıyla uygulandı.")
        except FileNotFoundError:
            logger.warning(f"Tema dosyası bulunamadı: {theme_path}")

    def _setup_shortcuts(self) -> None:
        """Klavye kısayollarını tanımlar."""
        # Ctrl+T: Yeni sekme
        new_tab_action = QAction("Yeni Sekme", self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.triggered.connect(lambda: self.add_new_tab())
        self.addAction(new_tab_action)

        # Ctrl+W: Sekmeyi kapat
        close_tab_action = QAction("Sekmeyi Kapat", self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(
            lambda: self.close_tab(self._tab_widget.currentIndex())
        )
        self.addAction(close_tab_action)

        # Ctrl+L: Adres çubuğuna odaklan
        focus_url_action = QAction("Adres Çubuğu", self)
        focus_url_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_url_action.triggered.connect(self._address_bar.selectAll)
        focus_url_action.triggered.connect(self._address_bar.setFocus)
        self.addAction(focus_url_action)

        # F5: Yenile
        reload_action = QAction("Yenile", self)
        reload_action.setShortcut(QKeySequence("F5"))
        reload_action.triggered.connect(self._reload_page)
        self.addAction(reload_action)

        # Ctrl+Shift+A: AI panelini aç/kapat
        ai_action = QAction("AI Panel", self)
        ai_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        ai_action.triggered.connect(self._toggle_ai_sidebar)
        self.addAction(ai_action)

        # Ctrl+Shift+F: Finans panelini aç/kapat
        finance_action = QAction("Finans Panel", self)
        finance_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        finance_action.triggered.connect(self._toggle_finance_sidebar)
        self.addAction(finance_action)

        # Ctrl+Shift+G: Tam ekran finans terminali
        finance_full_action = QAction("Finans Terminal", self)
        finance_full_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        finance_full_action.triggered.connect(self._open_finance_fullscreen)
        self.addAction(finance_full_action)

        # Ctrl+Shift+M: Tam sayfa müzik
        music_full_action = QAction("Müzik Sayfası", self)
        music_full_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        music_full_action.triggered.connect(self._open_music_fullscreen)
        self.addAction(music_full_action)

    def _setup_status_bar(self) -> None:
        """Durum çubuğunu oluşturur."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Sol: URL hover bilgisi
        self._status_url = QLabel("Hazır")
        status_bar.addWidget(self._status_url)

        # Sağ: Bellek kullanımı
        self._status_memory = QLabel()
        self._status_memory.setObjectName("memoryLabel")
        status_bar.addPermanentWidget(self._status_memory)

        # Sağ: Yüklü model göstergesi
        self._status_models = QLabel()
        status_bar.addPermanentWidget(self._status_models)

    # ─── Sekme Yönetimi ───────────────────────────────────────────

    def add_new_tab(self, url: QUrl = None, title: str = "Yeni Sekme") -> BrowserTab:
        """Yeni bir tarayıcı sekmesi ekler."""
        # URL yoksa yeni sekme sayfası göster
        if url is None:
            return self._show_new_tab_page()
        
        # Ad blocker interceptor'ı geç
        ad_blocker = self._privacy_engine.get_ad_blocker() if hasattr(self, '_privacy_engine') else None
        tab = BrowserTab(self._bridge, self, ad_blocker=ad_blocker)

        index = self._tab_widget.addTab(tab, title)
        self._tab_widget.setCurrentIndex(index)

        # Sayfa başlığı güncellendiğinde sekme başlığını güncelle
        tab.titleChanged.connect(
            lambda t, tab=tab: self._update_tab_title(tab, t)
        )

        # URL değiştiğinde adres çubuğunu güncelle
        tab.urlChanged.connect(
            lambda u, tab=tab: self._update_address_bar(tab, u)
        )

        # Yükleme başladığında/bittiğinde durum çubuğunu güncelle
        tab.loadStarted.connect(
            lambda: self._status_url.setText("Yükleniyor...")
        )
        tab.loadFinished.connect(
            lambda ok: self._status_url.setText("Yüklendi" if ok else "Yükleme hatası")
        )

        # Sayfa yüklendiğinde ürün sayfası mı kontrol et — otomatik analiz
        tab.loadFinished.connect(
            lambda ok, tab=tab: self._auto_detect_product_page(tab) if ok else None
        )

        # Sayfaya git
        tab.setUrl(url)

        QTimer.singleShot(50, self._update_new_tab_btn_pos)
        return tab
    
    def _show_new_tab_page(self):
        """Yeni Sekme Command Center sayfasını göster."""
        from new_tab_page import NewTabPage
        
        # Mevcut new tab page varsa onu göster
        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if hasattr(widget, '_is_new_tab_page'):
                self._tab_widget.setCurrentIndex(i)
                return widget
        
        # Yeni oluştur
        page = NewTabPage()
        page.set_browser(self)
        page.search_requested.connect(self._on_newtab_search)
        page.open_music_page.connect(self._open_music_fullscreen)
        
        index = self._tab_widget.addTab(page, "✨ Yeni Sekme")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)
        return page
        
    def _on_newtab_search(self, query: str, engine: str):
        """New Tab'dan arama isteği."""
        # Mevcut new tab page'i kaldır, yerine normal tab aç
        current_idx = self._tab_widget.currentIndex()
        current_widget = self._tab_widget.widget(current_idx)
        
        if hasattr(current_widget, '_is_new_tab_page'):
            # New tab page'i kaldır
            self._tab_widget.removeTab(current_idx)
            current_widget.deleteLater()
            
        # URL oluştur
        if engine == "google":
            url = f"https://www.google.com/search?q={query}"
        elif engine == "duckduckgo":
            url = f"https://duckduckgo.com/?q={query}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={query}"
        else:
            url = f"https://www.google.com/search?q={query}"
            
        # Yeni browser tab aç
        self.add_new_tab(QUrl(url), query[:20])

    def close_tab(self, index: int) -> None:
        """Belirtilen indeksteki sekmeyi kapatır."""
        if self._tab_widget.count() <= 1:
            # Son sekme — uygulamayı kapat
            self.close()
            return

        widget = self._tab_widget.widget(index)
        
        # Ghost sekme kontrolü
        is_ghost = hasattr(self, '_ghost_manager') and self._ghost_manager.is_ghost_tab(widget)
        
        self._tab_widget.removeTab(index)
        if widget:
            if hasattr(widget, 'cleanup'):
                widget.cleanup()
            widget.deleteLater()
            
        # Ghost sekme kapatıldıysa bildirim
        if is_ghost:
            self.statusBar().showMessage("👻 Hayalet sekme kapatıldı — Tüm izler temizlendi", 3000)
            
        QTimer.singleShot(50, self._update_new_tab_btn_pos)

    def _open_settings_tab(self) -> None:
        """Ayarlar sayfasını yeni sekmede aç."""
        # Zaten açık mı kontrol et
        for i in range(self._tab_widget.count()):
            if self._tab_widget.tabText(i) == "⚙️ Ayarlar":
                self._tab_widget.setCurrentIndex(i)
                return

        from settings_page import SettingsPage
        page = SettingsPage()
        index = self._tab_widget.addTab(page, "⚙️ Ayarlar")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)

    def _open_ai_fullscreen(self) -> None:
        """Tam ekran AI sohbetini yeni sekmede aç."""
        from ai_fullscreen import AIFullscreenPage
        page = AIFullscreenPage()
        # Browser referansı — AI'ın yeni sekme açabilmesi için
        page.set_browser(self)
        index = self._tab_widget.addTab(page, "🧠 AI Sohbet")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)

        # Sidebar'ı kapat
        if self._ai_sidebar.isVisible():
            self._ai_sidebar.hide()

    def _current_tab(self) -> Optional[QWebEngineView]:
        """Aktif web sekmesini döndürür (normal veya hayalet)."""
        widget = self._tab_widget.currentWidget()
        return widget if isinstance(widget, QWebEngineView) else None

    def _on_tab_changed(self, index: int) -> None:
        """Aktif sekme değiştiğinde adres çubuğunu günceller ve panelleri yönetir."""
        tab = self._current_tab()
        if tab:
            self._address_bar.setText(tab.url().toString())
        self._update_ghost_button_state()

        QTimer.singleShot(50, self._update_new_tab_btn_pos)

        # Müzik paneli açıksa otomatik küçült
        if getattr(self, '_music_panel', None) and self._music_panel.isVisible():
            welcome = getattr(self, '_welcome', None)
            if welcome and welcome.is_playing:
                self._minimize_music_panel()
            else:
                self._music_panel.hide()

    def _update_tab_title(self, tab: BrowserTab, title: str) -> None:
        """Sekme başlığını günceller (maksimum 25 karakter)."""
        index = self._tab_widget.indexOf(tab)
        if index >= 0:
            truncated = title[:25] + "…" if len(title) > 25 else title
            self._tab_widget.setTabText(index, truncated)

    def _update_address_bar(self, tab: BrowserTab, url: QUrl) -> None:
        """Aktif sekmenin URL'si değiştiğinde adres çubuğunu günceller."""
        if tab == self._current_tab():
            self._address_bar.setText(url.toString())

    # ─── Navigasyon ───────────────────────────────────────────────

    def _navigate_to_url(self) -> None:
        """Adres çubuğundaki URL'ye gider."""
        # Müzik panelini küçült
        self._auto_minimize_music()

        url_text = self._address_bar.text().strip()
        if not url_text:
            return

        # Arama terimi mi yoksa URL mi?
        if " " in url_text or "." not in url_text:
            # Arama terimi — Google'da ara
            url_text = f"https://www.google.com/search?q={url_text}"

        tab = self._current_tab()
        if tab:
            if hasattr(tab, "navigate_to"):
                tab.navigate_to(url_text)
            else:
                if not url_text.startswith(("http://", "https://")):
                    url_text = "https://" + url_text
                tab.setUrl(QUrl(url_text))

    def _go_back(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.back()

    def _go_forward(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.forward()

    def _reload_page(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.reload()

    def _go_home(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.setUrl(QUrl(config.DEFAULT_HOME_URL))

    # ─── Site Türü Algılama ─────────────────────────────────────────

    def _is_ecommerce_site(self, url: str = None) -> bool:
        """Geçerli URL'nin e-ticaret sitesi olup olmadığını kontrol eder."""
        if url is None:
            tab = self._current_tab()
            if not tab:
                return False
            url = tab.url().toString().lower()
        else:
            url = url.lower()

        ecommerce_domains = [
            'trendyol.com', 'hepsiburada.com', 'amazon.com', 'amazon.com.tr',
            'n11.com', 'gittigidiyor.com', 'ciceksepeti.com', 'lcwaikiki.com',
            'boyner.com.tr', 'defacto.com.tr', 'koton.com', 'zara.com',
            'hm.com', 'alibaba.com', 'aliexpress.com', 'ebay.com',
        ]
        return any(domain in url for domain in ecommerce_domains)

    def _auto_detect_product_page(self, tab) -> None:
        """Sayfa değiştiğinde sidebar modunu ayarlar, ürün sayfasında otomatik açar."""
        if tab != self._current_tab():
            return

        url = tab.url().toString().lower()
        is_ecommerce = self._is_ecommerce_site(url)

        # Sidebar modunu ayarla
        if is_ecommerce:
            self._ai_sidebar.set_site_mode("ecommerce")
        else:
            self._ai_sidebar.set_site_mode("general")

        # E-ticaret ürün sayfalarında otomatik sidebar aç
        is_product_page = any([
            'trendyol.com' in url and ('-p-' in url or '/brand/' in url),
            'hepsiburada.com' in url and '-pm-' in url,
            'amazon' in url and ('/dp/' in url or '/gp/product/' in url),
            'n11.com' in url and '/urun/' in url,
        ])

        if is_product_page and not self._ai_sidebar.isVisible():
            x_pos = self.width() - self._ai_sidebar.width() - 20
            y_pos = self._toolbar.height() + self._tab_widget.tabBar().height() + 10
            self._ai_sidebar.move(x_pos, y_pos)
            self._ai_sidebar.raise_()
            self._ai_sidebar.animate_open()

    # ─── AI Sidebar ───────────────────────────────────────────────

    def _toggle_ai_sidebar(self) -> None:
        """AI kenar panelini aç/kapat. Site türüne göre mod ayarlar."""
        # Müzik paneli açıksa küçült
        self._auto_minimize_music()

        if self._ai_sidebar.isVisible():
            self._ai_sidebar.hide()
        else:
            # Site türüne göre mod ayarla
            if self._is_ecommerce_site():
                self._ai_sidebar.set_site_mode("ecommerce")
            else:
                self._ai_sidebar.set_site_mode("general")

            # Yüzen ada pozisyon hesaplama
            x_pos = self.width() - self._ai_sidebar.width() - 20
            y_pos = self._toolbar.height() + self._tab_widget.tabBar().height() + 10
            self._ai_sidebar.move(x_pos, y_pos)
            self._ai_sidebar.raise_()
            self._ai_sidebar.animate_open()

    def _run_review_scraper(self) -> None:
        """Aktif sekmede yorum kazıma JavaScript'ini çalıştırır — 2sn gecikme ile."""
        tab = self._current_tab()
        if not tab:
            return

        self._ai_sidebar._status_label.setText("⏳ Sayfa içeriği taranıyor...")

        # Sayfanın yorum DOM'larını yüklemesi için 2 saniye bekle
        QTimer.singleShot(2000, lambda: self._execute_scraper(tab))

    def _execute_scraper(self, tab) -> None:
        """Gecikme sonrası scraper'ı çalıştırır."""
        if not tab:
            return
        # Önce sayfayı yorum bölümüne kaydır, sonra kazı
        scroll_and_scrape_js = """
        (function() {
            // Yorum bölümüne scroll dene
            var reviewSection = document.querySelector(
                '[class*="review"], [class*="yorum"], [class*="comment"], ' +
                '[class*="Rating"], [class*="rating"], [id*="review"], [id*="comment"]'
            );
            if (reviewSection) {
                reviewSection.scrollIntoView({behavior: 'instant', block: 'center'});
            }
            // Kısa bekleme sonrası kazı
            return window.__visionaryScrapeReviews ? window.__visionaryScrapeReviews() : '{}';
        })();
        """
        tab.page().runJavaScript(scroll_and_scrape_js, self._on_reviews_scraped)

    def _on_reviews_scraped(self, result) -> None:
        """Kazınan yorum verileri geldiğinde AI panelini günceller."""
        if result and self._ai_sidebar:
            self._ai_sidebar.analyze_reviews(str(result))

    def handle_review_data(self, data: dict) -> None:
        """Doğrudan DOM'dan gelen yorum verisini işler."""
        if self._ai_sidebar:
            self._ai_sidebar.analyze_reviews(json.dumps(data))

    def _handle_chat_request(self, user_message: str) -> None:
        """Sohbet isteği geldiğinde aktif sayfanın metnini alıp AI'ya iletir."""
        tab = self._current_tab()
        if not tab:
            return

        # Sayfa metnini JavaScript ile al
        tab.page().runJavaScript(
            "(document.body.innerText || '').substring(0, 4000)",
            lambda page_text: self._ai_sidebar.process_chat_response(
                page_text or "Sayfa içeriği alınamadı.", user_message
            )
        )

    # ─── Finans Sidebar ───────────────────────────────────────────

    def _toggle_finance_sidebar(self) -> None:
        """Finansal Zekâ panelini aç/kapat."""
        # Müzik paneli açıksa küçült
        self._auto_minimize_music()

        if self._finance_sidebar.isVisible():
            self._finance_sidebar.hide()
        else:
            # Yüzen ada pozisyonu — sol tarafta
            x_pos = 20
            y_pos = self._toolbar.height() + self._tab_widget.tabBar().height() + 10
            self._finance_sidebar.move(x_pos, y_pos)
            self._finance_sidebar.raise_()
            self._finance_sidebar.show()

            # Aktif sayfayı otomatik tara
            self._auto_scan_finance()

    def _auto_scan_finance(self) -> None:
        """Aktif sayfayı finans ticker'ları için tarar."""
        tab = self._current_tab()
        if not tab:
            return

        url = tab.url().toString()
        # Finansal site mi kontrol et
        finance_domains = [
            'finance.yahoo.com', 'google.com/finance', 'investing.com',
            'bloomberg.com', 'tradingview.com', 'bigpara.hurriyet.com',
            'marketwatch.com', 'cnbc.com', 'reuters.com',
            'finans.mynet.com', 'borsaistanbul.com',
        ]
        is_finance_site = any(d in url.lower() for d in finance_domains)

        if is_finance_site:
            # Sayfa metnini al ve taramayı başlat
            tab.page().runJavaScript(
                "(document.body.innerText || '').substring(0, 8000)",
                lambda text: self._finance_sidebar.scan_page(url, text or "")
            )

    def _on_finance_scan_requested(self, ticker_or_cmd: str) -> None:
        """Finans panelinden tarama veya analiz isteği."""
        if ticker_or_cmd == "__SCAN__":
            # Manuel sayfa tarama
            tab = self._current_tab()
            if tab:
                url = tab.url().toString()
                tab.page().runJavaScript(
                    "(document.body.innerText || '').substring(0, 8000)",
                    lambda text: self._finance_sidebar.scan_page(url, text or "")
                )
        else:
            self._finance_sidebar.start_analysis(ticker_or_cmd)

    def _on_finance_closed(self) -> None:
        """Finans paneli kapatıldığında."""
        self._finance_sidebar.hide()

    def _open_finance_fullscreen(self, initial_ticker: str = "") -> None:
        """Tam ekran finansal zekâ terminalini yeni sekmede açar."""
        from finance_fullpage import FinanceFullPage

        # Aktif sidebar'dan ticker'ı al
        ticker = initial_ticker
        if not ticker and self._finance_sidebar and self._finance_sidebar._current_ticker:
            ticker = self._finance_sidebar._current_ticker

        page = FinanceFullPage(initial_ticker=ticker)
        page.set_browser(self)
        page.open_in_sidebar.connect(self._finance_fullscreen_to_sidebar)

        index = self._tab_widget.addTab(page, f"📊 Finans{' — ' + ticker if ticker else ''}")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)

        # Sidebar açıksa kapat
        if self._finance_sidebar.isVisible():
            self._finance_sidebar.hide()

    def _finance_fullscreen_to_sidebar(self, ticker: str) -> None:
        """Tam ekran finans sayfasından sidebar'a geçiş."""
        # Sidebar'ı göster
        if not self._finance_sidebar.isVisible():
            self._toggle_finance_sidebar()
        # Ticker varsa analiz et
        if ticker:
            self._finance_sidebar.start_analysis(ticker)

    def _open_music_fullscreen(self) -> None:
        """Tam sayfa müzik sayfasını sekmede açar (varsa mevcut olanı gösterir)."""
        # Mevcut müzik sekmesi var mı kontrol et
        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if hasattr(widget, '_is_music_fullpage'):
                self._tab_widget.setCurrentIndex(i)
                return

        from music_fullpage import MusicFullPage
        if not hasattr(self, '_music_fullpage') or self._music_fullpage is None:
            self._music_fullpage = MusicFullPage()
            self._music_fullpage.set_browser(self)
            self._music_fullpage.open_in_browser.connect(
                lambda url: self.add_new_tab(QUrl(url), "YouTube")
            )
        page = self._music_fullpage
        index = self._tab_widget.addTab(page, "🎵 Müzik")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)
        # Müzik paneli açıksa kapat
        if self._music_panel.isVisible():
            self._music_panel.hide()

    # ─── Gizlilik & Meta-Arama ────────────────────────────────────────
    
    def _open_privacy_panel(self) -> None:
        """Gizlilik kalkanı durumunu göster."""
        if not hasattr(self, '_privacy_engine'):
            return
            
        status = self._privacy_engine.get_status()
        
        # Basit bilgi mesajı
        msg = (
            f"🛡️ Gizlilik Kalkanı Durumu\n\n"
            f"• Reklam Engelleyici: {'✅ Aktif' if status['blocker_enabled'] else '❌ Pasif'}\n"
            f"• Engellenen İstek: {status['blocked_requests']}\n"
            f"• Engelleme Oranı: {status['block_rate']}\n\n"
            f"• Tor Ağı: {'✅ Bağlı' if status['tor_enabled'] else '❌ Kapalı'}\n"
        )
        if status['tor_enabled'] and status['tor_ip']:
            msg += f"• Tor IP: {status['tor_ip']}\n"
            
        msg += f"\n🔒 Gizlilik Skoru: {status['privacy_score']}/100"
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Gizlilik Kalkanı", msg)
        
    def _open_visionary_search(self) -> None:
        """Visionary meta-arama sayfasını aç."""
        # Sorgu iste
        query, ok = QInputDialog.getText(
            self, "Visionary Arama", "Arama sorgusu:"
        )
        if not ok or not query.strip():
            return
            
        # Arama sayfası oluştur
        page = self._search_manager.search(query.strip())
        # Link tıklandığında mevcut sekmede aç (yeni sekme değil)
        page.link_clicked.connect(lambda url: self._open_url_in_current_tab(url))
        
        index = self._tab_widget.addTab(page, f"🔍 {query[:15]}...")
        self._tab_widget.setCurrentIndex(index)
        QTimer.singleShot(50, self._update_new_tab_btn_pos)
        
    def _toggle_tor(self) -> None:
        """Tor ağını aç/kapat."""
        if not hasattr(self, '_privacy_engine'):
            return
            
        from PyQt6.QtWidgets import QMessageBox
            
        if self._privacy_engine.is_tor_enabled():
            # Kapat
            self._privacy_engine.disable_tor()
            remove_proxy()
            if hasattr(self, "_tor_btn"):
                self._tor_btn.setToolTip("Tor Ağı: Kapalı")
                self._tor_btn.setChecked(False)
            self.statusBar().showMessage("🧅 Tor ağı kapatıldı. Tam devre dışı bırakmak için uygulamayı yeniden başlatın.", 5000)
            
            # Yeniden başlatma öner
            reply = QMessageBox.question(
                self, "Tor Ağı",
                "Tor bağlantısı kapatıldı.\n\nDeğişikliklerin tam olarak uygulanması için tarayıcıyı yeniden başlatmanız önerilir.\n\nŞimdi yeniden başlatılsın mı?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._restart_app()
        else:
            # Aç
            self.statusBar().showMessage("🧅 Tor'a bağlanılıyor...", 0)
            success = self._privacy_engine.enable_tor()
            if success:
                apply_tor_proxy_to_profile(None, self._privacy_engine.tor_manager)
                if hasattr(self, "_tor_btn"):
                    self._tor_btn.setToolTip("Tor Ağı: Bağlı ✓")
                    self._tor_btn.setChecked(True)
                
                # Yeniden başlatma öner
                reply = QMessageBox.question(
                    self, "Tor Ağı Aktif",
                    "Tor ağına bağlandı! ✓\n\nTüm web trafiğinin Tor üzerinden geçmesi için tarayıcıyı yeniden başlatmanız gerekiyor.\n\nŞimdi yeniden başlatılsın mı?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._restart_app()
                else:
                    self.statusBar().showMessage("🧅 Tor aktif. Tam koruma için tarayıcıyı yeniden başlatın.", 5000)
            else:
                if hasattr(self, "_tor_btn"):
                    self._tor_btn.setToolTip("Tor Ağı: Hata!")
                    self._tor_btn.setChecked(False)
                self.statusBar().showMessage(
                    "❌ Tor bağlantısı başarısız. macOS: 'brew install tor' | Linux: 'sudo apt install tor'.",
                    6000
                )
                
    def _restart_app(self) -> None:
        """Uygulamayı yeniden başlat."""
        import sys
        import os
        
        # Kapatmadan önce ayarları kaydet
        try:
            self._settings.save()
        except Exception:
            pass
            
        # Yeniden başlat
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _open_url_in_current_tab(self, url: str) -> None:
        """URL'yi mevcut sekmede aç (arama sonuçları için)."""
        current_idx = self._tab_widget.currentIndex()
        current_widget = self._tab_widget.widget(current_idx)
        
        # Eğer mevcut widget bir BrowserTab değilse (arama sayfası vs.) değiştir
        if current_widget and not isinstance(current_widget, BrowserTab):
            self._tab_widget.removeTab(current_idx)
            current_widget.deleteLater()
            
            # Yeni tarayıcı sekmesi oluştur
            tab = BrowserTab(self)
            tab.setUrl(QUrl(url))
            idx = self._tab_widget.insertTab(current_idx, tab, "Yükleniyor...")
            self._tab_widget.setCurrentIndex(idx)
        elif current_widget:
            # Normal BrowserTab, direkt URL değiştir
            current_widget.setUrl(QUrl(url))
        else:
            # Sekme yok, yeni aç
            self.add_new_tab(QUrl(url))

    # ─── Guardian Güvenlik Kontrolü ────────────────────────────────
    
    def _toggle_guardian(self) -> None:
        """Guardian güvenlik sistemini aç/kapat."""
        if not hasattr(self, '_guardian'):
            return
            
        enabled = self._guardian.toggle()
        if enabled:
            if hasattr(self, "_guardian_btn"):
                self._guardian_btn.setToolTip("Guardian: Aktif ✓")
                self._guardian_btn.setChecked(True)
            self.statusBar().showMessage("🛡️ Visionary Guardian etkinleştirildi — Güvenli gezinti modu", 3000)
        else:
            if hasattr(self, "_guardian_btn"):
                self._guardian_btn.setToolTip("Guardian: Kapalı")
                self._guardian_btn.setChecked(False)
            self.statusBar().showMessage("⚠️ Guardian devre dışı — Dikkatli gezinin!", 3000)
            
    def _show_guardian_stats(self) -> None:
        """Guardian istatistiklerini göster."""
        if not hasattr(self, '_guardian'):
            return
            
        stats = self._guardian.get_stats()
        
        from PyQt6.QtWidgets import QMessageBox
        msg = "🛡️ Visionary Guardian İstatistikleri\n"
        msg += "━" * 35 + "\n\n"
        msg += f"📊 Durum: {'Aktif ✓' if stats['guardian_enabled'] else 'Kapalı ✗'}\n"
        msg += f"🚫 Kara Liste: {stats['blacklist_count']} domain\n"
        msg += f"✅ Beyaz Liste: {stats['whitelist_count']} domain\n"
        msg += f"🔒 Güvenli Domain: {stats['safe_domains_count']} adet\n"
        msg += f"⛔ Toplam Engelleme: {stats['total_blocks']} kez\n"
        msg += f"🔄 Aktif Tarama: {stats['active_scans']} adet"
        
        QMessageBox.information(self, "Guardian İstatistikleri", msg)
        
    def _on_guardian_blocked(self, url: str, threat_type: str) -> None:
        """Guardian bir URL'yi engellediğinde çağrılır."""
        logger.warning(f"Guardian engelledi: {url} - {threat_type}")
        
        # Mevcut sekmeyi bul
        current_tab = self._tab_widget.currentWidget()
        if not current_tab:
            return
            
        # Uyarı sayfası oluştur
        warning_page = self._guardian.create_warning_page(url, threat_type)
        warning_page.go_back_clicked.connect(lambda: self._guardian_go_back(current_tab))
        warning_page.proceed_anyway_clicked.connect(
            lambda u: self._guardian_proceed_anyway(u, current_tab)
        )
        
        # Mevcut sekmenin içeriğini değiştir
        current_idx = self._tab_widget.currentIndex()
        self._tab_widget.removeTab(current_idx)
        
        idx = self._tab_widget.insertTab(current_idx, warning_page, "⚠️ Güvenlik Uyarısı")
        self._tab_widget.setCurrentIndex(idx)
        
        self.statusBar().showMessage(f"🛡️ Tehlikeli site engellendi: {threat_type}", 5000)
        
    def _guardian_go_back(self, original_tab) -> None:
        """Uyarı sayfasından geri dön."""
        current_idx = self._tab_widget.currentIndex()
        self._tab_widget.removeTab(current_idx)
        
        # Yeni boş sekme aç
        self.add_new_tab(QUrl(config.DEFAULT_HOME_URL), "Ana Sayfa")
        
    def _guardian_proceed_anyway(self, url: str, original_tab) -> None:
        """Kullanıcı uyarıya rağmen devam etmek istedi."""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.warning(
            self,
            "⚠️ Tehlikeli Site",
            "Bu siteye girmek cihazınıza ve verilerinize zarar verebilir.\n\n"
            "Yine de devam etmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Domain'i beyaz listeye ekle (bu oturum için)
            self._guardian.add_to_whitelist(url)
            
            # Uyarı sayfasını kaldır ve siteyi aç
            current_idx = self._tab_widget.currentIndex()
            current_widget = self._tab_widget.widget(current_idx)
            self._tab_widget.removeTab(current_idx)
            current_widget.deleteLater()
            
            # Yeni sekme aç
            self.add_new_tab(QUrl(url), "Yükleniyor...")
            self.statusBar().showMessage("⚠️ Dikkat: Güvensiz siteye erişim sağlandı", 5000)

    # ─── Ghost Sandbox (Hayalet Mod) ─────────────────────────────────

    def _update_ghost_button_state(self) -> None:
        """Hayalet mod buton durumunu aktif sekmeye göre günceller."""
        if not hasattr(self, "_ghost_btn") or not hasattr(self, "_ghost_manager"):
            return

        current_widget = self._tab_widget.currentWidget()
        is_ghost_active = self._ghost_manager.is_ghost_tab(current_widget)
        self._ghost_btn.setChecked(is_ghost_active)
        self._ghost_btn.setToolTip(
            "Hayalet Mod: Aktif (izole sekmedesiniz)"
            if is_ghost_active
            else "Hayalet Mod: Pasif (yeni izole sekme aç)"
        )
    
    def _open_ghost_tab(self) -> None:
        """Yeni izole hayalet sekme aç."""
        if not hasattr(self, '_ghost_manager'):
            return
            
        # Tor aktifse, ghost manager'a bildir
        if hasattr(self, '_privacy_engine') and self._privacy_engine.is_tor_enabled():
            self._ghost_manager.enable_tor(True)
        
        # Yeni ghost tab oluştur
        ghost_tab = self._ghost_manager.create_ghost_tab(self)
        
        # Tab widget'a ekle
        idx = self._tab_widget.addTab(ghost_tab, "👻 Hayalet Sekme")
        self._tab_widget.setCurrentIndex(idx)
        self._update_ghost_button_state()
        
        # Rose gold stilini sekme başlığına uygula
        tab_bar = self._tab_widget.tabBar()
        tab_bar.setTabTextColor(idx, QColor(230, 199, 194))  # Rose gold
        
        # Başlangıç sayfası olarak DuckDuckGo aç (gizlilik odaklı)
        ghost_tab.navigate_to("https://duckduckgo.com")
        
        # URL değişikliklerini takip et
        ghost_tab.urlChanged.connect(
            lambda u, tab=ghost_tab: self._update_address_bar(tab, u)
        )
        ghost_tab.titleChanged.connect(
            lambda t, tab=ghost_tab, i=idx: self._tab_widget.setTabText(
                self._tab_widget.indexOf(tab), f"👻 {t[:25]}..." if len(t) > 25 else f"👻 {t}"
            )
        )
        
        # Bildirim göster
        notification = GhostNotification(
            "👻 Hayalet Sekme açıldı — Tamamen izole ve geçici mod",
            self
        )
        notification.show_notification(self)
        
        self.statusBar().showMessage(
            "👻 Hayalet Mod aktif — İndirme engelli, geçmiş tutulmaz, tamamen izole", 
            4000
        )
        
        logger.info(f"[Ghost] Yeni hayalet sekme açıldı: {ghost_tab.get_profile_id()}")
        
    def _close_ghost_tab(self, index: int) -> None:
        """Hayalet sekmeyi kapat ve temizle."""
        widget = self._tab_widget.widget(index)
        
        if self._ghost_manager.is_ghost_tab(widget):
            widget.cleanup()
            
        self._tab_widget.removeTab(index)
        widget.deleteLater()
        
        self.statusBar().showMessage("👻 Hayalet sekme kapatıldı — Tüm izler temizlendi", 3000)

    # ─── Smart Proxy (Ülke Bazlı Proxy) ──────────────────────────────
    
    def _show_proxy_menu(self) -> None:
        """Proxy ülke seçim menüsünü göster."""
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14142A, stop:1 #0E0E1A);
                border: 1px solid rgba(34, 197, 94, 0.3);
                border-radius: 10px;
                padding: 8px 4px;
            }
            QMenu::item {
                color: #EDEDF2;
                padding: 10px 20px;
                border-radius: 6px;
                margin: 2px 4px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: rgba(34, 197, 94, 0.2);
                color: #22C55E;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(34, 197, 94, 0.2);
                margin: 6px 10px;
            }
        """)
        
        # Proxy durumu
        if self._proxy_manager.is_proxy_active():
            proxy = self._proxy_manager.get_current_proxy()
            if proxy:
                status_action = menu.addAction(f"✅ Bağlı: {proxy.country} ({proxy.speed_ms}ms)")
                status_action.setEnabled(False)
                
            disconnect_action = menu.addAction("❌ Bağlantıyı Kes")
            disconnect_action.triggered.connect(self._disconnect_proxy)
            menu.addSeparator()
        else:
            status_action = menu.addAction("🌍 Ülke Seçin")
            status_action.setEnabled(False)
            menu.addSeparator()
        
        # Ülke listesi
        for code, name in PROXY_COUNTRIES.items():
            action = menu.addAction(name)
            action.triggered.connect(lambda checked, c=code: self._select_proxy_country(c))
            
        menu.addSeparator()
        
        # Proxy havuzunu yenile
        refresh_action = menu.addAction("🔄 Proxy Listesini Yenile")
        refresh_action.triggered.connect(self._refresh_proxy_list)
        
        # Menüyü göster
        menu.exec(self._proxy_btn.mapToGlobal(self._proxy_btn.rect().bottomLeft()))
        
    def _select_proxy_country(self, country_code: str) -> None:
        """Ülke seç ve proxy'ye bağlan."""
        country_name = PROXY_COUNTRIES.get(country_code, country_code)
        self.statusBar().showMessage(f"🌍 {country_name} için proxy aranıyor...", 5000)
        
        # Proxy çek ve bağlan
        self._proxy_manager.fetch_proxies(country_code, ProxyType.HTTP)
        
    def _disconnect_proxy(self) -> None:
        """Proxy bağlantısını kes."""
        # Tüm profile'lardan kaldır
        self._proxy_manager.remove_proxy_from_profile(None)
        
    def _refresh_proxy_list(self) -> None:
        """Proxy listesini yenile."""
        self._proxy_manager.fetch_proxies()
        self.statusBar().showMessage("🔄 Proxy listesi yenileniyor...", 2000)
        
    def _on_proxy_connected(self, country: str, host: str, port: int) -> None:
        """Proxy bağlantısı kuruldu."""
        if hasattr(self, '_proxy_btn'):
            self._proxy_btn.setChecked(True)
            self._proxy_btn.setToolTip(f"Akıllı Proxy: {country} ({host}:{port})")
        self.statusBar().showMessage(
            f"✅ Proxy aktif: {country} ({host}:{port})",
            5000
        )
        
    def _on_proxy_disconnected(self) -> None:
        """Proxy bağlantısı kesildi."""
        if hasattr(self, '_proxy_btn'):
            self._proxy_btn.setChecked(False)
            self._proxy_btn.setToolTip("Akıllı Proxy: Kapalı (ülke seç)")
        self.statusBar().showMessage("🌍 Proxy kapatıldı", 3000)
        
    def _on_proxy_error(self, error: str) -> None:
        """Proxy hatası."""
        self.statusBar().showMessage(f"⚠️ Proxy hatası: {error}", 4000)
        
    def _on_proxy_status_changed(self, status: ProxyStatus, message: str) -> None:
        """Proxy durumu değişti."""
        # Status bar güncelle
        status_icons = {
            ProxyStatus.CONNECTED: "✅",
            ProxyStatus.DISCONNECTED: "⚫",
            ProxyStatus.CONNECTING: "🔄",
            ProxyStatus.VALIDATING: "🔍",
            ProxyStatus.FAILED: "❌",
        }
        icon = status_icons.get(status, "🌍")
        self.statusBar().showMessage(f"{icon} {message}", 4000)

    # ─── AR Modülü ────────────────────────────────────────────────

    # ─── Gesture / Kamera Kontrolü ──────────────────────────────────
    def _toggle_gesture(self) -> None:
        """Jest kontrol panelini aç/kapat."""
        if self._gesture_widget.isVisible():
            self._gesture_widget.stop_gesture()
            self._gesture_widget.hide()
            self._gesture_action.setText("✋  Jest Kontrolü")
            self.statusBar().showMessage("✋ Jest kontrol kapatıldı", 2000)
            return

        self._gesture_widget.show()
        self._gesture_widget.raise_()
        self._update_gesture_position()
        self._gesture_widget.start_gesture()

        self._gesture_action.setText("✋  Jest Kontrolü (Aktif)")
        self.statusBar().showMessage("✋ Jest kontrol aktif — el hareketlerinizi kullanın", 3000)

    def _update_gesture_position(self) -> None:
        """Gesture widget'ı sol alt köşeye, müzik FAB'ın üstüne konumla."""
        if not self._gesture_widget:
            return
        x = 16
        y = self.height() - self._gesture_widget.height() - 80 - self.statusBar().height()
        self._gesture_widget.move(x, y)

    def _on_gesture_closed(self) -> None:
        """Gesture widget kendi kapatma butonuyla kapanınca."""
        self._gesture_widget.hide()
        self._gesture_action.setText("✋  Jest Kontrolü")
        self.statusBar().showMessage("✋ Jest kontrol kapatıldı", 2000)

    def _update_floating_widgets_position(self) -> None:
        """Yüzen adaların konumlarını pencere boyutuna göre günceller."""
        if hasattr(self, '_gesture_widget') and self._gesture_widget.isVisible():
            x = 16
            y = self.height() - self._gesture_widget.height() - 80 - self.statusBar().height()
            self._gesture_widget.move(x, y)
            


    def _toggle_ar_module(self) -> None:
        """AR modülünü aç/kapat — sadece e-ticaret sitelerinde."""
        if self._ar_container.isVisible():
            self._ar_widget.close_ar()
            self._ar_container.hide()
            return

        # E-ticaret sitesi kontrolü
        if not self._is_ecommerce_site():
            self.statusBar().showMessage("⚠️ AR özelliği sadece e-ticaret sitelerinde kullanılabilir", 3000)
            return

        w, h = 420, 480
        self._ar_container.resize(w, h)
        x_pos = self.width() - w - 20
        y_pos = self.height() - h - 20 - self.statusBar().height()
        self._ar_container.move(x_pos, y_pos)
        self._ar_container.raise_()

        self._ar_container.show()
        self._ar_widget.show()
        self._ar_widget.start_ar()

    def handle_try_on(self, data: dict) -> None:
        """
        'Üstünde Dene' butonuna tıklandığında çağrılır.
        Ürün görselini indirir, arka planı arka planda siler ve AR başlatır.
        """
        image_src = data.get("imageSrc", "")
        image_alt = data.get("imageAlt", "")
        page_url = data.get("pageUrl", "")

        if not image_src:
            logger.warning("Ürün görseli URL'si boş.")
            return

        logger.info(f"Sanal deneme başlatılıyor: {image_src[:80]}...")

        # AR panelini hemen aç, kameraya başla
        w, h = 420, 480
        self._ar_container.resize(w, h)
        x_pos = self.width() - w - 20
        y_pos = self.height() - h - 20 - self.statusBar().height()
        self._ar_container.move(x_pos, y_pos)
        self._ar_container.raise_()
        self._ar_container.show()
        self._ar_widget.show()

        # Kamerayı hemen başlat (ürünsüz — kullanıcı kendini görür)
        self._ar_widget.start_ar(None, "clothing")
        self._ar_widget._status_label.setText("⏳ Ürün hazırlanıyor...")

        # Arka planda ürün indir + arka plan sil
        from PyQt6.QtCore import QThread, pyqtSignal

        class _TryOnWorker(QThread):
            finished = pyqtSignal(object, str)  # (product_img, category)
            error = pyqtSignal(str)

            def __init__(self, src, alt, url, parent_browser):
                super().__init__()
                self._src = src
                self._alt = alt
                self._url = url
                self._browser = parent_browser

            def run(self):
                try:
                    import numpy as np
                    import cv2

                    # 1. İndir
                    req = urllib.request.Request(
                        self._src, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    resp = urllib.request.urlopen(req, timeout=15)
                    img_bytes = resp.read()
                    arr = np.asarray(bytearray(img_bytes), dtype=np.uint8)
                    product_img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

                    if product_img is None:
                        self.error.emit("Ürün görseli decode edilemedi.")
                        return

                    # 2. Arka plan sil
                    try:
                        from rembg import remove
                        from PIL import Image
                        import io

                        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                        pil_result = remove(pil_img)
                        result_np = np.array(pil_result)
                        product_img = cv2.cvtColor(result_np, cv2.COLOR_RGBA2BGRA)
                        logger.info("Arka plan başarıyla silindi.")
                    except Exception as e:
                        logger.warning(f"Arka plan silme hatası: {e}")
                        if len(product_img.shape) == 2 or product_img.shape[2] == 3:
                            product_img = cv2.cvtColor(product_img, cv2.COLOR_BGR2BGRA)

                    # 3. Kategori
                    category = self._browser._detect_product_category(
                        self._src, self._alt, self._url, product_img
                    )
                    logger.info(f"Ürün kategorisi: {category}")

                    self.finished.emit(product_img, category)

                except Exception as e:
                    self.error.emit(str(e))

        def _on_tryon_ready(product_img, category):
            """Arka plan silme tamamlandı — ürünü AR'a gönder."""
            self._ar_widget._product_image = product_img
            self._ar_widget._product_category = category
            # MediaPipe'ı başlat
            if not self._ar_widget._tracker_initialized:
                try:
                    self._ar_widget._pose_tracker.initialize()
                    self._ar_widget._tracker_initialized = True
                except Exception:
                    pass
            self._ar_widget._status_label.setText(f"● {category.capitalize()} — Aktif")
            self._ar_widget._status_label.setStyleSheet("color: #00E676; font-size: 12px; font-weight: 600;")

        def _on_tryon_error(msg):
            self._ar_widget._status_label.setText(f"❌ {msg[:50]}")

        worker = _TryOnWorker(image_src, image_alt, page_url, self)
        worker.finished.connect(_on_tryon_ready)
        worker.error.connect(_on_tryon_error)
        worker.start()

        # Worker referansını tut (GC koruması)
        self._tryon_worker = worker

    def _detect_product_category(self, url: str, alt: str, page_url: str, img: np.ndarray) -> str:
        """URL, alt text ve görsel oranına göre ürün kategorisi belirler."""
        combined = (url + " " + alt + " " + page_url).lower()

        # Gözlük / güneş gözlüğü
        eyewear_kw = ['gozluk', 'gözlük', 'eyewear', 'sunglasses', 'glasses', 'lens']
        if any(kw in combined for kw in eyewear_kw):
            return "eyewear"

        # Şapka / bere / kep
        headwear_kw = ['sapka', 'şapka', 'bere', 'hat', 'cap', 'beanie', 'kep']
        if any(kw in combined for kw in headwear_kw):
            return "headwear"

        # Ayakkabı (daha sonra)
        shoe_kw = ['ayakkabi', 'ayakkabı', 'shoe', 'sneaker', 'boot', 'sandalet']
        if any(kw in combined for kw in shoe_kw):
            return "clothing"  # Şimdilik kıyafet gibi davran

        # Varsayılan: aspect ratio ile tahmin
        h, w = img.shape[:2]
        ratio = w / max(h, 1)
        if ratio > 2.5:
            return "eyewear"  # Çok geniş → muhtemelen gözlük
        
        return "clothing"  # Varsayılan kıyafet

    def _on_ar_closed(self) -> None:
        """AR modülü kapatıldığında."""
        self._ar_container.hide()

    # ─── Bellek İzleme ────────────────────────────────────────────

    def _update_memory_display(self) -> None:
        """Durum çubuğundaki bellek bilgisini günceller."""
        try:
            # RuntimeError: wrapped C/C++ object has been deleted (on exit)
            if not getattr(self, "isVisible", lambda: False)():
                return
            stats = self._resource_manager.get_memory_stats()
            self._status_memory.setText(
                f"💾 {stats['process_ram_mb']} MB"
            )

            models = stats["loaded_models"]
            if models:
                self._status_models.setText(f"🧠 {', '.join(models)}")
            else:
                self._status_models.setText("🧠 —")
        except Exception:
            pass

    # ─── Pencere Kapatma ──────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Pencere kapatılırken tüm kaynakları temizler."""
        # YouTube video penceresi kapat
        if getattr(self, '_yt_video_frame', None):
            try:
                self._yt_video_frame._close_video()
                self._yt_video_frame.close()
            except Exception:
                pass
        logger.info("Uygulama kapatılıyor...")

        # Bellek izleme zamanlayıcısını durdur
        if hasattr(self, '_memory_timer') and self._memory_timer.isActive():
            self._memory_timer.stop()

        # AI LLM thread'ini durdur
        if self._ai_sidebar and self._ai_sidebar._llm_worker:
            if self._ai_sidebar._llm_worker.isRunning():
                self._ai_sidebar._llm_worker.terminate()
                self._ai_sidebar._llm_worker.wait(3000)

        # Finans analiz worker'ını durdur
        if getattr(self, '_finance_sidebar', None) and self._finance_sidebar._analysis_worker:
            if self._finance_sidebar._analysis_worker.isRunning():
                self._finance_sidebar._analysis_worker.cancel()
                self._finance_sidebar._analysis_worker.quit()
                self._finance_sidebar._analysis_worker.wait(2000)

        # AR modülünü kapat
        if self._ar_widget:
            self._ar_widget.close_ar()

        # Gesture / Kamera thread'ini durdur
        if getattr(self, "_gesture_widget", None):
            self._gesture_widget.stop_gesture()

        # Tüm kaynakları serbest bırak
        self._resource_manager.shutdown()

        # Tüm sekmeleri kapat
        while self._tab_widget.count():
            widget = self._tab_widget.widget(0)
            self._tab_widget.removeTab(0)
            if widget:
                widget.deleteLater()

        event.accept()

    def resizeEvent(self, event) -> None:
        """Pencere boyutu değiştiğinde yüzen adaların konumlarını günceller."""
        super().resizeEvent(event)
        
        if getattr(self, "_ai_sidebar", None) and self._ai_sidebar.isVisible():
            x_pos = self.width() - self._ai_sidebar.width() - 20
            y_pos = self._toolbar.height() + self._tab_widget.tabBar().height() + 10
            self._ai_sidebar.move(x_pos, y_pos)
            
        if getattr(self, "_ar_container", None) and self._ar_container.isVisible():
            w, h = 420, 480
            x_pos = self.width() - w - 20
            y_pos = self.height() - h - 20 - self.statusBar().height()
            self._ar_container.move(x_pos, y_pos)

        # Finans sidebar konumunu güncelle
        if getattr(self, "_finance_sidebar", None) and self._finance_sidebar.isVisible():
            x_pos = 20
            y_pos = self._toolbar.height() + self._tab_widget.tabBar().height() + 10
            self._finance_sidebar.move(x_pos, y_pos)

        # Müzik FAB konumunu güncelle
        if getattr(self, "_music_fab", None):
            self._update_music_fab_position()

        # Mini player konumunu güncelle
        if getattr(self, "_mini_player", None) and self._mini_player.isVisible():
            self._update_mini_player_position()

        # Tab bar + butonunu güncelle
        if getattr(self, "_new_tab_btn", None):
            self._update_new_tab_btn_pos()

        # Gesture widget konumunu güncelle
        if getattr(self, "_gesture_widget", None) and self._gesture_widget.isVisible():
            self._update_gesture_position()

    def showEvent(self, event) -> None:
        """Pencere gösterildiğinde FAB ve tab butonunu ayarla."""
        super().showEvent(event)
        QTimer.singleShot(100, self._on_show_position_update)

    def _on_show_position_update(self) -> None:
        if getattr(self, "_music_fab", None):
            self._update_music_fab_position()
        if getattr(self, "_new_tab_btn", None):
            self._update_new_tab_btn_pos()
