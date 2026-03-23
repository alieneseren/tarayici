"""
Visionary Navigator — Finansal Zekâ Motoru (Finance Engine)
Hisse senedi / kripto ticker tespiti, tarihsel veri çekme, teknik analiz,
LSTM derin öğrenme tahmini ve güven bulutu (confidence cloud) hesaplama.

Mimari Prensipler:
─────────────────
• Veri Normalizasyonu  : yfinance "auto_adjust=True" ile split/divident düzeltmesi,
                         IQR tabanlı outlier kırpma, MinMaxScaler [0,1] aralığı.
• Eğitim vs Çıkarım    : Ağır LSTM eğitimi QThread içinde çalışır, UI donmaz.
                         Model ağırlıkları diske kaydedilir → tekrar eğitime gerek kalmaz.
• Güven Aralığı         : Monte Carlo Dropout ile %80 / %95 bantları hesaplanır.
• Duygu Analizi Hibrit  : Mevcut Yerel LLM modülüyle entegre → haber başlıkları
                         analiz edilerek Boğa/Ayı (Bullish/Bearish) skoru ayarlanır.

Bağımlılıklar: yfinance, pandas, numpy, scikit-learn (opsiyonel: tensorflow, pandas_ta)
"""

import logging
import os
import re
import json
import hashlib
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ─── Loglama ───────────────────────────────────────────────────────
logger = logging.getLogger("FinanceEngine")
logger.setLevel(logging.INFO)

# ─── Sabitler ──────────────────────────────────────────────────────
LOOKBACK_WINDOW = 60          # LSTM kayan pencere — son 60 gün
FORECAST_DAYS = 14            # Tahmin ufku — 14 gün
MONTE_CARLO_RUNS = 50         # Güven aralığı simülasyon sayısı
LSTM_EPOCHS = 25              # Hızlı eğitim — dondurma yok
LSTM_BATCH_SIZE = 32
HISTORY_YEARS = 5             # 5 yıllık tarihsel veri
MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "finance_cache")

# ─── Önbellek dizinini oluştur ─────────────────────────────────────
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# ─── Bilinen ticker pattern'leri ───────────────────────────────────
# Borsa İstanbul sembolleri ".IS" son ekiyle gelir (örn: THYAO.IS)
# Kripto para sembolleri "-USD" ile biter (örn: BTC-USD)
TICKER_PATTERNS = [
    # Amerikan borsası sembolleri (1-5 harf, büyük)
    r'\b([A-Z]{1,5})\b',
    # Borsa İstanbul (THYAO.IS, GARAN.IS)
    r'\b([A-Z]{2,5}\.IS)\b',
    # Kripto para (BTC-USD, ETH-USD)
    r'\b([A-Z]{2,10}-USD)\b',
    # Kripto sembol ($BTC, $ETH)
    r'\$([A-Z]{2,10})\b',
]

# Yanlış pozitif filtreleme — ticker olmayan kısaltmalar
FALSE_POSITIVE_WORDS = {
    'THE', 'AND', 'FOR', 'NOT', 'ARE', 'BUT', 'ALL', 'CAN', 'HAD', 'HER',
    'WAS', 'ONE', 'OUR', 'OUT', 'HAS', 'HIS', 'HOW', 'ITS', 'LET', 'MAY',
    'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GET', 'HIM',
    'HIT', 'HOT', 'MAN', 'RAN', 'RED', 'RUN', 'SAY', 'SHE', 'TOO', 'USE',
    'DAD', 'MOM', 'SET', 'TOP', 'USA', 'CEO', 'API', 'URL', 'PDF', 'HTML',
    'CSS', 'RSS', 'FAQ', 'ETC', 'NBA', 'NFL', 'MLB', 'NHL', 'UFC', 'FIFA',
    'NASA', 'HTTP', 'HTTPS', 'NEWS', 'HOME', 'NEXT', 'BACK', 'MORE', 'BEST',
    'FREE', 'JUST', 'LIKE', 'LIVE', 'MOST', 'THIS', 'THAT', 'WILL', 'YOUR',
    'FROM', 'HAVE', 'BEEN', 'THEY', 'WITH', 'WHAT', 'WHEN', 'SOME', 'THAN',
    'THEM', 'ALSO', 'ONLY', 'EACH', 'MADE', 'FIND', 'HERE', 'KNOW', 'TAKE',
    'WANT', 'MANY', 'SAID', 'DOES', 'LOOK', 'INTO', 'YEAR', 'VERY', 'LONG',
    'MAKE', 'MUCH', 'THEN', 'GOOD', 'WELL', 'OVER', 'SUCH', 'EVEN', 'HIGH',
    'SIGN', 'LOGIN', 'MENU', 'PAGE', 'VIEW', 'EDIT', 'SAVE', 'HELP', 'ABOUT',
    'INFO', 'DATA', 'BLOG', 'POST', 'SHARE', 'NULL', 'TRUE', 'BODY', 'HEAD',
    'LINK', 'TEXT', 'FORM', 'CLICK', 'READ', 'LOAD', 'SEND', 'OPEN', 'CLOSE',
}

# Yüksek güvenilirlikli bilinen ticker'lar — doğrudan kabul et
KNOWN_TICKERS = {
    # ABD büyük hisseler
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA',
    'BRK', 'JPM', 'V', 'MA', 'UNH', 'XOM', 'JNJ', 'WMT', 'PG', 'HD',
    'CVX', 'MRK', 'KO', 'PEP', 'ABBV', 'COST', 'AVGO', 'TMO', 'MCD',
    'CSCO', 'ACN', 'ABT', 'DHR', 'LIN', 'ADBE', 'TXN', 'CRM', 'NFLX',
    'AMD', 'INTC', 'QCOM', 'PYPL', 'INTU', 'AMAT', 'ISRG', 'BKNG',
    'SBUX', 'MDLZ', 'ADP', 'LRCX', 'GILD', 'REGN', 'ADI', 'VRTX',
    'PANW', 'SNPS', 'KLAC', 'CDNS', 'MNST', 'FTNT', 'MELI', 'ORLY',
    'DIS', 'BA', 'NKE', 'IBM', 'GS', 'MS', 'C', 'BAC', 'WFC',
    # Borsa İstanbul
    'THYAO.IS', 'GARAN.IS', 'AKBNK.IS', 'SISE.IS', 'EREGL.IS',
    'BIMAS.IS', 'KCHOL.IS', 'SAHOL.IS', 'TCELL.IS', 'TUPRS.IS',
    'HEKTS.IS', 'ASELS.IS', 'PGSUS.IS', 'SASA.IS', 'TOASO.IS',
    'YKBNK.IS', 'ISCTR.IS', 'VAKBN.IS', 'KOZAL.IS', 'PETKM.IS',
    # Kripto
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD',
    'ADA-USD', 'DOGE-USD', 'DOT-USD', 'AVAX-USD', 'MATIC-USD',
    'LINK-USD', 'ATOM-USD', 'UNI-USD', 'LTC-USD', 'SHIB-USD',
}


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 1 — Ticker Tespit Motoru
# ═══════════════════════════════════════════════════════════════════

class TickerDetector:
    """
    Web sayfası metninden ve URL'den hisse/kripto ticker sembollerini tespit eder.
    Yanlış pozitifleri filtreler ve güvenilirlik skoru atar.
    """

    @staticmethod
    def detect_from_url(url: str) -> List[Dict[str, Any]]:
        """
        URL yapısından ticker tespit eder.
        Finans siteleri belirli URL pattern'leri kullanır.
        Örnek: finance.yahoo.com/quote/AAPL → AAPL
        """
        results = []
        url_lower = url.lower()

        # Yahoo Finance: /quote/AAPL
        match = re.search(r'finance\.yahoo\.com/quote/([A-Z0-9.\-]+)', url, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper()
            results.append({"sembol": ticker, "kaynak": "URL (Yahoo Finance)", "güven": 0.99})

        # Google Finance: /finance/quote/AAPL:NASDAQ
        match = re.search(r'google\.com/finance/quote/([A-Z0-9]+)', url, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper()
            results.append({"sembol": ticker, "kaynak": "URL (Google Finance)", "güven": 0.98})

        # Investing.com: /equities/apple-inc
        if 'investing.com' in url_lower:
            results.append({"sembol": "__INVESTING_PAGE__", "kaynak": "URL (Investing.com)", "güven": 0.85})

        # Bloomberg: /quote/AAPL:US
        match = re.search(r'bloomberg\.com/quote/([A-Z0-9]+)', url, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper()
            results.append({"sembol": ticker, "kaynak": "URL (Bloomberg)", "güven": 0.97})

        # TradingView: /symbols/AAPL
        match = re.search(r'tradingview\.com/symbols/([A-Z0-9.\-]+)', url, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper().replace('-', '.')
            results.append({"sembol": ticker, "kaynak": "URL (TradingView)", "güven": 0.97})

        # Bigpara / Mynet (Borsa İstanbul)
        match = re.search(r'bigpara\.hurriyet\.com\.tr/borsa/hisse-fiyatlari/([A-Z]+)', url, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper() + ".IS"
            results.append({"sembol": ticker, "kaynak": "URL (Bigpara)", "güven": 0.95})

        return results

    @staticmethod
    def detect_from_text(text: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Sayfa metninden ticker sembollerini tespit eder.
        Regex + bilinen ticker veritabanı ile çapraz doğrulama yapar.
        """
        if not text or len(text) < 10:
            return []

        candidates = {}

        # 1. Kripto pattern'leri ($BTC, BTC-USD)
        for match in re.finditer(r'\$([A-Z]{2,10})\b', text):
            sym = match.group(1)
            crypto_sym = f"{sym}-USD"
            if crypto_sym in KNOWN_TICKERS:
                candidates[crypto_sym] = {"sembol": crypto_sym, "kaynak": "Metin ($sembol)", "güven": 0.92}

        for match in re.finditer(r'\b([A-Z]{2,10}-USD)\b', text):
            sym = match.group(1)
            if sym in KNOWN_TICKERS:
                candidates[sym] = {"sembol": sym, "kaynak": "Metin (kripto)", "güven": 0.95}

        # 2. Borsa İstanbul pattern'leri (XXX.IS)
        for match in re.finditer(r'\b([A-Z]{2,5}\.IS)\b', text):
            sym = match.group(1)
            candidates[sym] = {"sembol": sym, "kaynak": "Metin (BIST)", "güven": 0.93}

        # 3. Genel ticker pattern — yalnızca bilinen listede olanları al
        for match in re.finditer(r'\b([A-Z]{1,5})\b', text):
            sym = match.group(1)
            if sym in FALSE_POSITIVE_WORDS:
                continue
            if sym in KNOWN_TICKERS and sym not in candidates:
                candidates[sym] = {"sembol": sym, "kaynak": "Metin (bilinen)", "güven": 0.88}

        # 4. Kontekst tabanlı — "AAPL hissesi", "THYAO fiyatı" gibi
        context_patterns = [
            (r'\b([A-Z]{1,5})\s+(?:hisse|stock|share|fiyat|price)', 0.90),
            (r'(?:buy|sell|al|sat|tut|hold)\s+([A-Z]{1,5})\b', 0.87),
            (r'\b([A-Z]{1,5})\s+(?:coin|token|kripto|crypto)', 0.89),
        ]
        for pattern, confidence in context_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                sym = match.group(1).upper()
                if sym not in FALSE_POSITIVE_WORDS and sym not in candidates:
                    candidates[sym] = {"sembol": sym, "kaynak": "Metin (kontekst)", "güven": confidence}

        # Güven skoruna göre sırala ve limitle
        sorted_results = sorted(candidates.values(), key=lambda x: x["güven"], reverse=True)
        return sorted_results[:max_results]

    @staticmethod
    def detect(url: str, page_text: str) -> List[Dict[str, Any]]:
        """
        URL + sayfa metni birleşik tespit.
        Tekrar eden ticker'ları güven skoru en yüksek olanla birleştirir.
        """
        url_results = TickerDetector.detect_from_url(url)
        text_results = TickerDetector.detect_from_text(page_text)

        # Birleştir — aynı sembol varsa en yüksek güvenli olanı al
        merged = {}
        for r in url_results + text_results:
            sym = r["sembol"]
            if sym.startswith("__"):
                continue
            if sym not in merged or r["güven"] > merged[sym]["güven"]:
                merged[sym] = r

        return sorted(merged.values(), key=lambda x: x["güven"], reverse=True)


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 2 — Veri Motoru (yfinance)
# ═══════════════════════════════════════════════════════════════════

class FinanceDataEngine:
    """
    yfinance üzerinden tarihsel ve gerçek zamanlı veri çeker.
    Veri normalizasyonu: split düzeltmesi + IQR outlier kırpma.
    """

    @staticmethod
    def fetch_historical(ticker: str, years: int = HISTORY_YEARS) -> Optional[pd.DataFrame]:
        """
        Tarihsel OHLCV verisini çeker.
        auto_adjust=True → split ve dividant düzeltmesi otomatik.
        """
        try:
            import yfinance as yf

            end = datetime.now()
            start = end - timedelta(days=years * 365)

            logger.info(f"Veri çekiliyor: {ticker} ({start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')})")

            data = yf.download(
                ticker,
                start=start.strftime('%Y-%m-%d'),
                end=end.strftime('%Y-%m-%d'),
                auto_adjust=True,    # Split/dividend otomatik düzeltme
                progress=False,
                timeout=15
            )

            if data is None or data.empty:
                logger.warning(f"Veri bulunamadı: {ticker}")
                return None

            # Sütun isimlerini düzelt (multi-index gelirse)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Eksik veri doldurma (forward-fill)
            data = data.ffill().bfill()

            # IQR tabanlı outlier kırpma (Close sütunu üzerinde)
            data = FinanceDataEngine._clip_outliers(data, 'Close')

            logger.info(f"Veri başarıyla çekildi: {ticker} — {len(data)} gün")
            return data

        except Exception as e:
            logger.error(f"Veri çekme hatası ({ticker}): {e}")
            return None

    @staticmethod
    def _clip_outliers(df: pd.DataFrame, column: str, factor: float = 3.0) -> pd.DataFrame:
        """
        IQR (Çeyrekler Arası Aralık) tabanlı outlier kırpma.
        Aşırı uç değerleri %1-99 persentile sınırlar.
        Split/dividant hâlâ tutarsız bir şekilde yansımışsa korur.
        """
        if column not in df.columns:
            return df

        q1 = df[column].quantile(0.01)
        q99 = df[column].quantile(0.99)
        iqr = q99 - q1
        lower = q1 - factor * iqr
        upper = q99 + factor * iqr

        df[column] = df[column].clip(lower=max(lower, 0), upper=upper)
        return df

    @staticmethod
    def fetch_info(ticker: str) -> Optional[Dict]:
        """Şirket/coin temel bilgilerini çeker."""
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            return {
                "ad": info.get("shortName", info.get("longName", ticker)),
                "sektör": info.get("sector", info.get("category", "Bilinmiyor")),
                "piyasa_degeri": info.get("marketCap", 0),
                "para_birimi": info.get("currency", "USD"),
                "borsa": info.get("exchange", "Bilinmiyor"),
                "52h_yuksek": info.get("fiftyTwoWeekHigh", 0),
                "52h_dusuk": info.get("fiftyTwoWeekLow", 0),
                "gunluk_hacim": info.get("averageVolume", 0),
                "fk_orani": info.get("trailingPE", None),
                "temettü_verimi": info.get("dividendYield", None),
            }
        except Exception as e:
            logger.warning(f"Bilgi çekme hatası ({ticker}): {e}")
            return None


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 3 — Teknik Analiz Motoru
# ═══════════════════════════════════════════════════════════════════

class TechnicalAnalyzer:
    """
    Pandas-TA ile teknik göstergeler hesaplar.
    RSI, MACD, Bollinger Bantları, SMA/EMA, ATR.
    """

    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrame'e teknik gösterge sütunları ekler.
        Pandas-TA kullanılamıyorsa manuel hesaplama yapılır.
        """
        if df is None or df.empty:
            return df

        try:
            import pandas_ta as ta

            # RSI (14 periyot)
            df['RSI'] = ta.rsi(df['Close'], length=14)

            # MACD (12, 26, 9)
            macd_result = ta.macd(df['Close'], fast=12, slow=26, signal=9)
            if macd_result is not None and not macd_result.empty:
                df['MACD'] = macd_result.iloc[:, 0]
                df['MACD_Sinyal'] = macd_result.iloc[:, 1]
                df['MACD_Histogram'] = macd_result.iloc[:, 2]

            # Bollinger Bantları (20 periyot, 2 std)
            bb_result = ta.bbands(df['Close'], length=20, std=2)
            if bb_result is not None and not bb_result.empty:
                df['BB_Üst'] = bb_result.iloc[:, 0]
                df['BB_Orta'] = bb_result.iloc[:, 1]
                df['BB_Alt'] = bb_result.iloc[:, 2]

            # Hareketli Ortalamalar
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['SMA_200'] = ta.sma(df['Close'], length=200)
            df['EMA_12'] = ta.ema(df['Close'], length=12)
            df['EMA_26'] = ta.ema(df['Close'], length=26)

            # ATR (Average True Range — volatilite)
            df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

            logger.info("Teknik göstergeler hesaplandı (pandas_ta).")

        except ImportError:
            logger.warning("pandas_ta bulunamadı, manuel hesaplama yapılıyor...")
            df = TechnicalAnalyzer._compute_manual(df)

        return df

    @staticmethod
    def _compute_manual(df: pd.DataFrame) -> pd.DataFrame:
        """pandas_ta olmadan temel göstergeleri hesaplar."""
        close = df['Close']

        # RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))

        # SMA
        df['SMA_20'] = close.rolling(window=20).mean()
        df['SMA_50'] = close.rolling(window=50).mean()
        df['SMA_200'] = close.rolling(window=200).mean()

        # EMA
        df['EMA_12'] = close.ewm(span=12, adjust=False).mean()
        df['EMA_26'] = close.ewm(span=26, adjust=False).mean()

        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_Sinyal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Sinyal']

        # Bollinger Bantları
        df['BB_Orta'] = df['SMA_20']
        bb_std = close.rolling(window=20).std()
        df['BB_Üst'] = df['BB_Orta'] + 2 * bb_std
        df['BB_Alt'] = df['BB_Orta'] - 2 * bb_std

        return df

    @staticmethod
    def generate_signals(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Teknik göstergelerden AL / SAT / TUT sinyalleri üretir.
        Her gösterge +1 (boğa), -1 (ayı) veya 0 (nötr) puanı verir.
        Toplam puana göre nihai sinyal belirlenir.
        """
        if df is None or df.empty or len(df) < 50:
            return {"sinyal": "BELİRSİZ", "puan": 0, "detay": {}}

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        signals = {}

        # RSI Sinyali
        rsi = latest.get('RSI', 50)
        if pd.notna(rsi):
            if rsi < 30:
                signals['RSI'] = {"yön": "AL", "puan": 1, "değer": f"{rsi:.1f} (Aşırı Satım)"}
            elif rsi > 70:
                signals['RSI'] = {"yön": "SAT", "puan": -1, "değer": f"{rsi:.1f} (Aşırı Alım)"}
            else:
                signals['RSI'] = {"yön": "NÖTR", "puan": 0, "değer": f"{rsi:.1f}"}

        # MACD Sinyali
        macd = latest.get('MACD', 0)
        macd_signal = latest.get('MACD_Sinyal', 0)
        prev_macd = prev.get('MACD', 0)
        prev_signal = prev.get('MACD_Sinyal', 0)
        if pd.notna(macd) and pd.notna(macd_signal):
            if prev_macd < prev_signal and macd > macd_signal:
                signals['MACD'] = {"yön": "AL", "puan": 1, "değer": "Yukarı Kesişim ↑"}
            elif prev_macd > prev_signal and macd < macd_signal:
                signals['MACD'] = {"yön": "SAT", "puan": -1, "değer": "Aşağı Kesişim ↓"}
            else:
                direction = "Boğa" if macd > macd_signal else "Ayı"
                signals['MACD'] = {"yön": "NÖTR", "puan": 0, "değer": f"{direction}"}

        # Bollinger Bant Sinyali
        close = latest.get('Close', 0)
        bb_upper = latest.get('BB_Üst', 0)
        bb_lower = latest.get('BB_Alt', 0)
        if pd.notna(bb_upper) and pd.notna(bb_lower) and bb_upper > 0:
            if close <= bb_lower:
                signals['Bollinger'] = {"yön": "AL", "puan": 1, "değer": "Alt Banda Dokunuş"}
            elif close >= bb_upper:
                signals['Bollinger'] = {"yön": "SAT", "puan": -1, "değer": "Üst Banda Dokunuş"}
            else:
                pos = (close - bb_lower) / (bb_upper - bb_lower) * 100
                signals['Bollinger'] = {"yön": "NÖTR", "puan": 0, "değer": f"%{pos:.0f} bant konumu"}

        # SMA Kesişim Sinyali (Altın Haç / Ölüm Haçı)
        sma50 = latest.get('SMA_50', 0)
        sma200 = latest.get('SMA_200', 0)
        if pd.notna(sma50) and pd.notna(sma200) and sma200 > 0:
            if sma50 > sma200:
                signals['SMA Kesişim'] = {"yön": "AL", "puan": 1, "değer": "Altın Haç (SMA50 > SMA200)"}
            else:
                signals['SMA Kesişim'] = {"yön": "SAT", "puan": -1, "değer": "Ölüm Haçı (SMA50 < SMA200)"}

        # Fiyat - SMA20 ilişkisi
        sma20 = latest.get('SMA_20', 0)
        if pd.notna(sma20) and sma20 > 0:
            if close > sma20:
                signals['SMA 20'] = {"yön": "AL", "puan": 1, "değer": "Fiyat SMA20 üstünde"}
            else:
                signals['SMA 20'] = {"yön": "SAT", "puan": -1, "değer": "Fiyat SMA20 altında"}

        # Toplam puan ve nihai sinyal
        total_score = sum(s["puan"] for s in signals.values())
        max_possible = len(signals) if signals else 1

        if total_score >= 2:
            final_signal = "GÜÇLÜ AL"
        elif total_score == 1:
            final_signal = "AL"
        elif total_score == 0:
            final_signal = "TUT"
        elif total_score == -1:
            final_signal = "SAT"
        else:
            final_signal = "GÜÇLÜ SAT"

        confidence = abs(total_score) / max(max_possible, 1) * 100

        return {
            "sinyal": final_signal,
            "puan": total_score,
            "güven": min(confidence, 100),
            "detay": signals
        }


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 4 — LSTM Tahmin Motoru
# ═══════════════════════════════════════════════════════════════════

class LSTMPredictor:
    """
    Zaman serisi tahmin motoru — Adaptif Mimari.

    Strateji:
    ─────────
    1. TensorFlow mevcutsa → LSTM (128→64) + Monte Carlo Dropout
    2. TensorFlow yoksa    → scikit-learn Ridge Regresyon + Bootstrap güven aralığı
    
    Her iki durumda da:
    • MinMaxScaler ile [0,1] normalizasyon
    • Kayan pencere (60 gün) → Sonraki 1 günü tahminle
    • Güven aralığı (confidence interval) — %80 ve %95 bantları
    • Model ticker bazlı diske cache'lenir (24 saat geçerlilik)
    • Eğitim QThread'de çalışır → UI donmaz
    """

    # TensorFlow kullanılabilirliğini modül seviyesinde kontrol et
    _tf_available = None

    @classmethod
    def _check_tf(cls) -> bool:
        """TensorFlow import edilebilir mi kontrol eder (bir kere)."""
        if cls._tf_available is None:
            try:
                os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
                import tensorflow as tf
                tf.get_logger().setLevel('ERROR')
                cls._tf_available = True
                logger.info("TensorFlow bulundu — LSTM modu aktif.")
            except ImportError:
                cls._tf_available = False
                logger.info("TensorFlow bulunamadı — Ridge Regresyon + Bootstrap modu aktif.")
        return cls._tf_available

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.model = None
        self.scaler = None
        self._use_tf = self._check_tf()
        self._model_path = os.path.join(
            MODEL_CACHE_DIR,
            f"model_{hashlib.md5(ticker.encode()).hexdigest()}.{'h5' if self._use_tf else 'pkl'}"
        )
        self._scaler_path = os.path.join(
            MODEL_CACHE_DIR,
            f"scaler_{hashlib.md5(ticker.encode()).hexdigest()}.npy"
        )
        self._meta_path = os.path.join(
            MODEL_CACHE_DIR,
            f"meta_{hashlib.md5(ticker.encode()).hexdigest()}.json"
        )

    # ─── Veri Hazırlama ───────────────────────────────────────────

    def _prepare_data(self, df: pd.DataFrame) -> Optional[Tuple]:
        """
        Veriyi model eğitimi için hazırlar.
        MinMaxScaler ile [0,1] normalizasyon + kayan pencere oluşturma.
        """
        from sklearn.preprocessing import MinMaxScaler

        close_prices = df['Close'].values.reshape(-1, 1)

        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = self.scaler.fit_transform(close_prices)

        # Kayan pencere oluştur
        X, y = [], []
        for i in range(LOOKBACK_WINDOW, len(scaled_data)):
            X.append(scaled_data[i - LOOKBACK_WINDOW:i, 0])
            y.append(scaled_data[i, 0])

        if len(X) < 10:
            logger.warning("Yeterli eğitim verisi yok.")
            return None

        X = np.array(X)
        y = np.array(y)

        # Eğitim/test bölmesi (%85/%15)
        split = int(len(X) * 0.85)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        return X_train, y_train, X_test, y_test, scaled_data

    # ─── Model Oluşturma ──────────────────────────────────────────

    def _build_lstm(self, input_shape: Tuple[int, int]) -> Any:
        """TensorFlow LSTM modeli oluşturur."""
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM as KerasLSTM, Dense, Dropout, Input

        model = Sequential([
            Input(shape=input_shape),
            KerasLSTM(128, return_sequences=True),
            Dropout(0.2),
            KerasLSTM(64, return_sequences=False),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dense(1)
        ])
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='huber'
        )
        logger.info(f"LSTM modeli oluşturuldu — {model.count_params()} parametre")
        return model

    def _build_ridge_ensemble(self) -> Any:
        """
        scikit-learn Ridge Regresyon topluluk modeli (TF yoksa fallback).
        Birden fazla Ridge modeli farklı alpha değerleriyle eğitilir →
        Bootstrap benzeri güven aralığı hesaplanabilir.
        """
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import PolynomialFeatures

        # 5 farklı alpha ile topluluk (bootstrap diversity)
        ensemble = []
        alphas = [0.1, 1.0, 10.0, 50.0, 100.0]
        for alpha in alphas:
            pipe = Pipeline([
                ('poly', PolynomialFeatures(degree=2, include_bias=False)),
                ('ridge', Ridge(alpha=alpha))
            ])
            ensemble.append(pipe)

        logger.info(f"Ridge Ensemble oluşturuldu — {len(ensemble)} model")
        return ensemble

    # ─── Eğitim ───────────────────────────────────────────────────

    def train(self, df: pd.DataFrame, callback=None) -> bool:
        """
        Modeli eğitir veya cache'den yükler.
        callback: İlerleme bildirimi (epoch, loss).
        """
        # Önce cache'e bak
        if self._load_cached_model(df):
            if callback:
                callback(-1, 0)  # -1 = cache'den yüklendi
            return True

        prepared = self._prepare_data(df)
        if prepared is None:
            return False

        X_train, y_train, X_test, y_test, _ = prepared

        try:
            if self._use_tf:
                return self._train_lstm(X_train, y_train, X_test, y_test, df, callback)
            else:
                return self._train_ridge(X_train, y_train, X_test, y_test, df, callback)
        except Exception as e:
            logger.error(f"Eğitim hatası: {e}")
            # TF hata verdiyse Ridge'e düş
            if self._use_tf:
                logger.info("LSTM hatası, Ridge Ensemble'a geçiliyor...")
                self._use_tf = False
                try:
                    return self._train_ridge(X_train, y_train, X_test, y_test, df, callback)
                except Exception as e2:
                    logger.error(f"Ridge eğitim hatası: {e2}")
            return False

    def _train_lstm(self, X_train, y_train, X_test, y_test, df, callback) -> bool:
        """TensorFlow LSTM eğitimi."""
        import tensorflow as tf

        # LSTM (samples, timesteps, features) formatı
        X_train_3d = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
        X_test_3d = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))

        self.model = self._build_lstm((X_train_3d.shape[1], 1))
        if self.model is None:
            return False

        class ProgressCallback(tf.keras.callbacks.Callback):
            def __init__(self, ext_cb):
                super().__init__()
                self._ext = ext_cb
            def on_epoch_end(self, epoch, logs=None):
                if self._ext:
                    self._ext(epoch + 1, logs.get('loss', 0))

        callbacks = []
        if callback:
            callbacks.append(ProgressCallback(callback))
        callbacks.append(tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=5, restore_best_weights=True
        ))

        self.model.fit(
            X_train_3d, y_train,
            epochs=LSTM_EPOCHS, batch_size=LSTM_BATCH_SIZE,
            validation_data=(X_test_3d, y_test),
            callbacks=callbacks, verbose=0
        )

        self._save_cached_model(df)
        logger.info(f"LSTM eğitimi tamamlandı: {self.ticker}")
        return True

    def _train_ridge(self, X_train, y_train, X_test, y_test, df, callback) -> bool:
        """scikit-learn Ridge Ensemble eğitimi (hızlı, TF gerektirmez)."""
        self.model = self._build_ridge_ensemble()

        total_models = len(self.model)
        for i, pipe in enumerate(self.model):
            # Her model farklı alt-örneklem üzerinde eğitilir (bootstrap)
            n = len(X_train)
            idx = np.random.choice(n, size=int(n * 0.8), replace=True)
            pipe.fit(X_train[idx], y_train[idx])

            if callback:
                loss = np.mean((pipe.predict(X_test) - y_test) ** 2)
                callback(i + 1, loss)

        self._save_cached_model(df)
        logger.info(f"Ridge Ensemble eğitimi tamamlandı: {self.ticker}")
        return True

    # ─── Tahmin ───────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame, days: int = FORECAST_DAYS) -> Optional[Dict]:
        """
        Gelecek N günü tahmin eder + güven bulutu hesaplar.

        TF modu  : Monte Carlo Dropout (training=True) ile stokastik tahmin
        Ridge modu: Topluluk modellerin varyansı ile güven aralığı

        Dönüş:
        ──────
        {
            "tarihler": [...],
            "tahmin": [...],
            "üst_bant_95": [...], "alt_bant_95": [...],
            "üst_bant_80": [...], "alt_bant_80": [...],
            "std": [...],
        }
        """
        if self.model is None or self.scaler is None:
            logger.error("Model henüz eğitilmedi.")
            return None

        try:
            close_prices = df['Close'].values.reshape(-1, 1)
            scaled_data = self.scaler.transform(close_prices)
            last_window = scaled_data[-LOOKBACK_WINDOW:]

            if self._use_tf:
                all_predictions = self._predict_mc_dropout(last_window, days)
            else:
                all_predictions = self._predict_ridge_ensemble(last_window, days)

            if all_predictions is None:
                return None

            all_predictions = np.array(all_predictions)

            # Ters dönüşüm (scaler inverse)
            predictions_inv = []
            for run in all_predictions:
                inv = self.scaler.inverse_transform(run.reshape(-1, 1)).flatten()
                predictions_inv.append(inv)
            predictions_inv = np.array(predictions_inv)

            # İstatistikler
            mean_pred = np.mean(predictions_inv, axis=0)
            std_pred = np.std(predictions_inv, axis=0)

            # Güven bantları
            upper_95 = mean_pred + 1.96 * std_pred
            lower_95 = mean_pred - 1.96 * std_pred
            upper_80 = mean_pred + 1.28 * std_pred
            lower_80 = mean_pred - 1.28 * std_pred

            # Tarihler
            last_date = df.index[-1]
            future_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=days)

            return {
                "tarihler": [d.strftime('%Y-%m-%d') for d in future_dates],
                "tahmin": mean_pred.tolist(),
                "üst_bant_95": upper_95.tolist(),
                "alt_bant_95": np.maximum(lower_95, 0).tolist(),
                "üst_bant_80": upper_80.tolist(),
                "alt_bant_80": np.maximum(lower_80, 0).tolist(),
                "std": std_pred.tolist(),
                "yöntem": "LSTM (Monte Carlo)" if self._use_tf else "Ridge Ensemble (Bootstrap)",
            }

        except Exception as e:
            logger.error(f"Tahmin hatası: {e}")
            return None

    def _predict_mc_dropout(self, last_window, days) -> Optional[list]:
        """TensorFlow Monte Carlo Dropout tahmini."""
        import tensorflow as tf
        all_predictions = []
        for _ in range(MONTE_CARLO_RUNS):
            current_window = last_window.copy()
            run_preds = []
            for _ in range(days):
                x_input = current_window.reshape(1, LOOKBACK_WINDOW, 1)
                pred_scaled = self.model(x_input, training=True).numpy()[0, 0]
                run_preds.append(pred_scaled)
                current_window = np.append(current_window[1:], [[pred_scaled]], axis=0)
            all_predictions.append(run_preds)
        return all_predictions

    def _predict_ridge_ensemble(self, last_window, days) -> Optional[list]:
        """Ridge Ensemble + bootstrap pertürbasyon tahmini."""
        all_predictions = []

        for run_idx in range(MONTE_CARLO_RUNS):
            current_window = last_window.flatten().copy()
            run_preds = []

            for day in range(days):
                # Her topluluk modelinden tahmin al
                model_preds = []
                x_2d = current_window.reshape(1, -1)
                for pipe in self.model:
                    try:
                        p = pipe.predict(x_2d)[0]
                        model_preds.append(p)
                    except Exception:
                        pass

                if not model_preds:
                    break

                # Ortalama + küçük gürültü (stokastik çeşitlilik)
                mean_p = np.mean(model_preds)
                std_p = max(np.std(model_preds), 1e-6)
                noise = np.random.normal(0, std_p * 0.5)
                pred_scaled = np.clip(mean_p + noise, 0, 1)

                run_preds.append(pred_scaled)
                # Pencereyi kaydır
                current_window = np.append(current_window[1:], pred_scaled)

            all_predictions.append(run_preds)

        return all_predictions

    # ─── Cache Yönetimi ───────────────────────────────────────────

    def _save_cached_model(self, df: pd.DataFrame) -> None:
        """Model ve scaler'ı diske kaydeder."""
        try:
            if self._use_tf and self.model:
                self.model.save_weights(self._model_path)
            elif not self._use_tf and self.model:
                import pickle
                with open(self._model_path, 'wb') as f:
                    pickle.dump(self.model, f)

            if self.scaler:
                np.save(self._scaler_path, [self.scaler.data_min_, self.scaler.data_max_])

            with open(self._meta_path, 'w') as f:
                json.dump({
                    "ticker": self.ticker,
                    "data_length": len(df),
                    "trained_at": datetime.now().isoformat(),
                    "lookback": LOOKBACK_WINDOW,
                    "engine": "lstm" if self._use_tf else "ridge",
                }, f)

            logger.info(f"Model cache'lendi: {self.ticker} ({('LSTM' if self._use_tf else 'Ridge')})")
        except Exception as e:
            logger.warning(f"Model cache hatası: {e}")

    def _load_cached_model(self, df: pd.DataFrame) -> bool:
        """Cache'den model yükler (24 saat geçerlilikte)."""
        try:
            if not os.path.exists(self._meta_path) or not os.path.exists(self._model_path):
                return False

            with open(self._meta_path, 'r') as f:
                meta = json.load(f)

            # Cache süresi kontrolü (24 saat)
            trained_at = datetime.fromisoformat(meta["trained_at"])
            if (datetime.now() - trained_at).total_seconds() > 86400:
                logger.info("Cache süresi doldu, yeniden eğitim gerekli.")
                return False

            # Veri uzunluğu kontrolü
            if abs(meta.get("data_length", 0) - len(df)) > 5:
                logger.info("Veri boyutu değişti, yeniden eğitim gerekli.")
                return False

            # Motor uyumluluğu kontrolü
            cached_engine = meta.get("engine", "lstm")
            current_engine = "lstm" if self._use_tf else "ridge"
            if cached_engine != current_engine:
                logger.info(f"Motor değişti ({cached_engine} → {current_engine}), yeniden eğitim.")
                return False

            # Scaler'ı yeniden oluştur
            prepared = self._prepare_data(df)
            if prepared is None:
                return False

            X_train = prepared[0]

            # Modeli yükle
            if self._use_tf:
                self.model = self._build_lstm((X_train.shape[1], 1))
                if self.model is None:
                    return False
                self.model.load_weights(self._model_path)
            else:
                import pickle
                with open(self._model_path, 'rb') as f:
                    self.model = pickle.load(f)

            logger.info(f"Model cache'den yüklendi: {self.ticker} ({current_engine})")
            return True

        except Exception as e:
            logger.warning(f"Cache yükleme hatası: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 5 — Hibrit Duygu Analizi (LLM Entegrasyonu)
# ═══════════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """
    Mevcut Yerel LLM modülü ile haber başlıklarını analiz eder.
    Boğa/Ayı güven skoru döndürür.
    """

    @staticmethod
    def analyze_headlines(ticker: str, headlines: List[str]) -> Dict[str, Any]:
        """
        Haber başlıklarından duygu analizi yapar.
        LLM yoksa basit keyword tabanlı analiz kullanır.
        """
        if not headlines:
            return {"skor": 0.0, "yorum": "Haber verisi yok", "yön": "NÖTR"}

        # Önce keyword tabanlı hızlı analiz
        positive_keywords = [
            'rally', 'surge', 'jump', 'gain', 'rise', 'high', 'record', 'bull',
            'strong', 'growth', 'profit', 'beat', 'upgrade', 'buy', 'outperform',
            'yükseliş', 'artış', 'rekor', 'güçlü', 'kâr', 'hedef', 'al',
            'boğa', 'pozitif', 'kazanç', 'büyüme',
        ]
        negative_keywords = [
            'crash', 'fall', 'drop', 'loss', 'decline', 'low', 'bear', 'sell',
            'weak', 'risk', 'fear', 'miss', 'downgrade', 'cut', 'underperform',
            'düşüş', 'kayıp', 'risk', 'zayıf', 'zarar', 'sat', 'ayı',
            'negatif', 'endişe', 'kriz', 'çöküş',
        ]

        pos_count = 0
        neg_count = 0
        for headline in headlines:
            hl_lower = headline.lower()
            pos_count += sum(1 for kw in positive_keywords if kw in hl_lower)
            neg_count += sum(1 for kw in negative_keywords if kw in hl_lower)

        total = pos_count + neg_count
        if total == 0:
            return {"skor": 0.0, "yorum": "Belirleyici haber yok", "yön": "NÖTR"}

        sentiment_score = (pos_count - neg_count) / total  # [-1, 1] arası

        if sentiment_score > 0.3:
            direction = "BOĞA 🐂"
            comment = "Haberler ağırlıklı olarak pozitif"
        elif sentiment_score < -0.3:
            direction = "AYI 🐻"
            comment = "Haberler ağırlıklı olarak negatif"
        else:
            direction = "NÖTR ⚖️"
            comment = "Karışık haberler"

        return {
            "skor": round(sentiment_score, 3),
            "yön": direction,
            "yorum": comment,
            "pozitif": pos_count,
            "negatif": neg_count,
            "toplam_haber": len(headlines),
        }

    @staticmethod
    def build_llm_prompt(ticker: str, headlines: List[str]) -> str:
        """
        LLM için duygu analizi prompt'u oluşturur.
        Mevcut ai_logic.py LLMWorker ile kullanılabilir.
        """
        headlines_text = "\n".join(f"• {h}" for h in headlines[:15])
        return (
            f"Sen bir finansal analist olarak aşağıdaki haber başlıklarını {ticker} "
            f"hissesi/coin'i açısından değerlendir.\n\n"
            f"Haber Başlıkları:\n{headlines_text}\n\n"
            f"Lütfen şu formatta tek satır yanıt ver:\n"
            f"SKOR: [+1.0 ile -1.0 arası sayı] | YÖN: [BOĞA/AYI/NÖTR] | YORUM: [tek cümle açıklama]\n"
            f"Örnek: SKOR: 0.65 | YÖN: BOĞA | YORUM: Güçlü satış rakamları piyasa beklentilerini aştı."
        )


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 5.5 — Akıllı Karar Motoru (Smart Verdict)
#  Borsayı bilmeyen birinin bile "alayım mı almayayım mı"
#  sorusuna net ve anlaşılır cevap verir.
# ═══════════════════════════════════════════════════════════════════

class SmartVerdict:
    """
    Tüm analiz çıktılarını (teknik sinyal, tahmin, trend, volatilite)
    bir araya getirip 1-10 puan ve sade Türkçe açıklama üretir.

    Hedef kitle: Borsadan hiç anlamayan sıradan kullanıcı.

    Puan Skalası:
    ─────────────
    1-2  → 🔴 UZAK DUR — Ciddi düşüş riski var
    3-4  → 🟠 RİSKLİ   — Şu an almak tehlikeli olabilir
    5    → 🟡 BELİRSİZ — Net bir yön yok, beklemede kal
    6-7  → 🟢 FIRSATA YAKIN — Olumlu sinyaller var ama dikkatli ol
    8-10 → 🟢 İYİ FIRSAT — Göstergeler büyük ölçüde olumlu

    Karar:
    ──────
    "AL"        → Alabilirsin (puan ≥ 7)
    "BEKLEMede kal" → Henüz erken, takipte kal (puan 4–6)
    "ALMA"      → Şimdi almanı önermiyoruz (puan ≤ 3)
    """

    @staticmethod
    def evaluate(
        signals: Dict,
        prediction: Optional[Dict],
        df: Optional["pd.DataFrame"] = None,
        info: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Tüm verileri birleştirip nihai karar üretir.

        Dönüş:
        ──────
        {
            "puan": 7,
            "karar": "AL",
            "emoji": "🟢",
            "başlık": "Alabilirsin",
            "özet": "Teknik göstergeler olumlu, fiyat yükseliş trendinde...",
            "detay_maddeleri": ["✅ ...", "⚠️ ...", ...],
            "risk_seviyesi": "DÜŞÜK",
            "risk_açıklama": "...",
            "termometre": "🟢🟢🟢🟢🟢🟢🟢⚪⚪⚪",
        }
        """
        puan_toplam = 0.0
        max_puan = 0.0
        detaylar: List[str] = []
        artılar: List[str] = []
        eksiler: List[str] = []

        # ────────────────────────────────────────────────────────
        # 1) TEKNİK SİNYAL ANALİZİ (max 3 puan)
        # ────────────────────────────────────────────────────────
        max_puan += 3.0
        teknik_sinyal = signals.get("sinyal", "BELİRSİZ")
        teknik_puan_raw = signals.get("puan", 0)
        teknik_guven = signals.get("güven", 0)

        sinyal_map = {
            "GÜÇLÜ AL":  3.0,
            "AL":        2.0,
            "TUT":       1.5,
            "SAT":       0.5,
            "GÜÇLÜ SAT": 0.0,
            "BELİRSİZ":  1.0,
        }
        teknik_puan = sinyal_map.get(teknik_sinyal, 1.0)
        puan_toplam += teknik_puan

        if teknik_puan >= 2.0:
            artılar.append("Teknik göstergeler (RSI, MACD, SMA) genel olarak alım sinyali veriyor")
        elif teknik_puan <= 0.5:
            eksiler.append("Teknik göstergelerin çoğu satış sinyali veriyor — bu olumsuz bir işaret")
        else:
            detaylar.append("Teknik göstergeler karışık — net bir yön belirleyemiyorlar")

        # RSI detayı (herkesin anlayacağı dilde)
        rsi_data = signals.get("detay", {}).get("RSI", {})
        rsi_val = rsi_data.get("değer", "")
        if "Aşırı Satım" in str(rsi_val):
            artılar.append("Hisse aşırı satılmış durumda — bu genelde toparlanma fırsatı olabilir")
        elif "Aşırı Alım" in str(rsi_val):
            eksiler.append("Hisse aşırı alınmış (pahalılaşmış) durumda — yakında düşebilir")

        # SMA kesişim detayı
        sma_data = signals.get("detay", {}).get("SMA Kesişim", {})
        if sma_data.get("yön") == "AL":
            artılar.append("Uzun vadeli trend yukarı yönlü (Altın Haç oluşmuş)")
        elif sma_data.get("yön") == "SAT":
            eksiler.append("Uzun vadeli trend aşağı yönlü (Ölüm Haçı oluşmuş)")

        # ────────────────────────────────────────────────────────
        # 2) TAHMİN MODEL ANALİZİ (max 3 puan)
        # ────────────────────────────────────────────────────────
        max_puan += 3.0
        if prediction and prediction.get("tahmin"):
            preds = prediction["tahmin"]
            pred_first = preds[0]
            pred_last = preds[-1]
            pred_change_pct = ((pred_last - pred_first) / pred_first * 100) if pred_first else 0

            # Güven aralığı genişliği
            stds = prediction.get("std", [])
            avg_std = sum(stds) / len(stds) if stds else 0
            avg_pred = sum(preds) / len(preds) if preds else 1
            uncertainty = (avg_std / avg_pred * 100) if avg_pred else 50

            if pred_change_pct > 5:
                tahmin_puan = 3.0
                artılar.append(f"Yapay zekâ modeli önümüzdeki {len(preds)} gün için %{pred_change_pct:.1f} yükseliş öngörüyor")
            elif pred_change_pct > 2:
                tahmin_puan = 2.5
                artılar.append(f"Model hafif yükseliş öngörüyor (%{pred_change_pct:.1f})")
            elif pred_change_pct > 0:
                tahmin_puan = 2.0
                detaylar.append(f"Model çok az yükseliş öngörüyor (%{pred_change_pct:.1f}) — heyecanlanma erken")
            elif pred_change_pct > -2:
                tahmin_puan = 1.5
                detaylar.append(f"Model yatay seyir / çok hafif düşüş öngörüyor (%{pred_change_pct:.1f})")
            elif pred_change_pct > -5:
                tahmin_puan = 0.8
                eksiler.append(f"Model %{abs(pred_change_pct):.1f} düşüş öngörüyor — dikkatli ol")
            else:
                tahmin_puan = 0.0
                eksiler.append(f"Model ciddi düşüş öngörüyor (%{abs(pred_change_pct):.1f}) — tehlike sinyali")

            # Belirsizlik yüksekse puanı düşür
            if uncertainty > 15:
                tahmin_puan *= 0.7
                eksiler.append("Model tahminlerinin güvenilirliği düşük — belirsizlik yüksek")
            elif uncertainty < 5:
                artılar.append("Model tahminleri oldukça tutarlı — güvenilirlik yüksek")

            puan_toplam += tahmin_puan
        else:
            # Tahmin yoksa nötr puan
            puan_toplam += 1.5
            detaylar.append("Yapay zekâ tahmin modeli çalışmadı — karar sadece teknik verilere dayanıyor")

        # ────────────────────────────────────────────────────────
        # 3) TREND ANALİZİ (max 2 puan)
        # ────────────────────────────────────────────────────────
        max_puan += 2.0
        if df is not None and len(df) > 20:
            close = df['Close']
            # Son 20 gün trend
            son20 = close.iloc[-20:]
            son5 = close.iloc[-5:]
            trend_20 = ((son20.iloc[-1] - son20.iloc[0]) / son20.iloc[0]) * 100
            trend_5 = ((son5.iloc[-1] - son5.iloc[0]) / son5.iloc[0]) * 100

            if trend_20 > 5 and trend_5 > 0:
                trend_puan = 2.0
                artılar.append(f"Fiyat son 20 günde %{trend_20:.1f} yükselmiş ve momentum hâlâ yukarıda")
            elif trend_20 > 0:
                trend_puan = 1.5
                detaylar.append(f"Son 20 günde hafif yükseliş var (%{trend_20:.1f})")
            elif trend_20 > -5:
                trend_puan = 1.0
                detaylar.append(f"Son 20 günde hafif düşüş var (%{trend_20:.1f})")
            elif trend_20 > -15:
                trend_puan = 0.5
                eksiler.append(f"Son 20 günde belirgin düşüş var (%{trend_20:.1f}) — dipten dönüş beklenebilir ama risk yüksek")
            else:
                trend_puan = 0.0
                eksiler.append(f"Son 20 günde sert düşüş (%{trend_20:.1f}) — şu an çok riskli")

            # Momentum çelişkisi: 20 gün düşüş ama 5 gün toparlanma
            if trend_20 < -5 and trend_5 > 2:
                detaylar.append("Kısa vadede toparlanma sinyali var ama uzun vadeli trend hâlâ olumsuz")
                trend_puan = min(trend_puan + 0.3, 2.0)

            puan_toplam += trend_puan
        else:
            puan_toplam += 1.0

        # ────────────────────────────────────────────────────────
        # 4) VOLATİLİTE (RİSK) ANALİZİ (max 2 puan)
        # ────────────────────────────────────────────────────────
        max_puan += 2.0
        risk_seviye = "ORTA"
        risk_aciklama = ""

        if df is not None and len(df) > 20:
            # Son 20 günlük günlük değişim yüzdesi
            returns = df['Close'].pct_change().dropna().iloc[-20:]
            volatility = returns.std() * 100  # Yüzde cinsinden

            # En büyük günlük düşüş
            max_drop = returns.min() * 100

            if volatility < 1.5:
                vol_puan = 2.0
                risk_seviye = "DÜŞÜK"
                risk_aciklama = "Bu hisse/coin son dönemde sakin hareket ediyor — ani sürpriz riski az"
                artılar.append("Fiyat oynaklığı düşük — görece güvenli bir dönemde")
            elif volatility < 3.0:
                vol_puan = 1.5
                risk_seviye = "ORTA"
                risk_aciklama = "Normal seviyede dalgalanma var — her yatırımda olduğu gibi dikkatli ol"
            elif volatility < 5.0:
                vol_puan = 1.0
                risk_seviye = "YÜKSEK"
                risk_aciklama = "Fiyat çok dalgalanıyor — kısa sürede büyük kazanç veya kayıp yaşanabilir"
                eksiler.append(f"Fiyat çok dalgalı (günlük ±%{volatility:.1f}) — yüksek risk")
            else:
                vol_puan = 0.3
                risk_seviye = "ÇOK YÜKSEK"
                risk_aciklama = "Aşırı dalgalı — kumar gibi, sadece kaybetmeyi göze alabileceksen düşün"
                eksiler.append(f"Aşırı dalgalanma (günlük ±%{volatility:.1f}) — çok riskli")

            if max_drop < -5:
                eksiler.append(f"Son dönemde tek günde %{abs(max_drop):.1f} düşüş yaşanmış — sert hareketler var")
                vol_puan = max(vol_puan - 0.3, 0)

            puan_toplam += vol_puan
        else:
            puan_toplam += 1.0
            risk_aciklama = "Yeterli veri olmadığı için risk ölçülemedi"

        # ────────────────────────────────────────────────────────
        # 5) NİHAİ PUAN HESAPLAMA (1-10 skalaya normalizasyon)
        # ────────────────────────────────────────────────────────
        if max_puan > 0:
            normalized = (puan_toplam / max_puan) * 10
        else:
            normalized = 5.0

        final_puan = max(1, min(10, round(normalized)))

        # ────────────────────────────────────────────────────────
        # 6) KARAR VE AÇIKLAMA ÜRETİMİ
        # ────────────────────────────────────────────────────────
        if final_puan >= 8:
            karar = "ALABİLİRSİN"
            emoji = "🟢"
            baslik = "İyi Fırsat Görünüyor"
            renk = "buy"
        elif final_puan >= 7:
            karar = "ALABİLİRSİN"
            emoji = "🟢"
            baslik = "Olumlu Sinyaller Var"
            renk = "buy"
        elif final_puan >= 5:
            karar = "BEKLE"
            emoji = "🟡"
            baslik = "Şimdilik Beklemede Kal"
            renk = "hold"
        elif final_puan >= 4:
            karar = "ALMA"
            emoji = "🟠"
            baslik = "Riskli Görünüyor"
            renk = "sell"
        else:
            karar = "UZAK DUR"
            emoji = "🔴"
            baslik = "Şu An Uzak Dur"
            renk = "sell"

        # Termometre (görsel puan çubuğu)
        filled = final_puan
        empty = 10 - filled
        if final_puan >= 7:
            dot = "🟢"
        elif final_puan >= 5:
            dot = "🟡"
        elif final_puan >= 4:
            dot = "🟠"
        else:
            dot = "🔴"
        termometre = dot * filled + "⚪" * empty

        # Madde listesi oluştur (artılar → detaylar → eksiler sırasıyla)
        madde_listesi = []
        for a in artılar:
            madde_listesi.append(f"✅ {a}")
        for d in detaylar:
            madde_listesi.append(f"ℹ️ {d}")
        for e in eksiler:
            madde_listesi.append(f"⚠️ {e}")

        # Özet cümlesi (basit dil)
        if final_puan >= 7:
            ozet = (
                f"Bu hisse/coin şu an olumlu sinyaller veriyor. "
                f"Teknik göstergeler ve yapay zekâ modeli genel olarak yükseliş bekliyor. "
                f"Ama unutma: hiçbir tahmin kesin değildir."
            )
        elif final_puan >= 5:
            ozet = (
                f"Şu an net bir yön yok. Bazı göstergeler olumlu, bazıları değil. "
                f"Acele etmeden beklemeni ve gelişmeleri takip etmeni öneriyoruz."
            )
        elif final_puan >= 4:
            ozet = (
                f"Göstergelerin çoğu olumsuz. Şu an almak riskli olabilir. "
                f"Daha uygun bir zamanda tekrar bakmanda fayda var."
            )
        else:
            ozet = (
                f"Göstergeler ciddi olumsuzluk gösteriyor. "
                f"Şu an bu varlığa para yatırmak büyük risk — beklemenizi kesinlikle öneriyoruz."
            )

        return {
            "puan": final_puan,
            "karar": karar,
            "emoji": emoji,
            "başlık": baslik,
            "renk": renk,
            "özet": ozet,
            "detay_maddeleri": madde_listesi,
            "risk_seviyesi": risk_seviye,
            "risk_açıklama": risk_aciklama,
            "termometre": termometre,
            "artı_sayısı": len(artılar),
            "eksi_sayısı": len(eksiler),
        }


# ═══════════════════════════════════════════════════════════════════
#  BÖLÜM 6 — QThread Worker'lar (UI Donmaz)
# ═══════════════════════════════════════════════════════════════════

from PyQt6.QtCore import QThread, pyqtSignal


class FinanceAnalysisWorker(QThread):
    """
    Tüm finansal analiz pipeline'ını arka planda çalıştırır.
    UI thread'i asla bloklamaz.

    Sinyal Akışı:
    ─────────────
    status_update → Durum mesajı (str)
    progress_update → İlerleme yüzdesi (int 0-100)
    data_ready → Tarihsel veri ve göstergeler (dict)
    prediction_ready → LSTM tahmin sonuçları (dict)
    analysis_complete → Tüm analiz tamamlandı (dict)
    error_occurred → Hata mesajı (str)
    """

    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    data_ready = pyqtSignal(dict)
    prediction_ready = pyqtSignal(dict)
    analysis_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, ticker: str, parent=None):
        super().__init__(parent)
        self.ticker = ticker
        self._cancelled = False

    def cancel(self):
        """İşlemi iptal et."""
        self._cancelled = True

    def run(self):
        """Ana analiz pipeline'ı."""
        try:
            # ── Adım 1: Şirket bilgisi çek (%5) ─────────────────
            self.status_update.emit(f"📡 {self.ticker} bilgileri çekiliyor...")
            self.progress_update.emit(5)

            info = FinanceDataEngine.fetch_info(self.ticker)
            if self._cancelled:
                return

            # ── Adım 2: Tarihsel veri çek (%20) ──────────────────
            self.status_update.emit(f"📊 {HISTORY_YEARS} yıllık tarihsel veri indiriliyor...")
            self.progress_update.emit(10)

            df = FinanceDataEngine.fetch_historical(self.ticker)
            if df is None or df.empty:
                self.error_occurred.emit(f"❌ '{self.ticker}' için veri bulunamadı. Geçersiz sembol olabilir.")
                return

            if self._cancelled:
                return

            self.progress_update.emit(25)

            # ── Adım 3: Teknik göstergeler hesapla (%35) ─────────
            self.status_update.emit("📐 Teknik göstergeler hesaplanıyor (RSI, MACD, BB)...")
            self.progress_update.emit(30)

            df = TechnicalAnalyzer.compute_indicators(df)
            signals = TechnicalAnalyzer.generate_signals(df)

            if self._cancelled:
                return

            self.progress_update.emit(40)

            # Veri hazır sinyali gönder — grafik çizilebilir
            self.data_ready.emit({
                "ticker": self.ticker,
                "info": info,
                "df": df.to_json(date_format='iso'),
                "signals": signals,
            })

            # ── Adım 4: Model eğitimi/cache yükleme (%80) ─────
            engine_name = "LSTM" if LSTMPredictor._check_tf() else "Ridge Ensemble"
            self.status_update.emit(f"🧠 {engine_name} tahmin modeli hazırlanıyor...")
            self.progress_update.emit(45)

            predictor = LSTMPredictor(self.ticker)

            def on_epoch(epoch, loss):
                if epoch == -1:
                    self.status_update.emit("⚡ Model cache'den yüklendi!")
                    self.progress_update.emit(75)
                else:
                    pct = 45 + int((epoch / LSTM_EPOCHS) * 35)
                    self.status_update.emit(f"🧠 Eğitim Epoch {epoch}/{LSTM_EPOCHS} — Kayıp: {loss:.6f}")
                    self.progress_update.emit(min(pct, 80))

            success = predictor.train(df, callback=on_epoch)

            if self._cancelled:
                return

            prediction = None
            if success:
                method = "Monte Carlo" if predictor._use_tf else "Bootstrap Ensemble"
                self.status_update.emit(f"🔮 Gelecek tahmin ediliyor ({method})...")
                self.progress_update.emit(85)
                prediction = predictor.predict(df, days=FORECAST_DAYS)

                if prediction:
                    self.prediction_ready.emit(prediction)

            self.progress_update.emit(95)

            # ── Adım 5: Akıllı Karar (SmartVerdict) ─────────────
            self.status_update.emit("🧩 Akıllı karar motoru çalışıyor...")
            self.progress_update.emit(92)

            verdict = SmartVerdict.evaluate(
                signals=signals,
                prediction=prediction,
                df=df,
                info=info,
            )

            # ── Adım 6: Final raporu (%100) ──────────────────────
            self.status_update.emit("✅ Analiz tamamlandı!")
            self.progress_update.emit(100)

            # Son kapanış fiyatı
            last_close = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else last_close
            daily_change = ((last_close - prev_close) / prev_close) * 100

            # Tahmin değişim oranı
            pred_change = 0
            if prediction and prediction["tahmin"]:
                pred_last = prediction["tahmin"][-1]
                pred_change = ((pred_last - last_close) / last_close) * 100

            self.analysis_complete.emit({
                "ticker": self.ticker,
                "info": info,
                "son_fiyat": last_close,
                "günlük_değişim": daily_change,
                "sinyal": signals,
                "tahmin": prediction,
                "tahmin_değişim": pred_change,
                "veri_sayısı": len(df),
                "verdict": verdict,
            })

        except Exception as e:
            logger.error(f"Analiz pipeline hatası: {e}", exc_info=True)
            self.error_occurred.emit(f"❌ Analiz hatası: {str(e)}")


class TickerDetectionWorker(QThread):
    """
    Sayfa metninden ticker tespitini arka planda yapar.
    """

    tickers_found = pyqtSignal(list)  # List[Dict]
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str, page_text: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.page_text = page_text

    def run(self):
        try:
            results = TickerDetector.detect(self.url, self.page_text)
            self.tickers_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
