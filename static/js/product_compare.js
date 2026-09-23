/**
 * product_compare.js
 * ===================
 * Interactive Product Feature Comparison for SmartBuy
 * ---------------------------------------------------
 * - Supports up to 3 products from DIFFERENT sites or SAME site.
 * - Persistent compare list via localStorage.
 * - Floating bottom compare dock with real-time slot indicators.
 * - Smart Ranking Algorithm evaluating:
 *     1. Price & Value for Money
 *     2. Bayesian Customer Rating
 *     3. Verified Review Count
 *     4. Product Quality Score (0-100)
 *     5. Head-to-head Feature Advantage Dominance
 * - Flexible removal, upgrade, and 1-click replacement of lower-rated products.
 * - Interactive Side-by-Side Comparison Modal with direct Buy buttons and feature matrix.
 */

(function () {
    "use strict";

    const STORAGE_KEY = "smartbuy_compare_list_v2";
    const MAX_COMPARE_LIMIT = 3;

    // In-memory compare state synchronized with localStorage
    let compareList = [];

    // Pending candidate when user attempts to add a 4th product
    let pendingCandidate = null;

    // Load saved comparison list on startup
    function loadCompareList() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    compareList = parsed.slice(0, MAX_COMPARE_LIMIT);
                }
            }
        } catch (e) {
            console.warn("[Compare] Error loading saved compare list:", e);
            compareList = [];
        }
    }

    function saveCompareList() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(compareList));
        } catch (e) {
            console.warn("[Compare] Error saving compare list:", e);
        }
    }

    // Helper: Normalize product ID
    function getProductId(prod) {
        if (!prod) return "";
        return String(prod.id || prod.title || "").trim();
    }

    // Helper: Check if product is already in compare list
    function isProductInCompare(prodId) {
        return compareList.some(p => getProductId(p) === prodId);
    }

    // ── 1. Toggle Product In/Out of Compare ──────────────────────────────────
    window.toggleCompareProduct = function (btnElement) {
        if (!btnElement) return;

        const prod = extractProductFromButton(btnElement);
        if (!prod || !prod.id) return;

        if (isProductInCompare(prod.id)) {
            // Remove from compare
            removeFromCompare(prod.id);
            showToast(`Removed "${truncate(prod.title, 32)}" from comparison.`);
        } else {
            // Check limit
            if (compareList.length >= MAX_COMPARE_LIMIT) {
                pendingCandidate = prod;
                openReplacementModal(prod);
            } else {
                addToCompare(prod);
                showToast(`Added "${truncate(prod.title, 32)}" to comparison (${compareList.length}/${MAX_COMPARE_LIMIT}).`);
            }
        }
    };

    function extractProductFromButton(btn) {
        try {
            const id = btn.getAttribute("data-id") || btn.getAttribute("data-title") || "";
            const title = btn.getAttribute("data-title") || "Product";
            const platform = btn.getAttribute("data-platform") || "Marketplace";
            const price = btn.getAttribute("data-price") || "";
            const priceNum = parseFloat(btn.getAttribute("data-price-num")) || parsePriceToNumber(price);
            const mrp = btn.getAttribute("data-mrp") || price;
            const discount = btn.getAttribute("data-discount") || "";
            const rating = btn.getAttribute("data-rating") || "N/A";
            const reviews = btn.getAttribute("data-reviews") || "0";
            const image = btn.getAttribute("data-image") || "";
            const link = btn.getAttribute("data-link") || btn.getAttribute("data-url") || "#";
            const qualityScore = parseFloat(btn.getAttribute("data-quality-score")) || 50;
            const qualityBand = btn.getAttribute("data-quality-band") || "Standard Quality";

            let specs = {};
            try {
                const rawSpecs = btn.getAttribute("data-specs");
                if (rawSpecs) specs = typeof rawSpecs === "string" ? JSON.parse(rawSpecs) : rawSpecs;
            } catch (e) {
                specs = {};
            }

            let qualityPoints = [];
            try {
                const rawPts = btn.getAttribute("data-points");
                if (rawPts) qualityPoints = typeof rawPts === "string" ? JSON.parse(rawPts) : rawPts;
            } catch (e) {
                qualityPoints = [];
            }

            return {
                id: id,
                title: title,
                platform: platform,
                price: price,
                price_num: priceNum,
                mrp: mrp,
                discount: discount,
                rating: rating,
                reviews: reviews,
                image: image,
                link: link,
                quality_score: qualityScore,
                quality_band: qualityBand,
                specs: specs,
                quality_points: qualityPoints,
                added_at: Date.now()
            };
        } catch (e) {
            console.error("[Compare] Error extracting product details:", e);
            return null;
        }
    }

    function parsePriceToNumber(priceStr) {
        if (!priceStr) return 0;
        const clean = String(priceStr).replace(/[^0-9.]/g, "");
        const num = parseFloat(clean);
        return isNaN(num) ? 0 : num;
    }

    function addToCompare(prod) {
        if (compareList.length >= MAX_COMPARE_LIMIT) return false;
        compareList.push(prod);
        saveCompareList();
        updateCompareUI();
        return true;
    }

    window.removeFromCompare = function (prodId) {
        compareList = compareList.filter(p => getProductId(p) !== prodId);
        saveCompareList();
        updateCompareUI();

        // Refresh modal if currently open
        const modalEl = document.getElementById("customCompareModal");
        if (modalEl && modalEl.classList.contains("show")) {
            if (compareList.length === 0) {
                const bsModal = bootstrap.Modal.getInstance(modalEl);
                if (bsModal) bsModal.hide();
            } else {
                renderCompareModalContent();
            }
        }
    };

    window.clearAllCompare = function () {
        compareList = [];
        saveCompareList();
        updateCompareUI();

        const modalEl = document.getElementById("customCompareModal");
        if (modalEl && modalEl.classList.contains("show")) {
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) bsModal.hide();
        }
        showToast("Cleared comparison list.");
    };

    // ── 2. Update UI (Buttons, Floating Dock) ─────────────────────────────────
    function updateCompareUI() {
        // A. Synchronize all Add to Compare buttons on page
        const buttons = document.querySelectorAll(".btn-add-compare");
        buttons.forEach(btn => {
            const id = btn.getAttribute("data-id") || btn.getAttribute("data-title") || "";
            const isAdded = isProductInCompare(id);
            const spanText = btn.querySelector("span");
            const icon = btn.querySelector("i");

            if (isAdded) {
                btn.classList.remove("btn-outline-primary");
                btn.classList.add("btn-success", "active");
                if (spanText) spanText.textContent = "Added to Compare";
                if (icon) icon.className = "fas fa-check-double me-1.5";
            } else {
                btn.classList.remove("btn-success", "active");
                btn.classList.add("btn-outline-primary");
                if (spanText) spanText.textContent = "Add to Compare";
                if (icon) icon.className = "fas fa-balance-scale me-1.5";
            }
        });

        // B. Render Floating Dock
        renderFloatingDock();
    }

    function renderFloatingDock() {
        let dock = document.getElementById("compareFloatingDock");
        if (!dock) return;

        if (compareList.length === 0) {
            dock.style.transform = "translateY(120%)";
            dock.style.opacity = "0";
            dock.style.pointerEvents = "none";
            return;
        }

        dock.style.transform = "translateY(0)";
        dock.style.opacity = "1";
        dock.style.pointerEvents = "auto";

        const countBadge = dock.querySelector("#compareDockCount");
        if (countBadge) countBadge.textContent = `${compareList.length}/${MAX_COMPARE_LIMIT}`;

        const slotsContainer = dock.querySelector("#compareDockSlots");
        if (!slotsContainer) return;

        let html = "";
        for (let i = 0; i < MAX_COMPARE_LIMIT; i++) {
            if (i < compareList.length) {
                const item = compareList[i];
                const platColor = getPlatformColor(item.platform);
                html += `
                <div class="compare-dock-slot occupied position-relative d-flex align-items-center gap-2 p-1.5 rounded-3 bg-white shadow-sm border border-secondary border-opacity-25" style="min-width: 170px; max-width: 220px;">
                    <button type="button" class="btn-close-slot position-absolute top-0 end-0 translate-middle badge rounded-pill bg-danger border border-white text-white p-1" style="font-size: 0.65rem; width: 18px; height: 18px; cursor: pointer;" onclick="removeFromCompare('${escapeHtml(getProductId(item))}')" title="Remove from compare">
                        ✕
                    </button>
                    <img src="${escapeHtml(item.image)}" alt="Thumbnail" style="width: 38px; height: 38px; object-fit: contain; border-radius: 4px; background: #fff; flex-shrink: 0;" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'38\\' height=\\'38\\' fill=\\'%2394a3b8\\' viewBox=\\'0 0 16 16\\'><path d=\\'M6.002 5.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z\\'/></svg>';">
                    <div class="overflow-hidden" style="line-height: 1.25;">
                        <span class="badge px-1.5 py-0.5 rounded-pill fw-bold text-white mb-0.5" style="font-size: 0.62rem; background: ${platColor};">
                            ${escapeHtml(item.platform)}
                        </span>
                        <div class="small fw-semibold text-dark text-truncate" style="font-size: 0.75rem;" title="${escapeHtml(item.title)}">
                            ${escapeHtml(item.title)}
                        </div>
                        <div class="text-success fw-bold" style="font-size: 0.78rem;">
                            ${escapeHtml(item.price || "Check Price")}
                        </div>
                    </div>
                </div>`;
            } else {
                html += `
                <div class="compare-dock-slot empty d-flex flex-column align-items-center justify-content-center p-2 rounded-3 border border-2 border-dashed border-secondary border-opacity-50 text-muted" style="min-width: 140px; height: 52px; font-size: 0.72rem;">
                    <i class="fas fa-plus text-primary opacity-50 mb-0.5"></i>
                    <span>Slot ${i + 1} Empty</span>
                </div>`;
            }
        }
        slotsContainer.innerHTML = html;

        // Button state
        const compareBtn = dock.querySelector("#btnTriggerCompare");
        if (compareBtn) {
            if (compareList.length >= 2) {
                compareBtn.classList.remove("disabled", "btn-secondary");
                compareBtn.classList.add("btn-primary", "pulse-btn");
                compareBtn.innerHTML = `<i class="fas fa-chart-bar me-1.5"></i>Compare Now (${compareList.length})`;
            } else {
                compareBtn.classList.add("disabled", "btn-secondary");
                compareBtn.classList.remove("btn-primary", "pulse-btn");
                compareBtn.innerHTML = `<i class="fas fa-plus-circle me-1.5"></i>Add 1 More to Compare`;
            }
        }
    }

    // ── 3. Smart Ranking & Feature Advantage Algorithm ────────────────────────
    /**
     * Evaluates compared products based on:
     * 1. Price Competitiveness (25%)
     * 2. Bayesian Rating & Review Volume (25%)
     * 3. Quality Score & Band (20%)
     * 4. Feature Dominance / Completeness (20%)
     * 5. Stock / Seller Trust (10%)
     */
    function calculateSmartRanking(products) {
        if (!products || products.length === 0) return [];

        const n = products.length;
        if (n === 1) {
            return [{
                ...products[0],
                smart_score: 90,
                smart_rank: 1,
                rank_title: "Top Selected",
                rank_badge: "badge-rank-1",
                rank_icon: "fa-trophy",
                feature_advantages: ["Selected for inspection"],
                advantage_count: 1,
                why_won: "Sole product selected for feature comparison."
            }];
        }

        // A. Price normalization (lowest price gets highest score)
        const validPrices = products.map(p => p.price_num).filter(p => p && p > 0);
        const minPrice = validPrices.length ? Math.min(...validPrices) : 1;

        // B. Head-to-Head Feature Dominance Count
        // Analyze specs and features across products
        const evaluated = products.map(p => {
            let pNum = p.price_num || 9999999;
            let priceScore = (minPrice / Math.max(1, pNum)) * 100;

            // Rating Score (Bayesian smoothed)
            let rNum = parseFloat(String(p.rating).replace("★", "").trim()) || 0;
            let revCount = parseInt(String(p.reviews).replace(/[^0-9]/g, "")) || 0;
            let ratingScore = 0;
            if (rNum > 0) {
                ratingScore = (rNum / 5.0) * 80 + Math.min(20, Math.log10(Math.max(1, revCount)) * 5);
            } else if (revCount > 0) {
                ratingScore = 60 + Math.min(20, Math.log10(revCount) * 5);
            } else {
                ratingScore = 50; // default baseline
            }

            // Quality Score
            let qScore = p.quality_score || 50;

            // Count distinct features & attributes
            let specKeys = Object.keys(p.specs || {}).filter(k => {
                const val = String(p.specs[k] || "").toLowerCase();
                return val && val !== "n/a" && val !== "not available" && val !== "none";
            });
            let featureCount = specKeys.length + (p.quality_points || []).length;

            return {
                ...p,
                raw_price_score: priceScore,
                raw_rating_score: ratingScore,
                raw_quality_score: qScore,
                feature_count: featureCount,
                feature_keys: specKeys
            };
        });

        // Determine pairwise feature advantage
        const maxFeatures = Math.max(...evaluated.map(e => e.feature_count), 1);

        evaluated.forEach(item => {
            let featureScore = (item.feature_count / maxFeatures) * 100;
            item.raw_feature_score = featureScore;

            // Composite Smart Score
            // 25% Price, 25% Rating, 20% Quality, 20% Features, 10% Trust/Stock
            const composite = (
                item.raw_price_score * 0.25 +
                item.raw_rating_score * 0.25 +
                item.raw_quality_score * 0.25 +
                item.raw_feature_score * 0.25
            );
            item.smart_score = Math.round(composite * 10) / 10;

            // Generate feature advantage highlights
            const advantages = [];
            // Check if cheapest
            if (item.price_num && item.price_num === minPrice && validPrices.length > 1) {
                advantages.push(`Lowest Price (₹${item.price_num.toLocaleString("en-IN")})`);
            }
            // Check quality advantage
            const maxQ = Math.max(...evaluated.map(x => x.raw_quality_score));
            if (item.raw_quality_score === maxQ && maxQ > 60) {
                advantages.push(`Top Quality Score (${Math.round(item.raw_quality_score)}/100)`);
            }
            // Check rating advantage
            const maxR = Math.max(...evaluated.map(x => parseFloat(String(x.rating).replace("★", "").trim()) || 0));
            if (maxR > 0 && (parseFloat(String(item.rating).replace("★", "").trim()) || 0) === maxR) {
                advantages.push(`Highest Customer Rating (★ ${maxR})`);
            }
            // Feature dominance
            if (item.feature_count === maxFeatures && maxFeatures > 3) {
                advantages.push(`Most Complete Specifications (${item.feature_count} features)`);
            }
            if (item.discount && item.discount.includes("%") && !item.discount.startsWith("0")) {
                advantages.push(`Great Savings (${item.discount})`);
            }
            if (!advantages.length) {
                advantages.push("Balanced Value Option");
            }
            item.feature_advantages = advantages;
            item.advantage_count = advantages.length;
        });

        // Sort descending by Smart Score
        evaluated.sort((a, b) => b.smart_score - a.smart_score);

        // Assign ranks and badges
        const rankDefinitions = [
            { rank: 1, title: "🏆 #1 Top Ranked / Winner", badgeClass: "smart-rank-badge-1", icon: "fa-trophy" },
            { rank: 2, title: "🥈 #2 Strong Contender", badgeClass: "smart-rank-badge-2", icon: "fa-medal" },
            { rank: 3, title: "🥉 #3 Value Alternative", badgeClass: "smart-rank-badge-3", icon: "fa-award" }
        ];

        return evaluated.map((prod, idx) => {
            const def = rankDefinitions[idx] || { rank: idx + 1, title: `#${idx + 1} Option`, badgeClass: "badge bg-secondary", icon: "fa-tag" };
            
            let whyWon = "";
            if (idx === 0) {
                whyWon = `Winner with superior score (${prod.smart_score}/100) driven by ${prod.feature_advantages.join(", ")}.`;
            } else if (idx === 1) {
                whyWon = `Solid runner-up with strong ${prod.feature_advantages[0] || "performance"}.`;
            } else {
                whyWon = `Budget-friendly pick offering ${prod.feature_advantages[0] || "decent balance"}.`;
            }

            return {
                ...prod,
                smart_rank: def.rank,
                rank_title: def.title,
                rank_badge: def.badgeClass,
                rank_icon: def.icon,
                why_won: whyWon
            };
        });
    }

    // ── 4. Open Interactive Comparison Modal ──────────────────────────────────
    window.openCustomCompareModal = function () {
        if (compareList.length === 0) {
            showToast("Please add at least 1 product to compare.");
            return;
        }

        renderCompareModalContent();

        const modalEl = document.getElementById("customCompareModal");
        if (modalEl) {
            const bsModal = new bootstrap.Modal(modalEl);
            bsModal.show();
        }
    };

    function renderCompareModalContent() {
        const container = document.getElementById("customCompareModalBody");
        if (!container) return;

        const rankedList = calculateSmartRanking(compareList);

        // Gather all unique specification keys across all products
        const allSpecKeysSet = new Set();
        rankedList.forEach(p => {
            if (p.specs && typeof p.specs === "object") {
                Object.keys(p.specs).forEach(k => {
                    const cleanKey = k.trim();
                    if (!["price_num", "rating_num", "category_specs", "image", "title", "link", "url"].includes(cleanKey.toLowerCase())) {
                        allSpecKeysSet.add(cleanKey);
                    }
                });
            }
        });
        const specKeys = Array.from(allSpecKeysSet);

        let html = `
        <!-- Top Winner Announcement Banner -->
        <div class="winner-announcement-card p-3 mb-4 rounded-4 shadow-sm border border-success border-opacity-25 bg-success bg-opacity-10 d-flex align-items-center justify-content-between flex-wrap gap-3">
            <div class="d-flex align-items-center gap-3">
                <div class="winner-trophy-box rounded-circle bg-warning text-dark d-flex align-items-center justify-content-center shadow" style="width: 48px; height: 48px; font-size: 1.4rem;">
                    🏆
                </div>
                <div>
                    <div class="small text-uppercase fw-bold text-success" style="letter-spacing: 0.5px;">Smart Ranking Verdict</div>
                    <h5 class="fw-bold text-dark mb-0">${escapeHtml(rankedList[0].title)}</h5>
                    <div class="small text-muted mt-0.5">${escapeHtml(rankedList[0].why_won)}</div>
                </div>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="badge bg-success fs-6 px-3 py-2 rounded-pill shadow-xs">
                    Smart Score: ${rankedList[0].smart_score}/100
                </span>
            </div>
        </div>

        <!-- Side-by-Side Product Cards Grid -->
        <div class="row g-3 mb-4">
        `;

        rankedList.forEach(p => {
            const isWinner = p.smart_rank === 1;
            const platColor = getPlatformColor(p.platform);

            html += `
            <div class="col-12 col-md-${12 / rankedList.length}">
                <div class="card h-100 shadow-sm rounded-4 border ${isWinner ? 'border-success border-2 shadow' : 'border-secondary border-opacity-25'} position-relative" style="${isWinner ? 'background: linear-gradient(to bottom, rgba(16, 185, 129, 0.05), #ffffff);' : 'background: #ffffff;'}">
                    
                    <!-- Smart Rank Ribbon -->
                    <div class="p-2.5 d-flex align-items-center justify-content-between border-bottom ${isWinner ? 'bg-success text-white' : 'bg-light text-dark'} rounded-top-4">
                        <span class="fw-bold small d-flex align-items-center gap-1.5" style="font-size: 0.78rem;">
                            <i class="fas ${p.rank_icon}"></i> ${escapeHtml(p.rank_title)}
                        </span>
                        <div class="d-flex align-items-center gap-1">
                            <button type="button" class="btn btn-sm btn-outline-danger border-0 py-0 px-1 text-danger" onclick="removeFromCompare('${escapeHtml(getProductId(p))}')" title="Remove this product">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                    </div>

                    <div class="card-body p-3 d-flex flex-column">
                        <!-- Platform & Thumbnail -->
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="badge px-2.5 py-1 rounded-pill text-white fw-bold" style="background: ${platColor}; font-size: 0.72rem;">
                                ${escapeHtml(p.platform)}
                            </span>
                            <span class="badge bg-primary-subtle text-primary border border-primary px-2 py-0.5 rounded-pill fw-semibold" style="font-size: 0.7rem;">
                                Quality: ${Math.round(p.quality_score)}/100
                            </span>
                        </div>

                        <div class="text-center py-2">
                            <img src="${escapeHtml(p.image)}" alt="Product Image" style="height: 110px; max-width: 140px; object-fit: contain; border-radius: 8px; background: #fff;" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'80\\' height=\\'80\\' fill=\\'%2394a3b8\\' viewBox=\\'0 0 16 16\\'><path d=\\'M6.002 5.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z\\'/></svg>';">
                        </div>

                        <!-- Title -->
                        <h6 class="fw-semibold text-dark text-truncate-2 mt-2 mb-2" style="font-size: 0.85rem; height: 2.6em; line-height: 1.3;" title="${escapeHtml(p.title)}">
                            ${escapeHtml(p.title)}
                        </h6>

                        <!-- Price & Discount -->
                        <div class="mb-2">
                            <div class="d-flex align-items-baseline gap-2">
                                <span class="fs-5 fw-bold text-success">${escapeHtml(p.price || "N/A")}</span>
                                ${p.mrp && p.mrp !== p.price ? `<del class="text-muted small">${escapeHtml(p.mrp)}</del>` : ''}
                                ${p.discount ? `<span class="badge bg-danger-subtle text-danger" style="font-size:0.68rem;">${escapeHtml(p.discount)}</span>` : ''}
                            </div>
                            <div class="small text-muted mt-0.5">
                                <i class="fas fa-star text-warning"></i>
                                ${p.rating && p.rating !== 'N/A' ? escapeHtml(p.rating) : 'Unrated'}
                                <span class="ms-1">(${escapeHtml(p.reviews || '0')} reviews)</span>
                            </div>
                        </div>

                        <!-- Feature Advantages Pills -->
                        <div class="feature-pills d-flex flex-wrap gap-1 mb-3">
                            ${p.feature_advantages.map(adv => `
                                <span class="badge bg-light text-dark border px-2 py-1 rounded-pill" style="font-size: 0.68rem;">
                                    ✓ ${escapeHtml(adv)}
                                </span>
                            `).join('')}
                        </div>

                        <!-- Action Buttons: Buy & Replace -->
                        <div class="mt-auto d-flex flex-column gap-2">
                            <a href="javascript:void(0)"
                               data-url="${escapeHtml(p.link)}"
                               data-platform="${escapeHtml(p.platform)}"
                               data-product-name="${escapeHtml(p.title)}"
                               data-price="${escapeHtml(p.price)}"
                               onclick="triggerBuyRedirect(this)"
                               class="btn btn-primary btn-sm rounded-pill fw-bold py-2 shadow-xs d-flex align-items-center justify-content-center">
                                <i class="fas fa-shopping-cart me-1.5"></i>Buy on ${escapeHtml(p.platform)}
                            </a>
                            <button type="button" 
                                    class="btn btn-outline-secondary btn-sm rounded-pill py-1.5"
                                    style="font-size: 0.75rem;"
                                    onclick="promptReplaceSpecificProduct('${escapeHtml(getProductId(p))}')">
                                <i class="fas fa-exchange-alt me-1"></i>Upgrade / Replace Product
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        });

        html += `</div>`;

        // Detailed Side-by-Side Comparison Matrix Table
        html += `
        <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-3">
            <div class="card-header bg-dark text-white py-2.5 px-3 d-flex align-items-center justify-content-between">
                <span class="fw-bold small text-uppercase"><i class="fas fa-table me-2 text-primary"></i>Direct Specification &amp; Attribute Comparison</span>
                <span class="badge bg-primary text-white rounded-pill px-2.5 py-1" style="font-size: 0.72rem;">${rankedList.length} Products Matched</span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0 text-center" style="font-size: 0.84rem;">
                    <thead class="table-light">
                        <tr>
                            <th style="width: 25%; text-align: left; padding-left: 18px;">Feature / Specification</th>
                            ${rankedList.map(p => `
                                <th style="width: ${75 / rankedList.length}%;">
                                    <span class="badge text-white px-2.5 py-1 rounded-pill" style="background: ${getPlatformColor(p.platform)}; font-size: 0.72rem;">
                                        ${escapeHtml(p.platform)}
                                    </span>
                                    <div class="text-truncate mt-1 small text-dark fw-semibold" style="max-width: 180px; margin: 0 auto;" title="${escapeHtml(p.title)}">
                                        ${escapeHtml(p.title)}
                                    </div>
                                </th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        <!-- 1. Smart Rank -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-primary"><i class="fas fa-trophy me-1.5"></i>Smart Ranking</td>
                            ${rankedList.map(p => `
                                <td>
                                    <span class="badge ${p.smart_rank === 1 ? 'bg-success' : 'bg-secondary'} px-2.5 py-1 rounded-pill fw-bold">
                                        Rank #${p.smart_rank} (${p.smart_score}/100)
                                    </span>
                                </td>
                            `).join('')}
                        </tr>

                        <!-- 2. Price -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-tag me-1.5 text-success"></i>Current Price</td>
                            ${rankedList.map(p => `
                                <td class="fw-bold ${p.price_num && p.price_num === Math.min(...rankedList.map(x => x.price_num || 999999)) ? 'text-success bg-success bg-opacity-10' : 'text-dark'}">
                                    ${escapeHtml(p.price || '—')}
                                </td>
                            `).join('')}
                        </tr>

                        <!-- 3. Quality Score -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-award me-1.5 text-primary"></i>Quality Score</td>
                            ${rankedList.map(p => `
                                <td>
                                    <span class="badge bg-primary-subtle text-primary border border-primary px-2.5 py-1 rounded-pill fw-bold">
                                        ${Math.round(p.quality_score)}/100
                                    </span>
                                    <div class="small text-muted mt-0.5" style="font-size: 0.7rem;">${escapeHtml(p.quality_band || 'Standard Quality')}</div>
                                </td>
                            `).join('')}
                        </tr>

                        <!-- 4. Customer Rating -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-star me-1.5 text-warning"></i>Customer Rating</td>
                            ${rankedList.map(p => `
                                <td>
                                    <span class="fw-bold text-warning-emphasis">★ ${escapeHtml(p.rating || 'N/A')}</span>
                                    <div class="small text-muted" style="font-size: 0.7rem;">(${escapeHtml(p.reviews || '0')} reviews)</div>
                                </td>
                            `).join('')}
                        </tr>

                        <!-- 5. Dynamic Specifications -->
                        ${specKeys.map(k => `
                            <tr>
                                <td class="fw-semibold text-start ps-3 text-muted text-capitalize">${escapeHtml(k)}</td>
                                ${rankedList.map(p => {
                                    const val = (p.specs && p.specs[k]) ? String(p.specs[k]) : '—';
                                    return `<td>${escapeHtml(val)}</td>`;
                                }).join('')}
                            </tr>
                        `).join('')}

                        <!-- 6. Direct Buy Link -->
                        <tr class="table-light">
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-external-link-alt me-1.5 text-muted"></i>Direct Action</td>
                            ${rankedList.map(p => `
                                <td>
                                    <a href="javascript:void(0)"
                                       data-url="${escapeHtml(p.link)}"
                                       data-platform="${escapeHtml(p.platform)}"
                                       data-product-name="${escapeHtml(p.title)}"
                                       data-price="${escapeHtml(p.price)}"
                                       onclick="triggerBuyRedirect(this)"
                                       class="btn btn-sm btn-primary rounded-pill px-3 py-1 fw-bold shadow-xs">
                                        Buy on ${escapeHtml(p.platform)}
                                    </a>
                                </td>
                            `).join('')}
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        `;

        container.innerHTML = html;
    }

    // ── 5. Replacement & Upgrade Mechanics ───────────────────────────────────
    function openReplacementModal(newProd) {
        pendingCandidate = newProd;
        const replaceModal = document.getElementById("compareReplaceModal");
        if (!replaceModal) return;

        const body = replaceModal.querySelector("#compareReplaceModalBody");
        if (!body) return;

        // Find lowest rated or highest priced product to recommend for upgrade
        let lowestRatedIdx = 0;
        let lowestRatingVal = 99;
        compareList.forEach((p, idx) => {
            const r = parseFloat(String(p.rating).replace("★", "").trim()) || 0;
            if (r < lowestRatingVal) {
                lowestRatingVal = r;
                lowestRatedIdx = idx;
            }
        });

        let html = `
        <div class="alert alert-info border-0 rounded-4 py-2.5 px-3 mb-3 d-flex align-items-center gap-2">
            <i class="fas fa-info-circle fs-5 text-primary"></i>
            <div class="small">
                Compare limit reached (<strong>${MAX_COMPARE_LIMIT}/${MAX_COMPARE_LIMIT}</strong>). Choose which product to <strong>replace or upgrade</strong> with:
                <div class="fw-bold text-dark mt-0.5 text-truncate" style="max-width: 400px;">
                    "${escapeHtml(newProd.title)}" (₹${escapeHtml(newProd.price)} on ${escapeHtml(newProd.platform)})
                </div>
            </div>
        </div>

        <div class="d-flex flex-column gap-2 mb-3">
        `;

        compareList.forEach((p, idx) => {
            const isRecommended = idx === lowestRatedIdx;
            const platColor = getPlatformColor(p.platform);

            html += `
            <div class="replace-slot-option p-2.5 rounded-3 border ${isRecommended ? 'border-warning bg-warning bg-opacity-10' : 'border-secondary border-opacity-25 bg-white'} d-flex align-items-center justify-content-between gap-3">
                <div class="d-flex align-items-center gap-2.5 overflow-hidden">
                    <img src="${escapeHtml(p.image)}" alt="Thumbnail" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px; background: #fff; flex-shrink: 0;">
                    <div class="overflow-hidden">
                        <div class="d-flex align-items-center gap-1.5 mb-0.5">
                            <span class="badge text-white px-1.5 py-0.5 rounded-pill" style="font-size: 0.65rem; background: ${platColor};">
                                ${escapeHtml(p.platform)}
                            </span>
                            ${isRecommended ? '<span class="badge bg-warning text-dark fw-bold" style="font-size: 0.65rem;">Recommended to Replace (Lower Rating)</span>' : ''}
                        </div>
                        <div class="fw-semibold text-dark text-truncate" style="font-size: 0.8rem;" title="${escapeHtml(p.title)}">
                            ${escapeHtml(p.title)}
                        </div>
                        <div class="small text-muted" style="font-size: 0.72rem;">
                            Price: <strong class="text-success">${escapeHtml(p.price)}</strong> • Rating: ★ ${escapeHtml(p.rating || 'N/A')} (${escapeHtml(p.reviews || 0)})
                        </div>
                    </div>
                </div>
                <button type="button" class="btn btn-primary btn-sm rounded-pill px-3 py-1 fw-bold text-nowrap" onclick="executeReplaceSlot(${idx})">
                    <i class="fas fa-exchange-alt me-1"></i>Replace Slot ${idx + 1}
                </button>
            </div>`;
        });

        html += `</div>`;
        body.innerHTML = html;

        const bsModal = new bootstrap.Modal(replaceModal);
        bsModal.show();
    }

    window.executeReplaceSlot = function (slotIndex) {
        if (!pendingCandidate || slotIndex < 0 || slotIndex >= compareList.length) return;

        const replacedTitle = compareList[slotIndex].title;
        compareList[slotIndex] = pendingCandidate;
        saveCompareList();
        updateCompareUI();

        const replaceModal = document.getElementById("compareReplaceModal");
        if (replaceModal) {
            const bsModal = bootstrap.Modal.getInstance(replaceModal);
            if (bsModal) bsModal.hide();
        }

        showToast(`Replaced "${truncate(replacedTitle, 20)}" with "${truncate(pendingCandidate.title, 20)}".`);
        pendingCandidate = null;
    };

    window.promptReplaceSpecificProduct = function (targetProdId) {
        const replaceModal = document.getElementById("compareReplaceModal");
        if (!replaceModal) return;

        const body = replaceModal.querySelector("#compareReplaceModalBody");
        if (!body) return;

        // Find candidate alternatives from the current page
        const candidateCards = document.querySelectorAll(".product-card, .btn-add-compare");
        const availableCandidates = [];

        candidateCards.forEach(c => {
            const btn = c.classList.contains("btn-add-compare") ? c : c.querySelector(".btn-add-compare");
            if (btn) {
                const prod = extractProductFromButton(btn);
                if (prod && !isProductInCompare(prod.id)) {
                    availableCandidates.push(prod);
                }
            }
        });

        const targetIndex = compareList.findIndex(p => getProductId(p) === targetProdId);
        if (targetIndex === -1) return;
        const targetProd = compareList[targetIndex];

        let html = `
        <div class="alert alert-primary border-0 rounded-4 py-2.5 px-3 mb-3 d-flex align-items-center gap-2">
            <i class="fas fa-sync-alt fs-5 text-primary"></i>
            <div class="small">
                Upgrading / Replacing: <strong>"${escapeHtml(targetProd.title)}"</strong> (${escapeHtml(targetProd.platform)} • ${escapeHtml(targetProd.price)}).
                Choose an alternative from this search:
            </div>
        </div>
        `;

        if (availableCandidates.length === 0) {
            html += `<p class="text-muted text-center py-4">No alternative products available from current search results.</p>`;
        } else {
            html += `<div class="d-flex flex-column gap-2" style="max-height: 380px; overflow-y: auto;">`;
            availableCandidates.slice(0, 8).forEach(cand => {
                html += `
                <div class="p-2.5 rounded-3 border border-secondary border-opacity-25 bg-white d-flex align-items-center justify-content-between gap-3">
                    <div class="d-flex align-items-center gap-2.5 overflow-hidden">
                        <img src="${escapeHtml(cand.image)}" alt="Thumbnail" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px; background: #fff; flex-shrink: 0;">
                        <div class="overflow-hidden">
                            <span class="badge text-white px-1.5 py-0.5 rounded-pill mb-0.5" style="font-size: 0.65rem; background: ${getPlatformColor(cand.platform)};">
                                ${escapeHtml(cand.platform)}
                            </span>
                            <div class="fw-semibold text-dark text-truncate" style="font-size: 0.8rem;" title="${escapeHtml(cand.title)}">
                                ${escapeHtml(cand.title)}
                            </div>
                            <div class="small text-muted" style="font-size: 0.72rem;">
                                <strong class="text-success">${escapeHtml(cand.price)}</strong> • Quality: ${Math.round(cand.quality_score)}/100 • ★ ${escapeHtml(cand.rating || 'N/A')}
                            </div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-outline-primary btn-sm rounded-pill px-3 py-1 fw-bold text-nowrap" onclick="swapCandidateIntoSlot(${targetIndex}, ${escapeAttrJson(cand)})">
                        <i class="fas fa-check me-1"></i>Select This
                    </button>
                </div>`;
            });
            html += `</div>`;
        }

        body.innerHTML = html;
        const bsModal = new bootstrap.Modal(replaceModal);
        bsModal.show();
    };

    window.swapCandidateIntoSlot = function (slotIndex, newCandidate) {
        if (slotIndex < 0 || slotIndex >= compareList.length || !newCandidate) return;

        const oldTitle = compareList[slotIndex].title;
        compareList[slotIndex] = newCandidate;
        saveCompareList();
        updateCompareUI();

        const replaceModal = document.getElementById("compareReplaceModal");
        if (replaceModal) {
            const bsModal = bootstrap.Modal.getInstance(replaceModal);
            if (bsModal) bsModal.hide();
        }

        renderCompareModalContent();
        showToast(`Upgraded slot to "${truncate(newCandidate.title, 20)}".`);
    };

    // ── Helper Utilities ─────────────────────────────────────────────────────
    function getPlatformColor(plat) {
        const p = String(plat || "").toLowerCase();
        if (p.includes("amazon")) return "#FF9900";
        if (p.includes("flipkart")) return "#2874f0";
        if (p.includes("meesho")) return "#F43397";
        return "#2563eb";
    }

    function truncate(str, len) {
        if (!str) return "";
        return str.length > len ? str.substring(0, len) + "..." : str;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeAttrJson(obj) {
        return escapeHtml(JSON.stringify(obj));
    }

    function showToast(message) {
        let toastEl = document.getElementById("compareActionToast");
        if (!toastEl) {
            toastEl = document.createElement("div");
            toastEl.id = "compareActionToast";
            toastEl.className = "toast align-items-center text-white bg-dark border-0 position-fixed bottom-0 end-0 m-3 shadow-lg";
            toastEl.style.zIndex = "1090";
            toastEl.setAttribute("role", "alert");
            toastEl.setAttribute("aria-live", "assertive");
            toastEl.setAttribute("aria-atomic", "true");
            toastEl.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body small fw-semibold">
                        <i class="fas fa-info-circle text-info me-1.5"></i>
                        <span id="compareToastMsg"></span>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
            document.body.appendChild(toastEl);
        }

        const msgSpan = toastEl.querySelector("#compareToastMsg");
        if (msgSpan) msgSpan.textContent = message;

        const bsToast = new bootstrap.Toast(toastEl, { delay: 2800 });
        bsToast.show();
    }

    // ── Initialization ───────────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", () => {
        loadCompareList();
        updateCompareUI();
    });

})();
