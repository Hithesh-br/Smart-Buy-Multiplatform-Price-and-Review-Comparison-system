/**
 * SmartBuy Centralized API Configuration
 * Supports decoupled or same-origin backend deployments.
 */
window.SMARTBUY_CONFIG = window.SMARTBUY_CONFIG || {
    // When frontend and backend share an origin (Flask monolithic SSR), apiBaseUrl is empty.
    // When deployed separately or via CDN, set window.API_BASE_URL to the production backend origin.
    apiBaseUrl: window.API_BASE_URL || "",

    apiUrl: function(endpoint) {
        if (!endpoint) return "";
        if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
            return endpoint;
        }
        if (!endpoint.startsWith("/")) {
            endpoint = "/" + endpoint;
        }
        const base = this.apiBaseUrl ? this.apiBaseUrl.replace(/\/$/, "") : "";
        return base + endpoint;
    }
};
