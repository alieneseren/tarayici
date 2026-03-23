"""
Visionary Navigator — Tam Ekran AI Sohbet
Premium AI sohbet arayüzü — ULTRATHINK tasarım.
Web sitesi açma komutu + inline mini tarayıcı ile veri çekme.
"""

import json
import logging
import re
import urllib.request
from html.parser import HTMLParser
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFrame, QScrollArea, QInputDialog, QListWidget,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QFont, QTextCursor, QColor

from settings_manager import SettingsManager
import config

logger = logging.getLogger("AIFullscreen")
logger.setLevel(logging.INFO)


# ─── URL algılama regex ───────────────────────────────────────────
_URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+|www\.[^\s<>"\']+\.[^\s<>"\']+',
    re.IGNORECASE
)

# "şu siteyi aç", "youtube aç", "google'ı aç" gibi komutları algılama
_OPEN_SITE_PATTERNS = [
    # "youtube aç", "google aç", "trendyol aç"
    re.compile(r'^(.+?)\s+(?:aç|açar\s*mısın|açsana|açabilir\s*misin)\s*[.!?]*$', re.IGNORECASE),
    # "youtube'u aç", "google'ı aç", "trendyol'u aç", "hepsiburada'yı aç"
    re.compile(r"^(.+?)[''ʼ]?[yınıuü]{0,3}\s+(?:aç|açar\s*mısın|açsana)\s*[.!?]*$", re.IGNORECASE),
    # "aç youtube", "aç google"
    re.compile(r'^(?:aç|açsana)\s+(.+?)\s*[.!?]*$', re.IGNORECASE),
    # "şu siteyi aç: youtube", "bu sayfayı aç: google.com"
    re.compile(r'(?:şu|bu)\s+(?:siteyi?|sayfayı?|web\s*sitesi(?:ni|yi)?)\s*(?:aç|açar\s*mısın)\s*[:\-]?\s*(.+)', re.IGNORECASE),
    # "X sitesini aç", "X sayfasını aç"
    re.compile(r'^(.+?)\s+(?:sitesini|sayfasını|adresini|linkini)\s+(?:aç|açar\s*mısın)\s*[.!?]*$', re.IGNORECASE),
    # "X'e git", "X'a gir"
    re.compile(r"^(.+?)[''ʼ]?[eyaıuü]{0,2}\s+(?:git|gir|gidelim|girelim)\s*[.!?]*$", re.IGNORECASE),
    # İngilizce: "open youtube", "go to google"
    re.compile(r'^(?:open|go\s+to|navigate\s+to|visit)\s+(.+?)\s*[.!?]*$', re.IGNORECASE),
]


class _HTMLTextExtractor(HTMLParser):
    """HTML → düz metin."""
    def __init__(self):
        super().__init__()
        self._result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'header', 'footer', 'iframe'):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'header', 'footer', 'iframe'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._result.append(text)

    def get_text(self):
        return " ".join(self._result)


def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="ignore")
        extractor = _HTMLTextExtractor()
        extractor.feed(html)
        return extractor.get_text()[:max_chars]
    except Exception as e:
        return f"[Hata: {e}]"


class _AIWorker(QThread):
    """Hibrit AI yanıt üretici (Gemini + yerel Mistral fallback)."""

    token_generated = pyqtSignal(str)
    complete = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, messages: list, settings: SettingsManager,
                 custom_sites: list = None):
        super().__init__()
        self._messages = messages
        self._settings = settings
        self._custom_sites = custom_sites or []

    def run(self):
        try:
            context_parts = []
            if self._custom_sites:
                self.status.emit("📡 Referans siteler taranıyor...")
                for url in self._custom_sites[:5]:
                    text = _fetch_page_text(url, 2000)
                    if text and "[Hata" not in text:
                        context_parts.append(f"[{url}]: {text}")

            provider = self._settings.get("ai_provider", "auto")
            has_gemini = self._settings.has_gemini()

            if (provider in ("auto", "gemini")) and has_gemini:
                self._run_gemini(context_parts)
            else:
                self._run_local(context_parts)
        except Exception as e:
            self.error.emit(str(e))

    def _run_gemini(self, context_parts: list):
        self.status.emit("🤖 Gemini yanıtlıyor...")
        try:
            from google import genai
            client = genai.Client(api_key=self._settings.gemini_api_key)

            system = (
                "Sen Visionary Navigator yapay zeka asistanısın. Türkçe yanıt ver. "
                "Samimi, bilgili ve yardımcı ol. Markdown formatında yanıt ver."
            )
            profile = self._settings.get("user_profile_summary", "")
            if profile:
                system += f"\n\nKullanıcı hakkında: {profile}"
            if context_parts:
                system += "\n\nReferans siteler:\n" + "\n".join(context_parts[:3])

            contents = []
            for msg in self._messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            # Streaming ile token token yanıt al
            full_text = ""
            for chunk in client.models.generate_content_stream(
                model="gemini-2.5-flash-lite",
                contents=contents,
                config={"system_instruction": system, "temperature": 0.7, "max_output_tokens": 2048}
            ):
                if chunk.text:
                    full_text += chunk.text
                    self.token_generated.emit(chunk.text)

            if full_text:
                self.complete.emit(full_text)
            else:
                self.error.emit("Gemini'den yanıt alınamadı")
        except Exception as e:
            logger.error(f"Gemini hatası: {e}")
            self.status.emit("⚠️ Gemini başarısız, yerel model deneniyor...")
            self._run_local(context_parts)

    def _run_local(self, context_parts: list):
        self.status.emit("🧠 Yerel model yanıtlıyor...")
        try:
            from resource_manager import SmartResourceManager
            llm = SmartResourceManager().load_llm()
            if llm is None:
                self.error.emit("LLM modeli yüklenemedi.")
                return

            prompt_parts = ["<s>[INST] Sen Visionary Navigator yapay zeka asistanısın. Türkçe yanıt ver."]
            if context_parts:
                prompt_parts.append("Referans:\n" + "\n".join(context_parts[:2]))
            for msg in self._messages[-6:]:
                prefix = "Kullanıcı" if msg["role"] == "user" else "Asistan"
                prompt_parts.append(f"{prefix}: {msg['content']}")
            prompt_parts.append("[/INST]")

            full_text = ""
            for chunk in llm("\n".join(prompt_parts), max_tokens=config.LLM_MAX_TOKENS,
                           temperature=config.LLM_TEMPERATURE, stream=True):
                token = chunk["choices"][0]["text"]
                full_text += token
                self.token_generated.emit(token)
            self.complete.emit(full_text)
        except Exception as e:
            self.error.emit(f"Yerel model hatası: {str(e)[:80]}")


class AIFullscreenPage(QWidget):
    """Tam ekran AI sohbet — premium tasarım + web sitesi açma + mini tarayıcı."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiFullscreenPage")
        self._settings = SettingsManager()
        self._messages: list = []
        self._worker: Optional[_AIWorker] = None
        self._ai_response_buffer = ""
        self._streaming_words: list = []       # Kelime kelime gösterim kuyruğu
        self._stream_timer: Optional[QTimer] = None
        self._stream_bubble_started = False    # AI balonu açıldı mı?
        self._tts_preloading = False            # TTS arka planda hazırlanıyor mu?
        self._tts_ready_path: Optional[str] = None  # Hazır TTS dosya yolu
        self._tts_pending_text = ""             # TTS'e gönderilecek metin
        self._browser = None  # VisionaryBrowser referansı
        self._setup_ui()

    def set_browser(self, browser) -> None:
        """VisionaryBrowser referansı — yeni sekme açmak için."""
        self._browser = browser

    def _setup_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Üst çubuk ─────────────────────────────────────────────
        top = QFrame()
        top.setFixedHeight(56)
        top.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0F0F18, stop:0.5 #111120, stop:1 #0F0F18);
                border-bottom: 1px solid rgba(108,99,255,0.12);
            }
        """)
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(28, 0, 28, 0)

        # Logo + Başlık
        logo = QLabel("◆")
        logo.setStyleSheet("font-size: 22px; color: #6C63FF; padding-right: 8px;")
        title = QLabel("Visionary AI")
        title.setStyleSheet("""
            font-size: 15px; font-weight: 700; color: #FFFFFF;
            letter-spacing: 1.2px; text-transform: uppercase;
        """)

        # Site sayacı
        self._site_badge = QLabel("")
        self._site_badge.setStyleSheet("""
            background: rgba(108,99,255,0.12); color: #A79BFF;
            border: 1px solid rgba(108,99,255,0.2); border-radius: 10px;
            font-size: 11px; font-weight: 600; padding: 3px 10px;
        """)
        self._update_site_count()

        # Butonlar
        add_btn = self._ghost_btn("+ Site", "#6C63FF")
        add_btn.clicked.connect(self._add_custom_site)

        clear_btn = self._ghost_btn("Temizle", "#FF5252")
        clear_btn.clicked.connect(self._clear_chat)

        top_lay.addWidget(logo)
        top_lay.addWidget(title)
        top_lay.addSpacing(16)
        top_lay.addWidget(self._site_badge)
        top_lay.addStretch()
        top_lay.addWidget(add_btn)
        top_lay.addWidget(clear_btn)

        # ── Sohbet alanı ──────────────────────────────────────────
        chat_container = QWidget()
        chat_container.setStyleSheet("background-color: #0A0A0F;")
        chat_lay = QVBoxLayout(chat_container)
        chat_lay.setContentsMargins(0, 0, 0, 0)

        self._chat_area = QTextEdit()
        self._chat_area.setReadOnly(True)
        self._chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #0A0A0F;
                border: none;
                color: #E0E0E8;
                font-size: 14px;
                padding: 24px 48px;
                selection-background-color: rgba(108,99,255,0.25);
            }
            QScrollBar:vertical { background: transparent; width: 5px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.08); border-radius: 2px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.15); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._chat_area.setHtml(
            '<div style="text-align: center; padding: 60px 20px;">'
            '<div style="font-size: 42px; margin-bottom: 16px;">◆</div>'
            '<div style="font-size: 18px; font-weight: 700; color: #FFFFFF; '
            'letter-spacing: 1px; margin-bottom: 8px;">Visionary AI</div>'
            '<div style="color: #565670; font-size: 13px; line-height: 1.8;">'
            'Herhangi bir konuda soru sorabilirsiniz.<br>'
            'Referans siteler ekleyerek daha doğru yanıtlar alabilirsiniz.<br><br>'
            '<span style="color: #3A3A50;">Yazmaya başlayın...</span></div></div>'
        )
        chat_lay.addWidget(self._chat_area)

        # ── Durum çubuğu ──────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setFixedHeight(22)
        self._status_label.setStyleSheet("""
            color: #3A3A50; font-size: 11px; padding: 0 48px;
            background-color: #0A0A0F;
            letter-spacing: 0.3px;
        """)

        # ── Alt giriş çubuğu ─────────────────────────────────────
        input_bar = QFrame()
        input_bar.setFixedHeight(76)
        input_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(14,14,22,0.97), stop:1 rgba(17,17,32,0.98));
                border-top: 1px solid rgba(108,99,255,0.08);
            }
        """)
        inp_lay = QHBoxLayout(input_bar)
        inp_lay.setContentsMargins(48, 0, 48, 0)
        inp_lay.setSpacing(12)

        # Mikrofon
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(46, 46)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px; font-size: 18px; color: #8E8EA0;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,255,255,0.15); color: #FFFFFF;
            }
        """)
        self._mic_btn.clicked.connect(self._toggle_mic)

        # Metin girişi
        self._input = QLineEdit()
        self._input.setFixedHeight(46)
        self._input.setPlaceholderText("Mesajınızı yazın...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px; color: #ECECF1; font-size: 14px;
                padding: 0 22px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(108,99,255,0.45);
                background: rgba(255,255,255,0.06);
            }
        """)
        self._input.returnPressed.connect(self._send_message)

        # TTS toggle
        self._tts_toggle = QPushButton("🔊")
        self._tts_toggle.setFixedSize(46, 46)
        self._tts_toggle.setCheckable(True)
        self._tts_toggle.setChecked(self._settings.tts_enabled)
        self._tts_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tts_toggle.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px; font-size: 18px; color: #3A3A50;
            }
            QPushButton:checked {
                background: rgba(108,99,255,0.12);
                border-color: rgba(108,99,255,0.3); color: #6C63FF;
            }
            QPushButton:hover { background: rgba(255,255,255,0.08); }
        """)

        # TTS durdurma butonu
        self._tts_stop_btn = QPushButton("⏹")
        self._tts_stop_btn.setFixedSize(46, 46)
        self._tts_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tts_stop_btn.setToolTip("Seslendirmeyi durdur")
        self._tts_stop_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,82,82,0.12);
                border: 1px solid rgba(255,82,82,0.3);
                border-radius: 14px; font-size: 18px; color: #FF5252;
            }
            QPushButton:hover {
                background: rgba(255,82,82,0.25);
                border-color: rgba(255,82,82,0.6); color: #FF8A80;
            }
        """)
        self._tts_stop_btn.clicked.connect(self._stop_tts)
        self._tts_stop_btn.hide()  # Başlangıçta gizli

        # Gönder
        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(46, 46)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #4B4BFF);
                border: none; border-radius: 14px;
                font-size: 18px; font-weight: bold; color: #FFFFFF;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #7F77FF, stop:1 #5C5CFF);
            }
            QPushButton:disabled { background: #2A2A35; color: #3A3A50; }
        """)
        self._send_btn.clicked.connect(self._send_message)

        inp_lay.addWidget(self._mic_btn)
        inp_lay.addWidget(self._input, 1)
        inp_lay.addWidget(self._tts_toggle)
        inp_lay.addWidget(self._tts_stop_btn)
        inp_lay.addWidget(self._send_btn)

        # Birleştir
        main.addWidget(top)
        main.addWidget(chat_container, 1)
        main.addWidget(self._status_label)
        main.addWidget(input_bar)

    def _ghost_btn(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {color};
                border: 1px solid {color}40; border-radius: 6px;
                font-size: 11px; font-weight: 600; padding: 0 14px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: {color}18; border-color: {color}80;
            }}
        """)
        return btn

    def _append_message(self, sender: str, text: str, color: str = "#E0E0E8") -> None:
        is_user = sender == "user"
        accent = "#6C63FF" if is_user else "#00E676"
        name = "SİZ" if is_user else "VİSİONARY AI"
        icon = "👤" if is_user else "◆"
        bg = "rgba(108,99,255,0.06)" if is_user else "rgba(0,230,118,0.03)"
        border = "rgba(108,99,255,0.15)" if is_user else "rgba(0,230,118,0.08)"
        text_color = "#E8E8F0" if color == "#E0E0E8" else color

        safe_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        html = f"""
        <div style="background: {bg}; border-left: 3px solid {accent};
                    border-radius: 0 12px 12px 0; padding: 16px 20px;
                    margin: 10px 0; border: 1px solid {border};
                    border-left: 3px solid {accent};">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 14px; margin-right: 6px;">{icon}</span>
                <span style="font-size: 10px; font-weight: 700; color: {accent};
                            letter-spacing: 1.8px;">{name}</span>
            </div>
            <div style="color: {text_color}; font-size: 14px; line-height: 1.7;
                        letter-spacing: 0.2px;">
                {safe_text}
            </div>
        </div>
        """
        self._chat_area.append(html)
        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def _send_message(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._append_message("user", text)
        self._messages.append({"role": "user", "content": text})

        # ── Web sitesi açma komutu algıla ─────────────────────────
        if self._try_open_website(text):
            return

        # ── URL içeren sorgularda mini tarayıcı ile veri çek ─────
        urls_in_text = _URL_PATTERN.findall(text)
        if urls_in_text:
            self._fetch_with_mini_browser(urls_in_text[0], text)
            return

        # ── Normal AI sohbet ──────────────────────────────────────
        self._start_ai_worker()

    def _try_open_website(self, text: str) -> bool:
        """Kullanıcı 'şu siteyi aç' gibi bir komut verdiyse yeni sekmede aç."""
        for pattern in _OPEN_SITE_PATTERNS:
            match = pattern.search(text)
            if match:
                target = match.group(1).strip().strip("'\".,;:!?")
                if not target or len(target) < 2:
                    continue
                # URL'mi yoksa site adı mı?
                url = self._resolve_url(target)
                if url and self._browser:
                    self._browser.add_new_tab(QUrl(url), target[:30])
                    self._append_message("ai",
                        f'🌐 <b>{target}</b> yeni sekmede açıldı.<br>'
                        f'<span style="color:#565670;font-size:12px;">{url}</span>',
                        "#00E676")
                    self._messages.append({"role": "assistant",
                        "content": f"{target} sitesi yeni sekmede açıldı: {url}"})
                    return True
                elif url and not self._browser:
                    self._append_message("ai",
                        "⚠️ Tarayıcı bağlantısı yok — siteyi açamadım.", "#FF5252")
                    return True
        return False

    def _resolve_url(self, text: str) -> Optional[str]:
        """Metni URL'ye dönüştür. Geçerli URL veya site adı döndürür."""
        text = text.strip().strip("'\".,;:!?")
        # Türkçe ek temizliği: youtube'u, google'ı, trendyol'u → youtube, google, trendyol
        import re as _re
        text = _re.sub(r"[''ʼ][yınıuüaeyiöü]{0,4}$", "", text).strip()

        # Zaten URL ise
        if text.startswith(("http://", "https://")):
            return text
        if text.startswith("www."):
            return "https://" + text

        # Bilinen siteler
        known = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "reddit": "https://www.reddit.com",
            "trendyol": "https://www.trendyol.com",
            "hepsiburada": "https://www.hepsiburada.com",
            "amazon": "https://www.amazon.com.tr",
            "n11": "https://www.n11.com",
            "wikipedia": "https://tr.wikipedia.org",
            "spotify": "https://open.spotify.com",
            "netflix": "https://www.netflix.com",
            "whatsapp": "https://web.whatsapp.com",
            "pinterest": "https://www.pinterest.com",
            "twitch": "https://www.twitch.tv",
            "discord": "https://discord.com",
            "telegram": "https://web.telegram.org",
            "tiktok": "https://www.tiktok.com",
            "stackoverflow": "https://stackoverflow.com",
            "stack overflow": "https://stackoverflow.com",
            "chatgpt": "https://chat.openai.com",
            "gmail": "https://mail.google.com",
            "outlook": "https://outlook.live.com",
            "yahoo": "https://www.yahoo.com",
            "bing": "https://www.bing.com",
            "yandex": "https://yandex.com",
            "sahibinden": "https://www.sahibinden.com",
            "gittigidiyor": "https://www.gittigidiyor.com",
            "çiçeksepeti": "https://www.ciceksepeti.com",
            "ciceksepeti": "https://www.ciceksepeti.com",
            "lcwaikiki": "https://www.lcwaikiki.com",
            "boyner": "https://www.boyner.com.tr",
            "defacto": "https://www.defacto.com.tr",
            "koton": "https://www.koton.com",
            "zara": "https://www.zara.com/tr",
            "ekşi": "https://eksisozluk.com",
            "eksi": "https://eksisozluk.com",
            "ekşi sözlük": "https://eksisozluk.com",
            "udemy": "https://www.udemy.com",
            "coursera": "https://www.coursera.org",
        }

        lower = text.lower().strip()
        # Önce tam eşleşme dene
        if lower in known:
            return known[lower]
        # Sonra kısmi eşleşme
        for name, url in known.items():
            if name in lower or lower in name:
                return url

        # Domain gibi görünüyorsa (nokta içeriyor, boşluk yok)
        if "." in text and " " not in text:
            return "https://" + text

        # Tek kelime ise .com dene
        if " " not in lower and len(lower) > 2:
            return f"https://www.{lower}.com"

        return None

    def _start_ai_worker(self) -> None:
        """Normal AI yanıt işlemini başlat."""
        self._send_btn.setEnabled(False)
        self._status_label.setText("◆ Düşünüyorum...")
        self._status_label.setStyleSheet("""
            color: #6C63FF; font-size: 11px; padding: 0 48px;
            background-color: #0A0A0F; letter-spacing: 0.3px;
        """)

        # Streaming state sıfırla
        self._ai_response_buffer = ""
        self._streaming_words = []
        self._stream_bubble_started = False
        self._tts_preloading = False
        self._tts_ready_path = None
        self._tts_pending_text = ""
        if self._stream_timer:
            self._stream_timer.stop()

        self._worker = _AIWorker(self._messages, self._settings,
                                  custom_sites=self._settings.custom_sites)
        self._worker.token_generated.connect(self._on_token)
        self._worker.complete.connect(self._on_complete)
        self._worker.error.connect(self._on_error)
        self._worker.status.connect(lambda s: self._status_label.setText(s))
        self._worker.start()

    def _on_token(self, token: str):
        """Streaming token geldi — kelime kuyruğuna ekle ve canlı yaz."""
        self._ai_response_buffer += token

        # İlk token geldiğinde AI balonunu aç
        if not self._stream_bubble_started:
            self._stream_bubble_started = True
            self._open_ai_stream_bubble()
            # Kelime kelime yazan timer'ı başlat
            self._stream_timer = QTimer()
            self._stream_timer.setInterval(30)  # 30ms → hızlı akıcı yazım
            self._stream_timer.timeout.connect(self._flush_stream_word)
            self._stream_timer.start()

        # Gelen token'ları kelime kuyruğuna ekle
        self._streaming_words.append(token)

    def _open_ai_stream_bubble(self) -> None:
        """AI yanıt balonunu aç — içerik canlı dolacak."""
        html = (
            '<div style="background: rgba(0,230,118,0.03); border-left: 3px solid #00E676;'
            '            border-radius: 0 12px 12px 0; padding: 16px 20px;'
            '            margin: 10px 0; border: 1px solid rgba(0,230,118,0.08);'
            '            border-left: 3px solid #00E676;">'
            '    <div style="display: flex; align-items: center; margin-bottom: 8px;">'
            '        <span style="font-size: 14px; margin-right: 6px;">◆</span>'
            '        <span style="font-size: 10px; font-weight: 700; color: #00E676;'
            '                    letter-spacing: 1.8px;">VİSİONARY AI</span>'
            '    </div>'
            '    <div id="ai-stream" style="color: #E8E8F0; font-size: 14px; line-height: 1.7;'
            '                letter-spacing: 0.2px;">'
            '        <span style="color: #565670;">▍</span>'
            '    </div>'
            '</div>'
        )
        self._chat_area.append(html)
        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def _flush_stream_word(self) -> None:
        """Kuyruktan kelime al ve mevcut AI balonuna ekle."""
        if not self._streaming_words:
            return

        # Kuyruktan birkaç kelime al (akıcılık için)
        batch = ""
        count = min(3, len(self._streaming_words))
        for _ in range(count):
            batch += self._streaming_words.pop(0)

        # Mevcut HTML'in sonundaki cursor'ı kullanarak metin ekle
        safe = batch.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        cursor = self._chat_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<span style="color:#E8E8F0;font-size:14px;">{safe}</span>')
        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)
        self._chat_area.ensureCursorVisible()

    def _on_complete(self, full_text: str):
        """AI yanıtı tamamlandı — kalan kelimeleri yaz, TTS başlat."""
        # Kalan kelimeleri hemen flush et
        if self._stream_timer:
            self._stream_timer.stop()

        while self._streaming_words:
            batch = self._streaming_words.pop(0)
            safe = batch.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            cursor = self._chat_area.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml(f'<span style="color:#E8E8F0;font-size:14px;">{safe}</span>')

        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)

        # Eğer streaming hiç başlamadıysa (fallback) normal balon ekle
        if not self._stream_bubble_started:
            self._append_message("ai", full_text)

        self._messages.append({"role": "assistant", "content": full_text})
        self._send_btn.setEnabled(True)
        self._status_label.setText("")
        self._status_label.setStyleSheet("""
            color: #3A3A50; font-size: 11px; padding: 0 48px;
            background-color: #0A0A0F; letter-spacing: 0.3px;
        """)

        # TTS — TÜM metni seslendir + durdurma butonu göster
        if self._tts_toggle.isChecked():
            self._speak_full_text(full_text)

    def _speak_full_text(self, text: str) -> None:
        """TTS ile tüm metni seslendir. Ön hazırlık yapıldıysa hemen çal."""
        try:
            from voice_engine import AudioPlayer, TTSEngine
            from PyQt6.QtMultimedia import QMediaPlayer

            if not hasattr(self, '_audio_player'):
                self._audio_player = AudioPlayer()

            # Durdurma butonunu göster
            self._tts_stop_btn.show()

            def _on_tts_done():
                """Seslendirme bitti — butonu gizle."""
                self._tts_stop_btn.hide()

            # TTS üret ve hemen çal
            self._tts_engine = TTSEngine(text, self._settings.tts_voice)

            def _on_audio_ready(path):
                self._audio_player.play_file(path)
                # Bitince durdurma butonunu gizle
                self._audio_player._player.mediaStatusChanged.connect(
                    lambda s: _on_tts_done() if s == QMediaPlayer.MediaStatus.EndOfMedia else None
                )

            self._tts_engine.audio_ready.connect(_on_audio_ready)
            self._tts_engine.error.connect(lambda e: (logger.warning(f"TTS hatası: {e}"), self._tts_stop_btn.hide()))
            self._tts_engine.start()
        except Exception as e:
            logger.warning(f"TTS hatası: {e}")
            self._tts_stop_btn.hide()

    def _stop_tts(self) -> None:
        """Seslendirmeyi durdur."""
        try:
            if hasattr(self, '_audio_player'):
                self._audio_player.stop()
            self._tts_stop_btn.hide()
            self._status_label.setText("🔇 Seslendirme durduruldu")
            QTimer.singleShot(2000, lambda: self._status_label.setText(""))
        except Exception:
            pass

    def _on_error(self, msg: str):
        self._append_message("ai", f"Hata: {msg}", "#FF5252")
        self._send_btn.setEnabled(True)
        self._status_label.setText("")

    def _toggle_mic(self):
        self._mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,82,82,0.2);
                border: 2px solid #FF5252; border-radius: 12px;
                font-size: 18px; color: #FF5252;
            }
        """)
        self._status_label.setText("🎤 Dinleniyor... Konuşun.")

        from voice_engine import STTEngine
        self._stt = STTEngine("tr-TR")
        self._stt.text_recognized.connect(self._on_voice_text)
        self._stt.error.connect(self._on_voice_error)
        self._stt.listening_stopped.connect(self._reset_mic_style)
        self._stt.start()

    def _on_voice_text(self, text: str):
        self._input.setText(text)
        self._send_message()

    def _on_voice_error(self, msg: str):
        self._status_label.setText(f"🎤 {msg}")
        self._reset_mic_style()

    def _reset_mic_style(self):
        self._mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px; font-size: 18px; color: #8E8EA0;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,255,255,0.15); color: #FFFFFF;
            }
        """)

    def _add_custom_site(self):
        url, ok = QInputDialog.getText(self, "Referans Site Ekle",
            "AI'ın kaynak olarak kullanacağı URL:")
        if ok and url.strip():
            sites = self._settings.custom_sites
            if url.strip() not in sites:
                sites.append(url.strip())
                self._settings.set("custom_sites", sites)
                self._settings.save()
                self._update_site_count()
                self._append_message("ai", f"Site eklendi: {url.strip()}", "#00E676")

    def _update_site_count(self):
        count = len(self._settings.custom_sites)
        self._site_badge.setText(f"📌 {count} referans" if count else "")
        self._site_badge.setVisible(count > 0)

    def _clear_chat(self):
        self._chat_area.clear()
        self._chat_area.setHtml(
            '<div style="text-align: center; padding: 60px 20px;">'
            '<div style="font-size: 42px; margin-bottom: 16px;">◆</div>'
            '<div style="font-size: 18px; font-weight: 700; color: #FFFFFF; '
            'letter-spacing: 1px; margin-bottom: 8px;">Visionary AI</div>'
            '<div style="color: #565670; font-size: 13px; line-height: 1.8;">'
            'Sohbet temizlendi. Yeni bir konuya başlayabilirsiniz.</div></div>'
        )
        self._messages.clear()
        self._status_label.setText("")
        try:
            from resource_manager import SmartResourceManager
            SmartResourceManager().unload_llm()
        except Exception:
            pass

    # ─── Mini Tarayıcı ile Veri Çekme ─────────────────────────────

    def _fetch_with_mini_browser(self, url: str, user_question: str) -> None:
        """URL'den veri çekmek için sohbete mini tarayıcı ekle ve veriyi AI'ya ilet."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self._send_btn.setEnabled(False)
        self._status_label.setText("🌐 Web sitesine bağlanılıyor...")
        self._status_label.setStyleSheet("""
            color: #00D9FF; font-size: 11px; padding: 0 48px;
            background-color: #0A0A0F; letter-spacing: 0.3px;
        """)

        # Mini tarayıcı bilgi kartı göster
        self._append_mini_browser_card(url)

        # Arka planda veri çek
        self._web_fetcher = _WebFetchWorker(url)
        self._web_fetcher.finished.connect(
            lambda text: self._on_web_data_fetched(text, url, user_question)
        )
        self._web_fetcher.error.connect(
            lambda err: self._on_web_fetch_error(err, user_question)
        )
        self._web_fetcher.start()

    def _append_mini_browser_card(self, url: str) -> None:
        """Sohbete mini tarayıcı bilgi kartı ekle."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc or url[:40]

        html = f"""
        <div style="background: rgba(0,217,255,0.04); border: 1px solid rgba(0,217,255,0.12);
                    border-radius: 12px; padding: 14px 18px; margin: 10px 0;">
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 16px; margin-right: 8px;">🌐</span>
                <span style="font-size: 10px; font-weight: 700; color: #00D9FF;
                            letter-spacing: 1.5px;">MİNİ TARAYICI</span>
            </div>
            <div style="color: #B0B0C0; font-size: 13px; line-height: 1.6;">
                <b style="color: #E0E0E8;">{domain}</b> sitesine bağlanılıyor...<br>
                <span style="color: #565670; font-size: 11px;">{url[:80]}</span>
            </div>
            <div style="margin-top: 8px;">
                <span style="background: rgba(0,217,255,0.1); color: #00D9FF;
                            font-size: 10px; padding: 2px 8px; border-radius: 4px;
                            letter-spacing: 0.5px;">⏳ Veri çekiliyor...</span>
            </div>
        </div>
        """
        self._chat_area.append(html)
        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)

    def _on_web_data_fetched(self, page_text: str, url: str, user_question: str) -> None:
        """Web verisi çekildi — sonucu AI'ya ilet."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc or url[:40]

        # Veri çekildi bilgi kartını güncelle
        success_html = f"""
        <div style="background: rgba(0,230,118,0.04); border: 1px solid rgba(0,230,118,0.12);
                    border-radius: 12px; padding: 14px 18px; margin: 4px 0;">
            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 14px; margin-right: 6px;">✅</span>
                <span style="font-size: 10px; font-weight: 700; color: #00E676;
                            letter-spacing: 1.5px;">{domain}</span>
            </div>
            <div style="color: #565670; font-size: 11px;">
                {len(page_text)} karakter veri çekildi — AI analiz ediyor...
            </div>
        </div>
        """
        self._chat_area.append(success_html)
        self._chat_area.moveCursor(QTextCursor.MoveOperation.End)

        # Çekilen veriyi context olarak ekleyip AI'ya sor
        enriched_msg = (
            f"Kullanıcı sorusu: {user_question}\n\n"
            f"Aşağıda {url} adresinden çekilen web sitesi içeriği var. "
            f"Bu içeriğe dayanarak kullanıcının sorusuna Türkçe yanıt ver:\n\n"
            f"{page_text[:4000]}"
        )
        # Mesaj geçmişine zenginleştirilmiş halini ekle
        if self._messages and self._messages[-1]["role"] == "user":
            self._messages[-1]["content"] = enriched_msg
        else:
            self._messages.append({"role": "user", "content": enriched_msg})

        self._start_ai_worker()

    def _on_web_fetch_error(self, error: str, user_question: str) -> None:
        """Web verisi çekme hatası — yine de AI'ya sor."""
        self._append_message("ai",
            f"⚠️ Web verisini çekerken hata: {error[:60]}<br>"
            f"Mevcut bilgilerimle yanıtlamaya çalışıyorum...", "#FFB300")

        # Hata olsa bile AI'ya normal sor
        self._start_ai_worker()


class _WebFetchWorker(QThread):
    """Arka planda web sayfası içeriğini çeker."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, max_chars: int = 5000):
        super().__init__()
        self._url = url
        self._max = max_chars

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode("utf-8", errors="ignore")
            extractor = _HTMLTextExtractor()
            extractor.feed(html)
            text = extractor.get_text()[:self._max]
            if text:
                self.finished.emit(text)
            else:
                self.error.emit("Sayfa içeriği boş")
        except Exception as e:
            self.error.emit(str(e)[:80])
