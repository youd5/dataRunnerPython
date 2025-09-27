/**
 * Constants file for all hardcoded strings used in the application
 */

const MESSAGES = {
    // Page titles and headers
    PAGE_TITLE: 'Welcome to dataRunnerPython',
    MAIN_HEADING: '🚀 dataRunnerPython',
    
    // Welcome messages
    WELCOME_NOT_LOGGED_IN: 'Welcome to dataRunnerPython web service with Zerodha Kite integration! Get started by logging into your Zerodha account.',
    WELCOME_LOGGED_IN: 'Welcome back! You are logged in to Zerodha Kite. Check your holdings and positions below.',
    
    // Button texts
    LOGIN_TO_ZERODHA: '🔐 Login to Zerodha',
    TEST_API: '🚀 Test API',
    HOLDINGS: '💰 HOLDINGS',
    POSITIONS: '📊 POSITIONS',
    LOGOUT: '🚪 Logout',
    
    // Loading messages
    GETTING_LOGIN_URL: 'Getting Login URL...',
    CALLING_API: 'Calling API...',
    
    // API response messages
    API_RESPONSE_PREFIX: 'API Response: ',
    ERROR_PREFIX: 'Error: ',
    
    // Error messages
    LOGOUT_ERROR: 'Logout error:',
    
    // URLs and endpoints
    HOLDINGS_URL: '/holdings',
    POSITIONS_URL: '/positions',
    LOGIN_URL_ENDPOINT: '/api/kite/login-url',
    LOGOUT_ENDPOINT: '/api/kite/logout',
    HELLO_API_ENDPOINT: '/api/hello',
    PROFILE_ENDPOINT: '/api/kite/profile'
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MESSAGES;
}
