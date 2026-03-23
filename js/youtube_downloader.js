/**
 * Visionary Navigator — YouTube Müzik İndirme Eklentisi
 * YouTube video sayfalarında "⬇ Müziği İndir" butonu enjekte eder.
 * QWebChannel üzerinden Python backend'ine indirme isteği gönderir.
 */

(function() {
    'use strict';

    if (window.__visionaryYTDownloaderLoaded) return;
    window.__visionaryYTDownloaderLoaded = true;

    // Sadece YouTube'da çalış
    if (!location.hostname.includes('youtube.com')) return;

    let bridge = null;
    let channelReady = false;
    let currentVideoId = '';
    let buttonInjected = false;

    // ─── QWebChannel Bağlantısı ──────────────────────────────────
    function initChannel() {
        if (typeof QWebChannel === 'undefined') {
            setTimeout(initChannel, 500);
            return;
        }
        try {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.bridge;
                channelReady = true;
                console.log('[Visionary] YouTube downloader köprüsü hazır');
                checkAndInject();
            });
        } catch(e) {
            setTimeout(initChannel, 1000);
        }
    }

    // ─── İndirme Butonu Stili ────────────────────────────────────
    const BTN_STYLE = `
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #6C63FF, #4B4BFF);
        color: #FFFFFF;
        border: none;
        border-radius: 20px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: 600;
        font-family: "Roboto", "Segoe UI", sans-serif;
        cursor: pointer;
        box-shadow: 0 2px 12px rgba(108, 99, 255, 0.35);
        transition: all 0.25s ease;
        margin-left: 8px;
        letter-spacing: 0.3px;
        white-space: nowrap;
    `;

    const BTN_HOVER_STYLE = `
        background: linear-gradient(135deg, #7F77FF, #5C5CFF);
        box-shadow: 0 4px 20px rgba(108, 99, 255, 0.5);
        transform: scale(1.03);
    `;

    const BTN_LOADING_STYLE = `
        background: linear-gradient(135deg, #3A3A50, #2A2A35);
        cursor: wait;
        opacity: 0.7;
    `;

    // ─── Buton Oluştur ──────────────────────────────────────────
    function createDownloadButton() {
        const btn = document.createElement('button');
        btn.id = 'visionary-yt-download';
        btn.innerHTML = '⬇ Müziği İndir';
        btn.setAttribute('style', BTN_STYLE);
        btn.title = 'Visionary Navigator — Bu videoyu müzik olarak indir';

        btn.addEventListener('mouseenter', function() {
            if (!btn.classList.contains('loading')) {
                btn.setAttribute('style', BTN_STYLE + BTN_HOVER_STYLE);
            }
        });
        btn.addEventListener('mouseleave', function() {
            if (!btn.classList.contains('loading')) {
                btn.setAttribute('style', BTN_STYLE);
            }
        });

        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            if (btn.classList.contains('loading')) return;

            const videoUrl = location.href;
            const videoTitle = document.title.replace(' - YouTube', '').trim();

            btn.classList.add('loading');
            btn.innerHTML = '⏳ İndiriliyor...';
            btn.setAttribute('style', BTN_STYLE + BTN_LOADING_STYLE);

            if (bridge && channelReady) {
                bridge.onDomMessage(JSON.stringify({
                    action: 'download_music',
                    data: {
                        url: videoUrl,
                        title: videoTitle
                    }
                }));

                // 3 saniye sonra butonu sıfırla (indirme arka planda devam eder)
                setTimeout(function() {
                    btn.classList.remove('loading');
                    btn.innerHTML = '✅ İndirme başladı!';
                    btn.setAttribute('style', BTN_STYLE);
                    setTimeout(function() {
                        btn.innerHTML = '⬇ Müziği İndir';
                    }, 3000);
                }, 2000);
            } else {
                btn.innerHTML = '⚠️ Bağlantı yok';
                btn.setAttribute('style', BTN_STYLE);
                setTimeout(function() {
                    btn.classList.remove('loading');
                    btn.innerHTML = '⬇ Müziği İndir';
                }, 2000);
            }
        });

        return btn;
    }

    // ─── Butonu Enjekte Et ───────────────────────────────────────
    function injectButton() {
        // Mevcut butonu temizle
        const existing = document.getElementById('visionary-yt-download');
        if (existing) existing.remove();

        // Video sayfasında değilsek çık
        if (!location.pathname.startsWith('/watch')) {
            buttonInjected = false;
            return;
        }

        const videoId = new URLSearchParams(location.search).get('v');
        if (!videoId) return;

        // Aynı video için tekrar enjekte etme
        if (videoId === currentVideoId && buttonInjected) return;
        currentVideoId = videoId;

        // YouTube'un aksiyonlar bölümüne ekle
        // Öncelik sırası: #actions, #menu, #top-level-buttons-computed, #info
        const targets = [
            '#actions #top-level-buttons-computed',     // Yeni YouTube düzeni
            '#menu-container #top-level-buttons-computed',
            'ytd-menu-renderer #top-level-buttons-computed',
            '#actions',                                  // Fallback
            '#info #info-contents',                      // Eski düzen
        ];

        function tryInject() {
            for (const selector of targets) {
                const container = document.querySelector(selector);
                if (container) {
                    const btn = createDownloadButton();
                    container.appendChild(btn);
                    buttonInjected = true;
                    console.log('[Visionary] İndirme butonu enjekte edildi:', selector);
                    return true;
                }
            }
            return false;
        }

        // İlk deneme
        if (!tryInject()) {
            // YouTube SPA — element henüz yüklenmemiş olabilir
            let attempts = 0;
            const retryInterval = setInterval(function() {
                attempts++;
                if (tryInject() || attempts > 20) {
                    clearInterval(retryInterval);
                }
            }, 500);
        }
    }

    // ─── YouTube SPA Navigasyonunu İzle ─────────────────────────
    function checkAndInject() {
        injectButton();
    }

    // YouTube SPA: URL değişikliklerini dinle
    let lastUrl = location.href;
    const observer = new MutationObserver(function() {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            buttonInjected = false;
            // SPA navigasyondan sonra biraz bekle
            setTimeout(checkAndInject, 1500);
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // YouTube'un yt-navigate-finish event'ini dinle (en güvenilir)
    document.addEventListener('yt-navigate-finish', function() {
        buttonInjected = false;
        setTimeout(checkAndInject, 1000);
    });

    // Başlat
    initChannel();

    // Sayfa hazır olduğunda da dene
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(checkAndInject, 2000);
    } else {
        window.addEventListener('DOMContentLoaded', function() {
            setTimeout(checkAndInject, 2000);
        });
    }

})();
