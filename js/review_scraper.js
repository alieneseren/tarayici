/**
 * Visionary Navigator — Evrensel E-Ticaret Kazıyıcı
 * TÜM e-ticaret sitelerinde çalışır.
 * Ürün bilgileri, yorumlar, soru-cevap bölümleri ve satıcı verileri toplanır.
 * Sonuçları JSON olarak QWebChannel üzerinden Python'a iletir.
 */

(function () {
    'use strict';

    // ─── Site Algılama ───────────────────────────────────────────
    function detectSite() {
        const h = window.location.hostname.toLowerCase();
        if (h.includes('trendyol')) return 'trendyol';
        if (h.includes('hepsiburada')) return 'hepsiburada';
        if (h.includes('amazon')) return 'amazon';
        if (h.includes('n11')) return 'n11';
        if (h.includes('gittigidiyor') || h.includes('ebay')) return 'gittigidiyor';
        if (h.includes('ciceksepeti')) return 'ciceksepeti';
        if (h.includes('morhipo')) return 'morhipo';
        if (h.includes('boyner')) return 'boyner';
        if (h.includes('lcwaikiki')) return 'lcwaikiki';
        if (h.includes('koton')) return 'koton';
        if (h.includes('defacto')) return 'defacto';
        if (h.includes('zara')) return 'zara';
        if (h.includes('mango')) return 'mango';
        return 'generic';
    }

    // ─── Yardımcılar ────────────────────────────────────────────
    function qText(selector) {
        const el = document.querySelector(selector);
        return el ? el.textContent.trim() : '';
    }

    function qAllTexts(selectors, maxCount) {
        maxCount = maxCount || 30;
        const results = [];
        for (const sel of selectors) {
            try {
                const els = document.querySelectorAll(sel);
                els.forEach((el, i) => {
                    if (results.length >= maxCount) return;
                    const text = el.textContent.trim();
                    if (text && text.length > 5) {
                        results.push(text);
                    }
                });
            } catch (e) { /* geçersiz seçici */ }
        }
        return results;
    }

    function findFirstMatch(selectors) {
        for (const sel of selectors) {
            const val = qText(sel);
            if (val) return val;
        }
        return '';
    }

    // Yorum/Q&A sekmelerine tıklama girişimi — SADECE navigasyon yapmayan öğeler
    function clickReviewTabs() {
        // Sadece button, div, span, li gibi navigasyon yapmayan öğeleri tıkla.
        // Anchor (a) tagları SADECE href="#" veya "javascript:" ise tıklanır.
        const safeSelectors = [
            // Butonlar (en güvenli)
            'button[class*="review"], button[class*="yorum"], button[class*="comment"]',
            'button[class*="question"], button[class*="soru"], button[class*="qa"]',
            'button[class*="degerlendirme"], button[class*="Rating"]',
            // Tab rolleri (navigasyon yapmaz)
            '[role="tab"][aria-controls*="review"]',
            '[role="tab"][aria-controls*="comment"]',
            '[role="tab"][aria-controls*="yorum"]',
            '[role="tab"][aria-controls*="question"]',
            // Trendyol özel tab
            'li[data-tab="ratings"]',
            // Hepsiburada özel tab (data-test-id)
            '[data-test-id="review-tab"]',
            '[data-test-id="qa-tab"]',
            // Div/Span tabları
            'div[class*="tab"][class*="review"], div[class*="tab"][class*="yorum"]',
            'span[class*="tab"][class*="review"], span[class*="tab"][class*="yorum"]',
        ];

        for (const sel of safeSelectors) {
            try {
                const tabs = document.querySelectorAll(sel);
                tabs.forEach(tab => {
                    try { tab.click(); } catch (e) { }
                });
            } catch (e) { }
        }

        // Anchor taglarını YALNIZCA güvenli olanları tıkla (navigasyon yapmayan)
        const safeAnchors = document.querySelectorAll(
            'a[href="#"][class*="review"], a[href="#"][class*="yorum"], ' +
            'a[href="javascript:void(0)"][class*="review"], ' +
            'a[href^="#"][class*="tab"]'
        );
        safeAnchors.forEach(a => {
            try { a.click(); } catch (e) { }
        });
    }

    // ─── Trendyol ────────────────────────────────────────────────
    function scrapeTrendyol() {
        const data = { site: 'trendyol', productName: '', price: '', rating: '', reviewCount: '', seller: '', sellerScore: '', reviews: [], questions: [] };

        data.productName = findFirstMatch(['.pr-new-br h1', '.product-name', 'h1.pr-new-br', 'h1']);
        data.price = findFirstMatch(['.prc-dsc', '.prc-org', 'span[data-testid="price"]']);
        data.rating = findFirstMatch(['.tltp-avg', '.rating-line-count', '.star-w']);
        data.reviewCount = findFirstMatch(['.rnr-com-cnt', '.total-review-count']);
        data.seller = findFirstMatch(['.merchant-box .merchant-name', 'a[data-testid="merchant-name"]']);
        data.sellerScore = findFirstMatch(['.merchant-box .merchant-score', '.sl-pn']);

        // Yorumlar
        const reviewCards = document.querySelectorAll('.pr-rnr-com-w .comment, .rnr-com-w, [class*="review-card"], [class*="ReviewCard"]');
        reviewCards.forEach((card, i) => {
            if (i >= 30) return;
            const review = {};
            const starEl = card.querySelector('.star-w, .ratings, [class*="star"]');
            if (starEl) review.stars = starEl.textContent.trim();
            const textEl = card.querySelector('.rnr-com-tx p, .comment-text, [class*="comment-text"], p');
            if (textEl) review.text = textEl.textContent.trim();
            const userEl = card.querySelector('.rnr-com-nm, .comment-user');
            if (userEl) review.user = userEl.textContent.trim();
            if (review.text) data.reviews.push(review);
        });

        // Soru-Cevap
        const qaCards = document.querySelectorAll('.qa-w, [class*="question-item"], [class*="qa-item"]');
        qaCards.forEach((card, i) => {
            if (i >= 15) return;
            data.questions.push(card.textContent.trim().substring(0, 300));
        });

        return data;
    }

    // ─── Hepsiburada ─────────────────────────────────────────────
    function scrapeHepsiburada() {
        const data = { site: 'hepsiburada', productName: '', price: '', rating: '', reviewCount: '', seller: '', sellerScore: '', reviews: [], questions: [] };

        data.productName = findFirstMatch(['#product-name', 'h1[data-test-id="product-name"]', 'h1']);
        data.price = findFirstMatch(['[data-test-id="price-current-price"]', '.product-price', '.price-value']);
        data.rating = findFirstMatch(['.hermes-RatingStars-module', '.rating-value', '[class*="rating"]']);
        data.reviewCount = findFirstMatch(['.hermes-RatingStars-module + span', '.review-count']);
        data.seller = findFirstMatch(['.merchant-info .merchant-name', '[data-test-id="merchant-name"]']);

        const reviewCards = document.querySelectorAll('.hermes-ReviewCard, .review-item, [class*="ReviewCard"], [class*="review-card"]');
        reviewCards.forEach((card, i) => {
            if (i >= 30) return;
            const review = {};
            const starEl = card.querySelector('[class*="star"], [class*="Star"], [class*="rating"]');
            if (starEl) review.stars = starEl.textContent.trim();
            const textEl = card.querySelector('[class*="text"], [class*="comment"], p');
            if (textEl) review.text = textEl.textContent.trim();
            if (review.text) data.reviews.push(review);
        });

        // Soru-Cevap
        const qaCards = document.querySelectorAll('[class*="question"], [class*="Question"], [class*="qa"]');
        qaCards.forEach((card, i) => {
            if (i >= 15) return;
            const t = card.textContent.trim();
            if (t.length > 10) data.questions.push(t.substring(0, 300));
        });

        return data;
    }

    // ─── Amazon ──────────────────────────────────────────────────
    function scrapeAmazon() {
        const data = { site: 'amazon', productName: '', price: '', rating: '', reviewCount: '', seller: '', sellerScore: '', reviews: [], questions: [] };

        data.productName = findFirstMatch(['#productTitle', 'h1 span#productTitle']);
        data.price = findFirstMatch(['.a-price .a-offscreen', '#priceblock_ourprice', '#priceblock_dealprice', '.a-price-whole']);
        data.rating = findFirstMatch(['#acrPopover .a-icon-alt', '.averageStarRating span', '#averageCustomerReviews .a-icon-alt']);
        data.reviewCount = findFirstMatch(['#acrCustomerReviewText', '#reviewsMedley .a-size-base']);
        data.seller = findFirstMatch(['#sellerProfileTriggerId', '#merchant-info a', '#tabular-buybox .tabular-buybox-text a']);

        const reviewCards = document.querySelectorAll('.review, [data-hook="review"], .a-section.review');
        reviewCards.forEach((card, i) => {
            if (i >= 30) return;
            const review = {};
            const starEl = card.querySelector('.review-rating .a-icon-alt, [data-hook="review-star-rating"]');
            if (starEl) review.stars = starEl.textContent.trim();
            const textEl = card.querySelector('.review-text-content span, [data-hook="review-body"] span');
            if (textEl) review.text = textEl.textContent.trim();
            if (review.text) data.reviews.push(review);
        });

        // Soru-Cevap
        const qaCards = document.querySelectorAll('.askTeaserQuestions .a-fixed-left-grid, [class*="qanda"]');
        qaCards.forEach((card, i) => {
            if (i >= 15) return;
            data.questions.push(card.textContent.trim().substring(0, 300));
        });

        return data;
    }

    // ─── N11 ─────────────────────────────────────────────────────
    function scrapeN11() {
        const data = { site: 'n11', productName: '', price: '', rating: '', reviewCount: '', seller: '', sellerScore: '', reviews: [], questions: [] };

        data.productName = findFirstMatch(['.proName', 'h1.proName', 'h1']);
        data.price = findFirstMatch(['.newPrice ins', '.unf-p-price', '.newPrice']);
        data.rating = findFirstMatch(['.ratingCont strong', '.avgRating']);
        data.seller = findFirstMatch(['.sallerName a', '.seller-name a']);

        const reviewCards = document.querySelectorAll('.comment-row, .commentRow, [class*="comment-item"]');
        reviewCards.forEach((card, i) => {
            if (i >= 30) return;
            const review = {};
            const textEl = card.querySelector('.comment-body p, .commentBody, [class*="comment-text"]');
            if (textEl) review.text = textEl.textContent.trim();
            const starEl = card.querySelector('.star-w, [class*="star"], [class*="rating"]');
            if (starEl) review.stars = starEl.textContent.trim();
            if (review.text) data.reviews.push(review);
        });

        return data;
    }

    // ─── Evrensel Kazıma (Desteklenmeyen Siteler İçin) ──────────
    function scrapeGeneric() {
        const data = {
            site: detectSite(),
            productName: '',
            price: '',
            rating: '',
            reviewCount: '',
            seller: '',
            sellerScore: '',
            reviews: [],
            questions: [],
            pageText: '',
        };

        // Ürün adı — h1 veya title
        data.productName = findFirstMatch([
            'h1', '[class*="product-name"]', '[class*="productName"]',
            '[class*="product-title"]', '[class*="productTitle"]',
            '[itemprop="name"]'
        ]) || document.title;

        // Fiyat
        data.price = findFirstMatch([
            '[class*="price"]', '[itemprop="price"]',
            '[class*="Price"]', '[data-price]',
            '[class*="fiyat"]', '[class*="Fiyat"]',
        ]);

        // Puan
        data.rating = findFirstMatch([
            '[class*="rating"]', '[class*="Rating"]',
            '[itemprop="ratingValue"]', '[class*="star"]',
            '[class*="puan"]', '[class*="Puan"]',
        ]);

        // Yorumları akıllıca bul
        const reviewSelectors = [
            '[class*="review"]', '[class*="Review"]',
            '[class*="comment"]', '[class*="Comment"]',
            '[class*="yorum"]', '[class*="Yorum"]',
            '[class*="degerlendirme"]', '[class*="Degerlendirme"]',
            '[class*="feedback"]', '[class*="testimonial"]',
            '[itemprop="review"]',
        ];

        const seenTexts = new Set();
        for (const sel of reviewSelectors) {
            try {
                const els = document.querySelectorAll(sel);
                els.forEach(el => {
                    if (data.reviews.length >= 30) return;
                    const text = el.textContent.trim();
                    if (text.length > 20 && text.length < 2000 && !seenTexts.has(text)) {
                        seenTexts.add(text);
                        data.reviews.push({ text: text.substring(0, 500) });
                    }
                });
            } catch (e) { }
        }

        // Soru-Cevap bölümleri
        const qaSelectors = [
            '[class*="question"]', '[class*="Question"]',
            '[class*="soru"]', '[class*="Soru"]',
            '[class*="qa"]', '[class*="QA"]',
            '[class*="faq"]', '[class*="FAQ"]',
        ];

        for (const sel of qaSelectors) {
            try {
                const els = document.querySelectorAll(sel);
                els.forEach(el => {
                    if (data.questions.length >= 15) return;
                    const t = el.textContent.trim();
                    if (t.length > 10 && t.length < 1000) {
                        data.questions.push(t.substring(0, 300));
                    }
                });
            } catch (e) { }
        }

        // Fallback: Ham sayfa metni (reviews boş veya çok azsa)
        if (data.reviews.length < 3) {
            data.pageText = (document.body.innerText || '').substring(0, 6000);
        }

        return data;
    }

    // ─── Ana Kazıma Fonksiyonu ───────────────────────────────────
    window.__visionaryScrapeReviews = function () {
        // Önce yorum/değerlendirme sekmelerine tıklama dene
        clickReviewTabs();

        const site = detectSite();
        let result;
        switch (site) {
            case 'trendyol': result = scrapeTrendyol(); break;
            case 'hepsiburada': result = scrapeHepsiburada(); break;
            case 'amazon': result = scrapeAmazon(); break;
            case 'n11': result = scrapeN11(); break;
            default: result = scrapeGeneric(); break;
        }

        // Eğer hiç yorum bulunamadıysa pageText fallback
        if (result.reviews.length === 0 && !result.pageText) {
            result.pageText = (document.body.innerText || '').substring(0, 6000);
        }

        return JSON.stringify(result, null, 2);
    };

    console.log('[Visionary] Evrensel E-Ticaret Kazıyıcı hazır. Site:', detectSite());
})();
