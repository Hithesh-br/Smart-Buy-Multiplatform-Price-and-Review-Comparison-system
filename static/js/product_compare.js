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

    // ── Helper: Category & Product Compatibility Check ─────────────────────
    function areProductsCompatible(prodA, prodB) {
        if (!prodA || !prodB) return true;
        const tA = (prodA.title || "").toLowerCase();
        const tB = (prodB.title || "").toLowerCase();
        const cA = (prodA.category || (prodA.specs && prodA.specs.category) || "").toLowerCase();
        const cB = (prodB.category || (prodB.specs && prodB.specs.category) || "").toLowerCase();

        // 1. Phone vs Phone Accessories (Case, Cover, Glass, Charger)
        const isPhoneA = /(phone|mobile|smartphone|galaxy|iphone|redmi|realme|vivo|oppo|oneplus)/.test(tA) || /(phone|smartphone|mobile)/.test(cA);
        const isPhoneB = /(phone|mobile|smartphone|galaxy|iphone|redmi|realme|vivo|oppo|oneplus)/.test(tB) || /(phone|smartphone|mobile)/.test(cB);
        const isPhoneAccA = /(case|cover|tempered glass|screen guard|lens protector|skin|pouch)/.test(tA);
        const isPhoneAccB = /(case|cover|tempered glass|screen guard|lens protector|skin|pouch)/.test(tB);
        if ((isPhoneA && !isPhoneAccA && isPhoneAccB) || (isPhoneB && !isPhoneAccB && isPhoneAccA)) return false;

        // 2. Laptop vs Laptop Accessories (Bag, Sleeve, Charger)
        const isLaptopA = /(laptop|notebook|macbook|thinkpad|vivobook)/.test(tA) || /laptop/.test(cA);
        const isLaptopB = /(laptop|notebook|macbook|thinkpad|vivobook)/.test(tB) || /laptop/.test(cB);
        const isLaptopAccA = /(laptop bag|backpack|sleeve|keyboard cover)/.test(tA);
        const isLaptopAccB = /(laptop bag|backpack|sleeve|keyboard cover)/.test(tB);
        if ((isLaptopA && !isLaptopAccA && isLaptopAccB) || (isLaptopB && !isLaptopAccB && isLaptopAccA)) return false;

        // 3. Pressure Cooker vs Cooker Replacement Parts (Gasket, Sealing Ring, Safety Valve, Whistle)
        const isCookerA = /(cooker|pressure cooker)/.test(tA) || /cooker/.test(cA);
        const isCookerB = /(cooker|pressure cooker)/.test(tB) || /cooker/.test(cB);
        const isCookerPartA = /(gasket|sealing ring|safety valve|whistle|cooker handle)/.test(tA);
        const isCookerPartB = /(gasket|sealing ring|safety valve|whistle|cooker handle)/.test(tB);
        if ((isCookerA && !isCookerPartA && isCookerPartB) || (isCookerB && !isCookerPartB && isCookerPartA)) return false;

        // 4. Mixer Grinder vs Mixer Jar / Coupler / Blade
        const isMixerA = /(mixer|grinder)/.test(tA) || /mixer/.test(cA);
        const isMixerB = /(mixer|grinder)/.test(tB) || /mixer/.test(cB);
        const isMixerPartA = /(mixer jar|grinder jar|mixer blade|coupler)/.test(tA);
        const isMixerPartB = /(mixer jar|grinder jar|mixer blade|coupler)/.test(tB);
        if ((isMixerA && !isMixerPartA && isMixerPartB) || (isMixerB && !isMixerPartB && isMixerPartA)) return false;

        // 5. Cross-Category hard conflicts (e.g. Phone vs Cooker, Laptop vs Face Wash, Shoes vs Phone)
        if ((isPhoneA && !isPhoneB && !isPhoneAccA) || (isPhoneB && !isPhoneA && !isPhoneAccB)) {
            if (isLaptopA || isLaptopB || isCookerA || isCookerB || /(shoe|shirt|grocery|seeds|face wash|soap)/.test(tA) || /(shoe|shirt|grocery|seeds|face wash|soap)/.test(tB)) {
                return false;
            }
        }
        if ((isCookerA && !isCookerB) && (isMixerB || isLaptopB || /(kettle|shoe|shirt|phone|wash)/.test(tB))) return false;
        if ((isCookerB && !isCookerA) && (isMixerA || isLaptopA || /(kettle|shoe|shirt|phone|wash)/.test(tA))) return false;

        // 6. Beauty cross-category conflicts (Face wash vs Foundation vs Lipstick)
        const isFaceWashA = /(face wash|facewash|facial cleanser)/.test(tA);
        const isFaceWashB = /(face wash|facewash|facial cleanser)/.test(tB);
        const isMakeupA = /(lipstick|foundation|compact|kajal)/.test(tA);
        const isMakeupB = /(lipstick|foundation|compact|kajal)/.test(tB);
        if ((isFaceWashA && isMakeupB) || (isFaceWashB && isMakeupA)) return false;

        return true;
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
            // Validate category compatibility before adding
            if (compareList.length > 0) {
                for (let existing of compareList) {
                    if (!areProductsCompatible(existing, prod)) {
                        showToast(`Cannot compare incompatible products or accessories ("${truncate(prod.title, 20)}" vs "${truncate(existing.title, 20)}").`, "warning");
                        return;
                    }
                }
            }

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
            let rating = btn.getAttribute("data-rating") || "";
            let reviews = btn.getAttribute("data-reviews") || "";
            const image = btn.getAttribute("data-image") || "";
            const link = btn.getAttribute("data-link") || btn.getAttribute("data-url") || "#";
            const qualityScore = parseFloat(btn.getAttribute("data-quality-score")) || 50;
            const qualityBand = btn.getAttribute("data-quality-band") || "Standard Quality";
            // Read category from data attribute; fall back to specs.category
            const categoryAttr = (btn.getAttribute("data-category") || "").trim();

            let specs = {};
            try {
                const rawSpecs = btn.getAttribute("data-specs");
                if (rawSpecs) specs = typeof rawSpecs === "string" ? JSON.parse(rawSpecs) : rawSpecs;
            } catch (e) {
                specs = {};
            }

            // Fallback for rating & reviews from specs or parent card DOM
            if (!rating || rating === "N/A" || rating === "0" || rating === "0.0") {
                if (specs.rating) rating = String(specs.rating);
                else if (specs.rating_num) rating = String(specs.rating_num);
                else {
                    const card = btn.closest(".card, .product-card, [data-platform]");
                    if (card) {
                        const starEl = card.querySelector("[class*='star'], [class*='Rating'], [class*='rating'], .badge.bg-success");
                        if (starEl) {
                            const m_r = (starEl.textContent || "").match(/([1-5](?:\.\d+)?)/);
                            if (m_r) rating = m_r[1];
                        }
                    }
                }
            }
            if (!reviews || reviews === "0" || reviews === "N/A") {
                if (specs.reviews) reviews = String(specs.reviews);
                else if (specs.review_count) reviews = String(specs.review_count);
                else {
                    const card = btn.closest(".card, .product-card, [data-platform]");
                    if (card) {
                        const m_rev = (card.textContent || "").match(/([\d,]+)\s*(?:reviews?|ratings?)/i);
                        if (m_rev) reviews = m_rev[1];
                    }
                }
            }

            let qualityPoints = [];
            try {
                const rawPts = btn.getAttribute("data-points");
                if (rawPts) qualityPoints = typeof rawPts === "string" ? JSON.parse(rawPts) : rawPts;
            } catch (e) {
                qualityPoints = [];
            }

            // Resolve category: data-category > specs.category > empty
            const category = categoryAttr || (specs && specs.category) || "";

            return {
                id: id,
                title: title,
                platform: platform,
                price: price,
                price_num: priceNum,
                mrp: mrp,
                discount: discount,
                rating: rating || "N/A",
                reviews: reviews || "0",
                image: image,
                link: link,
                quality_score: qualityScore,
                quality_band: qualityBand,
                specs: specs,
                quality_points: qualityPoints,
                category: category,
                added_at: Date.now()
            };
        } catch (e) {
            console.error("[Compare] Error extracting product details:", e);
            return null;
        }
    }

    /**
     * Returns the ordered list of specification keys relevant to the given product category.
     * Mirrors the 8 canonical category specification profiles.
     */
    function getCategorySpecKeys(category) {
        const cat = (category || "").toLowerCase().trim();

        // 1. Mobiles
        if (/\b(phone|phones|smartphone|smartphones|mobile|mobiles|tablet|tablets)\b/.test(cat)) {
            return [
                "Operating System", "Custom UI", "Processor", "AnTuTu Score", "RAM", "Storage",
                "Storage Type", "Display Type", "Display Size", "Refresh Rate", "Peak Brightness",
                "Rear Camera", "Front Camera", "Battery Capacity", "Charging Speed",
                "Fast Charging Support", "5G Bands", "NFC Support", "IP Rating",
                "Fingerprint Sensor Type", "Weight", "Thickness", "Audio Jack"
            ];
        }
        // 2. Laptops
        if (/(laptop|computer|\bpc\b|notebook)/.test(cat)) {
            return [
                "Processor", "Generation", "Core/Thread Count", "Base/Boost Clock",
                "RAM Capacity", "RAM Type", "Expandable RAM", "Storage Capacity", "Storage Type",
                "Additional SSD Slot", "GPU", "TGP", "Display Size", "Resolution", "Panel Type",
                "Refresh Rate", "Color Gamut", "Battery Capacity", "Battery Life", "Charging Wattage",
                "Weight", "Ports", "Biometrics"
            ];
        }
        // 3. Audio / Earbuds / Headphones
        if (/(headphone|earphone|earbud|airpod|headset|tws|audio)/.test(cat)) {
            return [
                "Form Factor", "Driver Size", "Frequency Response", "ANC Support", "ANC Depth",
                "Transparency Mode", "Mic Count", "Environmental Noise Cancellation", "Latency",
                "Bluetooth Version", "Codec Support", "Battery Life (Earbuds)", "Battery Life (With Case)",
                "Charging Time", "Fast Charging Support", "Wireless Charging", "IP Rating",
                "App Support", "Touch Controls", "Multipoint Connection"
            ];
        }
        // 4. Pressure Cooker
        if (/(cooker|pressure cooker)/.test(cat)) {
            return [
                "Capacity", "Material", "Base Type", "Induction Compatibility", "Lid Type",
                "Safety Valve Count", "Handle Material", "Gasket Release System", "Dishwasher Safe", "Warranty"
            ];
        }
        // 5. Mixer Grinder
        if (/(mixer|grinder)/.test(cat)) {
            return [
                "Motor Wattage", "RPM", "Number of Jars", "Jar Capacities", "Blade Material",
                "Body Material", "Overload Protection", "Speed Settings", "Pulse Mode",
                "Locking Mechanism", "Noise Level", "Warranty"
            ];
        }
        // 6. Electric Kettle
        if (/(kettle|electric kettle)/.test(cat)) {
            return [
                "Capacity", "Power/Wattage", "Heating Element Type", "Body Material",
                "Auto Shut-Off", "Boil Dry Protection", "360-Degree Base", "Water Level Indicator",
                "Keep Warm Function", "Cord Length", "Warranty"
            ];
        }
        // 7. Clothing & Fashion
        if (/(clothing|fashion|apparel|saree|shirt|t-shirt|jeans|dress|kurti|kurta)/.test(cat)) {
            return [
                "Fabric Material", "Fabric Composition", "Fit Type", "Pattern", "Sleeve Length",
                "Neck/Collar Type", "Occasion", "Closure Type", "Care Instructions",
                "Transparency", "Stretchability"
            ];
        }
        // 8. Shoes & Footwear & Slippers
        if (/(shoe|footwear|sneaker|sandal|boot|slipper|slippers|slide)/.test(cat)) {
            return [
                "Upper Material", "Sole Material", "Insole/Cushioning", "Closure Type", "Toe Shape",
                "Heel Height/Type", "Ankle Height", "Water Resistance", "Occasion",
                "Care Instructions", "Weight per Shoe"
            ];
        }
        // 9. Bags & Backpacks
        if (/(\bbag\b|backpack|handbag|purse|wallet|luggage|tote)/.test(cat)) {
            return [
                "Capacity", "Material", "Number of Compartments", "Laptop Sleeve Size",
                "Water Resistance", "Dimensions", "Weight", "Closure Type", "Strap Type",
                "Lock Mechanism", "Expandability", "Rain Cover Included", "Warranty"
            ];
        }
        // 10. Grocery & Food
        if (/(grocery|food|rice|chocolate|coffee|tea|snack|\boil\b|spice|seed|nut|dal|flour|sugar|salt|protein)/.test(cat)) {
            return [
                "Net Quantity", "Pack Size", "Form", "Processing", "Protein Content",
                "Dietary Fibre", "Carbohydrates", "Added Sugar", "Fat/Trans Fat", "Calories",
                "Omega-3/Omega-6", "Vitamins/Minerals", "Shelf Life", "Country of Origin",
                "Certification", "Allergens"
            ];
        }
        // 11. Face Wash
        if (/(face_wash|facewash|face wash|cleanser)/.test(cat)) {
            return [
                "Skin Type", "Key Actives", "Key Benefits", "Formulation", "Target Concerns",
                "pH Level", "Sulphate-Free", "Paraben-Free", "Fragrance Type",
                "Non-Comedogenic", "Volume", "Shelf Life"
            ];
        }
        // 12. Sunscreen
        if (/(sunscreen|sun screen|sunblock)/.test(cat)) {
            return [
                "SPF Value", "PA Rating", "Broad Spectrum", "Filter Type", "Finish",
                "Water/Sweat Resistance", "White Cast", "Key Actives", "Paraben-Free", "Net Volume"
            ];
        }
        // 13. Moisturizer
        if (/(moisturizer|moisturiser|cream|lotion)/.test(cat)) {
            return [
                "Skin Type", "Texture", "Key Ingredients", "Finish", "SPF Included",
                "Non-Greasy", "Comedogenic Rating", "Target Concerns", "Paraben-Free", "Net Volume", "Shelf Life"
            ];
        }
        // 14. Foundation
        if (/foundation/.test(cat)) {
            return [
                "Skin Type", "Coverage", "Finish", "Formulation", "SPF Included",
                "Shade Range", "Cruelty-Free", "Waterproof", "Transfer-Proof", "Net Weight/Volume"
            ];
        }
        // 15. Lipstick
        if (/(lipstick|lip stick|lip gloss|lip balm)/.test(cat)) {
            return [
                "Finish", "Formulation", "Longevity", "Transfer-Proof", "Hydrating",
                "Cruelty-Free", "Paraben-Free", "Shade Family", "Net Weight"
            ];
        }
        // Default fallback
        return ["Material", "Color", "Dimensions", "Warranty", "Compatibility", "Weight"];
    }

    /**
     * Given the list of products being compared, resolves the common category.
     * Uses the most-frequent non-empty category among the products.
     */
    function resolveCompareCategory(products) {
        const freq = {};
        products.forEach(p => {
            const cat = (p.category || (p.specs && p.specs.category) || "").toLowerCase().trim();
            if (cat && cat !== "general" && cat !== "other") {
                freq[cat] = (freq[cat] || 0) + 1;
            }
        });
        // Return the most-frequent category
        let best = "", bestCount = 0;
        Object.entries(freq).forEach(([cat, count]) => {
            if (count > bestCount) { best = cat; bestCount = count; }
        });
        return best;
    }

    /**
     * Given category spec keys and a product's specs dict, returns an ordered map
     * of { displayLabel -> value } for keys that exist in the product's specs
     * (case-insensitively matched).
     */
    function matchSpecsForCategory(categoryKeys, specs) {
        const result = [];
        if (!specs || !categoryKeys) return result;

        // Build a lower-case index of all spec keys the product actually has
        const specIndex = {};
        Object.keys(specs).forEach(k => {
            specIndex[k.toLowerCase().trim()] = k; // lowercase -> original key
        });

        categoryKeys.forEach(displayLabel => {
            const lookupKey = displayLabel.toLowerCase().trim();
            // Try direct match, then underscore variation
            const originalKey = specIndex[lookupKey]
                || specIndex[lookupKey.replace(/ /g, "_")]
                || specIndex[lookupKey.replace(/_/g, " ")];
            if (originalKey) {
                const val = String(specs[originalKey] || "").trim();
                if (val && val !== "N/A" && val !== "Not Available" && val !== "None" && val !== "null") {
                    result.push({ label: displayLabel, key: originalKey, value: val });
                } else {
                    result.push({ label: displayLabel, key: originalKey, value: null });
                }
            } else {
                result.push({ label: displayLabel, key: null, value: null });
            }
        });
        return result;
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
                    <img src="${escapeHtml(item.image || getPlatformFallbackSvg(item.platform))}" alt="Thumbnail" style="width: 38px; height: 38px; object-fit: contain; border-radius: 4px; background: #fff; flex-shrink: 0;" onerror="this.onerror=null; this.src=getPlatformFallbackSvg('${escapeHtml(item.platform)}');">
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

            // Count only category-relevant features to avoid inflating scores
            // with irrelevant fields (e.g. electronic specs for grocery products)
            const resolvedCat = resolveCompareCategory(products);
            const catKeys = getCategorySpecKeys(resolvedCat);
            const catKeyNorm = catKeys.map(k => k.toLowerCase().trim());

            const specIndex = {};
            Object.keys(p.specs || {}).forEach(k => {
                specIndex[k.toLowerCase().trim()] = k;
            });

            // If category keys matched, count only those; otherwise fall back to all non-empty
            let relevantKeys = catKeyNorm
                .map(lk => specIndex[lk] || specIndex[lk.replace(/ /g, "_")] || specIndex[lk.replace(/_/g, " ")])
                .filter(Boolean);

            if (relevantKeys.length === 0) {
                // Fallback: count all non-empty specs
                relevantKeys = Object.keys(p.specs || {}).filter(k => {
                    const val = String((p.specs || {})[k] || "").toLowerCase();
                    return val && val !== "n/a" && val !== "not available" && val !== "none";
                });
            } else {
                relevantKeys = relevantKeys.filter(k => {
                    const val = String((p.specs || {})[k] || "").toLowerCase();
                    return val && val !== "n/a" && val !== "not available" && val !== "none";
                });
            }

            let featureCount = relevantKeys.length + (p.quality_points || []).length;

            return {
                ...p,
                raw_price_score: priceScore,
                raw_rating_score: ratingScore,
                raw_quality_score: qScore,
                feature_count: featureCount,
                feature_keys: relevantKeys
            };
        });

        // Determine pairwise feature advantage
        const maxFeatures = Math.max(...evaluated.map(e => e.feature_count), 1);

        evaluated.forEach(item => {
            let featureScore = (item.feature_count / maxFeatures) * 100;
            item.raw_feature_score = featureScore;

            // Composite Smart Score following Quality First, Price Second:
            // Priority 1: Specification-based quality (45%)
            // Priority 2: Feature completeness & coverage (25%)
            // Priority 3: Ratings & reviews (15%)
            // Priority 4: Stock & availability (10%)
            // Priority 5: Price competitiveness (5% tie-breaker)
            const composite = (
                item.raw_quality_score * 0.45 +
                item.raw_feature_score * 0.25 +
                item.raw_rating_score * 0.15 +
                (item.raw_price_score * 0.05) +
                10.0
            );
            item.smart_score = Math.round(composite * 10) / 10;

            // Generate feature advantage highlights
            const advantages = [];
            // Check quality advantage
            const maxQ = Math.max(...evaluated.map(x => x.raw_quality_score));
            if (item.raw_quality_score === maxQ && maxQ > 60) {
                advantages.push(`Top Quality Score (${Math.round(item.raw_quality_score)}/100)`);
            }
            // Feature dominance
            if (item.feature_count === maxFeatures && maxFeatures > 3) {
                advantages.push(`Most Complete Specifications (${item.feature_count} features)`);
            }
            // Check rating advantage
            const maxR = Math.max(...evaluated.map(x => parseFloat(String(x.rating).replace("★", "").trim()) || 0));
            if (maxR > 0 && (parseFloat(String(item.rating).replace("★", "").trim()) || 0) === maxR) {
                advantages.push(`Customer Rating (★ ${maxR})`);
            }
            // Check if cheapest
            if (item.price_num && item.price_num === minPrice && validPrices.length > 1) {
                advantages.push(`Lowest Price (₹${item.price_num.toLocaleString("en-IN")})`);
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

        // Sort descending: Quality First (raw_quality_score, feature_count, rating, -price)
        evaluated.sort((a, b) => {
            if (b.raw_quality_score !== a.raw_quality_score) {
                return b.raw_quality_score - a.raw_quality_score;
            }
            if (b.raw_feature_score !== a.raw_feature_score) {
                return b.raw_feature_score - a.raw_feature_score;
            }
            if (b.raw_rating_score !== a.raw_rating_score) {
                return b.raw_rating_score - a.raw_rating_score;
            }
            return (a.price_num || 9999999) - (b.price_num || 9999999);
        });

        // Assign ranks and badges
        const rankDefinitions = [
            { rank: 1, title: "🏆 #1 Top Ranked / Winner", badgeClass: "smart-rank-badge-1", icon: "fa-trophy" },
            { rank: 2, title: "🥈 #2 Strong Contender", badgeClass: "smart-rank-badge-2", icon: "fa-medal" },
            { rank: 3, title: "🥉 #3 Value Alternative", badgeClass: "smart-rank-badge-3", icon: "fa-award" }
        ];

        const topItem = evaluated[0];
        return evaluated.map((prod, idx) => {
            const def = rankDefinitions[idx] || { rank: idx + 1, title: `#${idx + 1} Option`, badgeClass: "badge bg-secondary", icon: "fa-tag" };
            
            let whyWon = "";
            if (idx === 0) {
                whyWon = `Ranked #1 based on superior verified specifications (${Math.round(prod.raw_quality_score)}/100 quality score, ${prod.feature_count} verified features).`;
            } else {
                if (prod.raw_quality_score < topItem.raw_quality_score && prod.price_num < topItem.price_num) {
                    whyWon = `Lower price, but fewer verified specifications (${prod.feature_count} features vs ${topItem.feature_count}).`;
                } else if (prod.raw_quality_score < topItem.raw_quality_score) {
                    whyWon = `Lower specification quality score (${Math.round(prod.raw_quality_score)}/100 vs ${Math.round(topItem.raw_quality_score)}/100).`;
                } else {
                    whyWon = `Solid alternative offering ${prod.feature_advantages[0] || "decent balance"}.`;
                }
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

        // ── Category-specific specification filtering ────────────────────────
        // Detect the common category from the products being compared
        const resolvedCategory = resolveCompareCategory(rankedList);
        const categoryDisplayName = resolvedCategory
            ? resolvedCategory.charAt(0).toUpperCase() + resolvedCategory.slice(1)
            : "General";
        const categoryKeys = getCategorySpecKeys(resolvedCategory);

        // Build an ordered spec key list: only include keys that exist in at
        // least ONE product and belong to the category schema.
        // A key is "included" if it maps to a real spec on any product.
        const EXCLUDED_KEYS = new Set(["price_num", "rating_num", "category_specs", "category",
            "image", "title", "link", "url", "product_id", "asin"]);

        // Build a set of all spec keys present across all products (normalised)
        const allSpecsLower = new Set();
        rankedList.forEach(p => {
            if (p.specs && typeof p.specs === "object") {
                Object.keys(p.specs).forEach(k => allSpecsLower.add(k.toLowerCase().trim()));
            }
        });

        // Filter category keys to those that exist in at least one product
        const filteredCategoryKeys = categoryKeys.filter(displayLabel => {
            const lk = displayLabel.toLowerCase().trim();
            return allSpecsLower.has(lk)
                || allSpecsLower.has(lk.replace(/ /g, "_"))
                || allSpecsLower.has(lk.replace(/_/g, " "));
        });

        // If no category keys matched at all, fall back gracefully to all non-system keys
        // sorted alphabetically (so at least we show something meaningful)
        let specKeys;
        if (filteredCategoryKeys.length > 0) {
            specKeys = filteredCategoryKeys; // already in priority order
        } else {
            specKeys = Array.from(allSpecsLower)
                .filter(k => !EXCLUDED_KEYS.has(k))
                .sort()
                .map(k => k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " "));
        }

        // Helper: given a display-label, look up its value in a product's specs
        function resolveSpecValue(displayLabel, specs) {
            if (!specs) return null;
            const lk = displayLabel.toLowerCase().trim();
            const candidates = [lk, lk.replace(/ /g, "_"), lk.replace(/_/g, " ")];
            for (const c of candidates) {
                for (const [k, v] of Object.entries(specs)) {
                    if (k.toLowerCase().trim() === c) {
                        const sv = String(v || "").trim();
                        return sv && sv !== "N/A" && sv !== "Not Available" ? sv : null;
                    }
                }
            }
            return null;
        }

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
                            <img src="${escapeHtml(p.image || getPlatformFallbackSvg(p.platform))}" alt="Product Image" style="height: 110px; max-width: 140px; object-fit: contain; border-radius: 8px; background: #fff;" onerror="this.onerror=null; this.src=getPlatformFallbackSvg('${escapeHtml(p.platform)}');">
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

        // ── Feature / Specification Comparison Section ──────────────────────
        // Inserted BELOW Smart Ranking product cards, ABOVE the Specification
        // Comparison table. Uses specKeys + resolveSpecValue already computed
        // above — no existing logic is modified.
        (function buildFeatureComparisonSection() {
            // Only show keys that at least one product has a value for
            const featureRows = specKeys.filter(k => rankedList.some(p => resolveSpecValue(k, p.specs)));

            if (featureRows.length === 0) return; // nothing to show

            // Coverage counts per product
            const coverageCounts = rankedList.map(p => ({
                platform: p.platform,
                count: featureRows.filter(k => resolveSpecValue(k, p.specs) !== null).length,
                total: featureRows.length
            }));

            // Decide winner column (most features)
            const maxCoverage = Math.max(...coverageCounts.map(c => c.count));

            html += `
        <!-- ══════════════════════════════════════════════════════════════
             FEATURE / SPECIFICATION COMPARISON
             Position: Below Smart Ranking, Above Specification Matrix
             ══════════════════════════════════════════════════════════════ -->
        <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-3" id="featureComparisonSection">

            <!-- Section Header -->
            <div class="card-header py-2 px-3 d-flex align-items-center justify-content-between"
                 style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);">
                <span class="fw-bold small text-uppercase d-flex align-items-center gap-2">
                    <span class="text-white"><i class="fas fa-layer-group me-1 text-info"></i>Feature / Specification Comparison</span>
                    <span class="badge bg-info text-dark rounded-pill px-2" style="font-size:0.65rem;">${escapeHtml(categoryDisplayName)}</span>
                    <span class="badge bg-warning text-dark rounded-pill px-2" style="font-size:0.65rem;">${featureRows.length} Features</span>
                </span>
                <span class="badge bg-white text-dark border rounded-pill px-2 py-1" style="font-size:0.7rem;">
                    <i class="fas fa-check-circle text-success me-1"></i>Actual extracted data only
                </span>
            </div>

            <!-- Coverage Summary Bars (one per product) -->
            <div class="px-3 pt-3 pb-2 bg-light border-bottom d-flex flex-wrap gap-3 align-items-center">
                <span class="small text-muted fw-semibold text-uppercase" style="font-size:0.72rem; letter-spacing:0.4px;">
                    <i class="fas fa-chart-bar me-1"></i>Spec Coverage
                </span>
                ${coverageCounts.map(c => {
                    const pct = featureRows.length ? Math.round((c.count / c.total) * 100) : 0;
                    const isTop = c.count === maxCoverage;
                    const platColor = getPlatformColor(c.platform);
                    return `
                    <div class="d-flex align-items-center gap-2" style="min-width:160px;">
                        <span class="badge text-white px-2 py-1 rounded-pill" style="background:${platColor}; font-size:0.68rem;">${escapeHtml(c.platform)}</span>
                        <div class="flex-grow-1" style="min-width:80px;">
                            <div class="progress" style="height:8px; border-radius:4px;">
                                <div class="progress-bar ${isTop ? 'bg-success' : 'bg-primary'}"
                                     style="width:${pct}%; border-radius:4px;" role="progressbar"></div>
                            </div>
                        </div>
                        <span class="fw-bold small ${isTop ? 'text-success' : 'text-secondary'}" style="font-size:0.72rem; white-space:nowrap;">
                            ${c.count}/${c.total} ${isTop ? '<i class="fas fa-crown" style="font-size:0.6rem;"></i>' : ''}
                        </span>
                    </div>`;
                }).join('')}
            </div>

            <!-- Feature-by-Feature Table -->
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0 text-center" style="font-size:0.83rem;">
                    <thead>
                        <tr style="background:#f8faff;">
                            <th style="width:28%; text-align:left; padding-left:20px; font-size:0.78rem; color:#555; text-transform:uppercase; letter-spacing:0.4px; border-bottom: 2px solid #e0e7ff;">
                                <i class="fas fa-list-check me-1 text-primary"></i>Feature
                            </th>
                            ${rankedList.map(p => {
                                const platColor = getPlatformColor(p.platform);
                                const c = coverageCounts.find(x => x.platform === p.platform) || {};
                                const isTop = c.count === maxCoverage;
                                return `
                                <th style="width:${72 / rankedList.length}%; border-bottom: 2px solid #e0e7ff; ${isTop ? 'background:rgba(16,185,129,0.06);' : ''}">
                                    <div class="d-flex flex-column align-items-center gap-1 py-1">
                                        <span class="badge text-white px-2 py-1 rounded-pill" style="background:${platColor}; font-size:0.7rem;">
                                            ${isTop ? '🏆 ' : ''}${escapeHtml(p.platform)}
                                        </span>
                                        <div class="text-truncate small text-dark fw-semibold" style="max-width:150px; font-size:0.72rem;" title="${escapeHtml(p.title)}">
                                            ${escapeHtml(p.title)}
                                        </div>
                                    </div>
                                </th>`;
                            }).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${featureRows.map((k, rowIdx) => {
                            // Alternate row shading
                            const rowBg = rowIdx % 2 === 0 ? '' : 'style="background:#fafbff;"';
                            const cells = rankedList.map(p => {
                                const val = resolveSpecValue(k, p.specs);
                                const c = coverageCounts.find(x => x.platform === p.platform) || {};
                                const isTop = c.count === maxCoverage;
                                if (val !== null && val !== undefined && val !== '') {
                                    // Has value → show green tick + value
                                    return `
                                    <td class="text-center" ${isTop ? 'style="background:rgba(16,185,129,0.04);"' : ''}>
                                        <div class="d-flex flex-column align-items-center gap-0.5">
                                            <span class="text-success fw-bold" style="font-size:0.9rem;">✓</span>
                                            <span class="text-dark" style="font-size:0.78rem; word-break:break-word; max-width:120px; display:block;">${escapeHtml(val)}</span>
                                        </div>
                                    </td>`;
                                } else {
                                    // Missing → show red cross
                                    return `
                                    <td class="text-center text-muted" ${isTop ? 'style="background:rgba(16,185,129,0.04);"' : ''}>
                                        <span class="text-danger" style="font-size:0.85rem;">✗</span>
                                        <div style="font-size:0.72rem; color:#bbb;">Not Available</div>
                                    </td>`;
                                }
                            }).join('');

                            return `<tr ${rowBg}>
                                <td class="fw-semibold text-start text-dark" style="padding-left:20px; font-size:0.8rem;">
                                    <i class="fas fa-circle-dot text-primary me-1" style="font-size:0.5rem; vertical-align:middle;"></i>
                                    ${escapeHtml(k)}
                                </td>
                                ${cells}
                            </tr>`;
                        }).join('')}
                    </tbody>
                    <!-- Footer: totals row -->
                    <tfoot>
                        <tr style="background:#f0f4ff; border-top:2px solid #e0e7ff;">
                            <td class="fw-bold text-start text-primary ps-4" style="font-size:0.78rem; text-transform:uppercase; letter-spacing:0.4px;">
                                <i class="fas fa-sigma me-1"></i>Total Features Available
                            </td>
                            ${coverageCounts.map(c => {
                                const isTop = c.count === maxCoverage;
                                return `
                                <td class="fw-bold text-center ${isTop ? 'text-success' : 'text-secondary'}">
                                    <span class="badge ${isTop ? 'bg-success' : 'bg-secondary'} px-3 py-1 rounded-pill" style="font-size:0.78rem;">
                                        ${c.count} / ${c.total}
                                        ${isTop ? ' ★' : ''}
                                    </span>
                                </td>`;
                            }).join('')}
                        </tr>
                    </tfoot>
                </table>
            </div>

            <!-- Legend -->
            <div class="px-3 py-2 bg-light border-top d-flex align-items-center gap-3 flex-wrap">
                <span class="small text-muted" style="font-size:0.72rem;">
                    <span class="text-success fw-bold">✓</span> = Feature verified &amp; extracted
                    &nbsp;|&nbsp;
                    <span class="text-danger fw-bold">✗</span> = Not available on this platform
                    &nbsp;|&nbsp;
                    <i class="fas fa-crown text-warning"></i> = Most complete specification coverage
                </span>
            </div>
        </div>`;
        })();
        // ── End Feature / Specification Comparison Section ─────────────────

        // Detailed Side-by-Side Comparison Matrix Table
        html += `
        <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-3">
            <div class="card-header bg-dark text-white py-2.5 px-3 d-flex align-items-center justify-content-between">
                <span class="fw-bold small text-uppercase d-flex align-items-center flex-wrap gap-2">
                    <span><i class="fas fa-table me-1.5 text-primary"></i>Specification Comparison</span>
                    <span class="badge bg-info text-dark rounded-pill px-2 py-0.5" style="font-size: 0.68rem; font-weight: 600;">${escapeHtml(categoryDisplayName)} Category</span>
                </span>
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
                        <!-- 0. Product Preview Row -->
                        <tr class="table-light">
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-image me-1.5 text-muted"></i>Preview</td>
                            ${rankedList.map(p => `
                                <td>
                                    <img src="${escapeHtml(p.image || getPlatformFallbackSvg(p.platform))}" alt="${escapeHtml(p.title)}" style="height: 60px; max-width: 90px; object-fit: contain; border-radius: 6px; background: #fff; padding: 2px;" onerror="this.onerror=null; this.src=getPlatformFallbackSvg('${escapeHtml(p.platform)}');">
                                </td>
                            `).join('')}
                        </tr>

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

                        <!-- 2. Quality Score (Priority 1) -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-award me-1.5 text-primary"></i>Specification Quality</td>
                            ${rankedList.map(p => `
                                <td>
                                    <span class="badge bg-primary-subtle text-primary border border-primary px-2.5 py-1 rounded-pill fw-bold">
                                        ${Math.round(p.quality_score)}/100
                                    </span>
                                    <div class="small text-muted mt-0.5" style="font-size: 0.7rem;">${escapeHtml(p.quality_band || 'Standard Quality')}</div>
                                </td>
                            `).join('')}
                        </tr>

                        <!-- 3. Dynamic Specifications (Priority 2) -->
                        ${specKeys.map(k => {
                            const anyHasVal = rankedList.some(p => resolveSpecValue(k, p.specs));
                            if (!anyHasVal) return '';
                            return `
                            <tr>
                                <td class="fw-semibold text-start ps-3 text-muted text-capitalize">${escapeHtml(k)}</td>
                                ${rankedList.map(p => {
                                    const val = resolveSpecValue(k, p.specs);
                                    return `<td class="${val ? '' : 'text-muted'}">${escapeHtml(val || '—')}</td>`;
                                }).join('')}
                            </tr>`;
                        }).join('')}

                        <!-- 4. Customer Rating & Reviews (Priority 3) -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-star me-1.5 text-warning"></i>Customer Rating</td>
                            ${rankedList.map(p => {
                                const cleanR = String(p.rating || 'N/A').replace(/^[★\s]+/, '').trim();
                                const isNA = !cleanR || cleanR.toUpperCase() === 'N/A' || cleanR === '0' || cleanR === '0.0';
                                return `
                                <td>
                                    <span class="fw-bold text-warning-emphasis">${isNA ? 'N/A' : '★ ' + escapeHtml(cleanR)}</span>
                                    <div class="small text-muted" style="font-size: 0.7rem;">(${escapeHtml(p.reviews || '0')} reviews)</div>
                                </td>`;
                            }).join('')}
                        </tr>

                        <!-- 5. Price & Value (Priority 4 & 5) -->
                        <tr>
                            <td class="fw-bold text-start ps-3 text-dark"><i class="fas fa-tag me-1.5 text-success"></i>Current Price</td>
                            ${rankedList.map(p => `
                                <td class="fw-bold ${p.price_num && p.price_num === Math.min(...rankedList.map(x => x.price_num || 999999)) ? 'text-success bg-success bg-opacity-10' : 'text-dark'}">
                                    ${escapeHtml(p.price || '—')}
                                </td>
                            `).join('')}
                        </tr>

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
                        <img src="${escapeHtml(cand.image || getPlatformFallbackSvg(cand.platform))}" alt="Thumbnail" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px; background: #fff; flex-shrink: 0;" onerror="this.onerror=null; this.src=getPlatformFallbackSvg('${escapeHtml(cand.platform)}');">
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
    function getPlatformFallbackSvg(plat) {
        const p = String(plat || "").toLowerCase();
        if (p.includes("flipkart")) {
            return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23f1f3f6'/><path d='M35 38 L65 38 L61 68 L39 68 Z' fill='%232874f0'/><path d='M43 38 C43 30 57 30 57 38' stroke='%23ff9f00' stroke-width='3' fill='none'/><text x='50' y='82' font-family='Arial' font-size='9' font-weight='bold' fill='%232874f0' text-anchor='middle'>Flipkart</text></svg>";
        }
        if (p.includes("meesho")) {
            return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23fdf2f8'/><path d='M35 38 L65 38 L61 68 L39 68 Z' fill='%23f43397'/><path d='M43 38 C43 30 57 30 57 38' stroke='%23831843' stroke-width='3' fill='none'/><text x='50' y='82' font-family='Arial' font-size='9' font-weight='bold' fill='%23f43397' text-anchor='middle'>Meesho</text></svg>";
        }
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23f7f7f7'/><path d='M32 40 L38 40 L45 60 L62 60 L68 45 L40 45' stroke='%23232f3e' stroke-width='3' fill='none'/><circle cx='46' cy='66' r='3' fill='%23ff9900'/><circle cx='61' cy='66' r='3' fill='%23ff9900'/><text x='50' y='82' font-family='Arial' font-size='9' font-weight='bold' fill='%23232f3e' text-anchor='middle'>Amazon</text></svg>";
    }

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
