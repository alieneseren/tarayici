"""
Visionary Navigator — Finansal Zekâ Arayüzü (Finance UI)
"Dark Terminal" tarzı PyQt6 kenar paneli.
Plotly candlestick grafikleri (QWebEngineView), tahmin bulutu, AL/SAT/TUT sinyalleri.

Tüm UI metinleri ve yorumlar Türkçe'dir.
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect, QSize, QUrl
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QProgressBar, QSizePolicy,
    QGraphicsDropShadowEffect, QCompleter
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

import config

# ─── Loglama ───────────────────────────────────────────────────────
logger = logging.getLogger("FinanceUI")
logger.setLevel(logging.INFO)

# ─── Stil Sabitleri — Dark Terminal Teması ─────────────────────────
TERMINAL_COLORS = {
    "bg": "#0A0A12",
    "bg_card": "#0F0F1A",
    "bg_input": "rgba(255,255,255,0.03)",
    "border": "rgba(0,255,136,0.12)",
    "border_active": "rgba(0,255,136,0.35)",
    "accent": "#00FF88",           # Terminal yeşili
    "accent_dim": "#00CC6A",
    "accent_glow": "rgba(0,255,136,0.15)",
    "red": "#FF4444",
    "red_dim": "#CC3333",
    "yellow": "#FFB800",
    "blue": "#4488FF",
    "cyan": "#00D9FF",
    "text": "#E0E8E4",
    "text_dim": "#6B7B72",
    "text_muted": "#3A4A42",
    "buy": "#00FF88",
    "sell": "#FF4444",
    "hold": "#FFB800",
}


# ═══════════════════════════════════════════════════════════════════
#  Plotly Grafik Oluşturucu (HTML çıktısı → QWebEngineView)
# ═══════════════════════════════════════════════════════════════════

class ChartBuilder:
    """
    Plotly ile interaktif grafiklerin HTML kodunu üretir.
    QWebEngineView'da görüntülenir — yüksek performanslı.
    """

    @staticmethod
    def build_candlestick_html(df_json: str, ticker: str,
                                prediction: Optional[Dict] = None,
                                show_indicators: bool = True) -> str:
        """
        Candlestick + hacim + teknik göstergeler + tahmin bulutu grafiği.
        Son 6 aylık veriyi gösterir (zoom ile tamamı görülebilir).
        """
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: {TERMINAL_COLORS["bg"]};
            font-family: 'Menlo', 'Fira Code', 'JetBrains Mono', monospace;
            overflow: hidden;
        }}
        #chart {{ width: 100%; height: 100vh; }}
        .loading {{
            display: flex; align-items: center; justify-content: center;
            height: 100vh; color: {TERMINAL_COLORS["accent"]}; font-size: 14px;
        }}
        .loading::after {{
            content: ''; width: 18px; height: 18px; margin-left: 12px;
            border: 2px solid {TERMINAL_COLORS["accent_dim"]};
            border-top-color: {TERMINAL_COLORS["accent"]};
            border-radius: 50%; animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div id="chart"><div class="loading">Grafik yükleniyor</div></div>
    <script>
    (function() {{
        const dfJson = {df_json};
        const ticker = "{ticker}";
        const predictionData = {json.dumps(prediction) if prediction else 'null'};
        const showIndicators = {'true' if show_indicators else 'false'};

        // JSON'dan DataFrame rekonstrüksiyonu
        const dates = Object.keys(dfJson.Close || {{}});
        if (dates.length === 0) {{
            document.getElementById('chart').innerHTML =
                '<div class="loading" style="color:{TERMINAL_COLORS["red"]}">Veri yok</div>';
            return;
        }}

        // Tarih sıralama
        dates.sort();

        // Son 180 gün (6 ay) görünür aralık
        const visibleStart = dates.length > 180 ? dates[dates.length - 180] : dates[0];
        const visibleEnd = dates[dates.length - 1];

        const open_vals = dates.map(d => dfJson.Open ? dfJson.Open[d] : null);
        const high_vals = dates.map(d => dfJson.High ? dfJson.High[d] : null);
        const low_vals = dates.map(d => dfJson.Low ? dfJson.Low[d] : null);
        const close_vals = dates.map(d => dfJson.Close[d]);
        const volume_vals = dates.map(d => dfJson.Volume ? dfJson.Volume[d] : 0);

        // Renk: yeşil = yükselen, kırmızı = düşen
        const colors = close_vals.map((c, i) =>
            c >= (open_vals[i] || c) ? '{TERMINAL_COLORS["accent"]}' : '{TERMINAL_COLORS["red"]}'
        );

        const traces = [];

        // ── Candlestick ──────────────────────────────
        traces.push({{
            x: dates, open: open_vals, high: high_vals,
            low: low_vals, close: close_vals,
            type: 'candlestick',
            name: ticker,
            increasing: {{ line: {{ color: '{TERMINAL_COLORS["accent"]}', width: 1 }} }},
            decreasing: {{ line: {{ color: '{TERMINAL_COLORS["red"]}', width: 1 }} }},
            xaxis: 'x', yaxis: 'y',
        }});

        // ── Teknik göstergeler ────────────────────────
        if (showIndicators) {{
            // SMA 20
            if (dfJson.SMA_20) {{
                const sma20 = dates.map(d => dfJson.SMA_20[d]);
                traces.push({{
                    x: dates, y: sma20, type: 'scatter', mode: 'lines',
                    name: 'SMA 20', line: {{ color: '{TERMINAL_COLORS["yellow"]}', width: 1, dash: 'dot' }},
                    yaxis: 'y', opacity: 0.7,
                }});
            }}
            // SMA 50
            if (dfJson.SMA_50) {{
                const sma50 = dates.map(d => dfJson.SMA_50[d]);
                traces.push({{
                    x: dates, y: sma50, type: 'scatter', mode: 'lines',
                    name: 'SMA 50', line: {{ color: '{TERMINAL_COLORS["cyan"]}', width: 1, dash: 'dot' }},
                    yaxis: 'y', opacity: 0.7,
                }});
            }}
            // Bollinger Bantları
            if (dfJson['BB_Üst'] && dfJson['BB_Alt']) {{
                const bbUpper = dates.map(d => dfJson['BB_Üst'][d]);
                const bbLower = dates.map(d => dfJson['BB_Alt'][d]);
                traces.push({{
                    x: dates, y: bbUpper, type: 'scatter', mode: 'lines',
                    name: 'BB Üst', line: {{ color: 'rgba(100,100,255,0.3)', width: 1 }},
                    yaxis: 'y', showlegend: false,
                }});
                traces.push({{
                    x: dates, y: bbLower, type: 'scatter', mode: 'lines',
                    name: 'BB Alt', line: {{ color: 'rgba(100,100,255,0.3)', width: 1 }},
                    fill: 'tonexty', fillcolor: 'rgba(100,100,255,0.04)',
                    yaxis: 'y', showlegend: false,
                }});
            }}
        }}

        // ── Tahmin Bulutu (Prediction Cloud) ─────────
        if (predictionData && predictionData.tarihler) {{
            const pDates = predictionData.tarihler;
            const pMean = predictionData.tahmin;
            const pUp95 = predictionData['üst_bant_95'];
            const pLow95 = predictionData['alt_bant_95'];
            const pUp80 = predictionData['üst_bant_80'];
            const pLow80 = predictionData['alt_bant_80'];

            // Geçiş noktası: son gerçek fiyat → ilk tahmin
            const lastReal = close_vals[close_vals.length - 1];
            const bridgeDates = [dates[dates.length-1], ...pDates];

            // %95 güven bandı
            traces.push({{
                x: bridgeDates,
                y: [lastReal, ...pUp95],
                type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }},
                showlegend: false, yaxis: 'y', hoverinfo: 'skip',
            }});
            traces.push({{
                x: bridgeDates,
                y: [lastReal, ...pLow95],
                type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }},
                fill: 'tonexty', fillcolor: 'rgba(0,255,136,0.06)',
                name: '%95 Güven', yaxis: 'y',
            }});

            // %80 güven bandı
            traces.push({{
                x: bridgeDates,
                y: [lastReal, ...pUp80],
                type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }},
                showlegend: false, yaxis: 'y', hoverinfo: 'skip',
            }});
            traces.push({{
                x: bridgeDates,
                y: [lastReal, ...pLow80],
                type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }},
                fill: 'tonexty', fillcolor: 'rgba(0,255,136,0.12)',
                name: '%80 Güven', yaxis: 'y',
            }});

            // Ortalama tahmin çizgisi
            traces.push({{
                x: bridgeDates,
                y: [lastReal, ...pMean],
                type: 'scatter', mode: 'lines+markers',
                name: 'LSTM Tahmin',
                line: {{ color: '{TERMINAL_COLORS["accent"]}', width: 2, dash: 'dash' }},
                marker: {{ size: 4, color: '{TERMINAL_COLORS["accent"]}' }},
                yaxis: 'y',
            }});
        }}

        // ── Hacim alt grafiği ────────────────────────
        traces.push({{
            x: dates, y: volume_vals, type: 'bar',
            name: 'Hacim', marker: {{ color: colors, opacity: 0.3 }},
            yaxis: 'y2', showlegend: false,
        }});

        // ── Layout ───────────────────────────────────
        const layout = {{
            paper_bgcolor: '{TERMINAL_COLORS["bg"]}',
            plot_bgcolor: '{TERMINAL_COLORS["bg"]}',
            font: {{
                family: "'Menlo', 'Fira Code', monospace",
                size: 10,
                color: '{TERMINAL_COLORS["text_dim"]}',
            }},
            margin: {{ l: 55, r: 15, t: 10, b: 30, pad: 0 }},
            showlegend: true,
            legend: {{
                x: 0.01, y: 0.99,
                bgcolor: 'rgba(10,10,18,0.85)',
                bordercolor: '{TERMINAL_COLORS["border"]}',
                borderwidth: 1,
                font: {{ size: 9, color: '{TERMINAL_COLORS["text_dim"]}' }},
                orientation: 'h',
            }},
            xaxis: {{
                type: 'date',
                range: [visibleStart, predictionData
                    ? predictionData.tarihler[predictionData.tarihler.length - 1]
                    : visibleEnd],
                rangeslider: {{ visible: false }},
                gridcolor: 'rgba(255,255,255,0.02)',
                linecolor: '{TERMINAL_COLORS["border"]}',
                tickfont: {{ size: 9 }},
                showgrid: true,
            }},
            yaxis: {{
                title: {{ text: 'Fiyat', font: {{ size: 10 }} }},
                side: 'right',
                gridcolor: 'rgba(255,255,255,0.03)',
                linecolor: '{TERMINAL_COLORS["border"]}',
                tickfont: {{ size: 9 }},
                domain: [0.22, 1],
            }},
            yaxis2: {{
                title: {{ text: 'Hacim', font: {{ size: 9 }} }},
                side: 'right',
                gridcolor: 'rgba(255,255,255,0.02)',
                linecolor: '{TERMINAL_COLORS["border"]}',
                tickfont: {{ size: 8 }},
                domain: [0, 0.18],
                showgrid: false,
            }},
            hovermode: 'x unified',
            hoverlabel: {{
                bgcolor: '#1A1A2E',
                bordercolor: '{TERMINAL_COLORS["border"]}',
                font: {{ size: 11, color: '{TERMINAL_COLORS["text"]}', family: 'monospace' }},
            }},
            dragmode: 'zoom',
        }};

        const plotConfig = {{
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
            displaylogo: false,
            scrollZoom: true,
        }};

        Plotly.newPlot('chart', traces, layout, plotConfig);
    }})();
    </script>
</body>
</html>
"""

    @staticmethod
    def build_mini_sparkline_html(prices: list, color: str = "#00FF88") -> str:
        """
        Mini sparkline SVG — ticker kartlarında kullanılır.
        Hafif, Plotly gerektirmez.
        """
        if not prices or len(prices) < 2:
            return ""

        w, h = 120, 35
        mn = min(prices)
        mx = max(prices)
        rng = mx - mn if mx != mn else 1

        points = []
        for i, p in enumerate(prices):
            x = (i / (len(prices) - 1)) * w
            y = h - ((p - mn) / rng) * (h - 4) - 2
            points.append(f"{x:.1f},{y:.1f}")

        polyline = " ".join(points)
        # Gradient fill altı
        fill_points = f"0,{h} " + polyline + f" {w},{h}"

        return f"""
        <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:{color};stop-opacity:0.2"/>
                    <stop offset="100%" style="stop-color:{color};stop-opacity:0"/>
                </linearGradient>
            </defs>
            <polygon points="{fill_points}" fill="url(#grad)" />
            <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" />
        </svg>
        """


# ═══════════════════════════════════════════════════════════════════
#  Ana Finans Sidebar Widget
# ═══════════════════════════════════════════════════════════════════

class FinanceSidebar(QWidget):
    """
    Finansal Zekâ Paneli — "Dark Terminal" tasarım.
    VisionaryBrowser'ın sol/sağ tarafına yüzen ada olarak eklenir.

    Özellikler:
    ──────────
    • Otomatik ticker tespiti (sayfa metninden)
    • Manuel ticker girişi
    • OHLCV candlestick grafik (Plotly, interaktif)
    • LSTM tahmin bulutu (Monte Carlo güven aralığı)
    • RSI, MACD, Bollinger Bands göstergeleri
    • AL/SAT/TUT sinyal konsensüsü
    • Teknik gösterge detay tablosu
    """

    # Dışarı yayılan sinyaller
    analysis_requested = pyqtSignal(str)     # Ticker analizi istendi
    close_requested = pyqtSignal()           # Panel kapatıldı
    fullscreen_requested = pyqtSignal(str)   # Tam ekran terminale geç (ticker)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("financeSidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setFixedWidth(420)

        # İç durum
        self._current_ticker: Optional[str] = None
        self._analysis_worker = None
        self._detected_tickers: List[Dict] = []

        # UI oluştur
        self._setup_ui()

        # Stil uygula
        self.setStyleSheet(f"""
            QWidget#financeSidebar {{
                background-color: {TERMINAL_COLORS["bg"]};
                border-radius: 16px;
                border: 1px solid {TERMINAL_COLORS["border"]};
            }}
        """)

    def _setup_ui(self) -> None:
        """Tüm panel bileşenlerini oluşturur."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Başlık Çubuğu ─────────────────────────────────────────
        header = self._create_header()
        layout.addWidget(header)

        # ── Arama / Ticker Girişi ──────────────────────────────────
        search_frame = self._create_search_bar()
        layout.addWidget(search_frame)

        # ── Tespit Edilen Ticker'lar (yatay scroll) ────────────────
        self._ticker_scroll = QWidget()
        self._ticker_scroll.setFixedHeight(44)
        self._ticker_scroll.setStyleSheet("background: transparent;")
        self._ticker_scroll_layout = QHBoxLayout(self._ticker_scroll)
        self._ticker_scroll_layout.setContentsMargins(12, 0, 12, 0)
        self._ticker_scroll_layout.setSpacing(6)
        self._ticker_scroll_layout.addStretch()
        self._ticker_scroll.hide()
        layout.addWidget(self._ticker_scroll)

        # ── Durum Çubuğu + İlerleme ───────────────────────────────
        status_frame = QFrame()
        status_frame.setStyleSheet("background: transparent;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(14, 4, 14, 4)

        self._status_icon = QLabel("●")
        self._status_icon.setStyleSheet(f"color: {TERMINAL_COLORS['text_muted']}; font-size: 8px;")
        self._status_label = QLabel("Hazır — Sembol girin veya sayfa taraması bekleyin")
        self._status_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
            font-family: 'Menlo', 'Fira Code', monospace;
        """)
        self._status_label.setWordWrap(True)

        status_layout.addWidget(self._status_icon)
        status_layout.addWidget(self._status_label, 1)
        layout.addWidget(status_frame)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(2)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255,255,255,0.02);
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {TERMINAL_COLORS["accent"]}, stop:1 {TERMINAL_COLORS["cyan"]});
                border-radius: 1px;
            }}
        """)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # ── Sinyal Kartı (AL/SAT/TUT) ─────────────────────────────
        self._signal_card = self._create_signal_card()
        self._signal_card.hide()
        layout.addWidget(self._signal_card)

        # ── Akıllı Karar Kartı (Yeni başlayanlar için) ────────────
        self._verdict_card = self._create_verdict_card()
        self._verdict_card.hide()
        layout.addWidget(self._verdict_card)

        # ── Fiyat Bilgi Kartı ──────────────────────────────────────
        self._price_card = self._create_price_card()
        self._price_card.hide()
        layout.addWidget(self._price_card)

        # ── Grafik Alanı (QWebEngineView — Plotly) ─────────────────
        self._chart_view = QWebEngineView()
        self._chart_view.setMinimumHeight(250)
        self._chart_view.setStyleSheet(f"background: {TERMINAL_COLORS['bg']};")
        self._chart_view.hide()
        layout.addWidget(self._chart_view, 1)

        # ── Teknik Gösterge Detay Alanı ────────────────────────────
        self._indicators_area = QScrollArea()
        self._indicators_area.setWidgetResizable(True)
        self._indicators_area.setFixedHeight(160)
        self._indicators_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 3px; }}
            QScrollBar::handle:vertical {{
                background: {TERMINAL_COLORS["border"]};
                border-radius: 1px; min-height: 15px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._indicators_container = QWidget()
        self._indicators_container.setStyleSheet("background: transparent;")
        self._indicators_layout = QVBoxLayout(self._indicators_container)
        self._indicators_layout.setContentsMargins(12, 4, 12, 4)
        self._indicators_layout.setSpacing(3)
        self._indicators_area.setWidget(self._indicators_container)
        self._indicators_area.hide()
        layout.addWidget(self._indicators_area)

        # ── Tahmin Özet Kartı ──────────────────────────────────────
        self._prediction_card = self._create_prediction_card()
        self._prediction_card.hide()
        layout.addWidget(self._prediction_card)

        # ── Alt Bilgi ─────────────────────────────────────────────
        footer = QLabel("⚠ Bu finansal tavsiye değildir. Yatırım kararlarınız size aittir.")
        footer.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_muted"]}; font-size: 9px;
            padding: 6px 14px; border-top: 1px solid {TERMINAL_COLORS["border"]};
            font-family: 'Menlo', monospace;
        """)
        footer.setWordWrap(True)
        layout.addWidget(footer)

    # ─── Bileşen Oluşturucular ────────────────────────────────────

    def _create_header(self) -> QFrame:
        """Terminal tarzı başlık çubuğu."""
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid {TERMINAL_COLORS["border"]};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 10, 10)

        # Terminal nokta ikonları
        dots = QLabel("● ● ●")
        dots.setStyleSheet("color: #333; font-size: 8px; letter-spacing: 4px;")

        # Başlık
        title = QLabel("📈 FİNANSAL ZEKÂ")
        title.setStyleSheet(f"""
            font-size: 13px; font-weight: 700;
            color: {TERMINAL_COLORS["accent"]};
            letter-spacing: 2px;
            font-family: 'Menlo', 'Fira Code', monospace;
        """)

        # Tam ekran butonu
        fullscreen_btn = QPushButton("□")
        fullscreen_btn.setFixedSize(26, 26)
        fullscreen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fullscreen_btn.setToolTip("Tam ekran terminalde aç")
        fullscreen_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TERMINAL_COLORS["text_muted"]};
                border: none; font-size: 13px;
            }}
            QPushButton:hover {{ color: {TERMINAL_COLORS["accent"]}; }}
        """)
        fullscreen_btn.clicked.connect(self._on_fullscreen)

        # Kapat butonu
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TERMINAL_COLORS["text_muted"]};
                border: none; font-size: 13px;
            }}
            QPushButton:hover {{ color: {TERMINAL_COLORS["red"]}; }}
        """)
        close_btn.clicked.connect(self._on_close)

        layout.addWidget(dots)
        layout.addSpacing(8)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(fullscreen_btn)
        layout.addWidget(close_btn)
        return header

    def _create_search_bar(self) -> QFrame:
        """Terminal tarzı arama çubuğu."""
        frame = QFrame()
        frame.setStyleSheet(f"background: transparent; padding: 4px 0;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        prompt = QLabel("$")
        prompt.setStyleSheet(f"""
            color: {TERMINAL_COLORS["accent"]}; font-size: 14px; font-weight: 700;
            font-family: 'Menlo', monospace;
        """)

        self._ticker_input = QLineEdit()
        self._ticker_input.setPlaceholderText("ticker girin... (AAPL, BTC-USD, THYAO.IS)")
        self._ticker_input.setStyleSheet(f"""
            QLineEdit {{
                background: {TERMINAL_COLORS["bg_input"]};
                border: 1px solid {TERMINAL_COLORS["border"]};
                border-radius: 8px;
                color: {TERMINAL_COLORS["text"]};
                font-size: 12px; padding: 7px 12px;
                font-family: 'Menlo', 'Fira Code', monospace;
            }}
            QLineEdit:focus {{
                border-color: {TERMINAL_COLORS["border_active"]};
                background: rgba(0,255,136,0.03);
            }}
        """)
        self._ticker_input.returnPressed.connect(self._on_manual_search)

        # Auto-complete
        completer_items = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'NFLX',
            'AMD', 'INTC', 'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD',
            'THYAO.IS', 'GARAN.IS', 'AKBNK.IS', 'SISE.IS', 'EREGL.IS',
            'BIMAS.IS', 'ASELS.IS', 'PGSUS.IS', 'TUPRS.IS',
        ]
        completer = QCompleter(completer_items)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._ticker_input.setCompleter(completer)

        go_btn = QPushButton("▶")
        go_btn.setFixedSize(34, 34)
        go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        go_btn.setStyleSheet(f"""
            QPushButton {{
                background: {TERMINAL_COLORS["accent_glow"]};
                border: 1px solid {TERMINAL_COLORS["border_active"]};
                border-radius: 8px; font-size: 13px;
                color: {TERMINAL_COLORS["accent"]};
            }}
            QPushButton:hover {{
                background: rgba(0,255,136,0.25);
                color: #FFFFFF;
            }}
        """)
        go_btn.clicked.connect(self._on_manual_search)

        # Sayfa tara butonu
        scan_btn = QPushButton("🔍")
        scan_btn.setFixedSize(34, 34)
        scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        scan_btn.setToolTip("Aktif sayfadaki ticker'ları tara")
        scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(68,136,255,0.1);
                border: 1px solid rgba(68,136,255,0.25);
                border-radius: 8px; font-size: 13px;
                color: {TERMINAL_COLORS["blue"]};
            }}
            QPushButton:hover {{
                background: rgba(68,136,255,0.2);
            }}
        """)
        scan_btn.clicked.connect(lambda: self.analysis_requested.emit("__SCAN__"))

        layout.addWidget(prompt)
        layout.addWidget(self._ticker_input, 1)
        layout.addWidget(go_btn)
        layout.addWidget(scan_btn)
        return frame

    def _create_verdict_card(self) -> QFrame:
        """
        Akıllı Karar kartı — borsayı bilmeyen birinin anlayacağı şekilde
        'Alayım mı almayayım mı?' sorusuna cevap verir.
        """
        card = QFrame()
        card.setObjectName("verdictCard")
        card.setStyleSheet(f"""
            QFrame#verdictCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(15,15,30,0.95), stop:1 rgba(8,8,18,0.95));
                border: 1px solid {TERMINAL_COLORS["border"]};
                border-radius: 12px;
                margin: 6px 12px;
            }}
        """)
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(6)

        # Başlık satırı: "🧩 ALAYIM MI?"
        header = QLabel("🧩 ALAYIM MI?")
        header.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_muted"]}; font-size: 9px;
            letter-spacing: 2px; font-weight: 700;
            font-family: 'Menlo', monospace;
        """)
        main_layout.addWidget(header)

        # Büyük emoji + karar
        top_row = QHBoxLayout()
        self._verdict_emoji_label = QLabel("⏳")
        self._verdict_emoji_label.setStyleSheet("font-size: 36px; padding: 0;")
        self._verdict_emoji_label.setFixedWidth(50)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        self._verdict_karar_label = QLabel("Analiz bekleniyor...")
        self._verdict_karar_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text"]}; font-size: 16px; font-weight: 800;
            font-family: 'Menlo', monospace;
        """)
        self._verdict_baslik_label = QLabel("")
        self._verdict_baslik_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 11px;
            font-family: 'Menlo', monospace;
        """)
        right_col.addWidget(self._verdict_karar_label)
        right_col.addWidget(self._verdict_baslik_label)

        top_row.addWidget(self._verdict_emoji_label)
        top_row.addLayout(right_col, 1)
        main_layout.addLayout(top_row)

        # Puan termometresi
        self._verdict_thermo_label = QLabel("⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪")
        self._verdict_thermo_label.setStyleSheet(f"""
            font-size: 12px; letter-spacing: 2px; padding: 4px 0;
        """)
        self._verdict_thermo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._verdict_thermo_label)

        # Puan / 10 etiketi
        self._verdict_puan_label = QLabel("— / 10")
        self._verdict_puan_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
            font-family: 'Menlo', monospace;
        """)
        self._verdict_puan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._verdict_puan_label)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {TERMINAL_COLORS['border']};")
        main_layout.addWidget(sep)

        # Özet açıklama (sade Türkçe)
        self._verdict_ozet_label = QLabel("")
        self._verdict_ozet_label.setWordWrap(True)
        self._verdict_ozet_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text"]}; font-size: 11px;
            line-height: 1.5; padding: 4px 0;
        """)
        main_layout.addWidget(self._verdict_ozet_label)

        # Risk seviyesi
        self._verdict_risk_label = QLabel("")
        self._verdict_risk_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
            font-family: 'Menlo', monospace; padding: 2px 0;
        """)
        main_layout.addWidget(self._verdict_risk_label)

        # Detay maddeleri
        self._verdict_details_label = QLabel("")
        self._verdict_details_label.setWordWrap(True)
        self._verdict_details_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
            line-height: 1.6; padding: 2px 0;
        """)
        main_layout.addWidget(self._verdict_details_label)

        # Yasal uyarı
        disclaimer = QLabel("⚠ Bu bir yatırım tavsiyesi değildir. Kararlarınız size aittir.")
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_muted"]}; font-size: 8px;
            font-style: italic; padding-top: 4px;
        """)
        main_layout.addWidget(disclaimer)

        return card

    def _update_verdict_card(self, verdict: Dict) -> None:
        """Akıllı Karar kartını günceller."""
        if not verdict:
            return

        karar = verdict.get("karar", "BEKLE")
        emoji = verdict.get("emoji", "🟡")
        baslik = verdict.get("başlık", "")
        puan = verdict.get("puan", 5)
        renk = verdict.get("renk", "hold")
        ozet = verdict.get("özet", "")
        risk_seviye = verdict.get("risk_seviyesi", "ORTA")
        risk_aciklama = verdict.get("risk_açıklama", "")
        termometre = verdict.get("termometre", "")
        madde_listesi = verdict.get("detay_maddeleri", [])

        color = TERMINAL_COLORS.get(renk, TERMINAL_COLORS["hold"])

        self._verdict_emoji_label.setText(emoji)
        self._verdict_karar_label.setText(karar)
        self._verdict_karar_label.setStyleSheet(f"""
            color: {color}; font-size: 16px; font-weight: 800;
            font-family: 'Menlo', monospace;
        """)
        self._verdict_baslik_label.setText(baslik)
        self._verdict_thermo_label.setText(termometre)
        self._verdict_puan_label.setText(f"{puan} / 10")
        self._verdict_puan_label.setStyleSheet(f"""
            color: {color}; font-size: 11px; font-weight: 700;
            font-family: 'Menlo', monospace;
        """)
        self._verdict_ozet_label.setText(ozet)

        # Risk seviyesi
        risk_colors = {
            "DÜŞÜK": TERMINAL_COLORS["buy"],
            "ORTA": TERMINAL_COLORS["hold"],
            "YÜKSEK": TERMINAL_COLORS["red"],
            "ÇOK YÜKSEK": TERMINAL_COLORS["red"],
        }
        risk_c = risk_colors.get(risk_seviye, TERMINAL_COLORS["hold"])
        risk_text = f"Risk: {risk_seviye}"
        if risk_aciklama:
            risk_text += f" — {risk_aciklama}"
        self._verdict_risk_label.setText(risk_text)
        self._verdict_risk_label.setStyleSheet(f"""
            color: {risk_c}; font-size: 10px;
            font-family: 'Menlo', monospace; padding: 2px 0;
        """)

        # Detay maddeleri
        if madde_listesi:
            self._verdict_details_label.setText("\n".join(madde_listesi))
            self._verdict_details_label.show()
        else:
            self._verdict_details_label.hide()

        # Kart kenarlık rengini karara göre değiştir
        self._verdict_card.setStyleSheet(f"""
            QFrame#verdictCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(15,15,30,0.95), stop:1 rgba(8,8,18,0.95));
                border: 1px solid {color};
                border-radius: 12px;
                margin: 6px 12px;
            }}
        """)

        self._verdict_card.show()

    def _create_signal_card(self) -> QFrame:
        """AL / SAT / TUT sinyal konsensüs kartı."""
        card = QFrame()
        card.setObjectName("signalCard")
        card.setStyleSheet(f"""
            QFrame#signalCard {{
                background: {TERMINAL_COLORS["bg_card"]};
                border: 1px solid {TERMINAL_COLORS["border"]};
                border-radius: 10px;
                margin: 6px 12px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        # Sol: Sinyal etiketi
        signal_col = QVBoxLayout()
        self._signal_label = QLabel("—")
        self._signal_label.setStyleSheet(f"""
            font-size: 22px; font-weight: 900;
            font-family: 'Menlo', monospace;
            letter-spacing: 2px;
        """)
        self._signal_sub = QLabel("sinyal bekleniyor")
        self._signal_sub.setStyleSheet(f"color: {TERMINAL_COLORS['text_dim']}; font-size: 10px;")
        signal_col.addWidget(self._signal_label)
        signal_col.addWidget(self._signal_sub)

        # Sağ: Güven skoru
        score_col = QVBoxLayout()
        score_col.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._confidence_label = QLabel("—%")
        self._confidence_label.setStyleSheet(f"""
            font-size: 26px; font-weight: 700;
            color: {TERMINAL_COLORS["text_dim"]};
            font-family: 'Menlo', monospace;
        """)
        self._confidence_sub = QLabel("AI Güven")
        self._confidence_sub.setStyleSheet(f"color: {TERMINAL_COLORS['text_muted']}; font-size: 9px; letter-spacing: 1px;")
        self._confidence_sub.setAlignment(Qt.AlignmentFlag.AlignRight)
        score_col.addWidget(self._confidence_label, alignment=Qt.AlignmentFlag.AlignRight)
        score_col.addWidget(self._confidence_sub)

        layout.addLayout(signal_col)
        layout.addStretch()
        layout.addLayout(score_col)
        return card

    def _create_price_card(self) -> QFrame:
        """Fiyat bilgi kartı."""
        card = QFrame()
        card.setObjectName("priceCard")
        card.setStyleSheet(f"""
            QFrame#priceCard {{
                background: {TERMINAL_COLORS["bg_card"]};
                border: 1px solid {TERMINAL_COLORS["border"]};
                border-radius: 10px;
                margin: 0 12px 6px 12px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 8, 14, 8)

        # Ticker adı + fiyat
        left = QVBoxLayout()
        self._ticker_name_label = QLabel("—")
        self._ticker_name_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text"]};
            font-size: 14px; font-weight: 600;
            font-family: 'Menlo', monospace;
        """)
        self._price_label = QLabel("$0.00")
        self._price_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["accent"]};
            font-size: 20px; font-weight: 700;
            font-family: 'Menlo', monospace;
        """)
        left.addWidget(self._ticker_name_label)
        left.addWidget(self._price_label)

        # Değişim + hacim
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._change_label = QLabel("0.00%")
        self._change_label.setStyleSheet(f"""
            font-size: 14px; font-weight: 600;
            font-family: 'Menlo', monospace;
        """)
        self._volume_label = QLabel("Hacim: —")
        self._volume_label.setStyleSheet(f"color: {TERMINAL_COLORS['text_muted']}; font-size: 9px;")
        self._volume_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._change_label, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._volume_label)

        layout.addLayout(left)
        layout.addStretch()
        layout.addLayout(right)
        return card

    def _create_prediction_card(self) -> QFrame:
        """Tahmin özet kartı."""
        card = QFrame()
        card.setObjectName("predCard")
        card.setStyleSheet(f"""
            QFrame#predCard {{
                background: {TERMINAL_COLORS["bg_card"]};
                border: 1px solid {TERMINAL_COLORS["border"]};
                border-radius: 10px;
                margin: 6px 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Başlık
        pred_title = QLabel("🔮 LSTM TAHMİN ÖZETİ")
        pred_title.setStyleSheet(f"""
            color: {TERMINAL_COLORS["accent"]}; font-size: 10px;
            font-weight: 700; letter-spacing: 1.5px;
            font-family: 'Menlo', monospace;
        """)
        layout.addWidget(pred_title)

        # Tahmin detayları
        self._pred_direction_label = QLabel("—")
        self._pred_direction_label.setStyleSheet(f"""
            font-size: 13px; font-weight: 600;
            font-family: 'Menlo', monospace;
        """)
        layout.addWidget(self._pred_direction_label)

        self._pred_range_label = QLabel("Aralık: —")
        self._pred_range_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
            font-family: 'Menlo', monospace;
        """)
        layout.addWidget(self._pred_range_label)

        self._pred_confidence_label = QLabel("Güven: —")
        self._pred_confidence_label.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_muted"]}; font-size: 10px;
            font-family: 'Menlo', monospace;
        """)
        layout.addWidget(self._pred_confidence_label)

        return card

    # ─── Sinyal / Veri Güncelleme Metotları ────────────────────────

    def update_detected_tickers(self, tickers: list) -> None:
        """Tespit edilen ticker'ları yatay buton listesi olarak gösterir."""
        # Önceki butonları temizle
        while self._ticker_scroll_layout.count() > 1:
            item = self._ticker_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._detected_tickers = tickers

        if not tickers:
            self._ticker_scroll.hide()
            return

        for t in tickers[:6]:  # Maksimum 6 ticker göster
            sym = t["sembol"]
            conf = t.get("güven", 0)
            btn = QPushButton(sym)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {TERMINAL_COLORS["accent_glow"]};
                    border: 1px solid {TERMINAL_COLORS["border"]};
                    border-radius: 6px; padding: 0 10px;
                    color: {TERMINAL_COLORS["accent"]};
                    font-size: 11px; font-weight: 600;
                    font-family: 'Menlo', monospace;
                }}
                QPushButton:hover {{
                    background: rgba(0,255,136,0.2);
                    border-color: {TERMINAL_COLORS["border_active"]};
                }}
            """)
            btn.clicked.connect(lambda _, s=sym: self.start_analysis(s))
            self._ticker_scroll_layout.insertWidget(self._ticker_scroll_layout.count() - 1, btn)

        self._ticker_scroll.show()

    def start_analysis(self, ticker: str) -> None:
        """Belirtilen ticker için tam analiz başlatır."""
        from finance_engine import FinanceAnalysisWorker

        ticker = ticker.strip().upper()
        if not ticker:
            return

        # Önceki worker'ı iptal et
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.cancel()
            self._analysis_worker.quit()
            self._analysis_worker.wait(2000)

        self._current_ticker = ticker
        self._ticker_input.setText(ticker)

        # UI'ı sıfırla
        self._signal_card.hide()
        self._verdict_card.hide()
        self._price_card.hide()
        self._chart_view.hide()
        self._indicators_area.hide()
        self._prediction_card.hide()
        self._progress_bar.show()
        self._progress_bar.setValue(0)

        # Durum güncelle
        self._update_status(f"Analiz başlatılıyor: {ticker}", "working")

        # Worker oluştur ve başlat
        self._analysis_worker = FinanceAnalysisWorker(ticker)
        self._analysis_worker.status_update.connect(self._on_status_update)
        self._analysis_worker.progress_update.connect(self._on_progress_update)
        self._analysis_worker.data_ready.connect(self._on_data_ready)
        self._analysis_worker.prediction_ready.connect(self._on_prediction_ready)
        self._analysis_worker.analysis_complete.connect(self._on_analysis_complete)
        self._analysis_worker.error_occurred.connect(self._on_error)
        self._analysis_worker.start()

    # ─── Worker Sinyal İşleyicileri ────────────────────────────────

    def _on_status_update(self, message: str) -> None:
        """Durum mesajı güncelleme."""
        self._update_status(message, "working")

    def _on_progress_update(self, value: int) -> None:
        """İlerleme çubuğu güncelleme."""
        self._progress_bar.setValue(value)
        if value >= 100:
            QTimer.singleShot(1500, self._progress_bar.hide)

    def _on_data_ready(self, data: dict) -> None:
        """Tarihsel veri ve göstergeler hazır — grafik çiz."""
        ticker = data["ticker"]
        df_json = data["df"]
        signals = data.get("signals", {})
        info = data.get("info")

        # Fiyat kartını güncelle
        self._update_price_card(ticker, df_json, info)

        # Sinyal kartını güncelle
        self._update_signal_card(signals)

        # Gösterge detaylarını güncelle
        self._update_indicators(signals.get("detay", {}))

        # Grafiği çiz (henüz tahmin yok)
        html = ChartBuilder.build_candlestick_html(df_json, ticker)
        self._chart_view.setHtml(html)
        self._chart_view.show()

    def _on_prediction_ready(self, prediction: dict) -> None:
        """LSTM tahmin sonuçları hazır — grafiği güncelle."""
        if not self._current_ticker:
            return

        # Tahmin kartını güncelle
        self._update_prediction_card(prediction)

        # Grafiği tahmin ile yeniden çiz
        # Not: Mevcut df_json'u worker'dan tekrar almamız gerekiyor,
        # bu yüzden analysis_complete'de nihai çizim yapılacak
        self._prediction_card.show()

    def _on_analysis_complete(self, result: dict) -> None:
        """Tüm analiz tamamlandı — nihai güncelleme."""
        ticker = result["ticker"]
        prediction = result.get("tahmin")

        # Akıllı Karar kartını güncelle
        verdict = result.get("verdict")
        if verdict:
            self._update_verdict_card(verdict)

        self._update_status(f"✅ {ticker} analizi tamamlandı", "success")
        self._progress_bar.hide()

        logger.info(f"Analiz tamamlandı: {ticker} — Sinyal: {result.get('sinyal', {}).get('sinyal', '?')}")

    def _on_error(self, error_msg: str) -> None:
        """Hata durumu."""
        self._update_status(error_msg, "error")
        self._progress_bar.hide()

    # ─── UI Güncelleme Yardımcıları ────────────────────────────────

    def _update_status(self, message: str, state: str = "idle") -> None:
        """Durum çubuğunu günceller."""
        colors = {
            "idle": TERMINAL_COLORS["text_muted"],
            "working": TERMINAL_COLORS["yellow"],
            "success": TERMINAL_COLORS["accent"],
            "error": TERMINAL_COLORS["red"],
        }
        color = colors.get(state, TERMINAL_COLORS["text_dim"])
        self._status_icon.setStyleSheet(f"color: {color}; font-size: 8px;")
        self._status_label.setText(message)

    def _update_price_card(self, ticker: str, df_json: str, info: Optional[Dict]) -> None:
        """Fiyat bilgi kartını günceller."""
        try:
            df_dict = json.loads(df_json)
            close_data = df_dict.get("Close", {})
            dates = sorted(close_data.keys())

            if not dates:
                return

            last_price = close_data[dates[-1]]
            prev_price = close_data[dates[-2]] if len(dates) > 1 else last_price
            change_pct = ((last_price - prev_price) / prev_price) * 100 if prev_price else 0

            # Şirket adı
            name = ticker
            if info:
                name = info.get("ad", ticker)

            self._ticker_name_label.setText(f"{ticker} — {name[:25]}")

            # Para birimi sembolü
            currency = "$"
            if info:
                curr = info.get("para_birimi", "USD")
                if curr == "TRY":
                    currency = "₺"
                elif curr == "EUR":
                    currency = "€"
                elif curr == "GBP":
                    currency = "£"

            self._price_label.setText(f"{currency}{last_price:,.2f}")

            # Değişim rengi
            if change_pct >= 0:
                self._change_label.setText(f"▲ +{change_pct:.2f}%")
                self._change_label.setStyleSheet(f"""
                    color: {TERMINAL_COLORS["buy"]}; font-size: 14px;
                    font-weight: 600; font-family: 'Menlo', monospace;
                """)
            else:
                self._change_label.setText(f"▼ {change_pct:.2f}%")
                self._change_label.setStyleSheet(f"""
                    color: {TERMINAL_COLORS["sell"]}; font-size: 14px;
                    font-weight: 600; font-family: 'Menlo', monospace;
                """)

            # Hacim
            volume_data = df_dict.get("Volume", {})
            if dates[-1] in volume_data:
                vol = volume_data[dates[-1]]
                if vol >= 1e9:
                    vol_str = f"{vol/1e9:.1f}B"
                elif vol >= 1e6:
                    vol_str = f"{vol/1e6:.1f}M"
                elif vol >= 1e3:
                    vol_str = f"{vol/1e3:.0f}K"
                else:
                    vol_str = str(int(vol))
                self._volume_label.setText(f"Hacim: {vol_str}")

            self._price_card.show()

        except Exception as e:
            logger.warning(f"Fiyat kartı güncelleme hatası: {e}")

    def _update_signal_card(self, signals: Dict) -> None:
        """Sinyal konsensüs kartını günceller."""
        final_signal = signals.get("sinyal", "BELİRSİZ")
        confidence = signals.get("güven", 0)

        # Sinyal renkleri
        signal_colors = {
            "GÜÇLÜ AL": TERMINAL_COLORS["buy"],
            "AL": TERMINAL_COLORS["buy"],
            "TUT": TERMINAL_COLORS["hold"],
            "SAT": TERMINAL_COLORS["sell"],
            "GÜÇLÜ SAT": TERMINAL_COLORS["sell"],
            "BELİRSİZ": TERMINAL_COLORS["text_dim"],
        }
        color = signal_colors.get(final_signal, TERMINAL_COLORS["text_dim"])

        self._signal_label.setText(final_signal)
        self._signal_label.setStyleSheet(f"""
            font-size: 22px; font-weight: 900;
            font-family: 'Menlo', monospace;
            letter-spacing: 2px; color: {color};
        """)

        self._signal_sub.setText(f"Teknik Konsensüs ({signals.get('puan', 0):+d} puan)")

        self._confidence_label.setText(f"{confidence:.0f}%")
        self._confidence_label.setStyleSheet(f"""
            font-size: 26px; font-weight: 700;
            color: {color};
            font-family: 'Menlo', monospace;
        """)

        self._signal_card.show()

    def _update_indicators(self, details: Dict) -> None:
        """Teknik gösterge detay tablosunu günceller."""
        # Önceki göstergeleri temizle
        while self._indicators_layout.count():
            item = self._indicators_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not details:
            return

        # Başlık
        title = QLabel("─── TEKNİK GÖSTERGELER ───")
        title.setStyleSheet(f"""
            color: {TERMINAL_COLORS["text_muted"]}; font-size: 9px;
            letter-spacing: 1px; padding: 4px 0;
            font-family: 'Menlo', monospace;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicators_layout.addWidget(title)

        for name, data in details.items():
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: rgba(255,255,255,0.015);
                    border-radius: 5px;
                    padding: 2px;
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 3, 8, 3)
            row_layout.setSpacing(4)

            # Gösterge adı
            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(90)
            name_lbl.setStyleSheet(f"""
                color: {TERMINAL_COLORS["text_dim"]}; font-size: 10px;
                font-family: 'Menlo', monospace;
            """)

            # Yön sembolü
            direction = data.get("yön", "NÖTR")
            dir_colors = {
                "AL": TERMINAL_COLORS["buy"],
                "SAT": TERMINAL_COLORS["sell"],
                "NÖTR": TERMINAL_COLORS["hold"],
            }
            dir_color = dir_colors.get(direction, TERMINAL_COLORS["text_dim"])
            dir_symbol = {"AL": "▲", "SAT": "▼", "NÖTR": "●"}.get(direction, "●")

            dir_lbl = QLabel(f"{dir_symbol} {direction}")
            dir_lbl.setFixedWidth(55)
            dir_lbl.setStyleSheet(f"""
                color: {dir_color}; font-size: 10px; font-weight: 600;
                font-family: 'Menlo', monospace;
            """)

            # Değer
            val_lbl = QLabel(str(data.get("değer", "—")))
            val_lbl.setStyleSheet(f"""
                color: {TERMINAL_COLORS["text_dim"]}; font-size: 9px;
                font-family: 'Menlo', monospace;
            """)
            val_lbl.setWordWrap(True)

            row_layout.addWidget(name_lbl)
            row_layout.addWidget(dir_lbl)
            row_layout.addWidget(val_lbl, 1)

            self._indicators_layout.addWidget(row)

        self._indicators_area.show()

    def _update_prediction_card(self, prediction: Dict) -> None:
        """Tahmin özet kartını günceller."""
        if not prediction or not prediction.get("tahmin"):
            return

        preds = prediction["tahmin"]
        last_pred = preds[-1]
        first_pred = preds[0]

        # Yön tespiti
        if last_pred > first_pred * 1.02:
            direction = "YÜKSELİŞ ▲"
            dir_color = TERMINAL_COLORS["buy"]
        elif last_pred < first_pred * 0.98:
            direction = "DÜŞÜŞ ▼"
            dir_color = TERMINAL_COLORS["sell"]
        else:
            direction = "YATAY ●"
            dir_color = TERMINAL_COLORS["hold"]

        self._pred_direction_label.setText(f"{len(preds)} günlük tahmin: {direction}")
        self._pred_direction_label.setStyleSheet(f"""
            font-size: 13px; font-weight: 600;
            font-family: 'Menlo', monospace;
            color: {dir_color};
        """)

        # Aralık
        up95 = prediction.get("üst_bant_95", preds)
        low95 = prediction.get("alt_bant_95", preds)
        if up95 and low95:
            self._pred_range_label.setText(
                f"Aralık: {min(low95):,.2f} — {max(up95):,.2f}"
            )

        # Ortalama güven (std bazlı)
        stds = prediction.get("std", [])
        if stds and preds:
            avg_pct_std = (sum(stds) / len(stds)) / (sum(preds) / len(preds)) * 100
            confidence = max(0, min(100, 100 - avg_pct_std * 5))
            self._pred_confidence_label.setText(f"Model Güveni: %{confidence:.0f}")

        self._prediction_card.show()

    # ─── Kullanıcı Etkileşimi ──────────────────────────────────────

    def _on_manual_search(self) -> None:
        """Manuel ticker girişi ile analiz başlat."""
        ticker = self._ticker_input.text().strip().upper()
        if ticker:
            self.start_analysis(ticker)

    def _on_close(self) -> None:
        """Panel kapatma."""
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.cancel()
            self._analysis_worker.quit()
        self.hide()
        self.close_requested.emit()

    def _on_fullscreen(self) -> None:
        """Tam ekran finans terminaline geçiş."""
        ticker = self._current_ticker or ""
        self.fullscreen_requested.emit(ticker)

    def scan_page(self, url: str, page_text: str) -> None:
        """
        Aktif sayfayı tarayarak ticker'ları tespit eder.
        browser_core.py'den çağrılır.
        """
        from finance_engine import TickerDetectionWorker

        self._update_status("🔍 Sayfa taranıyor...", "working")

        worker = TickerDetectionWorker(url, page_text)
        worker.tickers_found.connect(self._on_tickers_detected)
        worker.error_occurred.connect(lambda e: self._update_status(f"Tarama hatası: {e}", "error"))
        worker.start()

        # Worker referansını tut (GC koruması)
        self._scan_worker = worker

    def _on_tickers_detected(self, tickers: list) -> None:
        """Sayfa taramasından ticker'lar bulundu."""
        if tickers:
            self._update_status(f"✅ {len(tickers)} sembol tespit edildi", "success")
            self.update_detected_tickers(tickers)
            # En güvenilir ticker'ı otomatik analiz et
            self.start_analysis(tickers[0]["sembol"])
        else:
            self._update_status("Bu sayfada finansal sembol bulunamadı", "idle")
