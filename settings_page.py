"""
Visionary Navigator — Ayarlar Sayfası
Premium ULTRATHINK tasarım — kart tabanlı, inline formlar.
"""

import logging
from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QInputDialog, QSizePolicy, QSpinBox, QGraphicsDropShadowEffect,
    QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QFont, QIcon

from settings_manager import SettingsManager

logger = logging.getLogger("SettingsPage")


# ── Platform İkon Haritası ──────────────────────────────────────────
PLATFORM_ICONS = {
    "Instagram": "📷",
    "Twitter/X": "𝕏",
    "LinkedIn": "💼",
    "YouTube": "▶️",
    "GitHub": "🐙",
    "TikTok": "🎵",
    "Diğer": "🔗",
}


class _CardFrame(QFrame):
    """Glassmorphism kart container."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self.setStyleSheet("""
            QFrame#settingsCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.035), stop:1 rgba(255,255,255,0.012));
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


class _InlineForm(QFrame):
    """Satır içi form — URL / hesap ekleme."""

    submitted = pyqtSignal(str, str)  # (label, value)

    def __init__(self, placeholder="URL girin...", combo_items=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self._has_combo = combo_items is not None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        if self._has_combo:
            self._combo = QComboBox()
            self._combo.setFixedHeight(42)
            self._combo.addItems(combo_items)
            self._combo.setStyleSheet("""
                QComboBox {
                    background: rgba(255,255,255,0.04);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 10px; color: #ECECF1; font-size: 13px;
                    padding: 0 14px; min-width: 130px;
                }
                QComboBox:hover { border-color: rgba(255,255,255,0.14); }
                QComboBox::drop-down { border: none; width: 24px; }
                QComboBox::down-arrow { image: none; }
                QComboBox QAbstractItemView {
                    background: #16162A; color: #ECECF1;
                    border: 1px solid rgba(255,255,255,0.1);
                    selection-background-color: rgba(108,99,255,0.3);
                    padding: 4px; border-radius: 8px;
                }
            """)
            lay.addWidget(self._combo)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setFixedHeight(42)
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 16px;
            }
            QLineEdit:focus {
                border-color: rgba(108,99,255,0.45);
                background: rgba(255,255,255,0.06);
            }
        """)
        self._input.returnPressed.connect(self._submit)
        lay.addWidget(self._input, 1)

        self._add_btn = QPushButton("Ekle")
        self._add_btn.setFixedHeight(42)
        self._add_btn.setFixedWidth(76)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #5B54E0);
                color: #FFFFFF; border: none; border-radius: 10px;
                font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #7F77FF, stop:1 #6C63FF);
            }
            QPushButton:pressed { background: #4B4BFF; }
        """)
        self._add_btn.clicked.connect(self._submit)
        lay.addWidget(self._add_btn)

    def _default_input_style(self):
        return """
            QLineEdit {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 16px;
            }
            QLineEdit:focus {
                border-color: rgba(108,99,255,0.45);
                background: rgba(255,255,255,0.06);
            }
        """

    def _default_btn_style(self):
        return """
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #5B54E0);
                color: #FFFFFF; border: none; border-radius: 10px;
                font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #7F77FF, stop:1 #6C63FF);
            }
            QPushButton:pressed { background: #4B4BFF; }
        """

    def _submit(self):
        val = self._input.text().strip()
        if not val:
            self._input.setStyleSheet("""
                QLineEdit {
                    background: rgba(255,82,82,0.08);
                    border: 1px solid rgba(255,82,82,0.4);
                    border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 16px;
                }
            """)
            QTimer.singleShot(1500, lambda: self._input.setStyleSheet(self._default_input_style()))
            return

        label = self._combo.currentText() if self._has_combo else ""
        self.submitted.emit(label, val)
        self._input.clear()

        # Başarı feedback
        old_text = self._add_btn.text()
        self._add_btn.setText("✓")
        self._add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,230,118,0.2);
                color: #00E676; border: 1px solid rgba(0,230,118,0.3);
                border-radius: 10px; font-size: 14px; font-weight: 700;
            }
        """)
        QTimer.singleShot(800, lambda: (
            self._add_btn.setText(old_text),
            self._add_btn.setStyleSheet(self._default_btn_style())
        ))


class _ListItem(QFrame):
    """Özel liste öğesi — ikon + metin + silme butonu."""

    remove_requested = pyqtSignal(str)  # item key

    def __init__(self, icon, label, sublabel="", key="", parent=None):
        super().__init__(parent)
        self._key = key or label
        self.setFixedHeight(54)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 12px;
            }
            QFrame:hover {
                background: rgba(255,255,255,0.04);
                border-color: rgba(108,99,255,0.15);
            }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(12)

        # İkon badge
        ic = QLabel(icon)
        ic.setFixedSize(34, 34)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("""
            background: rgba(108,99,255,0.1);
            border-radius: 9px; font-size: 16px; border: none;
        """)
        lay.addWidget(ic)

        # Metin
        text_lay = QVBoxLayout()
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(1)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 13px; color: #ECECF1; font-weight: 500; background: transparent; border: none;")
        text_lay.addWidget(lbl)

        if sublabel:
            sub = QLabel(sublabel)
            sub.setStyleSheet("font-size: 11px; color: #565670; background: transparent; border: none;")
            sub.setMaximumWidth(260)
            text_lay.addWidget(sub)

        lay.addLayout(text_lay, 1)

        # Kaldır butonu
        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(30, 30)
        rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rm_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #3A3A50;
                border: none; border-radius: 8px; font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255,82,82,0.15); color: #FF5252;
            }
        """)
        rm_btn.clicked.connect(lambda: self.remove_requested.emit(self._key))
        lay.addWidget(rm_btn)


class SettingsPage(QWidget):
    """Premium ayarlar sayfası — kart tabanlı, inline formlar."""

    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._settings = SettingsManager()
        self._setup_ui()
        self._load_values()

    # ── Yardımcı widget fabrikaları ─────────────────────────────

    def _heading(self, icon, text, description=""):
        frame = QFrame()
        frame.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        ic_label = QLabel(icon)
        ic_label.setFixedSize(38, 38)
        ic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_label.setStyleSheet("""
            background: rgba(108,99,255,0.12);
            border-radius: 10px; font-size: 18px; border: none;
        """)

        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 15px; font-weight: 700; color: #FFFFFF;
            letter-spacing: 0.8px; border: none;
        """)

        title_row.addWidget(ic_label)
        title_row.addWidget(lbl)
        title_row.addStretch()
        lay.addLayout(title_row)

        if description:
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setStyleSheet("font-size: 12px; color: #565670; padding: 2px 0 4px 50px; border: none;")
            lay.addWidget(desc)

        return frame

    def _field(self, placeholder="", password=False):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(42)
        inp.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 16px;
            }
            QLineEdit:focus {
                border-color: rgba(108,99,255,0.45);
                background: rgba(255,255,255,0.06);
            }
        """)
        if password:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        return inp

    def _combo(self):
        c = QComboBox()
        c.setFixedHeight(42)
        c.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 14px;
            }
            QComboBox:hover { border-color: rgba(255,255,255,0.12); }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background: #16162A; color: #ECECF1;
                border: 1px solid rgba(255,255,255,0.1);
                selection-background-color: rgba(108,99,255,0.3);
                padding: 4px; border-radius: 8px;
            }
        """)
        return c

    def _pill_btn(self, text, color="#6C63FF", filled=False):
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if filled:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {color}, stop:1 {color}CC);
                    color: #FFFFFF; border: none; border-radius: 10px;
                    font-size: 12px; font-weight: 600; padding: 0 20px;
                    letter-spacing: 0.5px;
                }}
                QPushButton:hover {{ opacity: 0.9; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {color};
                    border: 1px solid {color}40; border-radius: 10px;
                    font-size: 12px; font-weight: 600; padding: 0 20px;
                }}
                QPushButton:hover {{ background: {color}15; border-color: {color}80; }}
            """)
        return btn

    def _checkbox(self, text):
        cb = QCheckBox(text)
        cb.setStyleSheet("""
            QCheckBox { color: #ECECF1; font-size: 13px; spacing: 10px; font-weight: 500; }
            QCheckBox::indicator {
                width: 18px; height: 18px; border-radius: 5px;
                border: 2px solid rgba(255,255,255,0.15);
                background: rgba(255,255,255,0.04);
            }
            QCheckBox::indicator:hover { border-color: rgba(108,99,255,0.4); }
            QCheckBox::indicator:checked {
                background: #6C63FF; border-color: #6C63FF;
            }
        """)
        return cb

    # ── Ana UI ──────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: #0A0A0F; border: none; }
            QWidget#_inner { background: #0A0A0F; }
            QScrollBar:vertical { background: transparent; width: 5px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.1); border-radius: 2px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.18); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setObjectName("_inner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(48, 36, 48, 48)
        lay.setSpacing(6)

        # ── Sayfa başlığı
        page_head = QLabel("⚙️  AYARLAR")
        page_head.setStyleSheet("""
            font-size: 24px; font-weight: 800; color: #FFFFFF;
            letter-spacing: 3px; padding-bottom: 2px;
        """)
        page_sub = QLabel("Visionary Navigator yapılandırması")
        page_sub.setStyleSheet("font-size: 12px; color: #565670; padding-bottom: 16px;")
        lay.addWidget(page_head)
        lay.addWidget(page_sub)
        lay.addSpacing(8)

        # ═══════════════════════════════════════════════════════
        # ── 1. Gemini API KART
        # ═══════════════════════════════════════════════════════
        card1 = _CardFrame()
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(24, 22, 24, 22)
        c1.setSpacing(12)

        c1.addWidget(self._heading("◆", "Gemini API",
            "Google Gemini API anahtarınızı girin. Hibrit AI modu aktif olur."))

        api_row = QHBoxLayout()
        api_row.setSpacing(8)
        self._gemini_input = self._field("API anahtarını yapıştırın...", password=True)
        self._gemini_test = self._pill_btn("⚡ Test", filled=True)
        self._gemini_test.clicked.connect(self._test_gemini)
        api_row.addWidget(self._gemini_input, 1)
        api_row.addWidget(self._gemini_test)
        c1.addLayout(api_row)

        self._gemini_status = QLabel("")
        self._gemini_status.setStyleSheet("font-size: 11px; color: #565670; padding: 0 0 2px 4px;")
        c1.addWidget(self._gemini_status)

        prov_row = QHBoxLayout()
        prov_row.setSpacing(12)
        prov_lbl = QLabel("AI Sağlayıcı")
        prov_lbl.setStyleSheet("color: #8E8EA0; font-size: 12px; font-weight: 500;")
        self._provider_combo = self._combo()
        self._provider_combo.addItems(["Otomatik (Hibrit)", "Sadece Gemini", "Sadece Yerel"])
        prov_row.addWidget(prov_lbl)
        prov_row.addWidget(self._provider_combo, 1)
        c1.addLayout(prov_row)

        lay.addWidget(card1)
        lay.addSpacing(12)

        # ═══════════════════════════════════════════════════════
        # ── 2. TTS KART
        # ═══════════════════════════════════════════════════════
        card2 = _CardFrame()
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(24, 22, 24, 22)
        c2.setSpacing(12)

        c2.addWidget(self._heading("🔊", "Ses Sentezi",
            "AI yanıtlarının sesli okunması — edge-tts Türkçe motor."))

        self._tts_enabled = self._checkbox("TTS Aktif")
        c2.addWidget(self._tts_enabled)

        voice_row = QHBoxLayout()
        voice_row.setSpacing(10)
        voice_lbl = QLabel("Ses")
        voice_lbl.setStyleSheet("color: #8E8EA0; font-size: 12px; font-weight: 500;")
        self._voice_combo = self._combo()
        self._voice_combo.addItems(["Ahmet (Erkek)", "Emel (Kadın)"])
        self._tts_test = self._pill_btn("▶ Dinle")
        self._tts_test.clicked.connect(self._test_tts)
        voice_row.addWidget(voice_lbl)
        voice_row.addWidget(self._voice_combo, 1)
        voice_row.addWidget(self._tts_test)
        c2.addLayout(voice_row)

        self._welcome_enabled = self._checkbox("Başlangıçta hoşgeldin selamlaması")
        c2.addWidget(self._welcome_enabled)

        lay.addWidget(card2)
        lay.addSpacing(12)

        # ═══════════════════════════════════════════════════════
        # ── 3. Müzik KART
        # ═══════════════════════════════════════════════════════
        card3 = _CardFrame()
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(24, 22, 24, 22)
        c3.setSpacing(12)

        c3.addWidget(self._heading("🎵", "Başlangıç Müziği",
            "YouTube veya herhangi bir URL. Uygulama açılışında çalınır."))

        self._music_input = self._field("https://youtube.com/watch?v=...")
        c3.addWidget(self._music_input)

        start_row = QHBoxLayout()
        start_row.setSpacing(10)
        start_lbl = QLabel("Başlangıç süresi")
        start_lbl.setStyleSheet("color: #8E8EA0; font-size: 12px; font-weight: 500;")
        self._music_start_spin = QSpinBox()
        self._music_start_spin.setRange(0, 9999)
        self._music_start_spin.setSuffix(" sn")
        self._music_start_spin.setFixedHeight(42)
        self._music_start_spin.setFixedWidth(120)
        self._music_start_spin.setStyleSheet("""
            QSpinBox {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; color: #ECECF1; font-size: 13px; padding: 0 14px;
            }
            QSpinBox:focus { border-color: rgba(108,99,255,0.45); }
            QSpinBox::up-button, QSpinBox::down-button { width: 20px; }
        """)
        start_row.addWidget(start_lbl)
        start_row.addWidget(self._music_start_spin)
        start_row.addStretch()
        c3.addLayout(start_row)

        lay.addWidget(card3)
        lay.addSpacing(12)

        # ═══════════════════════════════════════════════════════
        # ── 4. Sosyal Medya KART + INLINE FORM
        # ═══════════════════════════════════════════════════════
        card4 = _CardFrame()
        c4 = QVBoxLayout(card4)
        c4.setContentsMargins(24, 22, 24, 22)
        c4.setSpacing(12)

        c4.addWidget(self._heading("🌐", "Sosyal Medya Hesapları",
            "Hesaplarınızı bağlayın — AI sizi daha iyi tanısın."))

        platforms = list(PLATFORM_ICONS.keys())
        self._social_form = _InlineForm(
            placeholder="Profil URL'nizi girin...",
            combo_items=platforms
        )
        self._social_form.submitted.connect(self._on_social_added)
        c4.addWidget(self._social_form)

        self._social_container = QVBoxLayout()
        self._social_container.setSpacing(6)
        c4.addLayout(self._social_container)

        self._social_empty = QLabel("Henüz hesap eklenmedi")
        self._social_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._social_empty.setStyleSheet("color: #3A3A50; font-size: 12px; padding: 16px; font-style: italic;")
        c4.addWidget(self._social_empty)

        lay.addWidget(card4)
        lay.addSpacing(12)

        # ═══════════════════════════════════════════════════════
        # ── 5. Referans Siteler KART + INLINE FORM
        # ═══════════════════════════════════════════════════════
        card5 = _CardFrame()
        c5 = QVBoxLayout(card5)
        c5.setContentsMargins(24, 22, 24, 22)
        c5.setSpacing(12)

        c5.addWidget(self._heading("🔗", "Referans Siteler",
            "AI sohbetinde kaynak olarak kullanılacak web siteleri."))

        self._site_form = _InlineForm(placeholder="https://ornek.com")
        self._site_form.submitted.connect(self._on_site_added)
        c5.addWidget(self._site_form)

        self._sites_container = QVBoxLayout()
        self._sites_container.setSpacing(6)
        c5.addLayout(self._sites_container)

        self._sites_empty = QLabel("Henüz site eklenmedi")
        self._sites_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sites_empty.setStyleSheet("color: #3A3A50; font-size: 12px; padding: 16px; font-style: italic;")
        c5.addWidget(self._sites_empty)

        lay.addWidget(card5)
        lay.addSpacing(24)

        # ═══════════════════════════════════════════════════════
        # ── Kaydet
        # ═══════════════════════════════════════════════════════
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("   KAYDET   ")
        self._save_btn.setFixedSize(200, 48)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #6C63FF, stop:1 #4B4BFF);
                color: #FFFFFF; border: none; border-radius: 12px;
                font-size: 14px; font-weight: 700; letter-spacing: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #7F77FF, stop:1 #5C5CFF);
            }
            QPushButton:pressed { background: #4B4BFF; }
        """)
        shadow = QGraphicsDropShadowEffect(self._save_btn)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(108, 99, 255, 80))
        shadow.setOffset(0, 4)
        self._save_btn.setGraphicsEffect(shadow)
        self._save_btn.clicked.connect(self._save_settings)
        save_row.addWidget(self._save_btn)
        save_row.addStretch()
        lay.addLayout(save_row)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ── Inline form callback'leri ───────────────────────────────

    def _on_social_added(self, platform, url):
        icon = PLATFORM_ICONS.get(platform, "🔗")
        key = f"{platform}: {url}"
        item = _ListItem(icon, platform, url, key)
        item.remove_requested.connect(self._on_social_removed)
        self._social_container.addWidget(item)
        self._social_empty.hide()

    def _on_social_removed(self, key):
        for i in range(self._social_container.count()):
            w = self._social_container.itemAt(i).widget()
            if isinstance(w, _ListItem) and w._key == key:
                self._social_container.removeWidget(w)
                w.deleteLater()
                break
        has_items = any(
            isinstance(self._social_container.itemAt(i).widget(), _ListItem)
            for i in range(self._social_container.count())
        )
        if not has_items:
            self._social_empty.show()

    def _on_site_added(self, _label, url):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        domain = urlparse(url).netloc or url
        item = _ListItem("🌍", domain, url, url)
        item.remove_requested.connect(self._on_site_removed)
        self._sites_container.addWidget(item)
        self._sites_empty.hide()

    def _on_site_removed(self, key):
        for i in range(self._sites_container.count()):
            w = self._sites_container.itemAt(i).widget()
            if isinstance(w, _ListItem) and w._key == key:
                self._sites_container.removeWidget(w)
                w.deleteLater()
                break
        has_items = any(
            isinstance(self._sites_container.itemAt(i).widget(), _ListItem)
            for i in range(self._sites_container.count())
        )
        if not has_items:
            self._sites_empty.show()

    # ── Veri yükleme / kaydetme ─────────────────────────────────

    def _load_values(self):
        s = self._settings
        self._gemini_input.setText(s.gemini_api_key)
        self._tts_enabled.setChecked(s.tts_enabled)
        self._welcome_enabled.setChecked(s.get("welcome_enabled", True))
        self._music_input.setText(s.music_url)
        self._music_start_spin.setValue(s.get("music_start_sec", 0))

        voice = s.tts_voice
        self._voice_combo.setCurrentIndex(1 if "Emel" in voice else 0)

        provider = s.get("ai_provider", "auto")
        self._provider_combo.setCurrentIndex({"auto": 0, "gemini": 1, "local": 2}.get(provider, 0))

        # Sosyal medya
        for platform, url in s.social_accounts.items():
            icon = PLATFORM_ICONS.get(platform, "🔗")
            key = f"{platform}: {url}"
            item = _ListItem(icon, platform, url, key)
            item.remove_requested.connect(self._on_social_removed)
            self._social_container.addWidget(item)
        if s.social_accounts:
            self._social_empty.hide()

        # Referans siteler
        for site in s.custom_sites:
            domain = urlparse(site).netloc or site
            item = _ListItem("🌍", domain, site, site)
            item.remove_requested.connect(self._on_site_removed)
            self._sites_container.addWidget(item)
        if s.custom_sites:
            self._sites_empty.hide()

    def _save_settings(self):
        s = self._settings
        s.set("gemini_api_key", self._gemini_input.text().strip())
        s.set("tts_enabled", self._tts_enabled.isChecked())
        s.set("welcome_enabled", self._welcome_enabled.isChecked())
        s.set("music_url", self._music_input.text().strip())
        s.set("music_start_sec", self._music_start_spin.value())
        s.set("tts_voice", ["tr-TR-AhmetNeural", "tr-TR-EmelNeural"][self._voice_combo.currentIndex()])
        s.set("ai_provider", ["auto", "gemini", "local"][self._provider_combo.currentIndex()])

        accounts = {}
        for i in range(self._social_container.count()):
            w = self._social_container.itemAt(i).widget()
            if isinstance(w, _ListItem):
                key = w._key
                if ": " in key:
                    p, u = key.split(": ", 1)
                    accounts[p] = u
        s.set("social_accounts", accounts)

        sites = []
        for i in range(self._sites_container.count()):
            w = self._sites_container.itemAt(i).widget()
            if isinstance(w, _ListItem):
                sites.append(w._key)
        s.set("custom_sites", sites)
        s.save()

        self._save_btn.setText("✓  KAYDEDİLDİ")
        self._save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #00C853, stop:1 #00E676);
                color: #FFFFFF; border: none; border-radius: 12px;
                font-size: 14px; font-weight: 700; letter-spacing: 2px;
            }
        """)
        QTimer.singleShot(2000, lambda: (
            self._save_btn.setText("   KAYDET   "),
            self._save_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #6C63FF, stop:1 #4B4BFF);
                    color: #FFFFFF; border: none; border-radius: 12px;
                    font-size: 14px; font-weight: 700; letter-spacing: 2px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #7F77FF, stop:1 #5C5CFF);
                }
            """)
        ))
        self.settings_saved.emit()

    # ── Test fonksiyonları ──────────────────────────────────────

    def _test_gemini(self):
        key = self._gemini_input.text().strip()
        if not key:
            self._gemini_status.setText("❌ API anahtarı girilmedi")
            self._gemini_status.setStyleSheet("font-size: 11px; color: #FF5252; padding: 0 0 2px 4px;")
            return

        self._gemini_status.setText("⏳ Test ediliyor...")
        self._gemini_status.setStyleSheet("font-size: 11px; color: #FFC107; padding: 0 0 2px 4px;")

        from PyQt6.QtCore import QThread, pyqtSignal as Signal

        class _W(QThread):
            result = Signal(bool, str)
            def __init__(self, k):
                super().__init__()
                self._k = k
            def run(self):
                try:
                    from google import genai
                    client = genai.Client(api_key=self._k)
                    r = client.models.generate_content(
                        model="gemini-2.5-flash-lite", contents="Sadece 'OK' yaz.")
                    self.result.emit(bool(r and r.text), (r.text or "")[:30])
                except Exception as e:
                    self.result.emit(False, str(e)[:120])

        def _done(ok, msg):
            if ok:
                self._gemini_status.setText(f"✅ Bağlantı başarılı — {msg}")
                self._gemini_status.setStyleSheet("font-size: 11px; color: #00E676; padding: 0 0 2px 4px;")
            else:
                self._gemini_status.setText(f"❌ {msg}")
                self._gemini_status.setStyleSheet("font-size: 11px; color: #FF5252; padding: 0 0 2px 4px;")

        self._tw = _W(key)
        self._tw.result.connect(_done)
        self._tw.start()

    def _test_tts(self):
        from PyQt6.QtCore import QThread, pyqtSignal as Signal
        voice = ["tr-TR-AhmetNeural", "tr-TR-EmelNeural"][self._voice_combo.currentIndex()]

        class _T(QThread):
            done = Signal(bool, str)
            def __init__(self, v):
                super().__init__()
                self._v = v
            def run(self):
                try:
                    import edge_tts, asyncio, tempfile, os
                    async def g():
                        o = os.path.join(tempfile.gettempdir(), "vis_test.mp3")
                        await edge_tts.Communicate("Merhaba, test başarılı.", self._v).save(o)
                        return o
                    self.done.emit(True, asyncio.run(g()))
                except Exception as e:
                    self.done.emit(False, str(e))

        def _d(ok, p):
            if ok:
                try:
                    import subprocess
                    subprocess.Popen(["afplay", p])
                except Exception:
                    pass

        self._ttw = _T(voice)
        self._ttw.done.connect(_d)
        self._ttw.start()
