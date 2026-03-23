"""
visionary_search.py — Visionary Navigator Meta-Arama Motoru
Birden fazla arama motorundan anonim sonuç toplama ve özel sonuç sayfası
"""

from __future__ import annotations
import logging
import re
import html
from typing import List, Dict, Optional
from urllib.parse import quote_plus, urljoin, urlparse
from PyQt6.QtCore import QThread, pyqtSignal, QUrl, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QScrollArea, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor

logger = logging.getLogger("VisionarySearch")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DARK GLASSMORPHISM PALETTE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ana renkler (new_tab_page ile uyumlu)
_BG_DARK = "#0F0F1A"
_BG_CARD = "#1A1A2E"
_ACCENT_PURPLE = "#A855F7"
_ACCENT_PINK = "#EC4899"
_TEXT_WHITE = "#FFFFFF"
_TEXT_SECONDARY = "#94A3B8"
_TEXT_DIM = "rgba(255, 255, 255, 0.4)"
_LINK_COLOR = "#A855F7"
_LINK_HOVER = "#C084FC"

# Glass efekt
_GLASS_BG = "rgba(255, 255, 255, 0.08)"
_GLASS_BORDER = "rgba(255, 255, 255, 0.12)"
_CARD_BG = "rgba(255, 255, 255, 0.05)"
_CARD_HOVER = "rgba(168, 85, 247, 0.15)"
_GRADIENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0F0F1A, stop:1 #1A1A2E)"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ARAMA SONUCU MODELI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchResult:
    """Tek bir arama sonucunu temsil eder."""
    
    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: str = "unknown",
        rank: int = 0
    ):
        self.title = self._clean_text(title)
        self.url = url
        self.snippet = self._clean_text(snippet)
        self.source = source  # "google", "duckduckgo", "bing"
        self.rank = rank
        self.score = 0.0  # Meta-search skor
        
    def _clean_text(self, text: str) -> str:
        """HTML ve özel karakterleri temizle."""
        if not text:
            return ""
        # HTML etiketlerini kaldır
        text = re.sub(r'<[^>]+>', '', text)
        # HTML entities decode
        text = html.unescape(text)
        # Çoklu boşlukları tek boşluğa indir
        text = re.sub(r'\s+', ' ', text).strip()
        return text
        
    def get_domain(self) -> str:
        """URL'den domain çıkar."""
        try:
            parsed = urlparse(self.url)
            return parsed.netloc.replace('www.', '')
        except Exception:
            return self.url[:50]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ARAMA MOTORU ARAYÜZÜ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchEngine:
    """Arama motoru temel sınıfı."""
    
    name: str = "base"
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Arama yap ve sonuçları döndür."""
        raise NotImplementedError


class DuckDuckGoEngine(SearchEngine):
    """
    DuckDuckGo arama motoru.
    Gizlilik odaklı, ücretsiz API.
    """
    
    name = "duckduckgo"
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """DuckDuckGo HTML arama sonuçlarını çek."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # DuckDuckGo HTML sayfası
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for idx, result_div in enumerate(soup.select('.result')[:num_results]):
                try:
                    title_elem = result_div.select_one('.result__title a')
                    snippet_elem = result_div.select_one('.result__snippet')
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get('href', '')
                        
                        # DuckDuckGo redirect URL'sini çöz
                        if 'uddg=' in link:
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                            if 'uddg' in parsed:
                                link = urllib.parse.unquote(parsed['uddg'][0])
                        
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        results.append(SearchResult(
                            title=title,
                            url=link,
                            snippet=snippet,
                            source=self.name,
                            rank=idx + 1
                        ))
                except Exception as e:
                    logger.debug(f"Sonuç ayrıştırma hatası: {e}")
                    continue
                    
            logger.info(f"DuckDuckGo: {len(results)} sonuç bulundu")
            return results
            
        except Exception as e:
            logger.error(f"DuckDuckGo arama hatası: {e}")
            return []


class BingEngine(SearchEngine):
    """
    Bing arama motoru.
    HTML scraping ile sonuç çekme.
    """
    
    name = "bing"
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Bing HTML arama sonuçlarını çek."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num_results}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for idx, result_div in enumerate(soup.select('.b_algo')[:num_results]):
                try:
                    title_elem = result_div.select_one('h2 a')
                    snippet_elem = result_div.select_one('.b_caption p')
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        results.append(SearchResult(
                            title=title,
                            url=link,
                            snippet=snippet,
                            source=self.name,
                            rank=idx + 1
                        ))
                except Exception as e:
                    logger.debug(f"Sonuç ayrıştırma hatası: {e}")
                    continue
                    
            logger.info(f"Bing: {len(results)} sonuç bulundu")
            return results
            
        except Exception as e:
            logger.error(f"Bing arama hatası: {e}")
            return []


class GoogleEngine(SearchEngine):
    """
    Google arama motoru.
    NOT: Google scraping yasakladığı için SerpAPI veya alternatif gerekebilir.
    """
    
    name = "google"
    
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Google arama sonuçlarını çek (sınırlı)."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}&hl=tr"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Google sonuç yapısı sık değişir, genel selector
            for idx, result_div in enumerate(soup.select('div.g')[:num_results]):
                try:
                    title_elem = result_div.select_one('h3')
                    link_elem = result_div.select_one('a[href^="http"]')
                    snippet_elem = result_div.select_one('div[data-sncf]') or result_div.select_one('.VwiC3b')
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        link = link_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        # Google redirect URL temizle
                        if link.startswith('/url?'):
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                            if 'q' in parsed:
                                link = parsed['q'][0]
                        
                        results.append(SearchResult(
                            title=title,
                            url=link,
                            snippet=snippet,
                            source=self.name,
                            rank=idx + 1
                        ))
                except Exception as e:
                    logger.debug(f"Sonuç ayrıştırma hatası: {e}")
                    continue
                    
            logger.info(f"Google: {len(results)} sonuç bulundu")
            return results
            
        except Exception as e:
            logger.error(f"Google arama hatası: {e}")
            return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  META-SEARCH WORKER — Arka Plan Arama
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MetaSearchWorker(QThread):
    """
    Birden fazla arama motorundan paralel sonuç çeken worker.
    """
    
    search_complete = pyqtSignal(str, list)  # (query, results)
    search_error = pyqtSignal(str)
    progress_update = pyqtSignal(str)  # "DuckDuckGo tamamlandı..."
    
    def __init__(self, query: str, engines: List[str] = None):
        super().__init__()
        self.query = query
        self.engines = engines or ["duckduckgo", "bing"]  # Varsayılan motorlar
        self._all_results: List[SearchResult] = []
        
    def run(self):
        """Tüm motorlarda arama yap."""
        engine_map = {
            "duckduckgo": DuckDuckGoEngine(),
            "bing": BingEngine(),
            "google": GoogleEngine(),
        }
        
        for engine_name in self.engines:
            if engine_name not in engine_map:
                continue
                
            self.progress_update.emit(f"{engine_name.capitalize()} aranıyor...")
            
            try:
                engine = engine_map[engine_name]
                results = engine.search(self.query, num_results=10)
                self._all_results.extend(results)
            except Exception as e:
                logger.error(f"{engine_name} hatası: {e}")
                
        # Sonuçları birleştir ve skorla
        merged = self._merge_and_rank(self._all_results)
        self.search_complete.emit(self.query, merged)
        
    def _merge_and_rank(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Sonuçları birleştir, skorla ve sırala.
        Aynı URL'ler için kaynak sayısına göre skor artır.
        """
        url_map: Dict[str, SearchResult] = {}
        url_sources: Dict[str, set] = {}
        
        for result in results:
            url = result.url.rstrip('/')
            
            if url not in url_map:
                url_map[url] = result
                url_sources[url] = {result.source}
            else:
                url_sources[url].add(result.source)
                # Daha kısa rank daha iyi
                if result.rank < url_map[url].rank:
                    url_map[url] = result
                    
        # Skorları hesapla
        for url, result in url_map.items():
            # Temel skor: rank'ın tersi
            base_score = 1.0 / result.rank if result.rank > 0 else 0.5
            
            # Birden fazla motorda bulunduysa bonus
            source_bonus = len(url_sources[url]) * 0.3
            
            result.score = base_score + source_bonus
            
        # Skora göre sırala (yüksek önce)
        sorted_results = sorted(url_map.values(), key=lambda r: r.score, reverse=True)
        
        return sorted_results[:20]  # İlk 20 sonuç


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VISIONARY SEARCH PAGE — Özel Sonuç Sayfası
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VisionarySearchPage(QWidget):
    """
    Visionary meta-arama sonuç sayfası.
    Ultra-modern koyu glassmorphism tema.
    """
    
    _is_search_page = True  # browser_core tespiti için
    link_clicked = pyqtSignal(str)  # Tıklanan URL
    
    def __init__(self, query: str = "", parent=None):
        super().__init__(parent)
        self._query = query
        self._results: List[SearchResult] = []
        self._search_worker: Optional[MetaSearchWorker] = None
        self._animation_timer = None
        self._cards_to_animate = []
        self._setup_ui()
        
    def _setup_ui(self):
        """UI kurulumu — dark glassmorphism theme."""
        self.setStyleSheet(f"""
            QWidget {{
                background: {_GRADIENT};
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Üst: Arama header (sticky görünüm)
        self._build_search_header(main_layout)
        
        # Sonuçlar scroll alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {_BG_DARK};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(168, 85, 247, 0.4);
                border-radius: 4px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(168, 85, 247, 0.6);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        
        self._results_container = QWidget()
        self._results_container.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(60, 30, 60, 40)
        self._results_layout.setSpacing(0)
        
        # Durum mesajı
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_SECONDARY};
                font-size: 14px;
                padding: 16px 0 20px 0;
            }}
        """)
        self._results_layout.addWidget(self._status_label)
        
        # Sonuç kartları için container
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(16)
        self._results_layout.addWidget(self._cards_container)
        
        self._results_layout.addStretch()
        
        scroll.setWidget(self._results_container)
        main_layout.addWidget(scroll, 1)
        
        # İlk arama
        if self._query:
            self._start_search(self._query)
            
    def _build_search_header(self, layout: QVBoxLayout):
        """Ultra-modern arama başlığı."""
        header_container = QWidget()
        header_container.setFixedHeight(100)
        header_container.setStyleSheet(f"""
            QWidget {{
                background: {_GLASS_BG};
                border-bottom: 1px solid {_GLASS_BORDER};
            }}
        """)
        
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(60, 20, 60, 20)
        header_layout.setSpacing(20)
        
        # Logo ve marka
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)
        
        logo = QLabel("✨")
        logo.setStyleSheet("font-size: 32px;")
        brand_layout.addWidget(logo)
        
        brand_text = QLabel("Visionary")
        brand_text.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_WHITE};
                font-size: 24px;
                font-weight: 600;
            }}
        """)
        brand_layout.addWidget(brand_text)
        
        header_layout.addLayout(brand_layout)
        
        # Arama çubuğu (glass card style)
        search_bar = QFrame()
        search_bar.setStyleSheet(f"""
            QFrame {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid {_GLASS_BORDER};
                border-radius: 24px;
            }}
        """)
        
        # Gölge efekti
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(168, 85, 247, 30))
        shadow.setOffset(0, 4)
        search_bar.setGraphicsEffect(shadow)
        
        bar_layout = QHBoxLayout(search_bar)
        bar_layout.setContentsMargins(20, 8, 8, 8)
        bar_layout.setSpacing(12)
        
        # Arama ikonu
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 18px;")
        bar_layout.addWidget(search_icon)
        
        # Input
        self._search_input = QLineEdit()
        self._search_input.setText(self._query)
        self._search_input.setPlaceholderText("Visionary ile ara...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {_TEXT_WHITE};
                border: none;
                font-size: 16px;
                padding: 10px 8px;
            }}
            QLineEdit::placeholder {{
                color: {_TEXT_DIM};
            }}
        """)
        self._search_input.returnPressed.connect(
            lambda: self._start_search(self._search_input.text())
        )
        bar_layout.addWidget(self._search_input, 1)
        
        # Arama butonu (gradient)
        search_btn = QPushButton("Ara")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 {_ACCENT_PURPLE}, stop:1 {_ACCENT_PINK});
                color: {_TEXT_WHITE};
                border: none;
                border-radius: 18px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #B66EF8, stop:1 #F05DA3);
            }}
        """)
        search_btn.clicked.connect(
            lambda: self._start_search(self._search_input.text())
        )
        bar_layout.addWidget(search_btn)
        
        header_layout.addWidget(search_bar, 1)
        layout.addWidget(header_container)
        
    def _start_search(self, query: str):
        """Meta-arama başlat."""
        query = query.strip()
        if not query:
            return
            
        self._query = query
        self._search_input.setText(query)
        
        # Önceki sonuçları temizle
        self._clear_results()
        self._status_label.setText("🔍 Aranıyor...")
        
        # Worker başlat
        self._search_worker = MetaSearchWorker(query, ["duckduckgo", "bing"])
        self._search_worker.search_complete.connect(self._on_search_complete)
        self._search_worker.progress_update.connect(
            lambda msg: self._status_label.setText(f"🔍 {msg}")
        )
        self._search_worker.start()
        
    def _on_search_complete(self, query: str, results: List[SearchResult]):
        """Arama tamamlandığında sonuçları göster."""
        self._results = results
        
        if not results:
            self._status_label.setText("❌ Sonuç bulunamadı.")
            return
            
        self._status_label.setText(
            f"✅ \"{query}\" için {len(results)} sonuç bulundu"
        )
        
        # Sonuçları animasyonlu ekle
        self._cards_to_animate = []
        for result in results:
            card = self._create_result_card(result)
            card.setMaximumHeight(0)
            card.setStyleSheet(card.styleSheet() + "opacity: 0;")
            self._cards_layout.addWidget(card)
            self._cards_to_animate.append(card)
        
        # Animasyon timer
        self._animate_index = 0
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_next_card)
        self._animation_timer.start(80)  # 80ms aralıklarla kart göster
            
    def _animate_next_card(self):
        """Sıradaki kartı animasyonla göster."""
        if self._animate_index >= len(self._cards_to_animate):
            if self._animation_timer:
                self._animation_timer.stop()
            return
            
        card = self._cards_to_animate[self._animate_index]
        card.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        self._animate_index += 1
            
    def _create_result_card(self, result: SearchResult) -> QFrame:
        """Ultra-modern sonuç kartı oluştur."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {_CARD_BG};
                border: 1px solid {_GLASS_BORDER};
                border-radius: 20px;
            }}
            QFrame:hover {{
                background: {_CARD_HOVER};
                border: 1px solid rgba(168, 85, 247, 0.3);
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(10)
        
        # Üst satır: Domain + Kaynak Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        
        # Favicon placeholder + domain
        domain_container = QHBoxLayout()
        domain_container.setSpacing(8)
        
        favicon = QLabel("🌐")
        favicon.setStyleSheet("font-size: 14px;")
        domain_container.addWidget(favicon)
        
        domain = QLabel(result.get_domain())
        domain.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_DIM};
                font-size: 12px;
            }}
        """)
        domain_container.addWidget(domain)
        
        top_row.addLayout(domain_container)
        
        # Kaynak badge
        source_badge = QLabel(result.source.upper())
        source_colors = {
            "duckduckgo": "#DE5833",
            "bing": "#00809D",
            "google": "#4285F4",
        }
        badge_color = source_colors.get(result.source.lower(), _ACCENT_PURPLE)
        source_badge.setStyleSheet(f"""
            QLabel {{
                background: {badge_color};
                color: white;
                font-size: 9px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 10px;
                letter-spacing: 0.5px;
            }}
        """)
        top_row.addWidget(source_badge)
        top_row.addStretch()
        
        card_layout.addLayout(top_row)
        
        # Başlık
        title = QLabel(result.title)
        title.setStyleSheet(f"""
            QLabel {{
                color: {_LINK_COLOR};
                font-size: 18px;
                font-weight: 600;
            }}
            QLabel:hover {{
                color: {_LINK_HOVER};
            }}
        """)
        title.setWordWrap(True)
        card_layout.addWidget(title)
        
        # URL
        url_display = result.url[:80] + "..." if len(result.url) > 80 else result.url
        url_label = QLabel(url_display)
        url_label.setStyleSheet(f"""
            QLabel {{
                color: {_TEXT_DIM};
                font-size: 12px;
            }}
        """)
        card_layout.addWidget(url_label)
        
        # Snippet
        if result.snippet:
            snippet_text = result.snippet[:250] + "..." if len(result.snippet) > 250 else result.snippet
            snippet = QLabel(snippet_text)
            snippet.setStyleSheet(f"""
                QLabel {{
                    color: {_TEXT_SECONDARY};
                    font-size: 14px;
                    line-height: 1.5;
                }}
            """)
            snippet.setWordWrap(True)
            card_layout.addWidget(snippet)
            
        # Tıklama eventi
        card.mousePressEvent = lambda e, url=result.url: self.link_clicked.emit(url)
        
        return card
        
    def _clear_results(self):
        """Sonuçları temizle."""
        while self._cards_layout.count() > 0:
            child = self._cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def set_query(self, query: str):
        """Sorguyu ayarla ve ara."""
        self._start_search(query)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VISIONARY SEARCH MANAGER — Entegrasyon Sınıfı
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VisionarySearchManager:
    """
    Visionary arama yöneticisi.
    browser_core.py ile entegrasyon için.
    """
    
    def __init__(self, browser):
        self._browser = browser
        
    def search(self, query: str) -> VisionarySearchPage:
        """
        Visionary meta-arama yap ve sonuç sayfasını döndür.
        """
        page = VisionarySearchPage(query)
        page.link_clicked.connect(self._on_link_clicked)
        return page
        
    def _on_link_clicked(self, url: str):
        """Sonuç tıklandığında mevcut sekmede aç."""
        if self._browser:
            # Mevcut aktif sekmeyi al ve orada URL'yi aç
            current_tab = self._browser._tab_widget.currentWidget()
            if current_tab and hasattr(current_tab, 'setUrl'):
                current_tab.setUrl(QUrl(url))
            elif hasattr(self._browser, 'add_new_tab'):
                # Fallback: yeni sekme
                self._browser.add_new_tab(QUrl(url))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HTML TEMPLATE RENDERER — Yeni Premium Arama Sayfası
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os
from pathlib import Path

def render_search_results_html(
    query: str,
    results: List[SearchResult],
    search_time: float = 0.0,
    current_page: int = 1,
    total_pages: int = 1
) -> str:
    """
    Arama sonuçlarını HTML template ile render et.
    
    Args:
        query: Arama sorgusu
        results: SearchResult listesi
        search_time: Arama süresi (saniye)
        current_page: Mevcut sayfa
        total_pages: Toplam sayfa sayısı
        
    Returns:
        Tam HTML içeriği
    """
    # Template dosyasını yükle
    template_path = Path(__file__).parent / "templates" / "search_results.html"
    
    if template_path.exists():
        template = template_path.read_text(encoding='utf-8')
    else:
        # Fallback: basit template
        template = _get_fallback_template()
    
    # Sonuç kartlarını oluştur
    results_html = ""
    for i, result in enumerate(results):
        card_class = "result-card featured" if i == 0 else "result-card"
        
        # Domain çıkar
        domain = urlparse(result.url).netloc.replace("www.", "")
        
        # Snippet içinde arama terimlerini vurgula
        highlighted_snippet = _highlight_terms(result.snippet, query)
        
        # Favicon URL
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        
        results_html += f'''
        <article class="{card_class}" data-url="{html.escape(result.url)}">
            <div class="result-source">
                <div class="result-favicon">
                    <img src="{favicon_url}" alt="" onerror="this.style.display='none'">
                </div>
                <span class="result-url">
                    <span class="result-url-domain">{html.escape(domain)}</span>
                    › {html.escape(_get_path_display(result.url))}
                </span>
            </div>
            <h2 class="result-title">{html.escape(result.title)}</h2>
            <p class="result-snippet">{highlighted_snippet}</p>
        </article>
        '''
    
    # Placeholder'ları değiştir
    rendered = template
    rendered = rendered.replace("{{SEARCH_QUERY}}", html.escape(query))
    rendered = rendered.replace("{{RESULT_COUNT}}", f"{len(results) * 1000:,}".replace(",", "."))
    rendered = rendered.replace("{{SEARCH_TIME}}", f"{search_time:.2f}")
    rendered = rendered.replace("{{RESULTS_HTML}}", results_html)
    rendered = rendered.replace("{{CURRENT_PAGE}}", str(current_page))
    rendered = rendered.replace("{{TOTAL_PAGES}}", str(total_pages))
    rendered = rendered.replace("{{PREV_DISABLED}}", "disabled" if current_page <= 1 else "")
    rendered = rendered.replace("{{NEXT_DISABLED}}", "disabled" if current_page >= total_pages else "")
    
    return rendered


def _highlight_terms(text: str, query: str) -> str:
    """Arama terimlerini <mark> ile vurgula."""
    if not text or not query:
        return html.escape(text) if text else ""
    
    # Escape HTML first
    escaped = html.escape(text)
    
    # Her kelime için vurgula
    words = query.lower().split()
    for word in words:
        if len(word) < 2:
            continue
        # Case-insensitive replace
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        escaped = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", escaped)
    
    return escaped


def _get_path_display(url: str) -> str:
    """URL'den görüntülenebilir path çıkar."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if len(path) > 40:
            path = path[:37] + "..."
        return path or ""
    except:
        return ""


def _get_fallback_template() -> str:
    """Template dosyası yoksa basit bir fallback."""
    return '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Arama Sonuçları — Visionary</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .result-card { padding: 20px; margin: 10px 0; border: 1px solid #eee; border-radius: 12px; }
        .result-card:hover { background: #f9f9f9; }
        .result-title { color: #1a0dab; margin: 10px 0; }
        .result-url { color: #006621; font-size: 13px; }
        .result-snippet { color: #545454; }
        mark { background: #fff3cd; }
    </style>
</head>
<body>
    <h1>Arama: {{SEARCH_QUERY}}</h1>
    <p>{{RESULT_COUNT}} sonuç ({{SEARCH_TIME}} saniye)</p>
    <div class="results">{{RESULTS_HTML}}</div>
</body>
</html>'''
