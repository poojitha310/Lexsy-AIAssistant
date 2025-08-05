from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends, Request, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

# Import your existing services (with fallback for deployment)
try:
    from config import settings
    from database import init_db, get_db, SessionLocal
    from models.client import Client
    from models.document import Document
    from models.email import Email
    from models.conversation import Conversation
    from services.document_service import DocumentService
    from services.vector_service import VectorService
    from services.ai_service import AIService
    from services.gmail_service import GmailService
    FULL_FEATURES = True
    print("✅ Full features available")
except ImportError as e:
    print(f"⚠️ Limited features mode: {e}")
    FULL_FEATURES = False
    
    # Fallback minimal setup
    class Settings:
        UPLOAD_DIR = "./uploads"
        CHROMADB_PATH = "./chromadb"
        MAX_FILE_SIZE = 10 * 1024 * 1024
        GOOGLE_CLIENT_ID = None
        GOOGLE_CLIENT_SECRET = None
    settings = Settings()
    
    def get_db():
        yield None

# Create FastAPI app
app = FastAPI(
    title="AI Legal Assistant - Production",
    description="Real-time document and email analysis for legal professionals",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatRequest(BaseModel):
    question: str
    user_context: dict

class ChatResponse(BaseModel):
    success: bool
    answer: str
    sources: List[dict] = []
    response_time: float = 0.0

class UserAuth(BaseModel):
    name: str
    email: str
    org: str

class MonitoringRequest(BaseModel):
    label: str = "INBOX"
    thread_id: Optional[str] = None

# In-memory user sessions (in production, use Redis or database)
user_sessions = {}

# Global Gmail service instance
if FULL_FEATURES:
    gmail_service = GmailService()
else:
    gmail_service = None

def get_user_id(email: str) -> str:
    """Generate consistent user ID from email"""
    return hashlib.md5(email.encode()).hexdigest()

def get_current_user(x_user_email: str = Header(...), x_user_name: str = Header(...)):
    """Get current user from headers"""
    if not x_user_email:
        raise HTTPException(status_code=401, detail="User authentication required")
    
    user_id = get_user_id(x_user_email)
    
    # Store/update user session
    user_sessions[user_id] = {
        "email": x_user_email,
        "name": x_user_name,
        "last_active": datetime.now().isoformat()
    }
    
    return {
        "id": user_id,
        "email": x_user_email,
        "name": x_user_name
    }

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    print("🚀 Starting AI Legal Assistant (Production Mode)")
    
    # Create directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMADB_PATH, exist_ok=True)
    
    if FULL_FEATURES:
        try:
            init_db()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")

# Serve the main application
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the real-time AI Assistant interface"""
    try:
        if os.path.exists("index.html"):
            with open("index.html", 'r', encoding='utf-8') as file:
                return HTMLResponse(content=file.read())
    except Exception as e:
        print(f"Could not load index.html: {e}")
    
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>AI Legal Assistant</title></head>
    <body>
        <h1>AI Legal Assistant</h1>
        <p>Production deployment ready</p>
        <p>Please ensure index.html is in the root directory</p>
    </body>
    </html>
    """)

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-legal-assistant",
        "mode": "production",
        "features": FULL_FEATURES,
        "active_users": len(user_sessions)
    }

@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    google_configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    
    return {
        "api_version": "1.0.0",
        "status": "operational",
        "services": {
            "database": "SQLite",
            "vector_store": "ChromaDB",
            "ai_model": "gpt-4",
            "embedding_model": "text-embedding-3-small"
        },
        "features": {
            "openai_integration": openai_configured,
            "gmail_integration": google_configured,
            "document_upload": True,
            "multi_client_support": True,
            "full_features": FULL_FEATURES,
            "services_available": FULL_FEATURES
        },
        "configuration": {
            "openai_api_key": "✅ Configured" if openai_configured else "❌ Missing",
            "google_oauth": "✅ Configured" if google_configured else "❌ Missing (Demo Mode Available)",
            "environment": "production" if not os.getenv("DEBUG") else "development"
        },
        "active_users": len(user_sessions),
        "timestamp": datetime.now().isoformat()
    }

# Client management endpoints
@app.get("/api/clients")
async def list_clients():
    """List all available clients"""
    if not FULL_FEATURES:
        return {
            "success": True,
            "clients": [
                {
                    "id": 1,
                    "name": "Lexsy, Inc.",
                    "email": "legal@lexsy.com",
                    "company": "Lexsy, Inc.",
                    "description": "AI-powered legal technology startup"
                },
                {
                    "id": 2,
                    "name": "TechCorp LLC",
                    "email": "counsel@techcorp.com", 
                    "company": "TechCorp LLC",
                    "description": "Enterprise software company"
                }
            ]
        }
    
    try:
        db = SessionLocal()
        clients = db.query(Client).filter(Client.is_active == True).all()
        db.close()
        
        return {
            "success": True,
            "clients": [client.to_dict() for client in clients]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "clients": []
        }

@app.post("/api/clients")
async def create_client(
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(...),
    description: str = Form(...)
):
    """Create a new client"""
    if not FULL_FEATURES:
        return {
            "success": True,
            "client": {
                "id": 3,
                "name": name,
                "email": email,
                "company": company,
                "description": description
            }
        }
    
    try:
        db = SessionLocal()
        
        # Check if client already exists
        existing = db.query(Client).filter(Client.email == email).first()
        if existing:
            db.close()
            return {"success": False, "error": "Client with this email already exists"}
        
        # Create new client
        client = Client(
            name=name,
            email=email,
            company=company,
            description=description
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        db.close()
        
        return {
            "success": True,
            "client": client.to_dict()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/clients/{client_id}")
async def get_client(client_id: int):
    """Get specific client details"""
    if not FULL_FEATURES:
        demo_clients = {
            1: {"id": 1, "name": "Lexsy, Inc.", "email": "legal@lexsy.com", "company": "Lexsy, Inc."},
            2: {"id": 2, "name": "TechCorp LLC", "email": "counsel@techcorp.com", "company": "TechCorp LLC"}
        }
        return {"success": True, "client": demo_clients.get(client_id)}
    
    try:
        db = SessionLocal()
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        db.close()
        
        if not client:
            return {"success": False, "error": "Client not found"}
        
        return {"success": True, "client": client.to_dict()}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Document upload endpoint
@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_id: int = Form(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Upload and process a document for specific client"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        valid_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
        if file.content_type not in valid_types:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT")
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max size is 10MB")
        
        if not FULL_FEATURES:
            # Demo mode response
            return {
                "success": True,
                "message": f"File uploaded successfully for client {client_id} (demo mode)",
                "document": {
                    "id": str(uuid.uuid4()),
                    "filename": file.filename,
                    "client_id": client_id,
                    "processing_status": "completed"
                }
            }
        
        # Use client_id if provided, otherwise get from user
        if client_id:
            target_client_id = client_id
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
        else:
            # Get or create client for this user
            client = db.query(Client).filter(Client.email == user["email"]).first()
            if not client:
                client = Client(
                    name=user["name"],
                    email=user["email"],
                    company=user.get("org", "Individual"),
                    description=f"Individual user: {user['name']}"
                )
                db.add(client)
                db.commit()
                db.refresh(client)
            target_client_id = client.id
        
        # Initialize services
        doc_service = DocumentService()
        vector_service = VectorService()
        
        # Save file
        save_result = await doc_service.save_uploaded_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type
        )
        
        if not save_result["success"]:
            raise HTTPException(status_code=400, detail=save_result["error"])
        
        # Create document record
        document = Document(
            client_id=target_client_id,
            filename=save_result["filename"],
            original_filename=save_result["original_filename"],
            file_type=save_result["file_type"],
            file_size=save_result["file_size"],
            file_path=save_result["file_path"],
            processing_status="processing"
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Extract text and add to vector store
        try:
            extraction_result = doc_service.extract_text_from_file(
                file_path=save_result["file_path"],
                file_type=save_result["file_type"]
            )
            
            if extraction_result["success"]:
                document.extracted_text = extraction_result["text"]
                
                # Add to vector store with user context
                chunk_ids = vector_service.add_document_to_vector_store(
                    client_id=target_client_id,
                    document_id=document.id,
                    text=extraction_result["text"],
                    metadata={
                        "filename": document.original_filename,
                        "file_type": document.file_type,
                        "user_email": user["email"],
                        "uploaded_at": document.created_at.isoformat()
                    }
                )
                
                if chunk_ids:
                    document.chunk_ids = json.dumps(chunk_ids)
                    document.processing_status = "completed"
                else:
                    document.processing_status = "failed"
            else:
                document.processing_status = "failed"
                
            db.commit()
            
        except Exception as e:
            document.processing_status = "failed"
            db.commit()
            print(f"Processing error: {e}")
        
        return {
            "success": True,
            "message": "Document uploaded and processed successfully",
            "document": document.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# Get user's documents
@app.get("/api/documents/list")
async def list_documents(
    client_id: int = Query(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get documents for specific client"""
    try:
        if not FULL_FEATURES:
            if client_id == 1:
                return {
                    "documents": [
                        {"id": 1, "filename": "lexsy-board-approval.pdf", "original_filename": "Lexsy Board Approval.pdf", "client_id": 1, "processing_status": "completed", "file_type": "pdf", "file_size": 245760},
                        {"id": 2, "filename": "lexsy-advisor-agreement.docx", "original_filename": "Lexsy Advisor Agreement.docx", "client_id": 1, "processing_status": "completed", "file_type": "docx", "file_size": 87320},
                        {"id": 3, "filename": "lexsy-equity-plan.pdf", "original_filename": "Lexsy Equity Plan.pdf", "client_id": 1, "processing_status": "completed", "file_type": "pdf", "file_size": 156890}
                    ]
                }
            else:
                return {"documents": []}
        
        if client_id:
            # Get documents for specific client
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                return {"documents": []}
            documents = db.query(Document).filter(Document.client_id == client_id).all()
        else:
            # Get documents for current user's client
            client = db.query(Client).filter(Client.email == user["email"]).first()
            if not client:
                return {"documents": []}
            documents = db.query(Document).filter(Document.client_id == client.id).all()
        
        return {
            "documents": [doc.to_dict() for doc in documents],
            "total": len(documents)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get user's emails
@app.get("/api/emails/list")
async def list_emails(
    client_id: int = Query(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get emails for specific client"""
    try:
        if not FULL_FEATURES:
            if client_id == 1:
                # Return Lexsy sample emails using Gmail service
                if gmail_service:
                    sample_emails = gmail_service.simulate_mock_conversation("equity_grant")
                else:
                    sample_emails = []
                return {"emails": sample_emails}
            else:
                return {"emails": []}
        
        if client_id:
            # Get emails for specific client
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                return {"emails": []}
            emails = db.query(Email).filter(Email.client_id == client_id).all()
        else:
            # Get emails for current user's client
            client = db.query(Client).filter(Client.email == user["email"]).first()
            if not client:
                return {"emails": []}
            emails = db.query(Email).filter(Email.client_id == client.id).all()
        
        return {
            "emails": [email.to_dict() for email in emails],
            "total": len(emails)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# AI Chat endpoint
@app.post("/api/chat/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    client_id: int = Form(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Ask a question against user's documents and emails"""
    try:
        if not FULL_FEATURES:
            # Demo responses based on client
            question_lower = request.question.lower()
            
            if client_id == 1:  # Lexsy responses
                if "john smith" in question_lower or "equity" in question_lower:
                    answer = "Based on the email thread, Alex proposed a 15,000 RSA equity grant for John Smith as Strategic Advisor with 2-year monthly vesting and no cliff. The legal team confirmed they can prepare the necessary documentation including Board Consent, Advisor Agreement, and Stock Purchase Agreement."
                elif "vesting" in question_lower:
                    answer = "The vesting terms discussed are 2-year monthly vesting with no cliff, effective from July 22, 2025. This means 625 shares vest each month (15,000 ÷ 24 months). The legal team confirmed this is standard for advisor agreements."
                elif "tax" in question_lower:
                    answer = "Kristina explained that with RSAs, John pays tax on fair market value when vesting occurs, while stock options are only taxed when exercised. For an early-stage company like Lexsy, RSAs might be better due to lower current valuation (~$0.50/share). She also recommended filing an 83(b) election."
                elif "documentation" in question_lower or "paperwork" in question_lower:
                    answer = "The legal team needs to prepare: 1) Board Consent authorizing the grant, 2) Advisor Agreement (including board observer rights), 3) Stock Purchase Agreement, and 4) 83(b) election form. Timeline is ready by Friday July 25th, with Board Consent prioritized first for Thursday's board meeting."
                elif "shares" in question_lower and "available" in question_lower:
                    answer = "According to the legal team's analysis, Lexsy has 1,000,000 total shares in the EIP pool with 85,000 previously granted, leaving 915,000 shares available. The requested 15,000 shares for John Smith is well within the available pool."
                else:
                    answer = "I can help analyze Lexsy's legal documents and email discussions about advisor equity grants. Ask me about John Smith's grant, vesting terms, tax implications, required documentation, or share availability."
            else:  # TechCorp or other clients
                answer = "I don't see any documents or emails for this client yet. Please upload documents or connect Gmail to start analysis, or try switching to the Lexsy client which has sample data loaded."
            
            return ChatResponse(
                success=True,
                answer=answer,
                sources=[{"type": "demo", "content": "Sample response"}],
                response_time=0.5
            )
        
        # Use client_id if provided, otherwise get from user
        if client_id:
            target_client_id = client_id
        else:
            client = db.query(Client).filter(Client.email == user["email"]).first()
            if not client:
                client = Client(
                    name=user["name"],
                    email=user["email"],
                    company=request.user_context.get("org", "Individual"),
                    description=f"Individual user: {user['name']}"
                )
                db.add(client)
                db.commit()
                db.refresh(client)
            target_client_id = client.id
        
        # Initialize AI service
        ai_service = AIService()
        
        # Generate AI response using user's specific context
        response = ai_service.generate_response(
            client_id=target_client_id,
            question=request.question,
            conversation_history=None
        )
        
        if response["success"]:
            # Save conversation
            conversation = Conversation(
                client_id=target_client_id,
                question=request.question,
                answer=response["answer"],
                response_time=response["response_time"],
                tokens_used=response.get("tokens_used", 0)
            )
            db.add(conversation)
            db.commit()
            
            return ChatResponse(
                success=True,
                answer=response["answer"],
                sources=response.get("sources", []),
                response_time=response["response_time"]
            )
        else:
            raise HTTPException(status_code=500, detail="AI processing failed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(e)}")

# Gmail OAuth endpoints
@app.get("/api/auth/gmail/auth-url")
async def get_gmail_auth_url(user = Depends(get_current_user)):
    """Get Gmail OAuth URL for user"""
    try:
        # Check if we have Google OAuth credentials configured
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            return {
                "success": True,
                "auth_url": "#demo",
                "message": "Demo mode - Gmail integration simulated",
                "demo_mode": True
            }
        
        if not FULL_FEATURES or not gmail_service:
            return {
                "success": True,
                "auth_url": "#demo",
                "message": "Demo mode - Gmail integration simulated",
                "demo_mode": True
            }
        
        auth_url = gmail_service.get_auth_url()
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Gmail OAuth URL generated"
        }
        
    except Exception as e:
        return {
            "success": True,
            "auth_url": "#demo",
            "message": "Demo mode - Gmail integration simulated",
            "demo_mode": True
        }

@app.get("/api/auth/gmail/callback")
async def gmail_callback(code: str = Query(None), error: str = Query(None)):
    """Handle Gmail OAuth callback"""
    try:
        if error:
            return HTMLResponse(content=f"""
            <html>
            <body>
                <h2>❌ Gmail Authentication Error</h2>
                <p>Error: {error}</p>
                <script>
                    setTimeout(() => {{
                        window.close();
                    }}, 3000);
                </script>
            </body>
            </html>
            """)
        
        # Demo mode for immediate success
        return HTMLResponse(content="""
        <html>
        <body>
            <h2>✅ Gmail Connected Successfully!</h2>
            <p>OAuth authentication completed (demo mode)</p>
            <p>Mock conversations are now available for analysis.</p>
            <p>You can close this window and return to the app.</p>
            <script>
                // Notify parent window of success
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'GMAIL_AUTH_SUCCESS',
                        email: 'demo@gmail.com'
                    }, '*');
                }
                
                setTimeout(() => {
                    window.close();
                }, 2000);
            </script>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <html>
        <body>
            <h2>❌ Authentication Error</h2>
            <p>Error: {str(e)}</p>
            <script>
                setTimeout(() => {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """)

# Gmail monitoring endpoints
@app.post("/api/emails/start-thread-monitoring")
async def start_thread_monitoring(
    thread_id: str = Form("mock_thread_equity_001"),
    client_id: int = Form(None),
    check_interval: int = Form(300),
    user = Depends(get_current_user)
):
    """Start monitoring a specific Gmail thread"""
    try:
        if not FULL_FEATURES or not gmail_service:
            return {
                "success": True,
                "message": f"Started monitoring thread {thread_id} (demo mode)",
                "monitoring": {
                    "thread_id": thread_id,
                    "client_id": client_id or 1,
                    "check_interval": check_interval,
                    "status": "active",
                    "demo_mode": True
                }
            }
        
        # Use provided client_id or default to 1
        if not client_id:
            client_id = 1
        
        result = gmail_service.start_thread_monitoring(thread_id, client_id, check_interval)
        
        if result["success"]:
            result["monitoring"] = {
                "thread_id": thread_id,
                "client_id": client_id,
                "check_interval": check_interval,
                "status": "active",
                "started_at": datetime.now().isoformat()
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@app.get("/api/emails/monitoring-status")
async def get_monitoring_status(user = Depends(get_current_user)):
    """Get Gmail monitoring status"""
    try:
        if not FULL_FEATURES or not gmail_service:
            return {
                "total_monitors": 1,
                "active_monitors": [
                    {
                        "thread_id": "mock_thread_equity_001",
                        "client_id": 1,
                        "started_at": datetime.now().isoformat(),
                        "last_check": datetime.now().isoformat(),
                        "messages_found": 6,
                        "demo_mode": True
                    }
                ]
            }
        
        status = gmail_service.get_monitoring_status()
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring status: {str(e)}")

# Demo data loading
@app.post("/api/demo/load-sample")
async def load_sample_data(
    client_id: int = Form(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Load sample legal documents and emails for demo"""
    try:
        # Default to client_id 1 if not provided
        if not client_id:
            client_id = 1
            
        if not FULL_FEATURES:
            return {
                "success": True,
                "message": "Sample data loaded (demo mode)",
                "client_id": client_id,
                "client_name": "Lexsy, Inc.",
                "documents_loaded": 3,
                "emails_loaded": 6,
                "monitoring_started": True
            }
        
        # Get or create client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            # Create Lexsy client
            client = Client(
                name="Lexsy, Inc.",
                email="legal@lexsy.com",
                company="Lexsy, Inc.",
                description="AI-powered legal technology startup"
            )
            db.add(client)
            db.commit()
            db.refresh(client)
            client_id = client.id
        
        # Initialize services
        doc_service = DocumentService()
        vector_service = VectorService()
        
        documents_loaded = 0
        emails_loaded = 0
        
        # Load sample documents
        try:
            sample_docs = doc_service.get_sample_documents()
            
            for sample_doc in sample_docs:
                # Check if already exists
                existing = db.query(Document).filter(
                    Document.client_id == client_id,
                    Document.original_filename == sample_doc["original_filename"]
                ).first()
                
                if existing:
                    continue
                
                # Create document
                document = Document(
                    client_id=client_id,
                    filename=sample_doc["filename"],
                    original_filename=sample_doc["original_filename"],
                    file_type=sample_doc["file_type"],
                    file_size=len(sample_doc["content"]),
                    extracted_text=sample_doc["content"],
                    processing_status="completed"
                )
                
                db.add(document)
                db.commit()
                db.refresh(document)
                
                # Add to vector store
                chunk_ids = vector_service.add_document_to_vector_store(
                    client_id=client_id,
                    document_id=document.id,
                    text=sample_doc["content"],
                    metadata={
                        "filename": document.original_filename,
                        "file_type": document.file_type,
                        "user_email": user["email"],
                        "sample_document": True
                    }
                )
                
                if chunk_ids:
                    document.chunk_ids = json.dumps(chunk_ids)
                    db.commit()
                
                documents_loaded += 1
        
        except Exception as e:
            print(f"Error loading sample documents: {e}")
        
        # Load sample emails
        try:
            if gmail_service:
                sample_emails = gmail_service.simulate_mock_conversation("equity_grant")
                
                for email_data in sample_emails:
                    # Check if already exists
                    existing = db.query(Email).filter(
                        Email.gmail_message_id == email_data["id"],
                        Email.client_id == client_id
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Create email
                    email = Email(
                        client_id=client_id,
                        gmail_message_id=email_data["id"],
                        gmail_thread_id=email_data["thread_id"],
                        subject=email_data["subject"],
                        sender=email_data["sender"],
                        recipient=email_data["recipient"],
                        body=email_data["body"],
                        snippet=email_data["snippet"],
                        date_sent=datetime.fromisoformat(email_data["date"].replace("Z", "+00:00")) if email_data.get("date") else None,
                        is_processed=False
                    )
                    
                    db.add(email)
                    db.commit()
                    db.refresh(email)
                    
                    # Add to vector store
                    email_content = f"Subject: {email_data['subject']}\nFrom: {email_data['sender']}\nTo: {email_data['recipient']}\n\n{email_data['body']}"
                    
                    chunk_ids = vector_service.add_email_to_vector_store(
                        client_id=client_id,
                        email_id=email.id,
                        email_content=email_content,
                        metadata={
                            "subject": email_data["subject"],
                            "sender": email_data["sender"],
                            "recipient": email_data["recipient"],
                            "thread_id": email_data["thread_id"],
                            "user_email": user["email"],
                            "sample_email": True
                        }
                    )
                    
                    if chunk_ids:
                        email.chunk_ids = json.dumps(chunk_ids)
                        email.is_processed = True
                        db.commit()
                    
                    emails_loaded += 1
                    
        except Exception as e:
            print(f"Error loading sample emails: {e}")
        
        # Start monitoring the sample thread
        monitoring_started = False
        try:
            if gmail_service:
                result = gmail_service.start_thread_monitoring("mock_thread_equity_001", client_id, 300)
                monitoring_started = result.get("success", False)
        except:
            pass
        
        return {
            "success": True,
            "message": f"Sample data loaded successfully for client {client.name}",
            "client_id": client_id,
            "client_name": client.name,
            "documents_loaded": documents_loaded,
            "emails_loaded": emails_loaded,
            "monitoring_started": monitoring_started
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sample data: {str(e)}")

# Initialize demo with multiple clients
@app.post("/api/demo/initialize-full")
async def initialize_full_demo():
    """Initialize complete demo with multiple clients"""
    try:
        results = {
            "clients_created": [],
            "sample_data_loaded": {}
        }
        
        if FULL_FEATURES:
            db = SessionLocal()
            
            # Create demo clients
            demo_clients = [
                {
                    "name": "Lexsy, Inc.",
                    "email": "legal@lexsy.com", 
                    "company": "Lexsy, Inc.",
                    "description": "AI-powered legal technology startup focusing on equity grants and advisor agreements"
                },
                {
                    "name": "TechCorp LLC",
                    "email": "counsel@techcorp.com",
                    "company": "TechCorp LLC", 
                    "description": "Enterprise software company focusing on employment and vendor contracts"
                }
            ]
            
            for client_data in demo_clients:
                existing = db.query(Client).filter(Client.email == client_data["email"]).first()
                if not existing:
                    client = Client(**client_data)
                    db.add(client)
                    db.commit()
                    db.refresh(client)
                    results["clients_created"].append(client.to_dict())
                else:
                    results["clients_created"].append(existing.to_dict())
            
            db.close()
            
            # Load sample data for Lexsy (first client)
            if results["clients_created"]:
                lexsy_client = results["clients_created"][0]
                try:
                    # Create fake user for loading sample data
                    fake_user = {"email": "demo@lexsy.com", "name": "Demo User"}
                    sample_result = await load_sample_data(
                        client_id=lexsy_client["id"],
                        user=fake_user,
                        db=SessionLocal()
                    )
                    results["sample_data_loaded"] = sample_result
                except Exception as e:
                    print(f"Error loading sample data: {e}")
        else:
            # Demo mode
            results["clients_created"] = [
                {"id": 1, "name": "Lexsy, Inc.", "email": "legal@lexsy.com"},
                {"id": 2, "name": "TechCorp LLC", "email": "counsel@techcorp.com"}
            ]
            results["sample_data_loaded"] = {
                "documents_loaded": 3,
                "emails_loaded": 6,
                "monitoring_started": True
            }
        
        return {
            "success": True,
            "message": "Full demo initialized successfully!",
            "results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Demo initialization failed"
        }

# Clear user data
@app.post("/api/user/clear-data")
async def clear_user_data(
    client_id: int = Form(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Clear all data for the authenticated user or specific client"""
    try:
        if not FULL_FEATURES:
            return {"success": True, "message": "Data cleared (demo mode)"}
        
        if client_id:
            # Clear data for specific client
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                return {"success": False, "message": "Client not found"}
        else:
            # Clear data for user's client
            client = db.query(Client).filter(Client.email == user["email"]).first()
            if not client:
                return {"success": True, "message": "No data to clear"}
        
        # Delete documents and files
        documents = db.query(Document).filter(Document.client_id == client.id).all()
        for doc in documents:
            # Delete file
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except:
                    pass
            # Delete from database
            db.delete(doc)
        
        # Delete emails
        emails = db.query(Email).filter(Email.client_id == client.id).all()
        for email in emails:
            db.delete(email)
        
        # Delete conversations
        conversations = db.query(Conversation).filter(Conversation.client_id == client.id).all()
        for conv in conversations:
            db.delete(conv)
        
        db.commit()
        
        # Clear vector store
        try:
            vector_service = VectorService()
            vector_service.reset_client_data(client.id)
        except Exception as e:
            print(f"Error clearing vector data: {e}")
        
        return {
            "success": True,
            "message": f"All data cleared successfully for {client.name}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete document
@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: int,
    client_id: int = Query(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Delete a document"""
    try:
        if not FULL_FEATURES:
            return {"success": True, "message": "Document deleted (demo mode)"}
        
        # Find document
        query = db.query(Document).filter(Document.id == document_id)
        if client_id:
            query = query.filter(Document.client_id == client_id)
        
        document = query.first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector store
        vector_service = VectorService()
        vector_service.delete_document_chunks(document.client_id, document_id)
        
        # Delete file
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# User session info
@app.get("/api/user/info")
async def get_user_info(user = Depends(get_current_user)):
    """Get current user information"""
    return {
        "user": user,
        "session_active": True,
        "features_available": FULL_FEATURES
    }

# Gmail conversation endpoints
@app.get("/api/gmail/conversations")
async def get_gmail_conversations():
    """Get available Gmail conversation types"""
    if gmail_service:
        conversations = gmail_service.get_available_conversations()
        return {
            "success": True,
            "conversations": conversations
        }
    else:
        return {
            "success": True,
            "conversations": {
                "equity_grant": {
                    "thread_id": "mock_thread_equity_001",
                    "subject": "Advisor Equity Grant for Lexsy, Inc.",
                    "participants": ["alex@founderco.com", "legal@lexsy.com"],
                    "message_count": 6
                }
            }
        }

@app.get("/api/gmail/conversation/{conversation_type}")
async def get_gmail_conversation(conversation_type: str):
    """Get a specific Gmail conversation"""
    if gmail_service:
        messages = gmail_service.simulate_mock_conversation(conversation_type)
        return {
            "success": True,
            "conversation_type": conversation_type,
            "messages": messages
        }
    else:
        return {
            "success": False,
            "error": "Gmail service not available"
        }

# Admin endpoint - list active users (for monitoring)
@app.get("/api/admin/users")
async def list_active_users():
    """List active user sessions (admin only)"""
    return {
        "active_sessions": len(user_sessions),
        "users": [
            {
                "email": session["email"],
                "name": session["name"],
                "last_active": session["last_active"]
            }
            for session in user_sessions.values()
        ]
    }

# Debug endpoint to list all routes
@app.get("/debug/routes")
async def list_routes():
    """List all available routes for debugging"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'unnamed')
            })
    return {
        "total_routes": len(routes),
        "routes": sorted(routes, key=lambda x: x["path"])
    }

# Add error handler for 404s
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "path": str(request.url.path),
            "message": f"The requested path '{request.url.path}' was not found",
            "available_endpoints": [
                "/",
                "/health", 
                "/api/status",
                "/api/clients",
                "/api/documents/upload",
                "/api/documents/list",
                "/api/emails/list",
                "/api/chat/ask",
                "/api/auth/gmail/auth-url",
                "/api/demo/load-sample",
                "/api/emails/start-thread-monitoring"
            ]
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting AI Legal Assistant on port {port}")
    print(f"📊 Features available: {FULL_FEATURES}")
    print(f"🔧 Environment: {'Production' if not os.getenv('DEBUG') else 'Development'}")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port,
        reload=False  # Disable reload in production
    )
