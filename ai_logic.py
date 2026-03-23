"""
Visionary Navigator — AI Mantık Modülü
Yerel LLM entegrasyonu, DOM kazıma koordinasyonu ve AI kenar paneli (sidebar) UI.
llama-cpp-python ile Türkçe artı/eksi analizi üretir + sayfa sohbeti.
"""

import json
import logging
import os
from typing import Optional, Callable

from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt, QPropertyAnimation, QRect
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QScrollArea,
    QProgressBar, QSizePolicy, QLineEdit
)

import config
from resource_manager import SmartResourceManager

# ─── Loglama ───────────────────────────────────────────────────────
logger = logging.getLogger("AILogic")
logger.setLevel(logging.INFO)


class LLMWorker(QThread):
    """
    LLM çıkarımını ayrı thread'de çalıştırır (UI donmasını engeller).
    Token akışını gerçek zamanlı olarak sinyalle iletir.
    """

    # Token bazlı akış — her yeni token parçası gönderilir
    token_generated = pyqtSignal(str)
    # Üretim tamamlandı
    generation_complete = pyqtSignal(str)
    # Hata oluştu
    error_occurred = pyqtSignal(str)
    # Durum güncellemesi
    status_update = pyqtSignal(str)

    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self._prompt = prompt

    def run(self) -> None:
        """LLM çıkarımını çalıştırır — streaming destekli."""
        self.status_update.emit("LLM modeli yükleniyor...")

        resource_manager = SmartResourceManager()
        llm = resource_manager.load_llm()

        if llm is None:
            import os
            if os.path.exists(config.LLM_MODEL_PATH):
                file_size = os.path.getsize(config.LLM_MODEL_PATH)
                if file_size < 100 * 1024 * 1024:  # Eğer dosya 100MB'dan küçükse iniyordur
                    self.error_occurred.emit(
                        f"⏳ Model indirmesi devam ediyor...\n\n"
                        f"Şu anki boyut: {file_size / (1024*1024):.1f} MB\n"
                        f"Model (yaklaşık 8.5 GB) arka planda inmektedir. Lütfen bekleyin."
                    )
                else:
                    self.error_occurred.emit(
                        "⚠️ LLM modeli yüklenemedi.\nDosya bozuk olabilir veya bellek yetersiz."
                    )
            else:
                self.error_occurred.emit(
                    "⚠️ LLM modeli bulunamadı.\n\n"
                    "Lütfen 'models/model.gguf' konumuna geçerli bir GGUF indirin."
                )
            return

        self.status_update.emit("Analiz yapılıyor...")

        try:
            full_response = ""

            # Streaming instruct çıkarım (ChatML / Llama-3 format v.b. için)
            messages = [
                {"role": "system", "content": "Sen e-ticaret yorumlarını analiz eden ve alışveriş konusunda yardımcı olan uzman bir asistansın. Her zaman Türkçe, kısa, net ve profesyonel cevaplar verirsin. Emoji kullanabilirsin. Asla gereksiz bilgi verme."},
                {"role": "user", "content": self._prompt}
            ]

            stream = llm.create_chat_completion(
                messages,
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=config.LLM_TEMPERATURE,
                stream=True
            )

            for chunk in stream:
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk['choices'][0].get('delta', {})
                    if 'content' in delta:
                        token = delta['content']
                        full_response += token
                        self.token_generated.emit(token)

            self.generation_complete.emit(full_response)
            logger.info(f"LLM üretimi tamamlandı ({len(full_response)} karakter).")

        except Exception as e:
            logger.error(f"LLM çıkarım hatası: {e}")
            self.error_occurred.emit(f"LLM hatası: {str(e)}")


class ReviewAnalyzer:
    """
    DOM'dan kazınan yorum verilerini LLM prompt'una dönüştüren yardımcı sınıf.
    """

    @staticmethod
    def build_prompt(scraped_data: dict) -> str:
        """Kazınan veriyi analiz prompt'una dönüştürür."""
        product_name = scraped_data.get("productName", "Bilinmeyen Ürün")
        price = scraped_data.get("price", "Belirtilmemiş")
        rating = scraped_data.get("rating", "Yok")
        seller = scraped_data.get("seller", "Bilinmiyor")
        seller_score = scraped_data.get("sellerScore", "Bilinmiyor")
        reviews = scraped_data.get("reviews", [])
        questions = scraped_data.get("questions", [])
        site = scraped_data.get("site", "bilinmiyor")

        review_texts = []
        for i, review in enumerate(reviews[:20], 1):
            stars = review.get("stars", "?")
            text = review.get("text", "")
            review_texts.append(f"{i}. [{stars}] {text}")

        qa_texts = []
        for i, q in enumerate(questions[:10], 1):
            qa_texts.append(f"{i}. {q}")

        page_text = scraped_data.get("pageText", "")
        
        if review_texts:
            reviews_str = "\n".join(review_texts)
        elif page_text:
            reviews_str = f"[Ham Sayfa İçeriği]\n{page_text}"
        else:
            reviews_str = "Yorum bulunamadı."

        qa_str = "\n".join(qa_texts) if qa_texts else "Soru-cevap verisi yok."

        product_data = (
            f"Site: {site}\n"
            f"Ürün: {product_name}\n"
            f"Fiyat: {price}\n"
            f"Ortalama Puan: {rating}\n"
            f"Satıcı: {seller}\n"
            f"Satıcı Puanı: {seller_score}\n"
            f"\nYorumlar / Değerlendirmeler:\n{reviews_str}\n"
            f"\nSoru-Cevap Bölümü:\n{qa_str}"
        )

        return config.REVIEW_ANALYSIS_PROMPT.format(product_data=product_data)

    @staticmethod
    def format_fallback(scraped_data: dict) -> str:
        """LLM yoksa basit bir özet oluşturur (fallback)."""
        product_name = scraped_data.get("productName", "Bilinmeyen Ürün")
        reviews = scraped_data.get("reviews", [])
        rating = scraped_data.get("rating", "?")
        seller = scraped_data.get("seller", "Bilinmiyor")

        summary = (
            f"📦 Ürün: {product_name}\n"
            f"⭐ Puan: {rating}\n"
            f"🏪 Satıcı: {seller}\n\n"
        )

        if reviews:
            summary += "📋 Son Yorumlar:\n"
            for i, r in enumerate(reviews[:5], 1):
                text = r.get("text", "")[:100]
                summary += f"  {i}. {text}...\n"

        summary += (
            "\n⚠️ LLM modeli yüklenmediği için detaylı analiz yapılamadı.\n"
            "Modeli yüklemek için 'models/' klasörüne bir GGUF dosyası ekleyin."
        )

        return summary


class AISidebar(QWidget):
    """
    AI analiz ve sohbet paneli.
    Ürün analizi + sayfa hakkında sohbet özelliği.
    """

    analysis_requested = pyqtSignal()
    chat_requested = pyqtSignal(str)
    fullscreen_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #111118; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08);")
        self.setFixedWidth(config.SIDEBAR_WIDTH)

        self._llm_worker: Optional[LLMWorker] = None
        self._chat_history: list = []
        self._current_mode = "analysis"
        self._site_mode = "ecommerce"  # "ecommerce" veya "general"
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Kenar paneli arayüzünü oluşturur."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Başlık çubuğu ─────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 16, 16)

        title_icon = QLabel("◆")
        title_icon.setStyleSheet("font-size: 16px; color: #6C63FF; padding-right: 2px;")

        title = QLabel("AI Asistan")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #FFFFFF; letter-spacing: 0.8px;")

        fullscreen_btn = QPushButton("⛶")
        fullscreen_btn.setFixedSize(28, 28)
        fullscreen_btn.setToolTip("Tam ekran AI sohbet")
        fullscreen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fullscreen_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8E8EA0; border: none; font-size: 16px; }
            QPushButton:hover { color: #6C63FF; }
        """)
        fullscreen_btn.clicked.connect(self.fullscreen_requested.emit)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8E8EA0; border: none; font-size: 14px; }
            QPushButton:hover { color: #FFFFFF; }
        """)
        close_btn.clicked.connect(self._animate_close)

        header_layout.addWidget(title_icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(fullscreen_btn)
        header_layout.addWidget(close_btn)

        # ── Mod seçici (Analiz / Sohbet) ──────────────────────────
        mode_frame = QFrame()
        mode_frame.setStyleSheet("background-color: transparent;")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(16, 8, 16, 8)
        mode_layout.setSpacing(4)

        self._btn_css_active = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6C63FF, stop:1 #4B4BFF);
                color: #FFFFFF; border: none; border-radius: 8px;
                font-weight: 600; font-size: 12px; padding: 8px 16px;
            }
        """
        self._btn_css_inactive = """
            QPushButton {
                background-color: transparent; color: #8E8EA0;
                border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px;
                font-size: 12px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.04); color: #ECECF1; }
        """

        self._analysis_mode_btn = QPushButton("📊 Analiz")
        self._analysis_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analysis_mode_btn.setStyleSheet(self._btn_css_active)
        self._analysis_mode_btn.clicked.connect(lambda: self._switch_mode("analysis"))

        self._chat_mode_btn = QPushButton("💬 Sohbet")
        self._chat_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_mode_btn.setStyleSheet(self._btn_css_inactive)
        self._chat_mode_btn.clicked.connect(lambda: self._switch_mode("chat"))

        mode_layout.addWidget(self._analysis_mode_btn, 1)
        mode_layout.addWidget(self._chat_mode_btn, 1)

        # ── Durum göstergesi ──────────────────────────────────────
        self._status_frame = QFrame()
        self._status_frame.setStyleSheet("background-color: transparent;")
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(20, 8, 20, 0)

        self._status_label = QLabel("Hazır")
        self._status_label.setStyleSheet("color: #8E8EA0; font-size: 12px;")

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("analysisProgress")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(2)
        self._progress_bar.hide()

        status_layout.addWidget(self._status_label)
        status_layout.addWidget(self._progress_bar)

        # ── AI çıktı alanı ────────────────────────────────────────
        self._output_area = QTextEdit()
        self._output_area.setObjectName("aiOutput")
        self._output_area.setReadOnly(True)
        self._output_area.setPlaceholderText(
            "📊 Ürün analizi için 'Analizi Başlat' butonuna tıklayın\n"
            "💬 Sohbet için üstteki 'Sohbet' sekmesine geçin"
        )
        self._output_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255,255,255,0.01);
                border: none; color: #ECECF1;
                font-size: 14px; line-height: 1.7; padding: 12px 16px;
                selection-background-color: rgba(108,99,255,0.25);
            }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.08); border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        # ── Analiz kontrol çubuğu ─────────────────────────────────
        self._analysis_controls = QFrame()
        self._analysis_controls.setStyleSheet("""
            QFrame { background-color: transparent; border-top: 1px solid rgba(255, 255, 255, 0.05); padding: 12px 20px; }
        """)
        ac_layout = QHBoxLayout(self._analysis_controls)
        ac_layout.setContentsMargins(0, 0, 0, 0)

        self._analyze_btn = QPushButton("Analizi Başlat")
        self._analyze_btn.setObjectName("accentButton")
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.clicked.connect(self._on_analyze_clicked)

        self._clear_btn = QPushButton("Temizle")
        self._clear_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8E8EA0; border: 1px solid rgba(255, 255, 255, 0.1); }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.05); color: #ECECF1; }
        """)
        self._clear_btn.clicked.connect(self._clear_output)

        ac_layout.addWidget(self._analyze_btn, 2)
        ac_layout.addWidget(self._clear_btn, 1)

        # ── Sohbet giriş çubuğu ──────────────────────────────────
        self._chat_controls = QFrame()
        self._chat_controls.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(17,17,24,0.95), stop:1 rgba(14,14,20,0.98));
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                padding: 10px 14px;
            }
        """)
        cc_layout = QHBoxLayout(self._chat_controls)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.setSpacing(8)

        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Bu sayfa hakkında bir şey sorun...")
        self._chat_input.setFixedHeight(40)
        self._chat_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px; color: #ECECF1; font-size: 13px;
                padding: 0 16px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(108, 99, 255, 0.45);
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        self._chat_input.returnPressed.connect(self._on_chat_send)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(40, 40)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6C63FF, stop:1 #4B4BFF);
                color: #FFFFFF; border: none; border-radius: 12px;
                font-size: 16px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7F77FF, stop:1 #5C5CFF);
            }
            QPushButton:disabled {
                background: #2A2A35; color: #565670;
            }
        """)
        self._send_btn.clicked.connect(self._on_chat_send)

        self._chat_clear_btn = QPushButton("🗑")
        self._chat_clear_btn.setFixedSize(40, 40)
        self._chat_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_clear_btn.setToolTip("Sohbeti temizle ve AI bağlamını sıfırla")
        self._chat_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 82, 82, 0.1); color: #FF5252;
                border: 1px solid rgba(255, 82, 82, 0.2); border-radius: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 82, 82, 0.25);
                border-color: rgba(255, 82, 82, 0.4);
            }
        """)
        self._chat_clear_btn.clicked.connect(self._clear_output)

        cc_layout.addWidget(self._chat_input, 1)
        cc_layout.addWidget(self._send_btn)
        cc_layout.addWidget(self._chat_clear_btn)
        self._chat_controls.hide()

        # ── Bellek bilgisi ────────────────────────────────────────
        self._memory_label = QLabel()
        self._memory_label.setObjectName("memoryLabel")
        self._memory_label.setStyleSheet("""
            color: #3A3A50; font-size: 10px; padding: 6px 16px;
            border-top: 1px solid rgba(255,255,255,0.03);
            letter-spacing: 0.3px;
        """)
        self._update_memory_label()

        # Düzen birleştirme
        layout.addWidget(header)
        layout.addWidget(mode_frame)
        layout.addWidget(self._status_frame)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._output_area, 1)
        layout.addWidget(self._analysis_controls)
        layout.addWidget(self._chat_controls)
        layout.addWidget(self._memory_label)

    # ── Mod Değiştirme ────────────────────────────────────────────

    def _switch_mode(self, mode: str) -> None:
        """Analiz / Sohbet modu arasında geçiş yapar."""
        self._current_mode = mode
        if mode == "analysis":
            self._analysis_mode_btn.setStyleSheet(self._btn_css_active)
            self._chat_mode_btn.setStyleSheet(self._btn_css_inactive)
            self._analysis_controls.show()
            self._chat_controls.hide()
            self._output_area.setPlaceholderText("📊 Ürün analizi için 'Analizi Başlat' butonuna tıklayın")
        else:
            self._chat_mode_btn.setStyleSheet(self._btn_css_active)
            self._analysis_mode_btn.setStyleSheet(self._btn_css_inactive)
            self._analysis_controls.hide()
            self._chat_controls.show()
            self._chat_input.setFocus()
            if not self._output_area.toPlainText().strip():
                self._output_area.setHtml(
                    '<div style="padding: 20px 10px; text-align: center;">'
                    '<div style="font-size: 28px; margin-bottom: 12px;">💬</div>'
                    '<div style="color: #565670; font-size: 13px; line-height: 1.8;">'
                    'Hangi sayfadaysanız onun hakkında<br>sorular sorabilirsiniz.<br><br>'
                    '<span style="color: #3A3A50;">'
                    '• Bu sayfa hakkında ne düşünüyorsun?<br>'
                    '• Bu sayfadaki bilgileri özetle<br>'
                    '• Bana bu konuyu açıkla'
                    '</span></div></div>'
                )

    def set_site_mode(self, mode: str) -> None:
        """
        Web sitesi türüne göre sidebar modunu ayarlar.
        mode: 'ecommerce' → analiz + sohbet göster
              'general'   → sadece sohbet göster
        """
        self._site_mode = mode
        if mode == "ecommerce":
            self._analysis_mode_btn.show()
            self._switch_mode("analysis")
        else:
            self._analysis_mode_btn.hide()
            self._switch_mode("chat")

    # ── Analiz İşlemleri ──────────────────────────────────────────

    def analyze_reviews(self, scraped_json: str) -> None:
        """Kazınan yorum verilerini alır ve LLM ile analiz başlatır."""
        try:
            data = json.loads(scraped_json)
        except json.JSONDecodeError:
            self._output_area.setText("⚠️ Yorum verileri ayrıştırılamadı.")
            return

        product_name = data.get("productName", "Bilinmeyen Ürün")
        review_count = len(data.get("reviews", []))
        qa_count = len(data.get("questions", []))
        self._status_label.setText(f"📦 {product_name} — {review_count} yorum, {qa_count} soru")

        if os.path.exists(config.LLM_MODEL_PATH):
            prompt = ReviewAnalyzer.build_prompt(data)
            self._start_llm_analysis(prompt)
        else:
            fallback = ReviewAnalyzer.format_fallback(data)
            self._output_area.setText(fallback)
            self._status_label.setText("Tamamlandı (LLM olmadan)")

    # ── Sohbet İşlemleri ──────────────────────────────────────────

    def _on_chat_send(self) -> None:
        """Sohbet mesajı gönderildiğinde."""
        message = self._chat_input.text().strip()
        if not message:
            return
        self._chat_input.clear()
        self._chat_history.append({"role": "user", "content": message})
        self._append_chat_message("Siz", message, "#6C63FF")
        self.chat_requested.emit(message)

    def process_chat_response(self, page_text: str, user_message: str) -> None:
        """Sayfa içeriği geldiğinde sohbet yanıtını üret."""
        if not os.path.exists(config.LLM_MODEL_PATH):
            self._append_chat_message("AI", "⚠️ LLM modeli yüklenmedi.", "#FF5252")
            return

        system_prompt = (
            "Sen bir alışveriş asistanısın. Kullanıcı şu anda bir web sayfasında geziniyor. "
            "Sayfa içeriğine göre sorularını yanıtla. Türkçe, kısa ve net cevaplar ver. "
            "Emoji kullanabilirsin.\n\n"
            f"Sayfadaki İçerik:\n{page_text[:3000]}"
        )
        prompt = f"{system_prompt}\n\nKullanıcı sorusu: {user_message}"
        self._start_llm_analysis(prompt, is_chat=True)

    def _append_chat_message(self, sender: str, message: str, color: str) -> None:
        """Sohbet mesajını modern balon formatında ekler."""
        is_user = sender == "Siz"
        accent = "#6C63FF" if is_user else color
        bg = "rgba(108,99,255,0.08)" if is_user else "rgba(0,217,255,0.05)"
        border = "rgba(108,99,255,0.2)" if is_user else f"{color}30"
        label = "SİZ" if is_user else "AI"
        safe = message.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

        html = f"""
        <div style="background: {bg}; border-left: 3px solid {accent};
                    border-radius: 0 10px 10px 0; padding: 10px 14px;
                    margin: 6px 0; border: 1px solid {border};
                    border-left: 3px solid {accent};">
            <div style="font-size: 10px; font-weight: 700; color: {accent};
                        letter-spacing: 1.5px; margin-bottom: 4px;">
                {label}
            </div>
            <div style="color: #E0E0E8; font-size: 13px; line-height: 1.6;">
                {safe}
            </div>
        </div>
        """
        self._output_area.append(html)
        from PyQt6.QtGui import QTextCursor
        self._output_area.moveCursor(QTextCursor.MoveOperation.End)

    # ── LLM Worker ────────────────────────────────────────────────

    def _start_llm_analysis(self, prompt: str, is_chat: bool = False) -> None:
        """LLM worker thread'ini başlatır."""
        if self._llm_worker and self._llm_worker.isRunning():
            self._llm_worker.terminate()

        if not is_chat:
            self._output_area.clear()

        self._progress_bar.show()
        self._analyze_btn.setEnabled(False)
        self._send_btn.setEnabled(False)

        if is_chat:
            self._append_chat_message("AI", "", "#00D9FF")

        self._llm_worker = LLMWorker(prompt, self)
        self._llm_worker.token_generated.connect(self._on_token)
        self._llm_worker.generation_complete.connect(self._on_complete)
        self._llm_worker.error_occurred.connect(self._on_error)
        self._llm_worker.status_update.connect(self._on_status)
        self._llm_worker.start()

    def _on_token(self, token: str) -> None:
        """Yeni token geldiğinde çıktıya ekle."""
        cursor = self._output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self._output_area.setTextCursor(cursor)
        self._output_area.ensureCursorVisible()

    def _on_complete(self, full_text: str) -> None:
        """Üretim tamamlandığında."""
        self._progress_bar.hide()
        self._analyze_btn.setEnabled(True)
        self._send_btn.setEnabled(True)
        self._status_label.setText("✅ Tamamlandı")
        self._status_label.setStyleSheet("color: #00E676; font-size: 12px;")
        self._update_memory_label()
        if self._current_mode == "chat":
            self._chat_history.append({"role": "assistant", "content": full_text})

    def _on_error(self, error_msg: str) -> None:
        """Hata durumunda."""
        self._progress_bar.hide()
        self._analyze_btn.setEnabled(True)
        self._send_btn.setEnabled(True)
        if self._current_mode == "chat":
            self._append_chat_message("AI", f"⚠️ {error_msg}", "#FF5252")
        else:
            self._output_area.setText(error_msg)
        self._status_label.setText("⚠️ Hata oluştu")
        self._status_label.setStyleSheet("color: #FF5252; font-size: 12px;")

    def _on_status(self, status: str) -> None:
        self._status_label.setText(status)

    def _on_analyze_clicked(self) -> None:
        self.analysis_requested.emit()

    def _clear_output(self) -> None:
        """Çıktıyı temizle ve LLM bağlamını sıfırla."""
        self._output_area.clear()
        self._chat_history.clear()
        self._status_label.setText("Hazır")
        self._status_label.setStyleSheet("color: #A0A0B0; font-size: 12px;")

        # LLM bağlamını sıfırla
        try:
            from resource_manager import SmartResourceManager
            rm = SmartResourceManager()
            rm.unload_llm()
            logger.info("LLM bağlamı sıfırlandı.")
        except Exception as e:
            logger.warning(f"LLM sıfırlama hatası: {e}")

    def _update_memory_label(self) -> None:
        try:
            rm = SmartResourceManager()
            stats = rm.get_memory_stats()
            models = ", ".join(stats["loaded_models"]) if stats["loaded_models"] else "Yok"
            self._memory_label.setText(f"💾 RAM: {stats['process_ram_mb']} MB | Modeller: {models}")
        except Exception:
            self._memory_label.setText("💾 RAM: — MB")

    def _animate_close(self) -> None:
        self.hide()

    def animate_open(self) -> None:
        self.show()
