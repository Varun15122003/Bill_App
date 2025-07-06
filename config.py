import os

class Config:
    CLIENT_ID = "ABiHWaO5C05yuxL0mv0QL5rzC0z1RDvfoAVB2xMV64G3YgEmfv"
    CLIENT_SECRET = "VZD28FlMtQ6K914rMnKAuoA3bd5lSac6M7Ctle65"
    REDIRECT_URI = "http://localhost:5000/callback"
    REALM_ID = "9341454578080950"
    SECRET_KEY = os.urandom(24)
    ENV = os.getenv('FLASK_ENV', 'development')  # Default to production if not set
    
    # API endpoints
    AUTH_BASE_URL = "https://appcenter.intuit.com/connect/oauth2"
    TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    API_BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"
    
    # Fetch settings
    DEFAULT_BILL_FETCH_COUNT = 3
    DEFAULT_CUSTOMER_FETCH_COUNT = 5