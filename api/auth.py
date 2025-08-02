from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import Dict
import json
from database import get_db
from services.gmail_service import GmailService

router = APIRouter()

# Global Gmail service instance
gmail_service = GmailService()

@router.get("/gmail/auth-url")
async def get_gmail_auth_url():
    """Get Gmail OAuth authorization URL"""
    try:
        auth_url = gmail_service.get_auth_url()
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Redirect user to this URL for Gmail authentication"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate auth URL: {str(e)}")

@router.get("/gmail/callback")
async def gmail_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(None, description="State parameter"),
    error: str = Query(None, description="Error from OAuth")
):
    """Handle Gmail OAuth callback"""
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")
        
        # Exchange code for credentials
        result = gmail_service.authenticate_with_code(code)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Authentication failed"))
        
        return {
            "success": True,
            "message": "Gmail authentication successful",
            "user_email": result.get("email"),
            "messages_total": result.get("messages_total", 0),
            "threads_total": result.get("threads_total", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.post("/gmail/set-credentials")
async def set_gmail_credentials(credentials: Dict):
    """Set Gmail credentials from stored token"""
    try:
        success = gmail_service.set_credentials(credentials)
        
        if not success:
            raise HTTPException(status_code=400, detail="Invalid credentials")
        
        return {
            "success": True,
            "message": "Gmail credentials set successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set credentials: {str(e)}")

@router.get("/gmail/status")
async def get_gmail_status():
    """Check Gmail authentication status"""
    try:
        if gmail_service.service is None:
            return {
                "authenticated": False,
                "message": "Gmail not authenticated"
            }
        
        # Test connection by getting profile
        profile = gmail_service.service.users().getProfile(userId='me').execute()
        
        return {
            "authenticated": True,
            "email": profile.get('emailAddress'),
            "messages_total": profile.get('messagesTotal', 0),
            "threads_total": profile.get('threadsTotal', 0)
        }
        
    except Exception as e:
        return {
            "authenticated": False,
            "error": str(e)
        }

@router.get("/gmail/test-connection")
async def test_gmail_connection():
    """Test Gmail API connection"""
    try:
        if not gmail_service.service:
            raise HTTPException(status_code=401, detail="Gmail not authenticated")
        
        # Try to get user profile
        profile = gmail_service.service.users().getProfile(userId='me').execute()
        
        return {
            "success": True,
            "message": "Gmail connection working",
            "email": profile.get('emailAddress'),
            "messages_total": profile.get('messagesTotal', 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

@router.post("/gmail/logout")
async def gmail_logout():
    """Logout from Gmail (clear credentials)"""
    try:
        # Clear credentials
        gmail_service.credentials = None
        gmail_service.service = None
        
        return {
            "success": True,
            "message": "Gmail logout successful"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")