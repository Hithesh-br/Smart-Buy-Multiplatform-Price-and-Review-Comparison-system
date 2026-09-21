/**
 * url_search.js
 * ==============
 * SmartBuy "Search by Product URL" Frontend Controller:
 * - Toggles between [ Search Product Name ] and [ Search Product URL ]
 * - Auto-detects marketplace (Amazon, Flipkart, Meesho) on paste/typing
 * - Real-time SSE progress tracker (URL detected -> Source extracted -> Targets checked -> Matched -> Best Deal)
 * - Error isolation and graceful fallback
 */

(function () {
    'use strict';

    // Elements
    const modeNameBtn = document.getElementById('modeNameBtn');
    const modeUrlBtn = document.getElementById('modeUrlBtn');
    const nameSearchContainer = document.getElementById('nameSearchContainer') || document.getElementById('product-specs');
    const urlSearchContainer = document.getElementById('urlSearchContainer');
    const urlInput = document.getElementById('productUrlInput');
    const urlCompareBtn = document.getElementById('urlCompareBtn');
    const urlPlatformBadge = document.getElementById('urlPlatformBadge');
    const urlProgressCard = document.getElementById('urlProgressCard');
    const urlProgressBar = document.getElementById('urlProgressBar');
    const urlProgressSteps = document.getElementById('urlProgressSteps');
    const urlErrorAlert = document.getElementById('urlErrorAlert');

    const STEPS_DEF = [
        { id: 'url_detected', label: 'URL detected' },
        { id: 'source_extracted', label: 'Source product extracted' },
        { id: 'amazon_checked', label: 'Amazon checked' },
        { id: 'flipkart_checked', label: 'Flipkart checked' },
        { id: 'meesho_checked', label: 'Meesho checked' },
        { id: 'products_matched', label: 'Products matched' },
        { id: 'best_deal_calculated', label: 'Best deal calculated' },
    ];

    window.switchSearchMode = function (mode) {
        if (!modeNameBtn || !modeUrlBtn) return;

        if (mode === 'url') {
            modeNameBtn.classList.remove('active', 'btn-primary');
            modeNameBtn.classList.add('btn-outline-primary');
            modeUrlBtn.classList.add('active', 'btn-primary');
            modeUrlBtn.classList.remove('btn-outline-primary');

            if (nameSearchContainer) nameSearchContainer.classList.add('d-none');
            if (urlSearchContainer) {
                urlSearchContainer.classList.remove('d-none');
                if (urlInput) urlInput.focus();
            }
            try { localStorage.setItem('smartbuy_search_mode', 'url'); } catch (e) {}
        } else {
            modeUrlBtn.classList.remove('active', 'btn-primary');
            modeUrlBtn.classList.add('btn-outline-primary');
            modeNameBtn.classList.add('active', 'btn-primary');
            modeNameBtn.classList.remove('btn-outline-primary');

            if (urlSearchContainer) urlSearchContainer.classList.add('d-none');
            if (nameSearchContainer) nameSearchContainer.classList.remove('d-none');
            try { localStorage.setItem('smartbuy_search_mode', 'name'); } catch (e) {}
        }
    };

    function detectPlatformClient(val) {
        if (!val) return null;
        const low = val.toLowerCase().trim();
        if (low.includes('amazon.in') || low.includes('amazon.co.in') || low.includes('amzn.in') || low.includes('amzn.to')) {
            return { key: 'amazon', name: 'Amazon India', icon: 'fab fa-amazon text-warning', badgeClass: 'badge-amazon' };
        }
        if (low.includes('flipkart.com')) {
            return { key: 'flipkart', name: 'Flipkart', icon: 'fas fa-store text-primary', badgeClass: 'badge-flipkart' };
        }
        if (low.includes('meesho.com')) {
            return { key: 'meesho', name: 'Meesho', icon: 'fas fa-tags text-danger', badgeClass: 'badge-meesho' };
        }
        return null;
    }

    function updateUrlBadge() {
        if (!urlInput || !urlPlatformBadge) return;
        const val = urlInput.value.trim();
        const plat = detectPlatformClient(val);

        if (plat) {
            urlPlatformBadge.innerHTML = `<i class="${plat.icon} me-1"></i><strong>${plat.name}</strong> detected`;
            urlPlatformBadge.className = 'badge rounded-pill px-3 py-2 ' + (plat.key === 'amazon' ? 'bg-dark text-warning border border-warning' : (plat.key === 'flipkart' ? 'bg-primary text-white' : 'bg-danger text-white'));
            urlPlatformBadge.style.display = 'inline-flex';
        } else if (val.length > 5) {
            urlPlatformBadge.innerHTML = `<i class="fas fa-question-circle me-1"></i>Unknown Platform`;
            urlPlatformBadge.className = 'badge bg-secondary rounded-pill px-3 py-2 text-white';
            urlPlatformBadge.style.display = 'inline-flex';
        } else {
            urlPlatformBadge.style.display = 'none';
        }
    }

    if (urlInput) {
        urlInput.addEventListener('input', updateUrlBadge);
        urlInput.addEventListener('paste', () => setTimeout(updateUrlBadge, 50));
        urlInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                startUrlComparison();
            }
        });
    }

    window.pasteClipboardToUrl = async function () {
        if (!navigator.clipboard) return;
        try {
            const text = await navigator.clipboard.readText();
            if (text && urlInput) {
                urlInput.value = text.trim();
                updateUrlBadge();
                urlInput.focus();
            }
        } catch (e) {
            console.debug('Clipboard read permission denied', e);
        }
    };

    function resetProgressUI() {
        if (!urlProgressCard || !urlProgressSteps) return;
        urlProgressCard.classList.remove('d-none');
        if (urlErrorAlert) urlErrorAlert.classList.add('d-none');
        if (urlProgressBar) {
            urlProgressBar.style.width = '10%';
            urlProgressBar.className = 'progress-bar progress-bar-striped progress-bar-animated bg-primary';
        }

        let html = '';
        STEPS_DEF.forEach(step => {
            html += `
                <div class="progress-step-item d-flex align-items-center justify-content-between p-2 rounded-3 mb-2" id="step_row_${step.id}" style="background: rgba(248,250,252,0.8); border: 1px solid rgba(226,232,240,0.8);">
                    <div class="d-flex align-items-center gap-2">
                        <span class="step-icon" id="step_icon_${step.id}">
                            <i class="fas fa-circle-notch fa-spin text-muted" style="font-size: 0.9rem;"></i>
                        </span>
                        <span class="step-label fw-semibold small text-dark">${step.label}</span>
                    </div>
                    <span class="step-msg small text-muted" id="step_msg_${step.id}">Waiting...</span>
                </div>
            `;
        });
        urlProgressSteps.innerHTML = html;
    }

    function setStepStatus(stepId, status, message) {
        const row = document.getElementById(`step_row_${stepId}`);
        const icon = document.getElementById(`step_icon_${stepId}`);
        const msg = document.getElementById(`step_msg_${stepId}`);
        if (!row || !icon || !msg) return;

        if (status === 'done') {
            icon.innerHTML = '<i class="fas fa-check-circle text-success" style="font-size: 1.05rem;"></i>';
            row.style.background = 'rgba(236, 253, 245, 0.9)';
            row.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            msg.innerHTML = `<span class="text-success fw-medium">${message || 'Done'}</span>`;
        } else if (status === 'running') {
            icon.innerHTML = '<i class="fas fa-spinner fa-spin text-primary" style="font-size: 1.05rem;"></i>';
            row.style.background = 'rgba(239, 246, 255, 0.9)';
            row.style.borderColor = 'rgba(59, 130, 246, 0.3)';
            msg.innerHTML = `<span class="text-primary fw-medium">${message || 'Working...'}</span>`;
        } else if (status === 'warning') {
            icon.innerHTML = '<i class="fas fa-exclamation-triangle text-warning" style="font-size: 1.05rem;"></i>';
            row.style.background = 'rgba(254, 252, 232, 0.9)';
            row.style.borderColor = 'rgba(234, 179, 8, 0.3)';
            msg.innerHTML = `<span class="text-warning fw-medium">${message || 'Unavailable'}</span>`;
        } else if (status === 'error') {
            icon.innerHTML = '<i class="fas fa-times-circle text-danger" style="font-size: 1.05rem;"></i>';
            row.style.background = 'rgba(254, 242, 242, 0.9)';
            row.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            msg.innerHTML = `<span class="text-danger fw-medium">${message || 'Failed'}</span>`;
        }
    }

    window.startUrlComparison = function () {
        if (!urlInput) return;
        const targetUrl = urlInput.value.trim();
        if (!targetUrl) {
            alert('Please paste a product URL from Amazon, Flipkart, or Meesho.');
            urlInput.focus();
            return;
        }

        if (urlCompareBtn) {
            urlCompareBtn.disabled = true;
            urlCompareBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Comparing...';
        }

        resetProgressUI();
        setStepStatus('url_detected', 'running', 'Validating URL...');

        // Check if EventSource is supported for real streaming updates
        if (window.EventSource) {
            const streamUrl = `/api/compare-url/stream?url=${encodeURIComponent(targetUrl)}`;
            const evtSource = new EventSource(streamUrl);
            let stepsFinished = 0;

            evtSource.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.step_id) {
                        if (data.step_id === 'complete') {
                            evtSource.close();
                            if (urlProgressBar) {
                                urlProgressBar.style.width = '100%';
                                urlProgressBar.className = 'progress-bar bg-success';
                            }
                            // Redirect to results page to render full comparison
                            setTimeout(() => {
                                window.location.href = `/search?url=${encodeURIComponent(targetUrl)}`;
                            }, 450);
                            return;
                        }

                        stepsFinished++;
                        const pct = Math.min(95, Math.round((stepsFinished / 7) * 100));
                        if (urlProgressBar) urlProgressBar.style.width = `${pct}%`;

                        setStepStatus(data.step_id, data.status || 'done', data.message || '');
                    }
                } catch (e) {
                    console.error('Error parsing SSE event:', e);
                }
            };

            evtSource.onerror = function () {
                evtSource.close();
                // Fallback to direct navigation / POST
                fallbackComparePost(targetUrl);
            };
        } else {
            fallbackComparePost(targetUrl);
        }
    };

    function fallbackComparePost(targetUrl) {
        // Direct navigation to /search?url=...
        window.location.href = `/search?url=${encodeURIComponent(targetUrl)}`;
    }

    // Auto-restore active mode from localStorage & attach main search bar listener
    document.addEventListener('DOMContentLoaded', function () {
        const saved = localStorage.getItem('smartbuy_search_mode');
        if (saved === 'url') {
            switchSearchMode('url');
        }
        updateUrlBadge();

        // Auto-detect URLs pasted into the primary search bar (specSearchInput)
        const mainInput = document.getElementById('specSearchInput');
        const mainSearchBtn = document.getElementById('searchBtn');
        const searchBoxContainer = document.getElementById('searchBoxContainer');

        if (mainInput && searchBoxContainer) {
            let badgeEl = document.getElementById('mainSearchUrlBadge');
            if (!badgeEl) {
                badgeEl = document.createElement('div');
                badgeEl.id = 'mainSearchUrlBadge';
                badgeEl.className = 'mt-2 small px-3 py-1 rounded-pill d-none';
                badgeEl.style.width = 'fit-content';
                badgeEl.style.transition = 'all 0.3s ease';
                searchBoxContainer.parentNode.insertBefore(badgeEl, searchBoxContainer.nextSibling);
            }

            function handleMainInput() {
                const val = (mainInput.value || '').trim();
                const plat = detectPlatformClient(val);

                if (plat) {
                    badgeEl.className = 'mt-2 small px-3 py-1 rounded-pill d-inline-flex align-items-center gap-1 ' +
                        (plat.key === 'amazon' ? 'bg-dark text-warning border border-warning' : (plat.key === 'flipkart' ? 'bg-primary text-white' : 'bg-danger text-white'));
                    badgeEl.innerHTML = `<i class="${plat.icon}"></i> <strong>${plat.name}</strong> URL detected &mdash; SmartBuy will compare across all 3 platforms`;
                    if (mainSearchBtn) {
                        mainSearchBtn.innerHTML = `<i class="fas fa-balance-scale me-2"></i><span>Compare URL</span>`;
                    }
                } else {
                    badgeEl.className = 'mt-2 small px-3 py-1 rounded-pill d-none';
                    badgeEl.innerHTML = '';
                    if (mainSearchBtn) {
                        mainSearchBtn.innerHTML = `<i class="fas fa-search me-2"></i><span>Search Products</span>`;
                    }
                }
            }

            mainInput.addEventListener('input', handleMainInput);
            mainInput.addEventListener('paste', () => setTimeout(handleMainInput, 50));
            handleMainInput();
        }
    });

})();
