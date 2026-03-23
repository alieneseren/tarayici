/**
 * Visionary Navigator — DOM Interceptor
 * Dinamik SPA sayfalarında ürün görsellerini algılar ve "Üstünde Dene" butonu enjekte eder.
 * MutationObserver + IntersectionObserver ile lazy-load uyumlu çalışır.
 * QWebChannel üzerinden Python backend'ine mesaj gönderir.
 */

(function() {
    'use strict';

    // Zaten enjekte edilmişse tekrar çalıştırma
    if (window.__visionaryInterceptorLoaded) return;
    window.__visionaryInterceptorLoaded = true;

    // ─── Yapılandırma ────────────────────────────────────────────
    const CONFIG = {
        // Ürün görseli algılama desenleri
        imagePatterns: [
            'img[src*="product"]',
            'img[src*="urun"]',
            'img[data-src*="product"]',
            'img[data-src*="urun"]',
            'img.detail-section-img',         // Trendyol
            'img.product-image',              // Hepsiburada
            'img[src*="mnresize"]',           // Trendyol CDN
            'img[src*="productimages"]',      // Hepsiburada CDN
            'img[data-original]',             // Lazy-load varyantı
        ],
        // Minimum boyut filtresi — çok küçük görselleri atla
        minWidth: 150,
        minHeight: 150,
        // Buton stilleri
        buttonStyle: `
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
        buttonHoverStyle: `
            box-shadow: 0 6px 25px rgba(108, 99, 255, 0.6);
            transform: translateY(-2px) scale(1.03);
            opacity: 1;
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
            // QWebChannel yüklenmemişse 500ms sonra tekrar dene
            setTimeout(initWebChannel, 500);
        }
    }
    initWebChannel();

    // Python'a mesaj gönderme
    function sendToPython(action, data) {
        if (pyBridge && pyBridge.onDomMessage) {
            pyBridge.onDomMessage(JSON.stringify({ action: action, data: data }));
        } else {
            console.warn('[Visionary] Python köprüsü henüz hazır değil.');
        }
    }

    // ─── Buton Enjeksiyonu ───────────────────────────────────────
    const processedImages = new WeakSet();

    function injectTryOnButton(imgElement) {
        // Aynı görsele tekrar enjekte etme
        if (processedImages.has(imgElement)) return;

        // Boyut filtresi
        const rect = imgElement.getBoundingClientRect();
        if (rect.width < CONFIG.minWidth || rect.height < CONFIG.minHeight) return;

        // Üst elementi position:relative yap (buton konumlandırması için)
        const parent = imgElement.parentElement;
        if (!parent) return;

        const parentStyle = window.getComputedStyle(parent);
        if (parentStyle.position === 'static') {
            parent.style.position = 'relative';
        }

        // "Üstünde Dene" butonunu oluştur
        const button = document.createElement('button');
        button.textContent = '👕 Üstünde Dene';
        button.setAttribute('style', CONFIG.buttonStyle);
        button.className = 'visionary-tryon-btn';
        button.setAttribute('data-visionary', 'true');

        // Görsel üzerine gelince butonu göster
        parent.addEventListener('mouseenter', () => {
            button.style.opacity = '1';
            button.style.transform = 'translateY(0)';
        });

        parent.addEventListener('mouseleave', () => {
            button.style.opacity = '0';
            button.style.transform = 'translateY(8px)';
        });

        // Buton hover efekti
        button.addEventListener('mouseenter', () => {
            button.style.boxShadow = '0 6px 25px rgba(108, 99, 255, 0.6)';
            button.style.transform = 'translateY(-2px) scale(1.03)';
        });

        button.addEventListener('mouseleave', () => {
            button.style.boxShadow = '0 4px 15px rgba(108, 99, 255, 0.4)';
            button.style.transform = 'translateY(0)';
        });

        // Tıklama — Python'a ürün görselini gönder
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const imgSrc = imgElement.src || imgElement.dataset.src || imgElement.dataset.original || '';
            console.log('[Visionary] Üstünde Dene tıklandı:', imgSrc);

            sendToPython('try_on', {
                imageSrc: imgSrc,
                imageAlt: imgElement.alt || '',
                pageUrl: window.location.href,
            });
        });

        parent.appendChild(button);
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
                    // Görsel yüklendikten sonra enjekte et
                    if (img.complete && img.naturalWidth > 0) {
                        injectTryOnButton(img);
                    } else {
                        img.addEventListener('load', () => injectTryOnButton(img), { once: true });
                    }
                });
            } catch (e) {
                // Geçersiz selector — sessizce atla
            }
        });
    }

    // ─── MutationObserver — Dinamik İçerik İzleme ────────────────
    const mutationObserver = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Eklenen düğüm bir görsel mi?
                    if (node.tagName === 'IMG') {
                        injectTryOnButton(node);
                    }
                    // Veya görsel içeriyor mu?
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
                // data-src → src dönüşümünü bekle
                setTimeout(() => {
                    if (img.src && img.naturalWidth > 0) {
                        injectTryOnButton(img);
                    }
                }, 300);
                intersectionObserver.unobserve(img);
            }
        });
    }, { threshold: 0.1 });

    // Tüm görselleri gözlemle
    function observeAllImages() {
        document.querySelectorAll('img[data-src], img[data-original], img[loading="lazy"]').forEach(img => {
            if (!processedImages.has(img)) {
                intersectionObserver.observe(img);
            }
        });
    }

    // ─── Başlatma ────────────────────────────────────────────────
    function initialize() {
        // Mevcut görselleri tara
        scanForProductImages(document.body);

        // Lazy-load görselleri gözlemle
        observeAllImages();

        // Dinamik değişiklikleri izle
        mutationObserver.observe(document.body, {
            childList: true,
            subtree: true,
        });

        console.log('[Visionary] DOM Interceptor aktif.');
    }

    // DOM hazır olduğunda başlat
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // SPA navigasyon değişikliklerini algıla
    let lastUrl = window.location.href;
    setInterval(() => {
        if (window.location.href !== lastUrl) {
            lastUrl = window.location.href;
            console.log('[Visionary] Sayfa değişikliği algılandı, tekrar taranıyor...');
            setTimeout(() => {
                scanForProductImages(document.body);
                observeAllImages();
            }, 1000);
        }
    }, 1000);

})();
