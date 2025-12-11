/**
 * Global Configuration for Mini App
 * Change API_BASE_URL to point to your backend server
 */

const CONFIG = {
    //API_BASE_URL: "https://srvgc.tailcca3c2.ts.net/reports-api",
    API_BASE_URL: '/api',

    // Auth endpoints
    AUTH_LOGIN: '/auth/login',
    AUTH_VERIFY: '/auth/login/verify',

    // Report endpoints
    REPORTS_ADD: '/reports/add',
    REPORTS_GET: '/reports',
    REPORTS_EDIT: '/reports/edit',
    REPORTS_DELETE: '/reports/delete',
    
    // User endpoints
    PROFILE: '/profile',
    PROFILE_UPDATE: '/profile/edit',
    USERS_GET: '/users'

};

// Helper function to build full API URL
function getApiUrl(endpoint) {
    return CONFIG.API_BASE_URL + endpoint;
}
