import os
import json
import base64
from datetime import datetime
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import settings

class GmailService:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.labels'
        ]
        self.credentials = None
        self.service = None
        
    def get_auth_url(self) -> str:
        """Get Gmail OAuth authorization URL"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                    }
                },
                scopes=self.SCOPES
            )
            flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            return auth_url
            
        except Exception as e:
            print(f"❌ Error getting auth URL: {e}")
            raise
    
    def authenticate_with_code(self, authorization_code: str) -> Dict:
        """Exchange authorization code for credentials"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                    }
                },
                scopes=self.SCOPES
            )
            flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
            
            # Exchange code for credentials
            flow.fetch_token(code=authorization_code)
            self.credentials = flow.credentials
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.credentials)
            
            # Test connection
            profile = self.service.users().getProfile(userId='me').execute()
            
            return {
                "success": True,
                "email": profile.get('emailAddress'),
                "messages_total": profile.get('messagesTotal', 0),
                "threads_total": profile.get('threadsTotal', 0)
            }
            
        except Exception as e:
            print(f"❌ Error authenticating: {e}")
            return {"success": False, "error": str(e)}
    
    def set_credentials(self, credentials_dict: Dict):
        """Set credentials from stored token"""
        try:
            self.credentials = Credentials.from_authorized_user_info(credentials_dict)
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
            return True
        except Exception as e:
            print(f"❌ Error setting credentials: {e}")
            return False
    
    def get_messages_by_thread(self, thread_id: str) -> List[Dict]:
        """Get all messages in a specific thread"""
        try:
            if not self.service:
                raise Exception("Gmail service not authenticated")
            
            thread = self.service.users().threads().get(
                userId='me', 
                id=thread_id
            ).execute()
            
            messages = []
            for message in thread.get('messages', []):
                msg_detail = self.service.users().messages().get(
                    userId='me', 
                    id=message['id'],
                    format='full'
                ).execute()
                
                parsed_msg = self._parse_message(msg_detail)
                messages.append(parsed_msg)
            
            return messages
            
        except HttpError as e:
            print(f"❌ Gmail API error: {e}")
            return []
        except Exception as e:
            print(f"❌ Error getting thread messages: {e}")
            return []
    
    def search_messages(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search for messages matching a query"""
        try:
            if not self.service:
                raise Exception("Gmail service not authenticated")
            
            # Search for messages
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = []
            for msg in result.get('messages', []):
                msg_detail = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                parsed_msg = self._parse_message(msg_detail)
                messages.append(parsed_msg)
            
            return messages
            
        except HttpError as e:
            print(f"❌ Gmail API error: {e}")
            return []
        except Exception as e:
            print(f"❌ Error searching messages: {e}")
            return []
    
    def get_lexsy_sample_emails(self) -> List[Dict]:
        """Get the sample Lexsy email thread for demo purposes"""
        return [
            {
                "id": "lexsy_email_1",
                "thread_id": "lexsy_thread_001",
                "subject": "Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com",
                "recipient": "legal@lexsy.com",
                "date": "2025-07-22T09:00:00Z",
                "body": """Hi Kristina,

We'd like to bring on a new advisor for Lexsy, Inc.

• Name: John Smith
• Role: Strategic Advisor for AI/VC introductions  
• Proposed grant: 15,000 RSAs (restricted stock)
• Vesting: 2‑year vest, monthly, no cliff

Could you confirm if we have enough shares available under our Equity Incentive Plan (EIP) and prepare the necessary paperwork?

Thanks,
Alex""",
                "snippet": "We'd like to bring on a new advisor for Lexsy, Inc. Name: John Smith Role: Strategic Advisor..."
            },
            {
                "id": "lexsy_email_2", 
                "thread_id": "lexsy_thread_001",
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "legal@lexsy.com",
                "recipient": "alex@founderco.com",
                "date": "2025-07-22T14:30:00Z",
                "body": """Hi Alex,

Thanks for the details!

We can handle this. We will:

1. Check EIP availability to confirm 15,000 shares are free to grant.
2. Draft:
   • Advisor Agreement
   • Board Consent authorizing the grant
   • Stock Purchase Agreement (if RSAs)

Please confirm: Vesting starts at the effective date of the agreement, meaning whenever we prepare it—or should it start earlier?

Best,
Kristina""",
                "snippet": "Thanks for the details! We can handle this. We will: 1. Check EIP availability..."
            },
            {
                "id": "lexsy_email_3",
                "thread_id": "lexsy_thread_001", 
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com",
                "recipient": "legal@lexsy.com", 
                "date": "2025-07-23T10:15:00Z",
                "body": """Hi Kristina,

Thanks for the quick response. A few follow-ups:

1. Vesting start date: Let's make it effective from July 22, 2025 (retroactive to when we agreed)
2. Additional question: John mentioned he'd prefer equity over cash compensation. Is there any tax advantage for him with RSAs vs stock options?
3. Timeline: When can we have the paperwork ready? John wants to start making introductions next week.

Also, should we include any performance milestones or is the 2-year monthly vesting sufficient?

Best,
Alex""",
                "snippet": "Thanks for the quick response. A few follow-ups: 1. Vesting start date..."
            },
            {
                "id": "lexsy_email_4",
                "thread_id": "lexsy_thread_001",
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "legal@lexsy.com", 
                "recipient": "alex@founderco.com",
                "date": "2025-07-23T16:45:00Z",
                "body": """Hi Alex,

Great questions. Here's my analysis:

Tax Considerations:
• RSAs: John pays tax on fair market value when vesting occurs
• Stock Options: Only taxed when exercised  
• For early-stage company, RSAs might be better due to lower current valuation

Documentation Timeline:
• Board Consent: Can draft today
• Advisor Agreement: 1-2 days
• Stock Purchase Agreement: 1-2 days
• Total: Ready by Friday (July 25)

Performance Milestones:
Monthly vesting is standard. We could add milestones like "minimum 2 VC introductions per quarter" but that's typically in separate consulting agreement.

Let me know if you want to proceed with RSAs and July 22 effective date.

Best,
Kristina""",
                "snippet": "Great questions. Here's my analysis: Tax Considerations: RSAs: John pays tax..."
            },
            {
                "id": "lexsy_email_5",
                "thread_id": "lexsy_thread_001",
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com",
                "recipient": "legal@lexsy.com",
                "date": "2025-07-24T08:30:00Z", 
                "body": """Perfect! Let's proceed with:
• 15,000 RSAs for John Smith
• 2-year monthly vesting, no cliff
• Effective July 22, 2025
• Target completion: Friday July 25

Please prioritize the Board Consent - I can get that signed today.

Thanks!
Alex""",
                "snippet": "Perfect! Let's proceed with: 15,000 RSAs for John Smith 2-year monthly vesting..."
            }
        ]
    
    def _parse_message(self, message: Dict) -> Dict:
        """Parse Gmail API message into clean format"""
        try:
            headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
            
            # Extract body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data', '')
                        if data:
                            body = base64.urlsafe_b64decode(data).decode('utf-8')
                            break
            else:
                if message['payload']['mimeType'] == 'text/plain':
                    data = message['payload']['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
            
            return {
                "id": message['id'],
                "thread_id": message['threadId'], 
                "subject": headers.get('Subject', ''),
                "sender": headers.get('From', ''),
                "recipient": headers.get('To', ''),
                "date": headers.get('Date', ''),
                "body": body,
                "snippet": message.get('snippet', ''),
                "label_ids": message.get('labelIds', [])
            }
            
        except Exception as e:
            print(f"❌ Error parsing message: {e}")
            return {}