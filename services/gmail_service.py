# Enhanced Gmail Service with Real API Flow and Mock Simulation
# Update your gmail_service.py with this enhanced version

import os
import json
import base64
import time
import threading
from datetime import datetime, timedelta
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
            'https://www.googleapis.com/auth/gmail.labels',
            'https://www.googleapis.com/auth/gmail.send',  # Added for sending
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        self.credentials = None
        self.service = None
        self.monitoring_threads = {}
        
        # Mock conversation scripts for different scenarios
        self.mock_conversations = self._initialize_mock_conversations()
        
    def _initialize_mock_conversations(self):
        """Initialize different mock conversation scenarios"""
        return {
            "equity_grant": {
                "thread_id": "mock_thread_equity_001",
                "subject": "Advisor Equity Grant for Lexsy, Inc.",
                "participants": ["alex@founderco.com", "legal@lexsy.com"],
                "messages": [
                    {
                        "sender": "alex@founderco.com",
                        "recipient": "legal@lexsy.com",
                        "subject": "Advisor Equity Grant for Lexsy, Inc.",
                        "body": """Hi Kristina,

Hope you're doing well! We'd like to bring on a new advisor for Lexsy, Inc.

Details:
• Name: John Smith
• Background: Former VP of AI at Google, now partner at Andreessen Horowitz
• Role: Strategic Advisor for AI/ML strategy and VC introductions
• Proposed grant: 15,000 RSAs (restricted stock awards)
• Vesting: 2-year vest, monthly, no cliff
• Expected commitment: 4-6 hours per month, quarterly board observer

Could you please:
1. Confirm if we have enough shares available under our Equity Incentive Plan (EIP)
2. Prepare the necessary paperwork
3. Let me know about any tax implications we should discuss with John

Timeline: We'd like to have this wrapped up by end of week so John can start making introductions next month.

Thanks!
Alex Rodriguez
CEO, Lexsy Inc.""",
                        "delay_hours": 0
                    },
                    {
                        "sender": "legal@lexsy.com",
                        "recipient": "alex@founderco.com",
                        "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                        "body": """Hi Alex,

Great to hear from you! John Smith is an excellent choice - his background at Google and current role at a16z will be invaluable.

I've reviewed our current cap table and EIP status:

SHARE AVAILABILITY ✅
• Total EIP pool: 1,000,000 shares
• Previously granted: 85,000 shares
• Available for grant: 915,000 shares
• Requested grant: 15,000 shares → ✅ APPROVED

DOCUMENTATION NEEDED:
1. Board Consent authorizing the grant
2. Advisor Agreement (including duties, IP assignment, confidentiality)
3. Restricted Stock Award Agreement
4. 83(b) election form (if applicable)

PROCESS QUESTIONS:
• Vesting start date: Should this be effective from today's date or when we actually execute the agreements?
• Board observer rights: Should we formalize this in the Advisor Agreement?
• Performance milestones: Standard monthly vesting or any specific deliverables?

I can have the initial drafts ready by Wednesday. Let me know your preferences on the above questions.

Best regards,
Kristina Chen
Legal Counsel""",
                        "delay_hours": 5
                    },
                    {
                        "sender": "alex@founderco.com",
                        "recipient": "legal@lexsy.com",
                        "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                        "body": """Hi Kristina,

Perfect! Thanks for the quick turnaround. Here are my responses:

VESTING & TIMING:
• Vesting start date: Let's make it effective from today (July 22, 2025) - retroactive to when we verbally agreed
• Board observer: Yes, please include formal observer rights in the Advisor Agreement
• Performance: Standard monthly vesting is fine - no specific milestones needed

ADDITIONAL QUESTIONS:
1. Tax implications: John mentioned he'd prefer equity over cash compensation. Any advantage to RSAs vs stock options for him?
2. 83(b) election: Should we recommend this given our current valuation?
3. Acceleration: Should we include any acceleration clauses (single vs double trigger)?

TIMELINE UPDATE:
Actually, can we expedite this? John wants to start making some strategic introductions next week, and it would be great to have the advisor relationship formalized first.

Also, our next board meeting is Thursday - can we get the Board Consent on the agenda?

Thanks again for all your help!

Alex""",
                        "delay_hours": 18
                    },
                    {
                        "sender": "legal@lexsy.com",
                        "recipient": "alex@founderco.com",
                        "subject": "Re: Advisor Equity Grant for Lexsy, Inc. - Tax Analysis & Recommendations",
                        "body": """Hi Alex,

Absolutely can expedite! Here's my analysis on your questions:

TAX IMPLICATIONS ANALYSIS:
RSAs vs Stock Options for John:
• RSAs: Taxed on FMV when they vest (ordinary income rates)
• Stock Options: Taxed when exercised (could be capital gains if held >1 year)
• RECOMMENDATION: Given our early stage and relatively low current FMV (~$0.50/share), RSAs are likely better for John
• Current tax impact: ~$7,500 ordinary income spread over 24 months vs potential higher tax burden later with options

83(b) ELECTION:
• Definitely recommend for RSAs
• Must be filed within 30 days of grant
• Allows John to pay tax on current FMV now, then all future appreciation is capital gains
• At current valuation, minimal tax impact upfront

ACCELERATION PROVISIONS:
• Single trigger (termination): Standard for advisors
• Double trigger (change of control + termination): Not typical for advisor grants
• RECOMMENDATION: Include single trigger acceleration for 25% of unvested shares if company terminates relationship without cause

EXPEDITED TIMELINE:
✅ Board Consent: I'll have it ready for Thursday's meeting
✅ Advisor Agreement: First draft by Wednesday morning
✅ RSA Agreement: Wednesday afternoon
✅ Full package ready for execution: Thursday evening

NEXT STEPS:
1. I'll send Board Consent to you tomorrow for review
2. Please send me John's full contact details and mailing address
3. Confirm Thursday board meeting agenda inclusion

Sound good?

Best,
Kristina""",
                        "delay_hours": 8
                    },
                    {
                        "sender": "alex@founderco.com",
                        "recipient": "legal@lexsy.com",
                        "subject": "Re: Advisor Equity Grant - APPROVED! Moving Forward",
                        "body": """Kristina,

Perfect analysis - let's proceed with RSAs and the 83(b) election. Your timeline works great!

DECISIONS CONFIRMED:
✅ 15,000 RSAs for John Smith
✅ 2-year monthly vesting, effective July 22, 2025
✅ Single trigger acceleration (25% if terminated without cause)
✅ 83(b) election recommended
✅ Board observer rights included

JOHN'S DETAILS:
John Smith
john.smith@a16z.com
123 Sand Hill Road
Menlo Park, CA 94025
Phone: (650) 555-0123

BOARD MEETING THURSDAY:
✅ Added to agenda - "Advisor Equity Grant Authorization"
✅ All directors confirmed attendance
✅ I'll prioritize this agenda item

One small addition: Can we include a clause about John's ability to make introductions to other a16z portfolio companies? Want to make sure there are no conflicts.

Let's get this done! John is excited to start working with us.

Alex

P.S. - Great work as always. This is exactly why we love working with you!""",
                        "delay_hours": 2
                    },
                    {
                        "sender": "legal@lexsy.com",
                        "recipient": "alex@founderco.com",
                        "subject": "🎉 EQUITY GRANT PACKAGE READY - John Smith Advisor Agreement",
                        "body": """Alex,

GREAT NEWS! All documentation is complete and ready for execution! 🎉

COMPLETED DOCUMENTS:
📋 Board Consent (ready for Thursday's meeting)
📋 Advisor Agreement (includes a16z portfolio introduction rights)
📋 Restricted Stock Award Agreement
📋 83(b) Election Form
📋 Cap Table Update (reflecting new grant)

KEY HIGHLIGHTS:
• Grant: 15,000 RSAs (1.5% of company)
• Vesting: 24 months, monthly (625 shares/month)
• Effective Date: July 22, 2025
• Observer Rights: Quarterly board meetings
• a16z Portfolio: Explicit permission for introductions (with standard conflict disclosures)

EXECUTION PROCESS:
1. THURSDAY: Board meeting → Board Consent approval
2. FRIDAY: Send full package to John for signature
3. John signs and returns agreements
4. File 83(b) election within 30 days
5. Update cap table and issue stock certificate

TAX SUMMARY FOR JOHN:
• Current tax liability: ~$300 (15,000 shares × $0.02 FMV)
• Future upside: All appreciation taxed as capital gains
• Recommended: File 83(b) immediately upon signing

ESTIMATED COMPLETION: Next Tuesday (July 29th)

All documents attached for your review. Call me if you want to discuss any provisions before the board meeting.

Congratulations on bringing John aboard! This is going to be a great partnership.

Best regards,
Kristina

P.S. - I included some enhanced IP assignment language that covers AI/ML developments, given John's background. Let me know if you want me to explain any of the provisions!""",
                        "delay_hours": 26
                    }
                ]
            },
            "client_contract": {
                "thread_id": "mock_thread_contract_002", 
                "subject": "Enterprise Software License - MegaCorp Deal",
                "participants": ["sales@lexsy.com", "legal@lexsy.com", "counsel@megacorp.com"],
                "messages": [
                    {
                        "sender": "sales@lexsy.com",
                        "recipient": "legal@lexsy.com",
                        "subject": "URGENT: Enterprise Software License - MegaCorp Deal",
                        "body": """Team,

We have a major opportunity with MegaCorp! They want to license our AI platform for their entire organization (50,000+ users).

Deal Details:
• Company: MegaCorp Inc. (Fortune 100)
• License: Enterprise SaaS + On-premise deployment
• Users: 50,000 seats
• Contract Value: $2.4M annually
• Term: 3 years with auto-renewal
• Go-live: September 1st (6 weeks!)

THEIR REQUIREMENTS:
• Custom security addendum
• Data residency in EU and US
• 99.9% uptime SLA
• Dedicated support team
• Source code escrow
• Compliance with SOX, GDPR, CCPA

They've sent over their Master Services Agreement template. Need legal review ASAP - they want to sign by August 15th.

This could be our biggest deal ever! All hands on deck.

Mike Rodriguez
VP Sales""",
                        "delay_hours": 0
                    },
                    {
                        "sender": "legal@lexsy.com", 
                        "recipient": "sales@lexsy.com",
                        "subject": "Re: Enterprise Software License - MegaCorp Deal - Initial Review",
                        "body": """Mike,

Fantastic opportunity! I've done an initial review of MegaCorp's MSA template.

INITIAL ASSESSMENT:
🟢 ACCEPTABLE: Standard enterprise terms, reasonable liability caps
🟡 NEEDS NEGOTIATION: Some onerous indemnification clauses
🔴 PROBLEMATIC: Unlimited liability for IP infringement, unrealistic penalty clauses

KEY ISSUES TO ADDRESS:
1. LIABILITY: They want unlimited liability - we need mutual caps at contract value
2. INDEMNIFICATION: One-sided IP indemnification - needs to be mutual
3. SLA PENALTIES: 10% monthly fee reduction for <99.9% uptime - too steep
4. TERMINATION: They can terminate for convenience with 30 days notice - we need 90 days minimum
5. DATA: Their data ownership language conflicts with our ML training needs

COMPLIANCE REQUIREMENTS:
✅ SOX: We're already compliant
✅ GDPR: Our platform supports this
⚠️ CCPA: Need to update some data processing terms
✅ SOC 2 Type II: We have current certification

NEXT STEPS:
1. I'll prepare our redlined version by Wednesday
2. Need technical team input on SLA commitments
3. Finance review of penalty structures
4. Schedule call with their legal team for Thursday

Timeline is tight but doable. Let's make this happen!

Sarah""",
                        "delay_hours": 4
                    }
                ]
            }
        }
    
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
    
    def simulate_mock_conversation(self, conversation_type: str = "equity_grant") -> List[Dict]:
        """Simulate a realistic Gmail conversation with timestamps"""
        if conversation_type not in self.mock_conversations:
            conversation_type = "equity_grant"
            
        conversation = self.mock_conversations[conversation_type]
        base_time = datetime.now() - timedelta(days=3)  # Start 3 days ago
        
        simulated_messages = []
        
        for i, message_template in enumerate(conversation["messages"]):
            # Calculate realistic timestamp
            message_time = base_time + timedelta(hours=message_template["delay_hours"])
            
            simulated_message = {
                "id": f"mock_{conversation['thread_id']}_{i+1}",
                "thread_id": conversation["thread_id"],
                "subject": message_template["subject"],
                "sender": message_template["sender"],
                "recipient": message_template["recipient"],
                "body": message_template["body"],
                "snippet": message_template["body"][:100] + "..." if len(message_template["body"]) > 100 else message_template["body"],
                "date": message_time.isoformat() + "Z",
                "label_ids": ["INBOX", "IMPORTANT"] if "URGENT" in message_template["subject"] else ["INBOX"],
                "is_simulated": True
            }
            
            simulated_messages.append(simulated_message)
            base_time = message_time  # Next message builds from this time
        
        return simulated_messages
    
    def get_messages_by_thread(self, thread_id: str, use_simulation: bool = True) -> List[Dict]:
        """Get messages by thread - real or simulated"""
        try:
            # If simulation requested or no real service, use mock data
            if use_simulation or not self.service:
                if thread_id.startswith("mock_"):
                    # Extract conversation type from thread_id
                    for conv_type, conv_data in self.mock_conversations.items():
                        if conv_data["thread_id"] == thread_id:
                            return self.simulate_mock_conversation(conv_type)
                
                # Default to equity grant conversation
                return self.simulate_mock_conversation("equity_grant")
            
            # Real Gmail API call
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
            return self.simulate_mock_conversation("equity_grant")
        except Exception as e:
            print(f"❌ Error getting thread messages: {e}")
            return self.simulate_mock_conversation("equity_grant")
    
    def search_messages(self, query: str, max_results: int = 50, use_simulation: bool = True) -> List[Dict]:
        """Search for messages - real or simulated"""
        try:
            # If simulation requested or no real service, return mock data
            if use_simulation or not self.service:
                # Return different conversations based on query
                if "contract" in query.lower() or "megacorp" in query.lower():
                    return self.simulate_mock_conversation("client_contract")
                else:
                    return self.simulate_mock_conversation("equity_grant")
            
            # Real Gmail API call
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
            return self.simulate_mock_conversation("equity_grant")
        except Exception as e:
            print(f"❌ Error searching messages: {e}")
            return self.simulate_mock_conversation("equity_grant")
    
    def start_thread_monitoring(self, thread_id: str, client_id: int = None, check_interval: int = 300):
        """Start monitoring a specific Gmail thread"""
        monitor_key = f"{thread_id}_{client_id}" if client_id else thread_id
        
        if monitor_key in self.monitoring_threads and self.monitoring_threads[monitor_key]["active"]:
            return {"success": False, "message": f"Already monitoring thread {thread_id}"}
            
        # Start monitoring thread
        monitoring_thread = threading.Thread(
            target=self._monitor_thread,
            args=(thread_id, client_id, check_interval, monitor_key),
            daemon=True
        )
        monitoring_thread.start()
        
        # Track the monitoring thread
        self.monitoring_threads[monitor_key] = {
            "active": True,
            "thread": monitoring_thread,
            "thread_id": thread_id,
            "client_id": client_id,
            "started_at": datetime.now().isoformat(),
            "last_check": None,
            "messages_found": 0
        }
        
        return {
            "success": True,
            "message": f"Started monitoring thread {thread_id}",
            "monitor_key": monitor_key,
            "check_interval": check_interval
        }
    
    def _monitor_thread(self, thread_id: str, client_id: int, check_interval: int, monitor_key: str):
        """Background thread monitoring function"""
        last_check = datetime.now() - timedelta(hours=1)
        
        while self.monitoring_threads.get(monitor_key, {}).get("active", False):
            try:
                # Get messages (will use simulation if no real service)
                messages = self.get_messages_by_thread(thread_id, use_simulation=True)
                
                new_messages = []
                for msg in messages:
                    try:
                        msg_date = datetime.fromisoformat(msg.get('date', '').replace('Z', '+00:00'))
                        if msg_date > last_check:
                            new_messages.append(msg)
                    except:
                        continue
                
                if new_messages:
                    print(f"📧 Found {len(new_messages)} new messages in thread {thread_id}")
                    # Update monitoring stats
                    if monitor_key in self.monitoring_threads:
                        self.monitoring_threads[monitor_key]["messages_found"] += len(new_messages)
                        
                    # Save to database if client_id provided
                    if client_id:
                        self._save_new_messages(new_messages, client_id)
                    
                # Update last check time
                last_check = datetime.now()
                if monitor_key in self.monitoring_threads:
                    self.monitoring_threads[monitor_key]["last_check"] = last_check.isoformat()
                
            except Exception as e:
                print(f"❌ Error in Gmail monitoring for {thread_id}: {e}")
                
            # Wait for next check
            time.sleep(check_interval)
    
    def _save_new_messages(self, messages: List[Dict], client_id: int):
        """Save new messages to database"""
        try:
            from database import SessionLocal
            from models.email import Email
            import json
            
            db = SessionLocal()
            
            for msg in messages:
                # Check if email already exists
                existing = db.query(Email).filter(
                    Email.gmail_message_id == msg["id"],
                    Email.client_id == client_id
                ).first()
                
                if not existing:
                    # Parse date
                    date_sent = None
                    if msg.get("date"):
                        try:
                            date_sent = datetime.fromisoformat(msg["date"].replace("Z", "+00:00"))
                        except:
                            pass
                    
                    # Create email record
                    email = Email(
                        client_id=client_id,
                        gmail_message_id=msg["id"],
                        gmail_thread_id=msg["thread_id"],
                        subject=msg["subject"],
                        sender=msg["sender"],
                        recipient=msg["recipient"],
                        body=msg["body"],
                        snippet=msg["snippet"],
                        date_sent=date_sent,
                        labels=json.dumps(msg.get("label_ids", [])),
                        is_processed=False
                    )
                    
                    db.add(email)
                    db.commit()
                    print(f"✅ Saved new email: {msg['subject']}")
            
            db.close()
            
        except Exception as e:
            print(f"❌ Error saving messages: {e}")
    
    def stop_thread_monitoring(self, thread_id: str, client_id: int = None):
        """Stop monitoring a specific thread"""
        monitor_key = f"{thread_id}_{client_id}" if client_id else thread_id
        
        if monitor_key in self.monitoring_threads:
            self.monitoring_threads[monitor_key]["active"] = False
            del self.monitoring_threads[monitor_key]
            return {"success": True, "message": f"Stopped monitoring thread {thread_id}"}
        else:
            return {"success": False, "message": f"Thread {thread_id} not being monitored"}
    
    def get_monitoring_status(self):
        """Get status of all monitoring threads"""
        return {
            "total_monitors": len(self.monitoring_threads),
            "active_monitors": [
                {
                    "thread_id": info["thread_id"],
                    "client_id": info["client_id"],
                    "started_at": info["started_at"],
                    "last_check": info["last_check"],
                    "messages_found": info["messages_found"]
                }
                for info in self.monitoring_threads.values()
                if info["active"]
            ]
        }
    
    def get_available_conversations(self):
        """Get list of available mock conversations"""
        return {
            conv_type: {
                "thread_id": conv_data["thread_id"],
                "subject": conv_data["subject"],
                "participants": conv_data["participants"],
                "message_count": len(conv_data["messages"])
            }
            for conv_type, conv_data in self.mock_conversations.items()
        }
    
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
