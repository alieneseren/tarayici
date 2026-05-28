/**
 * Visionary Navigator — DOM Interceptor
 * Dinamik SPA sayfalarında ürün görsellerini algılar ve
 * "Üstünde Dene" (AR kıyafet) + "Yüzünü Dene" (FaceSwap) butonları enjekte eder.
 * MutationObserver + IntersectionObserver ile lazy-load uyumlu çalışır.
 *
 * Desteklenen siteler:
 *   Trendyol, Hepsiburada, DS Damat, Beymen, Koton, LCWaikiki,
 *   Mavi, Defacto, Boyner, Zara, H&M, N11, Amazon TR,
 *   ve genel e-ticaret siteleri.
 */

(function() {
    'use strict';

    if (window.__visionaryInterceptorLoaded) return;
    window.__visionaryInterceptorLoaded = true;

    // ─── Yapılandırma ────────────────────────────────────────────
    const CONFIG = {
        // Geniş ürün görseli algılama desenleri
        imagePatterns: [
            // ── Genel e-ticaret ──────────────────────────────
            'img[src*="product"]',
            'img[src*="urun"]',
            'img[data-src*="product"]',
            'img[data-src*="urun"]',
            'img[data-original]',

            // ── Trendyol ─────────────────────────────────────
            'img.detail-section-img',
            'img[src*="mnresize"]',
            'img[src*="ty1.imgix"]',
            'img.product-slide-img',

            // ── Hepsiburada ──────────────────────────────────
            'img.product-image',
            'img[src*="productimages"]',
            'img[src*="hepsiburada.net"]',

            // ── DS Damat ─────────────────────────────────────
            'img[src*="dsdamat"]',
            'img[src*="statics.boyner"]',
            '.product-detail img',
            '.product-image-container img',
            '.gallery-image img',
            '.image-wrapper img',
            '.slick-slide img',

            // ── Beymen ───────────────────────────────────────
            'img[src*="beymen.com"]',
            'img[src*="byndynet"]',
            '.o-productDetail__image img',
            '.product-detail-image img',

            // ── Koton ────────────────────────────────────────
            'img[src*="koton.com"]',
            '.product-detail-slider img',
            '.pdp-image img',

            // ── LCWaikiki ────────────────────────────────────
            'img[src*="lcwaikiki"]',
            'img[src*="lcw-cdn"]',
            '.product-detail-main-image img',

            // ── Mavi ─────────────────────────────────────────
            'img[src*="mavi.com"]',
            '.product-main-image img',

            // ── Defacto ──────────────────────────────────────
            'img[src*="defacto"]',
            '.product-detail-images img',

            // ── Boyner ───────────────────────────────────────
            'img[src*="boyner.com"]',

            // ── Zara / H&M / global ─────────────────────────
            'img[src*="zara.com"]',
            'img[src*="lp2.hm.com"]',
            '.media-image img',
            'img[src*="scene7"]',

            // ── N11 ──────────────────────────────────────────
            'img[src*="n11.com"]',
            '.productImage img',

            // ── Amazon TR ────────────────────────────────────
            'img[src*="images-amazon"]',
            '#landingImage',
            '#imgBlkFront',

            // ── Genel SPA desenleri ──────────────────────────
            '[data-testid*="product"] img',
            '[data-testid*="image"] img',
            '.product-gallery img',
            '.product-slider img',
            '.pdp-gallery img',
            '.carousel-item img',
            '.swiper-slide img',
            'picture source + img',
        ],
        // Minimum boyut filtresi
        minWidth: 180,
        minHeight: 220,

        // Yüz değiştirme butonu: daha yüksek görseller (mankenli)
        faceSwapMinHeight: 300,
        faceSwapMinAspectRatio: 0.5,  // height/width > 0.5

        // ── Buton stilleri ────────────────────────────────────────
        tryOnButtonStyle: `
            position: absolute;
            bottom: 12px;
            right: 12px;
            z-index: 10000;
            background: linear-gradient(135deg, #6C63FF, #00D9FF);
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
            font-family: "Inter", "Segoe UI", sans-serif;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(108, 99, 255, 0.4);
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
            opacity: 0;
            transform: translateY(8px);
        `,
        faceSwapButtonStyle: `
            position: absolute;
            bottom: 12px;
            left: 12px;
            z-index: 10000;
            background: linear-gradient(135deg, #FF6B6B, #EE5A24);
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
            font-family: "Inter", "Segoe UI", sans-serif;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255, 107, 107, 0.4);
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
            opacity: 0;
            transform: translateY(8px);
        `,
    };

    // ─── QWebChannel İletişimi ───────────────────────────────────
    let pyBridge = null;

    function initWebChannel() {
        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                pyBridge = channel.objects.bridge;
                console.log('[Visionary] QWebChannel bağlantısı kuruldu.');
            });
        } else {
            setTimeout(initWebChannel, 500);
        }
    }
    initWebChannel();

    function sendToPython(action, data) {
        if (pyBridge && pyBridge.onDomMessage) {
            pyBridge.onDomMessage(JSON.stringify({ action: action, data: data }));
        } else {
            console.warn('[Visionary] Python köprüsü henüz hazır değil.');
        }
    }

    // ─── Buton Enjeksiyonu ───────────────────────────────────────
    const processedImages = new WeakSet();

    /**
     * Görselin mankenli bir fotoğraf olup olmadığını heuristic olarak belirler.
     * Yüksek, dikey oranı olan görseller genellikle manken fotoğrafıdır.
     */
    function isLikelyModelPhoto(imgElement) {
        const rect = imgElement.getBoundingClientRect();
        if (rect.height < CONFIG.faceSwapMinHeight) return false;
        const ratio = rect.height / Math.max(rect.width, 1);
        return ratio >= CONFIG.faceSwapMinAspectRatio;
    }

    /**
     * URL veya context'e göre bu bir moda/giyim sitesi mi?
     */
    function isFashionSite() {
        const host = window.location.hostname.toLowerCase();
        const fashionDomains = [
            'trendyol', 'hepsiburada', 'dsdamat', 'beymen', 'koton',
            'lcwaikiki', 'mavi', 'defacto', 'boyner', 'zara', 'hm.com',
            'n11', 'amazon', 'morhipo', 'modanisa', 'penti', 'ipekyol',
            'vakko', 'networkfashion', 'colins', 'uspoloassn', 'kiğılı',
            'kigili', 'damat', 'hatemoğlu', 'hatemoglu', 'sarar',
            'waikiki', 'flo', 'atasun', 'gratis'
        ];
        return fashionDomains.some(d => host.includes(d));
    }

    function injectButtons(imgElement) {
        if (processedImages.has(imgElement)) return;

        const rect = imgElement.getBoundingClientRect();
        if (rect.width < CONFIG.minWidth || rect.height < CONFIG.minHeight) return;

        const parent = imgElement.parentElement;
        if (!parent) return;

        const parentStyle = window.getComputedStyle(parent);
        if (parentStyle.position === 'static') {
            parent.style.position = 'relative';
        }

        const imgSrc = imgElement.src || imgElement.dataset.src || imgElement.dataset.original || '';

        // ── "Üstünde Dene" butonu (AR kıyafet overlay) ──────────
        const tryOnBtn = document.createElement('button');
        tryOnBtn.textContent = '👕 Üstünde Dene';
        tryOnBtn.setAttribute('style', CONFIG.tryOnButtonStyle);
        tryOnBtn.className = 'visionary-tryon-btn';
        tryOnBtn.setAttribute('data-visionary', 'true');

        tryOnBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            sendToPython('try_on', {
                imageSrc: imgSrc,
                imageAlt: imgElement.alt || '',
                pageUrl: window.location.href,
            });
        });

        // ── "Yüzünü Dene" butonu (FaceSwap) ─────────────────────
        let faceSwapBtn = null;
        if (isLikelyModelPhoto(imgElement) || isFashionSite()) {
            faceSwapBtn = document.createElement('button');
            faceSwapBtn.textContent = '🎭 Yüzünü Dene';
            faceSwapBtn.setAttribute('style', CONFIG.faceSwapButtonStyle);
            faceSwapBtn.className = 'visionary-faceswap-btn';
            faceSwapBtn.setAttribute('data-visionary', 'true');

            faceSwapBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Visionary] Yüzünü Dene tıklandı:', imgSrc);
                sendToPython('face_try_on', {
                    imageSrc: imgSrc,
                    imageAlt: imgElement.alt || '',
                    pageUrl: window.location.href,
                });
            });

            // Hover efektleri
            faceSwapBtn.addEventListener('mouseenter', () => {
                faceSwapBtn.style.boxShadow = '0 6px 25px rgba(255, 107, 107, 0.6)';
                faceSwapBtn.style.transform = 'translateY(-2px) scale(1.03)';
            });
            faceSwapBtn.addEventListener('mouseleave', () => {
                faceSwapBtn.style.boxShadow = '0 4px 15px rgba(255, 107, 107, 0.4)';
                faceSwapBtn.style.transform = 'translateY(0)';
            });
        }

        // Hover: butonları göster/gizle
        parent.addEventListener('mouseenter', () => {
            tryOnBtn.style.opacity = '1';
            tryOnBtn.style.transform = 'translateY(0)';
            if (faceSwapBtn) {
                faceSwapBtn.style.opacity = '1';
                faceSwapBtn.style.transform = 'translateY(0)';
            }
        });
        parent.addEventListener('mouseleave', () => {
            tryOnBtn.style.opacity = '0';
            tryOnBtn.style.transform = 'translateY(8px)';
            if (faceSwapBtn) {
                faceSwapBtn.style.opacity = '0';
                faceSwapBtn.style.transform = 'translateY(8px)';
            }
        });

        // tryOn hover efektleri
        tryOnBtn.addEventListener('mouseenter', () => {
            tryOnBtn.style.boxShadow = '0 6px 25px rgba(108, 99, 255, 0.6)';
            tryOnBtn.style.transform = 'translateY(-2px) scale(1.03)';
        });
        tryOnBtn.addEventListener('mouseleave', () => {
            tryOnBtn.style.boxShadow = '0 4px 15px rgba(108, 99, 255, 0.4)';
            tryOnBtn.style.transform = 'translateY(0)';
        });

        parent.appendChild(tryOnBtn);
        if (faceSwapBtn) parent.appendChild(faceSwapBtn);
        processedImages.add(imgElement);
    }

    // ─── Ürün Görsellerini Tara ──────────────────────────────────
    function scanForProductImages(rootNode) {
        const root = rootNode || document.body;
        if (!root || !root.querySelectorAll) return;

        CONFIG.imagePatterns.forEach(selector => {
            try {
                const images = root.querySelectorAll(selector);
                images.forEach(img => {
                    if (img.complete && img.naturalWidth > 0) {
                        injectButtons(img);
                    } else {
                        img.addEventListener('load', () => injectButtons(img), { once: true });
                    }
                });
            } catch (e) {
                // Geçersiz selector
            }
        });
    }

    // ─── MutationObserver — Dinamik İçerik İzleme ────────────────
    const mutationObserver = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.tagName === 'IMG') {
                        injectButtons(node);
                    }
                    scanForProductImages(node);
                }
            });
        });
    });

    // ─── IntersectionObserver — Lazy-Load Algılama ───────────────
    const intersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                setTimeout(() => {
                    if (img.src && img.naturalWidth > 0) {
                        injectButtons(img);
                    }
                }, 300);
                intersectionObserver.unobserve(img);
            }
        });
    }, { threshold: 0.1 });

    function observeAllImages() {
        document.querySelectorAll('img[data-src], img[data-original], img[loading="lazy"]').forEach(img => {
            if (!processedImages.has(img)) {
                intersectionObserver.observe(img);
            }
        });
    }

    // ─── Başlatma ────────────────────────────────────────────────
    function initialize() {
        scanForProductImages(document.body);
        observeAllImages();

        mutationObserver.observe(document.body, {
            childList: true,
            subtree: true,
        });

        console.log('[Visionary] DOM Interceptor aktif — FaceSwap desteği açık.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // SPA navigasyon
    let lastUrl = window.location.href;
    setInterval(() => {
        if (window.location.href !== lastUrl) {
            lastUrl = window.location.href;
            console.log('[Visionary] Sayfa değişikliği — tekrar taranıyor...');
            setTimeout(() => {
                scanForProductImages(document.body);
                observeAllImages();
            }, 1000);
        }
    }, 1000);

})();
