import base64
import requests
from urllib.parse import urlencode
from flask import redirect, session, url_for
from config import Config

def get_auth_headers(access_token: str) -> dict:
    """Generate headers for API requests with access token"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/text"
    }

def get_basic_auth() -> str:
    """Generate Basic Auth header for token requests"""
    credentials = f"{Config.CLIENT_ID}:{Config.CLIENT_SECRET}"
    return base64.b64encode(credentials.encode()).decode()

def redirect_to_authorization(state_payload: str) -> redirect:
    """Redirect user to QuickBooks authorization page"""
    params = {
        "client_id": Config.CLIENT_ID,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "redirect_uri": Config.REDIRECT_URI,
        "state": state_payload
    }
    auth_url = f"{Config.AUTH_BASE_URL}?{urlencode(params)}"
    return redirect(auth_url)

def exchange_code_for_token(auth_code: str) -> dict:
    """Exchange authorization code for access token"""
    headers = {
        "Authorization": f"Basic {get_basic_auth()}",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": Config.REDIRECT_URI
    }

    try:
        response = requests.post(
            Config.TOKEN_URL,
            headers=headers,
            data=urlencode(data)
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Token exchange failed: {str(e)}")

def refresh_access_token(refresh_token: str) -> dict:
    """Refresh expired access token"""
    headers = {
        "Authorization": f"Basic {get_basic_auth()}",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    try:
        response = requests.post(
            Config.TOKEN_URL,
            headers=headers,
            data=urlencode(data)
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Token refresh failed: {str(e)}")

def is_authenticated() -> bool:
    """Check if user has valid access token"""
    if 'access_token' not in session:
        return False
    
    # Optional: Add token expiration check here
    return True

def handle_callback(auth_code: str, state: str):
    """Process OAuth callback and store tokens"""
    try:
        # Exchange code for tokens
        tokens = exchange_code_for_token(auth_code)
        
        # Store tokens in session
        session['access_token'] = tokens['access_token']
        session['refresh_token'] = tokens.get('refresh_token')
        session['expires_in'] = tokens.get('expires_in')
        
        # Parse state to determine where to redirect
        state_parts = state.split(':')
        entity_type = state_parts[0]
        
        if entity_type == "bills":
            return redirect(url_for(
                "fetch_and_save_worker",
                fetch_count=int(state_parts[1]),
                qb_start_position=int(state_parts[2]),
                display_count=int(state_parts[3]),
                display_start=int(state_parts[4])
            ))
        elif entity_type == "customers":
            return redirect(url_for(
                "fetch_and_save_customers_worker",
                fetch_count=int(state_parts[1]),
                qb_start_position=int(state_parts[2]),
                display_count=int(state_parts[3]),
                display_start=int(state_parts[4])
            ))
        
        return redirect(url_for("home"))
    
    except Exception as e:
        # Handle error appropriately
        return redirect(url_for("home", error=str(e)))