"""
Visionary Navigator — Tam Ekran Finansal Zekâ Sayfası
"Bloomberg Terminal" tarzı profesyonel finans arayüzü.

Sidebar'daki küçük panel yerine tüm sekme alanını kullanan gelişmiş sürüm:
  ▸ 6 panelli ızgara düzeni (dashboard)
  ▸ Büyük interaktif Plotly grafik (candlestick + tahmin bulutu)
  ▸ Watchlist — birden fazla ticker takibi
  ▸ Detaylı teknik gösterge tablosu (RSI, MACD, BB, SMA, EMA)
  ▸ Haber / duyarlılık analizi özeti
  ▸ Tahmin özet kartı + güven metrikleri
  ▸ Piyasa özeti satırı (BIST100, S&P500, BTC, EUR/TRY)

Tüm UI metinleri ve yorumlar Türkçe'dir.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QUrl, QSize
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QProgressBar, QSizePolicy,
    QGraphicsDropShadowEffect, QCompleter, QSplitter
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

import config

logger = logging.getLogger("FinanceFullPage")
logger.setLevel(logging.INFO)

# ─── Terminal Renk Paleti (Sidebar ile uyumlu) ─────────────────────
TC = {
    "bg":           "#06060E",
    "bg_panel":     "#0A0A14",
    "bg_card":      "#0E0E1A",
    "bg_input":     "rgba(255,255,255,0.03)",
    "bg_hover":     "rgba(0,255,136,0.04)",
    "border":       "rgba(0,255,136,0.10)",
    "border_active":"rgba(0,255,136,0.35)",
    "accent":       "#00FF88",
    "accent_dim":   "#00CC6A",
    "accent_glow":  "rgba(0,255,136,0.12)",
    "red":          "#FF4444",
    "red_dim":      "#CC3333",
    "yellow":       "#FFB800",
    "blue":         "#4488FF",
    "cyan":         "#00D9FF",
    "purple":       "#A78BFA",
    "text":         "#E0E8E4",
    "text_dim":     "#6B7B72",
    "text_muted":   "#2A3A32",
    "buy":          "#00FF88",
    "sell":         "#FF4444",
    "hold":         "#FFB800",
    "separator":    "rgba(255,255,255,0.04)",
}

# ─── Popüler ticker listesi (auto-complete) ───────────────────────
_POPULAR_TICKERS = [
    # ABD
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX",
    "AMD", "INTC", "DIS", "BA", "JPM", "V", "WMT", "KO", "PEP",
    # Kripto
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "ADA-USD", "DOGE-USD",
    # BIST
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "SISE.IS", "EREGL.IS", "BIMAS.IS",
    "ASELS.IS", "PGSUS.IS", "TUPRS.IS", "SAHOL.IS", "KCHOL.IS", "TCELL.IS",
    "YKBNK.IS", "HALKB.IS", "VAKBN.IS", "TOASO.IS", "SASA.IS",
    # Endeksler
    "^GSPC", "^IXIC", "^DJI", "XU100.IS",
    # Döviz
    "USDTRY=X", "EURTRY=X", "GBPTRY=X",
]


# ═══════════════════════════════════════════════════════════════════
#  Tam Ekran Grafik Oluşturucu (Plotly HTML — Geniş ekran optimize)
# ═══════════════════════════════════════════════════════════════════

class FullPageChartBuilder:
    """Geniş ekran için optimize Plotly grafikler üretir."""

    @staticmethod
    def build_advanced_chart_html(df_json: str, ticker: str,
                                   prediction: Optional[Dict] = None,
                                   rsi_data: bool = True) -> str:
        """
        Ana grafik — Candlestick + Hacim + RSI alt panel + Tahmin bulutu.
        Tam ekran genişliğine uyumlu, çoklu subplot destekli.
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
            background: {TC["bg"]};
            font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
            overflow: hidden;
        }}
        #chart {{ width: 100%; height: 100vh; }}
        .loading {{
            display: flex; align-items: center; justify-content: center;
            height: 100vh; color: {TC["accent"]}; font-size: 14px;
            font-family: 'SF Mono', monospace;
        }}
        .loading::after {{
            content: ''; width: 18px; height: 18px; margin-left: 12px;
            border: 2px solid {TC["accent_dim"]};
            border-top-color: {TC["accent"]};
            border-radius: 50%; animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div id="chart"><div class="loading">Grafik oluşturuluyor</div></div>
    <script>
    (function() {{
        const dfJson = {df_json};
        const ticker = "{ticker}";
        const predData = {json.dumps(prediction) if prediction else 'null'};

        const dates = Object.keys(dfJson.Close || {{}});
        if (dates.length === 0) {{
            document.getElementById('chart').innerHTML =
                '<div class="loading" style="color:{TC["red"]}">Veri bulunamadı</div>';
            return;
        }}
        dates.sort();

        // Son 1 yıl varsayılan görünüm
        const visibleStart = dates.length > 252 ? dates[dates.length - 252] : dates[0];
        const visibleEnd = dates[dates.length - 1];

        const o = dates.map(d => dfJson.Open ? dfJson.Open[d] : null);
        const h = dates.map(d => dfJson.High ? dfJson.High[d] : null);
        const l = dates.map(d => dfJson.Low  ? dfJson.Low[d]  : null);
        const c = dates.map(d => dfJson.Close[d]);
        const v = dates.map(d => dfJson.Volume ? dfJson.Volume[d] : 0);

        const barColors = c.map((cv, i) =>
            cv >= (o[i] || cv) ? '{TC["accent"]}' : '{TC["red"]}'
        );

        const traces = [];

        // ── 1) Candlestick ───────────────────
        traces.push({{
            x: dates, open: o, high: h, low: l, close: c,
            type: 'candlestick', name: ticker,
            increasing: {{ line: {{ color: '{TC["accent"]}', width: 1 }} }},
            decreasing: {{ line: {{ color: '{TC["red"]}', width: 1 }} }},
            xaxis: 'x', yaxis: 'y',
        }});

        // ── 2) SMA Çizgileri ─────────────────
        const smaColors = {{
            'SMA_20': ['{TC["yellow"]}', 'dot'],
            'SMA_50': ['{TC["cyan"]}', 'dot'],
            'SMA_200': ['{TC["purple"]}', 'dash'],
            'EMA_12': ['{TC["blue"]}', 'dashdot'],
        }};
        for (const [key, [clr, dsh]] of Object.entries(smaColors)) {{
            if (dfJson[key]) {{
                traces.push({{
                    x: dates, y: dates.map(d => dfJson[key][d]),
                    type: 'scatter', mode: 'lines',
                    name: key.replace('_', ' '),
                    line: {{ color: clr, width: 1, dash: dsh }},
                    yaxis: 'y', opacity: 0.7,
                }});
            }}
        }}

        // ── 3) Bollinger Bantları ────────────
        if (dfJson['BB_Üst'] && dfJson['BB_Alt']) {{
            const bbU = dates.map(d => dfJson['BB_Üst'][d]);
            const bbL = dates.map(d => dfJson['BB_Alt'][d]);
            traces.push({{
                x: dates, y: bbU, type: 'scatter', mode: 'lines',
                name: 'BB Üst', line: {{ color: 'rgba(100,100,255,0.3)', width: 1 }},
                yaxis: 'y', showlegend: false,
            }});
            traces.push({{
                x: dates, y: bbL, type: 'scatter', mode: 'lines',
                name: 'BB Alt', line: {{ color: 'rgba(100,100,255,0.3)', width: 1 }},
                fill: 'tonexty', fillcolor: 'rgba(100,100,255,0.04)',
                yaxis: 'y', showlegend: false,
            }});
        }}

        // ── 4) Tahmin Bulutu ─────────────────
        if (predData && predData.tarihler) {{
            const pD = predData.tarihler;
            const pM = predData.tahmin;
            const pU95 = predData['üst_bant_95'];
            const pL95 = predData['alt_bant_95'];
            const pU80 = predData['üst_bant_80'];
            const pL80 = predData['alt_bant_80'];
            const lastC = c[c.length - 1];
            const bridge = [dates[dates.length-1], ...pD];

            // %95 bant
            traces.push({{ x: bridge, y: [lastC, ...pU95], type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }}, showlegend: false, yaxis: 'y', hoverinfo: 'skip' }});
            traces.push({{ x: bridge, y: [lastC, ...pL95], type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }}, fill: 'tonexty',
                fillcolor: 'rgba(0,255,136,0.06)', name: '%95 Güven', yaxis: 'y' }});
            // %80 bant
            traces.push({{ x: bridge, y: [lastC, ...pU80], type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }}, showlegend: false, yaxis: 'y', hoverinfo: 'skip' }});
            traces.push({{ x: bridge, y: [lastC, ...pL80], type: 'scatter', mode: 'lines',
                line: {{ color: 'transparent' }}, fill: 'tonexty',
                fillcolor: 'rgba(0,255,136,0.12)', name: '%80 Güven', yaxis: 'y' }});
            // Ortalama tahmin çizgisi
            traces.push({{
                x: bridge, y: [lastC, ...pM],
                type: 'scatter', mode: 'lines+markers',
                name: (predData.yöntem || 'Tahmin'),
                line: {{ color: '{TC["accent"]}', width: 2, dash: 'dash' }},
                marker: {{ size: 4, color: '{TC["accent"]}' }},
                yaxis: 'y',
            }});
        }}

        // ── 5) Hacim barları ─────────────────
        traces.push({{
            x: dates, y: v, type: 'bar', name: 'Hacim',
            marker: {{ color: barColors, opacity: 0.3 }},
            yaxis: 'y2', showlegend: false,
        }});

        // ── 6) RSI alt grafiği ───────────────
        let hasRSI = false;
        if (dfJson['RSI']) {{
            hasRSI = true;
            const rsiVals = dates.map(d => dfJson['RSI'][d]);
            traces.push({{
                x: dates, y: rsiVals, type: 'scatter', mode: 'lines',
                name: 'RSI', line: {{ color: '{TC["purple"]}', width: 1.5 }},
                yaxis: 'y3',
            }});
            // Aşırı alım / satım çizgileri
            traces.push({{
                x: [dates[0], dates[dates.length-1]], y: [70, 70],
                type: 'scatter', mode: 'lines',
                line: {{ color: '{TC["red"]}', width: 0.5, dash: 'dot' }},
                yaxis: 'y3', showlegend: false, hoverinfo: 'skip',
            }});
            traces.push({{
                x: [dates[0], dates[dates.length-1]], y: [30, 30],
                type: 'scatter', mode: 'lines',
                line: {{ color: '{TC["accent"]}', width: 0.5, dash: 'dot' }},
                yaxis: 'y3', showlegend: false, hoverinfo: 'skip',
            }});
        }}

        // ── Layout (3 subplot: fiyat + hacim + RSI) ──
        const endRange = predData ? predData.tarihler[predData.tarihler.length - 1] : visibleEnd;

        const layout = {{
            paper_bgcolor: '{TC["bg"]}',
            plot_bgcolor: '{TC["bg"]}',
            font: {{ family: "'SF Mono', 'Fira Code', monospace", size: 10, color: '{TC["text_dim"]}' }},
            margin: {{ l: 60, r: 50, t: 15, b: 30, pad: 2 }},
            showlegend: true,
            legend: {{
                x: 0.01, y: 0.99, bgcolor: 'rgba(10,10,18,0.9)',
                bordercolor: '{TC["border"]}', borderwidth: 1,
                font: {{ size: 9, color: '{TC["text_dim"]}' }}, orientation: 'h',
            }},
            xaxis: {{
                type: 'date',
                range: [visibleStart, endRange],
                rangeslider: {{ visible: false }},
                gridcolor: 'rgba(255,255,255,0.02)',
                linecolor: '{TC["border"]}',
                tickfont: {{ size: 9 }},
            }},
            yaxis: {{
                title: {{ text: 'Fiyat', font: {{ size: 10 }} }},
                side: 'right',
                gridcolor: 'rgba(255,255,255,0.03)',
                linecolor: '{TC["border"]}',
                tickfont: {{ size: 9 }},
                domain: hasRSI ? [0.30, 1] : [0.22, 1],
            }},
            yaxis2: {{
                title: {{ text: 'Hacim', font: {{ size: 9 }} }},
                side: 'right',
                gridcolor: 'rgba(255,255,255,0.02)',
                linecolor: '{TC["border"]}',
                tickfont: {{ size: 8 }},
                domain: hasRSI ? [0.18, 0.28] : [0, 0.18],
                showgrid: false,
            }},
            yaxis3: {{
                title: {{ text: 'RSI', font: {{ size: 9 }} }},
                side: 'right',
                gridcolor: 'rgba(255,255,255,0.02)',
                linecolor: '{TC["border"]}',
                tickfont: {{ size: 8 }},
                domain: [0, 0.16],
                range: [0, 100],
                showgrid: true,
            }},
            hovermode: 'x unified',
            hoverlabel: {{
                bgcolor: '#1A1A2E', bordercolor: '{TC["border"]}',
                font: {{ size: 11, color: '{TC["text"]}', family: 'monospace' }},
            }},
            dragmode: 'zoom',
        }};

        Plotly.newPlot('chart', traces, layout, {{
            responsive: true, displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
            displaylogo: false, scrollZoom: true,
        }});

        // Pencere resize listener
        window.addEventListener('resize', () => Plotly.Plots.resize('chart'));
    }})();
    </script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════
#  Yardımcı Widget'lar
# ═══════════════════════════════════════════════════════════════════

class _TerminalCard(QFrame):
    """Tekrar kullanılabilir terminal tarzı kart bileşeni."""

    def __init__(self, title: str = "", icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("termCard")
        self.setStyleSheet(f"""
            QFrame#termCard {{
                background: {TC["bg_card"]};
                border: 1px solid {TC["border"]};
                border-radius: 10px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(6)

        if title:
            header = QLabel(f"{icon} {title}" if icon else title)
            header.setStyleSheet(f"""
                color: {TC["accent"]}; font-size: 10px; font-weight: 700;
                letter-spacing: 1.5px; font-family: 'SF Mono', monospace;
            """)
            self._layout.addWidget(header)

    def add(self, widget: QWidget):
        self._layout.addWidget(widget)

    def add_stretch(self):
        self._layout.addStretch()


class _WatchlistItem(QFrame):
    """Watchlist'teki tek bir ticker satırı."""

    clicked = pyqtSignal(str)

    def __init__(self, ticker: str, price: float = 0, change: float = 0,
                 currency: str = "$", parent=None):
        super().__init__(parent)
        self.ticker = ticker
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid {TC["separator"]};
                padding: 0 4px;
            }}
            QFrame:hover {{
                background: {TC["bg_hover"]};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # Ticker sembolü
        sym = QLabel(ticker)
        sym.setStyleSheet(f"""
            color: {TC["text"]}; font-size: 12px; font-weight: 700;
            font-family: 'SF Mono', monospace;
        """)
        sym.setFixedWidth(80)

        # Fiyat
        self._price_lbl = QLabel(f"{currency}{price:,.2f}" if price else "—")
        self._price_lbl.setStyleSheet(f"""
            color: {TC["text"]}; font-size: 11px;
            font-family: 'SF Mono', monospace;
        """)
        self._price_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Değişim
        self._change_lbl = QLabel("")
        self._change_lbl.setFixedWidth(70)
        self._change_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.update_data(price, change, currency)

        # Sil butonu
        del_btn = QPushButton("×")
        del_btn.setFixedSize(20, 20)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TC["text_muted"]};
                border: none; font-size: 14px; }}
            QPushButton:hover {{ color: {TC["red"]}; }}
        """)
        del_btn.clicked.connect(lambda: self.setParent(None))

        layout.addWidget(sym)
        layout.addStretch()
        layout.addWidget(self._price_lbl)
        layout.addWidget(self._change_lbl)
        layout.addWidget(del_btn)

    def update_data(self, price: float, change: float, currency: str = "$"):
        if price:
            self._price_lbl.setText(f"{currency}{price:,.2f}")
        if change >= 0:
            self._change_lbl.setText(f"▲ +{change:.2f}%")
            self._change_lbl.setStyleSheet(f"""
                color: {TC["buy"]}; font-size: 10px; font-weight: 600;
                font-family: 'SF Mono', monospace;
            """)
        else:
            self._change_lbl.setText(f"▼ {change:.2f}%")
            self._change_lbl.setStyleSheet(f"""
                color: {TC["sell"]}; font-size: 10px; font-weight: 600;
                font-family: 'SF Mono', monospace;
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ticker)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  ANA SAYFA — FinanceFullPage
# ═══════════════════════════════════════════════════════════════════

class FinanceFullPage(QWidget):
    """
    Tam Ekran Finansal Zekâ Sayfası — Bloomberg Terminal tarzı.

    Layout (QSplitter):
    ┌─────────────────────────────────────────┬───────────────┐
    │  ÜST ÇUBUK: Arama + Piyasa Özeti                       │
    ├──────────────────────────────────────────┬──────────────┤
    │                                          │  Watchlist   │
    │         ANA GRAFİK (Plotly)              │  Sinyal      │
    │         Candlestick + Hacim + RSI        │  Göstergeler │
    │                                          │  Tahmin      │
    │                                          │  Duyarlılık  │
    └──────────────────────────────────────────┴──────────────┘
    │  ALT BİLGİ ÇUBUĞU: Durum + İlerleme + Zaman damgası    │
    └─────────────────────────────────────────────────────────┘
    """

    # Dış sinyaller
    close_requested = pyqtSignal()
    open_in_sidebar = pyqtSignal(str)   # Sidebar'da aç (ticker)

    def __init__(self, parent=None, initial_ticker: str = ""):
        super().__init__(parent)
        self.setObjectName("financeFullPage")

        # Durum
        self._current_ticker: Optional[str] = None
        self._analysis_worker = None
        self._watchlist: List[str] = []
        self._last_df_json: Optional[str] = None
        self._last_prediction: Optional[Dict] = None
        self._browser = None

        # UI oluştur
        self._setup_ui()

        # Başlangıç ticker'ı varsa analiz et
        if initial_ticker:
            QTimer.singleShot(300, lambda: self._start_analysis(initial_ticker))

    def set_browser(self, browser):
        """VisionaryBrowser referansı."""
        self._browser = browser

    # ─── Ana UI Kurulumu ──────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Tam ekran dashboard layoutunu oluşturur."""
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.setStyleSheet(f"background: {TC['bg']};")

        # ── 1) Üst Çubuk ─────────────────────────────────────────
        top_bar = self._create_top_bar()
        main.addWidget(top_bar)

        # ── 2) Ana İçerik (Splitter: Grafik | Sağ Panel) ─────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {TC["border"]};
            }}
        """)

        # Sol: Büyük grafik alanı
        chart_container = self._create_chart_panel()
        self._splitter.addWidget(chart_container)

        # Sağ: Bilgi paneli (watchlist + sinyal + göstergeler + tahmin)
        right_panel = self._create_right_panel()
        self._splitter.addWidget(right_panel)

        # Oran: %72 grafik, %28 panel
        self._splitter.setStretchFactor(0, 72)
        self._splitter.setStretchFactor(1, 28)

        main.addWidget(self._splitter, 1)

        # ── 3) Alt Bilgi Çubuğu ──────────────────────────────────
        footer = self._create_footer()
        main.addWidget(footer)

    # ─── Üst Çubuk ────────────────────────────────────────────────

    def _create_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {TC["bg_panel"]}, stop:0.5 #0C0C16, stop:1 {TC["bg_panel"]});
                border-bottom: 1px solid {TC["border"]};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        # Logo + Başlık
        logo = QLabel("📊")
        logo.setStyleSheet("font-size: 20px;")
        title = QLabel("FİNANSAL ZEKÂ TERMİNALİ")
        title.setStyleSheet(f"""
            font-size: 13px; font-weight: 700; color: {TC["accent"]};
            letter-spacing: 2px; font-family: 'SF Mono', monospace;
        """)

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addSpacing(20)

        # Arama çubuğu
        prompt = QLabel("$")
        prompt.setStyleSheet(f"""
            color: {TC["accent"]}; font-size: 16px; font-weight: 700;
            font-family: 'SF Mono', monospace;
        """)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Sembol girin (AAPL, BTC-USD, THYAO.IS) ve Enter'a basın...")
        self._search_input.setFixedHeight(34)
        self._search_input.setFixedWidth(380)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {TC["bg_input"]};
                border: 1px solid {TC["border"]};
                border-radius: 8px;
                color: {TC["text"]};
                font-size: 13px; padding: 0 14px;
                font-family: 'SF Mono', 'Fira Code', monospace;
            }}
            QLineEdit:focus {{
                border-color: {TC["border_active"]};
                background: rgba(0,255,136,0.03);
            }}
        """)
        self._search_input.returnPressed.connect(self._on_search)

        completer = QCompleter(_POPULAR_TICKERS)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_input.setCompleter(completer)

        # Hızlı butonlar
        layout.addWidget(prompt)
        layout.addWidget(self._search_input)
        layout.addSpacing(8)

        for sym, name in [("AAPL", "Apple"), ("BTC-USD", "Bitcoin"),
                          ("THYAO.IS", "THY"), ("XU100.IS", "BIST100")]:
            btn = self._quick_btn(sym, name)
            layout.addWidget(btn)

        layout.addStretch()

        # Piyasa saat göstergesi
        self._clock_label = QLabel("")
        self._clock_label.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        layout.addWidget(self._clock_label)
        self._update_clock()
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(1000)

        # Sidebar'a geri dön butonu
        sidebar_btn = QPushButton("◧ Sidebar")
        sidebar_btn.setFixedHeight(30)
        sidebar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sidebar_btn.setToolTip("Finans panelini sidebar olarak aç")
        sidebar_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TC["text_dim"]};
                border: 1px solid {TC["border"]}; border-radius: 6px;
                font-size: 11px; padding: 0 12px;
                font-family: 'SF Mono', monospace;
            }}
            QPushButton:hover {{
                color: {TC["accent"]}; border-color: {TC["border_active"]};
            }}
        """)
        sidebar_btn.clicked.connect(lambda: self.open_in_sidebar.emit(
            self._current_ticker or ""
        ))
        layout.addWidget(sidebar_btn)

        return bar

    def _quick_btn(self, symbol: str, label: str) -> QPushButton:
        """Hızlı erişim butonları."""
        btn = QPushButton(label)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(symbol)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.03);
                border: 1px solid {TC["border"]}; border-radius: 6px;
                color: {TC["text_dim"]}; font-size: 10px; padding: 0 10px;
                font-family: 'SF Mono', monospace;
            }}
            QPushButton:hover {{
                background: {TC["accent_glow"]};
                color: {TC["accent"]}; border-color: {TC["border_active"]};
            }}
        """)
        btn.clicked.connect(lambda: self._start_analysis(symbol))
        return btn

    # ─── Sol Panel: Grafik ────────────────────────────────────────

    def _create_chart_panel(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"background: {TC['bg']};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Grafik başlık çubuğu
        chart_header = QFrame()
        chart_header.setFixedHeight(36)
        chart_header.setStyleSheet(f"""
            QFrame {{
                background: {TC["bg_panel"]};
                border-bottom: 1px solid {TC["separator"]};
            }}
        """)
        ch_lay = QHBoxLayout(chart_header)
        ch_lay.setContentsMargins(14, 0, 14, 0)

        self._chart_title = QLabel("─── Grafik bekleniyor ───")
        self._chart_title.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace; letter-spacing: 1px;
        """)
        ch_lay.addWidget(self._chart_title)
        ch_lay.addStretch()

        # Zaman aralığı butonları
        for period_label in ["1A", "3A", "6A", "1Y", "5Y", "Tümü"]:
            pbtn = QPushButton(period_label)
            pbtn.setFixedSize(36, 22)
            pbtn.setCursor(Qt.CursorShape.PointingHandCursor)
            pbtn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TC["text_muted"]};
                    border: none; font-size: 9px;
                    font-family: 'SF Mono', monospace;
                }}
                QPushButton:hover {{ color: {TC["accent"]}; }}
            """)
            ch_lay.addWidget(pbtn)

        layout.addWidget(chart_header)

        # Ana grafik alanı
        self._chart_view = QWebEngineView()
        self._chart_view.setStyleSheet(f"background: {TC['bg']};")

        # Başlangıç hoş geldin mesajı
        self._chart_view.setHtml(f"""
        <html>
        <body style="background:{TC['bg']}; display:flex; align-items:center;
                     justify-content:center; height:100vh; margin:0;">
            <div style="text-align:center; color:{TC['text_dim']};
                        font-family:'SF Mono',monospace;">
                <div style="font-size:48px; margin-bottom:16px; opacity:0.3;">📊</div>
                <div style="font-size:14px; letter-spacing:1px; margin-bottom:8px;
                            color:{TC['accent']};">FİNANSAL ZEKÂ TERMİNALİ</div>
                <div style="font-size:12px; color:{TC['text_muted']};">
                    Üstteki arama çubuğuna sembol girin veya hızlı erişim butonlarını kullanın
                </div>
            </div>
        </body>
        </html>
        """)
        layout.addWidget(self._chart_view, 1)

        return container

    # ─── Sağ Panel: Bilgi Sütunu ──────────────────────────────────

    def _create_right_panel(self) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(280)
        container.setMaximumWidth(420)
        container.setStyleSheet(f"""
            QWidget {{
                background: {TC["bg_panel"]};
                border-left: 1px solid {TC["border"]};
            }}
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 4px; }}
            QScrollBar::handle:vertical {{
                background: {TC["border"]}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self._right_layout = QVBoxLayout(inner)
        self._right_layout.setContentsMargins(10, 10, 10, 10)
        self._right_layout.setSpacing(10)

        # Panel bölümleri oluştur
        self._create_ticker_info_section()
        self._create_signal_section()
        self._create_verdict_section()
        self._create_indicators_section()
        self._create_prediction_section()
        self._create_watchlist_section()

        self._right_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        return container

    def _create_ticker_info_section(self):
        """Ticker bilgi kartı — fiyat, değişim, şirket adı."""
        card = _TerminalCard("AKTİF SEMBOL", "◉")
        self._info_card = card

        self._info_ticker_label = QLabel("—")
        self._info_ticker_label.setStyleSheet(f"""
            color: {TC["text"]}; font-size: 18px; font-weight: 800;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._info_ticker_label)

        self._info_name_label = QLabel("")
        self._info_name_label.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._info_name_label)

        # Fiyat satırı
        price_row = QHBoxLayout()
        self._info_price_label = QLabel("—")
        self._info_price_label.setStyleSheet(f"""
            color: {TC["accent"]}; font-size: 24px; font-weight: 700;
            font-family: 'SF Mono', monospace;
        """)
        self._info_change_label = QLabel("")
        self._info_change_label.setStyleSheet(f"""
            font-size: 13px; font-weight: 600;
            font-family: 'SF Mono', monospace;
        """)
        price_row.addWidget(self._info_price_label)
        price_row.addStretch()
        price_row.addWidget(self._info_change_label)

        price_widget = QWidget()
        price_widget.setLayout(price_row)
        card.add(price_widget)

        # Meta bilgiler (piyasa, hacim, P/E, mkt cap)
        self._info_meta_label = QLabel("")
        self._info_meta_label.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 9px;
            font-family: 'SF Mono', monospace;
            line-height: 1.6;
        """)
        self._info_meta_label.setWordWrap(True)
        card.add(self._info_meta_label)

        # Watchlist'e ekle butonu
        add_wl_btn = QPushButton("+ Watchlist'e Ekle")
        add_wl_btn.setFixedHeight(28)
        add_wl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_wl_btn.setStyleSheet(f"""
            QPushButton {{
                background: {TC["accent_glow"]};
                border: 1px solid {TC["border"]};
                border-radius: 6px; color: {TC["accent"]};
                font-size: 10px; font-weight: 600;
                font-family: 'SF Mono', monospace;
            }}
            QPushButton:hover {{
                background: rgba(0,255,136,0.2);
                border-color: {TC["border_active"]};
            }}
        """)
        add_wl_btn.clicked.connect(self._add_to_watchlist)
        card.add(add_wl_btn)

        self._info_card.hide()
        self._right_layout.addWidget(card)

    def _create_signal_section(self):
        """AL/SAT/TUT sinyal kartı."""
        card = _TerminalCard("SİNYAL KONSENSÜSü", "⚡")
        self._signal_card = card

        # Ana sinyal
        sig_row = QHBoxLayout()
        self._signal_main_label = QLabel("—")
        self._signal_main_label.setStyleSheet(f"""
            font-size: 24px; font-weight: 900;
            font-family: 'SF Mono', monospace; letter-spacing: 2px;
        """)
        self._signal_confidence_label = QLabel("—%")
        self._signal_confidence_label.setStyleSheet(f"""
            font-size: 22px; font-weight: 700;
            color: {TC["text_dim"]}; font-family: 'SF Mono', monospace;
        """)
        sig_row.addWidget(self._signal_main_label)
        sig_row.addStretch()
        sig_row.addWidget(self._signal_confidence_label)
        sig_w = QWidget()
        sig_w.setLayout(sig_row)
        card.add(sig_w)

        self._signal_detail_label = QLabel("")
        self._signal_detail_label.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._signal_detail_label)

        self._signal_card.hide()
        self._right_layout.addWidget(card)

    def _create_verdict_section(self):
        """
        Akıllı Karar paneli — borsayı bilmeyen birinin bile
        'alayım mı almayayım mı?' sorusuna net cevap verir.
        """
        card = _TerminalCard("🧩 ALAYIM MI?", "")
        self._verdict_fp_card = card

        # Büyük karar satırı: emoji + karar + puan
        top_row = QHBoxLayout()
        self._verdict_fp_emoji = QLabel("⏳")
        self._verdict_fp_emoji.setStyleSheet("font-size: 40px;")
        self._verdict_fp_emoji.setFixedWidth(52)

        mid_col = QVBoxLayout()
        mid_col.setSpacing(2)
        self._verdict_fp_karar = QLabel("Analiz bekleniyor...")
        self._verdict_fp_karar.setStyleSheet(f"""
            color: {TC["text"]}; font-size: 20px; font-weight: 900;
            font-family: 'SF Mono', monospace;
        """)
        self._verdict_fp_baslik = QLabel("")
        self._verdict_fp_baslik.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 12px;
            font-family: 'SF Mono', monospace;
        """)
        mid_col.addWidget(self._verdict_fp_karar)
        mid_col.addWidget(self._verdict_fp_baslik)

        score_col = QVBoxLayout()
        score_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._verdict_fp_puan = QLabel("—")
        self._verdict_fp_puan.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 28px; font-weight: 800;
            font-family: 'SF Mono', monospace;
        """)
        self._verdict_fp_puan.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._verdict_fp_puan_sub = QLabel("/ 10")
        self._verdict_fp_puan_sub.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        self._verdict_fp_puan_sub.setAlignment(Qt.AlignmentFlag.AlignRight)
        score_col.addWidget(self._verdict_fp_puan)
        score_col.addWidget(self._verdict_fp_puan_sub)

        top_row.addWidget(self._verdict_fp_emoji)
        top_row.addLayout(mid_col, 1)
        top_row.addLayout(score_col)
        top_w = QWidget()
        top_w.setLayout(top_row)
        top_w.setStyleSheet("background: transparent;")
        card.add(top_w)

        # Termometre
        self._verdict_fp_thermo = QLabel("⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪")
        self._verdict_fp_thermo.setStyleSheet("font-size: 14px; letter-spacing: 3px; padding: 6px 0;")
        self._verdict_fp_thermo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add(self._verdict_fp_thermo)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {TC['border']};")
        card.add(sep)

        # Özet
        self._verdict_fp_ozet = QLabel("")
        self._verdict_fp_ozet.setWordWrap(True)
        self._verdict_fp_ozet.setStyleSheet(f"""
            color: {TC["text"]}; font-size: 12px;
            line-height: 1.6; padding: 6px 0;
        """)
        card.add(self._verdict_fp_ozet)

        # Risk seviyesi
        self._verdict_fp_risk = QLabel("")
        self._verdict_fp_risk.setWordWrap(True)
        self._verdict_fp_risk.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 11px;
            font-family: 'SF Mono', monospace; padding: 2px 0;
        """)
        card.add(self._verdict_fp_risk)

        # Detay maddeleri
        self._verdict_fp_details = QLabel("")
        self._verdict_fp_details.setWordWrap(True)
        self._verdict_fp_details.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            line-height: 1.7; padding: 4px 0;
        """)
        card.add(self._verdict_fp_details)

        # Yasal uyarı
        disclaimer = QLabel("⚠ Bu bir yatırım tavsiyesi değildir. Kararlarınız tamamen size aittir.")
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 9px;
            font-style: italic; padding-top: 4px;
        """)
        card.add(disclaimer)

        self._verdict_fp_card.hide()
        self._right_layout.addWidget(card)

    def _create_indicators_section(self):
        """Teknik gösterge detay tablosu."""
        card = _TerminalCard("TEKNİK GÖSTERGELER", "📐")
        self._indicators_card = card

        self._indicators_container = QWidget()
        self._indicators_container.setStyleSheet("background: transparent;")
        self._indicators_layout = QVBoxLayout(self._indicators_container)
        self._indicators_layout.setContentsMargins(0, 0, 0, 0)
        self._indicators_layout.setSpacing(2)
        card.add(self._indicators_container)

        self._indicators_card.hide()
        self._right_layout.addWidget(card)

    def _create_prediction_section(self):
        """Tahmin özet kartı."""
        card = _TerminalCard("TAHMİN ÖZETİ", "🔮")
        self._prediction_card = card

        self._pred_method_label = QLabel("")
        self._pred_method_label.setStyleSheet(f"""
            color: {TC["cyan"]}; font-size: 9px;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._pred_method_label)

        self._pred_direction_label = QLabel("—")
        self._pred_direction_label.setStyleSheet(f"""
            font-size: 14px; font-weight: 600;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._pred_direction_label)

        self._pred_range_label = QLabel("Aralık: —")
        self._pred_range_label.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._pred_range_label)

        self._pred_change_label = QLabel("")
        self._pred_change_label.setStyleSheet(f"""
            font-size: 12px; font-weight: 600;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._pred_change_label)

        self._pred_confidence_label = QLabel("Model Güveni: —")
        self._pred_confidence_label.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)
        card.add(self._pred_confidence_label)

        self._prediction_card.hide()
        self._right_layout.addWidget(card)

    def _create_watchlist_section(self):
        """Watchlist — takip edilen ticker'lar."""
        card = _TerminalCard("WATCHLIST", "👁")
        self._watchlist_card = card

        self._watchlist_container = QWidget()
        self._watchlist_container.setStyleSheet("background: transparent;")
        self._watchlist_layout = QVBoxLayout(self._watchlist_container)
        self._watchlist_layout.setContentsMargins(0, 0, 0, 0)
        self._watchlist_layout.setSpacing(0)
        card.add(self._watchlist_container)

        # Boş durum
        self._wl_empty_label = QLabel("Henüz ticker eklenmedi.\nAnaliz edilen semboller otomatik eklenir.")
        self._wl_empty_label.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 9px;
            font-family: 'SF Mono', monospace; padding: 8px 0;
        """)
        self._wl_empty_label.setWordWrap(True)
        self._wl_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._watchlist_layout.addWidget(self._wl_empty_label)

        self._right_layout.addWidget(card)

    # ─── Alt Bilgi Çubuğu ─────────────────────────────────────────

    def _create_footer(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(32)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {TC["bg_panel"]};
                border-top: 1px solid {TC["border"]};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {TC['text_muted']}; font-size: 8px;")
        self._status_label = QLabel("Hazır — Sembol girin ve analizi başlatın")
        self._status_label.setStyleSheet(f"""
            color: {TC["text_dim"]}; font-size: 10px;
            font-family: 'SF Mono', monospace;
        """)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255,255,255,0.02); border: none; border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {TC["accent"]}, stop:1 {TC["cyan"]});
                border-radius: 1px;
            }}
        """)
        self._progress_bar.hide()

        disclaimer = QLabel("⚠ Finansal tavsiye değildir")
        disclaimer.setStyleSheet(f"""
            color: {TC["text_muted"]}; font-size: 8px;
            font-family: 'SF Mono', monospace;
        """)

        layout.addWidget(self._status_dot)
        layout.addSpacing(6)
        layout.addWidget(self._status_label)
        layout.addSpacing(12)
        layout.addWidget(self._progress_bar)
        layout.addStretch()
        layout.addWidget(disclaimer)
        return bar

    # ─── Analiz Başlatma ──────────────────────────────────────────

    def _on_search(self):
        ticker = self._search_input.text().strip().upper()
        if ticker:
            self._start_analysis(ticker)

    def _start_analysis(self, ticker: str) -> None:
        """Tam analiz pipeline'ını başlatır."""
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
        self._search_input.setText(ticker)
        self._last_df_json = None
        self._last_prediction = None

        # UI sıfırla
        self._info_card.hide()
        self._signal_card.hide()
        self._verdict_fp_card.hide()
        self._indicators_card.hide()
        self._prediction_card.hide()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._chart_title.setText(f"─── {ticker} yükleniyor ───")
        self._update_status(f"📡 {ticker} analiz başlatılıyor...", "working")

        # Yükleniyor animasyonu
        self._chart_view.setHtml(f"""
        <html>
        <body style="background:{TC['bg']}; display:flex; align-items:center;
                     justify-content:center; height:100vh; margin:0;">
            <div style="text-align:center; color:{TC['accent']};
                        font-family:'SF Mono',monospace;">
                <div style="font-size:24px; margin-bottom:16px;" class="pulse">⏳</div>
                <div style="font-size:13px; letter-spacing:1px;">{ticker} analiz ediliyor</div>
                <div style="font-size:10px; color:{TC['text_dim']}; margin-top:8px;">
                    Veri çekme + teknik analiz + tahmin modeli
                </div>
            </div>
            <style>
                .pulse {{ animation: pulse 1.5s ease-in-out infinite; }}
                @keyframes pulse {{
                    0%, 100% {{ opacity: 0.4; }}
                    50% {{ opacity: 1; }}
                }}
            </style>
        </body>
        </html>
        """)

        # Worker başlat
        self._analysis_worker = FinanceAnalysisWorker(ticker)
        self._analysis_worker.status_update.connect(self._on_status)
        self._analysis_worker.progress_update.connect(self._on_progress)
        self._analysis_worker.data_ready.connect(self._on_data_ready)
        self._analysis_worker.prediction_ready.connect(self._on_prediction_ready)
        self._analysis_worker.analysis_complete.connect(self._on_analysis_complete)
        self._analysis_worker.error_occurred.connect(self._on_error)
        self._analysis_worker.start()

    # ─── Worker Sinyal İşleyicileri ────────────────────────────────

    def _on_status(self, msg: str):
        self._update_status(msg, "working")

    def _on_progress(self, val: int):
        self._progress_bar.setValue(val)
        if val >= 100:
            QTimer.singleShot(1500, self._progress_bar.hide)

    def _on_data_ready(self, data: dict):
        """Tarihsel veri hazır — grafik çiz, bilgi kartlarını güncelle."""
        ticker = data["ticker"]
        df_json = data["df"]
        signals = data.get("signals", {})
        info = data.get("info")

        self._last_df_json = df_json

        # Bilgi kartı
        self._update_info_card(ticker, df_json, info)

        # Sinyal kartı
        self._update_signal_card(signals)

        # Gösterge tablosu
        self._update_indicators_table(signals.get("detay", {}))

        # Grafik çiz (henüz tahmin yok)
        html = FullPageChartBuilder.build_advanced_chart_html(df_json, ticker)
        self._chart_view.setHtml(html)
        self._chart_title.setText(f"─── {ticker} │ OHLCV + Teknik Göstergeler ───")

    def _on_prediction_ready(self, prediction: dict):
        """Tahmin hazır — grafiği güncelle, tahmin kartını göster."""
        self._last_prediction = prediction

        # Tahmin kartı
        self._update_prediction_card(prediction)

        # Grafiği tahmin ile yeniden çiz
        if self._last_df_json and self._current_ticker:
            html = FullPageChartBuilder.build_advanced_chart_html(
                self._last_df_json, self._current_ticker, prediction
            )
            self._chart_view.setHtml(html)
            method = prediction.get("yöntem", "Tahmin")
            self._chart_title.setText(
                f"─── {self._current_ticker} │ OHLCV + {method} ───"
            )

    def _on_analysis_complete(self, result: dict):
        """Analiz tamamlandı."""
        ticker = result["ticker"]
        self._update_status(f"✅ {ticker} analizi tamamlandı", "success")
        self._progress_bar.hide()

        # Akıllı Karar panelini güncelle
        verdict = result.get("verdict")
        if verdict:
            self._update_verdict_section(verdict)

        # Watchlist'e otomatik ekle
        self._add_ticker_to_watchlist(ticker, result)

    def _update_verdict_section(self, verdict: Dict):
        """Akıllı Karar panelini günceller."""
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

        color = TC.get(renk, TC["hold"])

        self._verdict_fp_emoji.setText(emoji)
        self._verdict_fp_karar.setText(karar)
        self._verdict_fp_karar.setStyleSheet(f"""
            color: {color}; font-size: 20px; font-weight: 900;
            font-family: 'SF Mono', monospace;
        """)
        self._verdict_fp_baslik.setText(baslik)
        self._verdict_fp_puan.setText(str(puan))
        self._verdict_fp_puan.setStyleSheet(f"""
            color: {color}; font-size: 28px; font-weight: 800;
            font-family: 'SF Mono', monospace;
        """)
        self._verdict_fp_thermo.setText(termometre)
        self._verdict_fp_ozet.setText(ozet)

        # Risk
        risk_colors = {
            "DÜŞÜK": TC["buy"], "ORTA": TC["hold"],
            "YÜKSEK": TC["red"], "ÇOK YÜKSEK": TC["red"],
        }
        risk_c = risk_colors.get(risk_seviye, TC["hold"])
        risk_text = f"⛑ Risk: {risk_seviye}"
        if risk_aciklama:
            risk_text += f" — {risk_aciklama}"
        self._verdict_fp_risk.setText(risk_text)
        self._verdict_fp_risk.setStyleSheet(f"""
            color: {risk_c}; font-size: 11px;
            font-family: 'SF Mono', monospace; padding: 2px 0;
        """)

        # Detaylar
        if madde_listesi:
            self._verdict_fp_details.setText("\n".join(madde_listesi))
            self._verdict_fp_details.show()
        else:
            self._verdict_fp_details.hide()

        self._verdict_fp_card.show()

    def _on_error(self, msg: str):
        self._update_status(msg, "error")
        self._progress_bar.hide()

        self._chart_view.setHtml(f"""
        <html>
        <body style="background:{TC['bg']}; display:flex; align-items:center;
                     justify-content:center; height:100vh; margin:0;">
            <div style="text-align:center; color:{TC['red']};
                        font-family:'SF Mono',monospace;">
                <div style="font-size:36px; margin-bottom:16px;">⚠</div>
                <div style="font-size:13px;">{msg}</div>
                <div style="font-size:10px; color:{TC['text_dim']}; margin-top:8px;">
                    Sembolün doğru olduğundan emin olun (ör: AAPL, THYAO.IS, BTC-USD)
                </div>
            </div>
        </body>
        </html>
        """)

    # ─── UI Güncelleme ────────────────────────────────────────────

    def _update_status(self, msg: str, state: str = "idle"):
        colors = {"idle": TC["text_muted"], "working": TC["yellow"],
                  "success": TC["accent"], "error": TC["red"]}
        c = colors.get(state, TC["text_dim"])
        self._status_dot.setStyleSheet(f"color: {c}; font-size: 8px;")
        self._status_label.setText(msg)

    def _update_clock(self):
        now = datetime.now()
        self._clock_label.setText(now.strftime("%H:%M:%S"))

    def _update_info_card(self, ticker: str, df_json: str, info: Optional[Dict]):
        """Ticker bilgi kartını günceller."""
        try:
            df_dict = json.loads(df_json)
            close_data = df_dict.get("Close", {})
            dates = sorted(close_data.keys())
            if not dates:
                return

            last_price = close_data[dates[-1]]
            prev_price = close_data[dates[-2]] if len(dates) > 1 else last_price
            change = ((last_price - prev_price) / prev_price) * 100 if prev_price else 0

            # Şirket adı
            name = ""
            currency = "$"
            meta_parts = []
            if info:
                name = info.get("ad", "")
                curr = info.get("para_birimi", "USD")
                if curr == "TRY": currency = "₺"
                elif curr == "EUR": currency = "€"
                elif curr == "GBP": currency = "£"
                sector = info.get("sektör", "")
                market_cap = info.get("piyasa_değeri", 0)
                pe_ratio = info.get("fk_oranı", 0)
                if sector: meta_parts.append(f"Sektör: {sector}")
                if market_cap:
                    if market_cap >= 1e12: mc = f"{market_cap/1e12:.1f}T"
                    elif market_cap >= 1e9: mc = f"{market_cap/1e9:.1f}B"
                    elif market_cap >= 1e6: mc = f"{market_cap/1e6:.0f}M"
                    else: mc = str(int(market_cap))
                    meta_parts.append(f"Piyasa Değeri: {currency}{mc}")
                if pe_ratio: meta_parts.append(f"F/K: {pe_ratio:.1f}")

            # Hacim
            vol_data = df_dict.get("Volume", {})
            if dates[-1] in vol_data:
                vol = vol_data[dates[-1]]
                if vol >= 1e9: vs = f"{vol/1e9:.1f}B"
                elif vol >= 1e6: vs = f"{vol/1e6:.1f}M"
                elif vol >= 1e3: vs = f"{vol/1e3:.0f}K"
                else: vs = str(int(vol))
                meta_parts.append(f"Hacim: {vs}")

            meta_parts.append(f"Veri: {len(dates)} gün")

            self._info_ticker_label.setText(ticker)
            self._info_name_label.setText(name)
            self._info_price_label.setText(f"{currency}{last_price:,.2f}")

            if change >= 0:
                self._info_change_label.setText(f"▲ +{change:.2f}%")
                self._info_change_label.setStyleSheet(f"""
                    color: {TC["buy"]}; font-size: 13px; font-weight: 600;
                    font-family: 'SF Mono', monospace;
                """)
            else:
                self._info_change_label.setText(f"▼ {change:.2f}%")
                self._info_change_label.setStyleSheet(f"""
                    color: {TC["sell"]}; font-size: 13px; font-weight: 600;
                    font-family: 'SF Mono', monospace;
                """)

            self._info_meta_label.setText(" │ ".join(meta_parts))
            self._info_card.show()

        except Exception as e:
            logger.warning(f"Info kart hatası: {e}")

    def _update_signal_card(self, signals: Dict):
        """Sinyal kartını günceller."""
        sig = signals.get("sinyal", "BELİRSİZ")
        conf = signals.get("güven", 0)
        puan = signals.get("puan", 0)

        color_map = {
            "GÜÇLÜ AL": TC["buy"], "AL": TC["buy"],
            "TUT": TC["hold"],
            "SAT": TC["sell"], "GÜÇLÜ SAT": TC["sell"],
        }
        c = color_map.get(sig, TC["text_dim"])

        self._signal_main_label.setText(sig)
        self._signal_main_label.setStyleSheet(f"""
            font-size: 24px; font-weight: 900; color: {c};
            font-family: 'SF Mono', monospace; letter-spacing: 2px;
        """)
        self._signal_confidence_label.setText(f"{conf:.0f}%")
        self._signal_confidence_label.setStyleSheet(f"""
            font-size: 22px; font-weight: 700; color: {c};
            font-family: 'SF Mono', monospace;
        """)
        self._signal_detail_label.setText(f"Teknik Konsensüs ({puan:+d} puan)")
        self._signal_card.show()

    def _update_indicators_table(self, details: Dict):
        """Teknik gösterge tablosunu günceller."""
        while self._indicators_layout.count():
            item = self._indicators_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not details:
            return

        for name, data in details.items():
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: rgba(255,255,255,0.015);
                    border-radius: 4px;
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(4)

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(95)
            name_lbl.setStyleSheet(f"""
                color: {TC["text_dim"]}; font-size: 10px;
                font-family: 'SF Mono', monospace;
            """)

            direction = data.get("yön", "NÖTR")
            dc = {
                "AL": TC["buy"], "SAT": TC["sell"], "NÖTR": TC["hold"]
            }.get(direction, TC["text_dim"])
            ds = {"AL": "▲", "SAT": "▼", "NÖTR": "●"}.get(direction, "●")

            dir_lbl = QLabel(f"{ds} {direction}")
            dir_lbl.setFixedWidth(60)
            dir_lbl.setStyleSheet(f"""
                color: {dc}; font-size: 10px; font-weight: 600;
                font-family: 'SF Mono', monospace;
            """)

            val_lbl = QLabel(str(data.get("değer", "—")))
            val_lbl.setStyleSheet(f"""
                color: {TC["text_dim"]}; font-size: 9px;
                font-family: 'SF Mono', monospace;
            """)
            val_lbl.setWordWrap(True)

            rl.addWidget(name_lbl)
            rl.addWidget(dir_lbl)
            rl.addWidget(val_lbl, 1)
            self._indicators_layout.addWidget(row)

        self._indicators_card.show()

    def _update_prediction_card(self, prediction: Dict):
        """Tahmin kartını günceller."""
        if not prediction or not prediction.get("tahmin"):
            return

        preds = prediction["tahmin"]
        last_p = preds[-1]
        first_p = preds[0]

        method = prediction.get("yöntem", "Tahmin Modeli")
        self._pred_method_label.setText(f"Motor: {method}")

        # Yön
        if last_p > first_p * 1.02:
            direction, dc = "YÜKSELİŞ ▲", TC["buy"]
        elif last_p < first_p * 0.98:
            direction, dc = "DÜŞÜŞ ▼", TC["sell"]
        else:
            direction, dc = "YATAY ●", TC["hold"]

        self._pred_direction_label.setText(f"{len(preds)} günlük tahmin: {direction}")
        self._pred_direction_label.setStyleSheet(f"""
            font-size: 14px; font-weight: 600; color: {dc};
            font-family: 'SF Mono', monospace;
        """)

        # Aralık
        up95 = prediction.get("üst_bant_95", preds)
        low95 = prediction.get("alt_bant_95", preds)
        self._pred_range_label.setText(f"Aralık: {min(low95):,.2f} — {max(up95):,.2f}")

        # Değişim
        if preds and len(preds) >= 2:
            total_change = ((last_p - first_p) / first_p) * 100
            if total_change >= 0:
                self._pred_change_label.setText(f"Beklenen: ▲ +{total_change:.2f}%")
                self._pred_change_label.setStyleSheet(f"""
                    color: {TC["buy"]}; font-size: 12px; font-weight: 600;
                    font-family: 'SF Mono', monospace;
                """)
            else:
                self._pred_change_label.setText(f"Beklenen: ▼ {total_change:.2f}%")
                self._pred_change_label.setStyleSheet(f"""
                    color: {TC["sell"]}; font-size: 12px; font-weight: 600;
                    font-family: 'SF Mono', monospace;
                """)

        # Güven
        stds = prediction.get("std", [])
        if stds and preds:
            avg_std_pct = (sum(stds) / len(stds)) / (sum(preds) / len(preds)) * 100
            conf = max(0, min(100, 100 - avg_std_pct * 5))
            self._pred_confidence_label.setText(f"Model Güveni: %{conf:.0f}")

        self._prediction_card.show()

    # ─── Watchlist ────────────────────────────────────────────────

    def _add_to_watchlist(self):
        """Aktif ticker'ı watchlist'e ekle."""
        if self._current_ticker and self._current_ticker not in self._watchlist:
            self._add_ticker_to_watchlist(self._current_ticker, {})

    def _add_ticker_to_watchlist(self, ticker: str, result: dict):
        """Ticker'ı watchlist'e ekler."""
        if ticker in self._watchlist:
            return

        self._watchlist.append(ticker)
        self._wl_empty_label.hide()

        price = result.get("son_fiyat", 0)
        change = result.get("günlük_değişim", 0)

        item = _WatchlistItem(ticker, price, change)
        item.clicked.connect(self._start_analysis)
        self._watchlist_layout.addWidget(item)

    # ─── Yardımcılar ──────────────────────────────────────────────

    def cleanup(self):
        """Kaynakları temizle."""
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.cancel()
            self._analysis_worker.quit()
            self._analysis_worker.wait(2000)
