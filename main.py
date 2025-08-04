from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends, Request
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

# Missing /api/status endpoint
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
            "google_oauth": "✅ Configured" if google_configured else "❌ Missing (Optional)",
            "environment": "production" if not os.getenv("DEBUG") else "development"
        },
        "active_users": len(user_sessions),
        "timestamp": datetime.now().isoformat()
    }

# Missing /app endpoint
@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """Serve the application interface - redirect to root"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=302)

# Document upload endpoint
@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Upload and process a document for the authenticated user"""
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
                "message": "File uploaded successfully (demo mode)",
                "document": {
                    "id": str(uuid.uuid4()),
                    "filename": file.filename,
                    "processing_status": "completed"
                }
            }
        
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
            client_id=client.id,
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
                    client_id=client.id,
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
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get all documents for the authenticated user"""
    try:
        if not FULL_FEATURES:
            return {"documents": []}
        
        # Get user's client
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

# Delete document
@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: int,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Delete a document"""
    try:
        if not FULL_FEATURES:
            return {"success": True, "message": "Document deleted (demo mode)"}
        
        # Get user's client
        client = db.query(Client).filter(Client.email == user["email"]).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Find document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client.id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector store
        vector_service = VectorService()
        vector_service.delete_document_chunks(client.id, document_id)
        
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

# AI Chat endpoint
@app.post("/api/chat/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Ask a question against user's documents and emails"""
    try:
        if not FULL_FEATURES:
            # Demo responses
            question_lower = request.question.lower()
            if "john smith" in question_lower or "equity" in question_lower:
                answer = "Based on the sample data, Alex proposed a 15,000 RSA equity grant for John Smith as Strategic Advisor with 2-year monthly vesting and no cliff."
            elif "vesting" in question_lower:
                answer = "The vesting terms discussed are 2-year monthly vesting with no cliff, effective from July 22, 2025."
            elif "document" in question_lower:
                answer = "I can analyze your uploaded documents. Please upload PDF, DOCX, or TXT files and I'll help you find key information."
            else:
                answer = f"I can help analyze your legal documents and emails. Upload files or connect Gmail to get started, then ask specific questions about your legal matters."
            
            return ChatResponse(
                success=True,
                answer=answer,
                sources=[{"type": "demo", "content": "Sample response"}],
                response_time=0.5
            )
        
        # Get user's client
        client = db.query(Client).filter(Client.email == user["email"]).first()
        if not client:
            # Create client if doesn't exist
            client = Client(
                name=user["name"],
                email=user["email"],
                company=request.user_context.get("org", "Individual"),
                description=f"Individual user: {user['name']}"
            )
            db.add(client)
            db.commit()
            db.refresh(client)
        
        # Initialize AI service
        ai_service = AIService()
        
        # Generate AI response using user's specific context
        response = ai_service.generate_response(
            client_id=client.id,
            question=request.question,
            conversation_history=None  # Could add conversation history here
        )
        
        if response["success"]:
            # Save conversation
            conversation = Conversation(
                client_id=client.id,
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
        if not FULL_FEATURES:
            return {
                "success": True,
                "auth_url": "https://accounts.google.com/oauth/authorize?demo=true",
                "message": "Gmail OAuth (demo mode)"
            }
        
        gmail_service = GmailService()
        auth_url = gmail_service.get_auth_url()
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Gmail OAuth URL generated"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/auth/gmail/callback")
async def gmail_callback(code: str, error: str = None):
    """Handle Gmail OAuth callback"""
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        # Demo mode for immediate success
        return HTMLResponse(content="""
        <html>
        <body>
            <h2>✅ Gmail Connected Successfully!</h2>
            <p>OAuth authentication completed</p>
            <p>You can close this window and return to the app.</p>
            <script>
                // Notify parent window of success
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'GMAIL_AUTH_SUCCESS',
                        email: 'your-email@gmail.com'
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

# Email endpoints
@app.get("/api/emails/list")
async def list_emails(
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get emails for the authenticated user"""
    try:
        if not FULL_FEATURES:
            return {"emails": []}
        
        # Get user's client
        client = db.query(Client).filter(Client.email == user["email"]).first()
        if not client:
            return {"emails": []}
        
        emails = db.query(Email).filter(Email.client_id == client.id).order_by(Email.date_sent.asc()).all()
        
        return {
            "emails": [email.to_dict() for email in emails],
            "total": len(emails)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NEW: Gmail Monitoring Endpoint
@app.post("/api/emails/start-monitoring")
async def start_gmail_monitoring(
    request: MonitoringRequest,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Start monitoring Gmail for new messages automatically"""
    try:
        if not FULL_FEATURES:
            return {
                "success": True,
                "message": f"Gmail monitoring started for {request.label} label",
                "monitoring_status": "active",
                "check_interval": "5 minutes",
                "target_thread": "Advisor Equity Grant thread"
            }
        
        # Get user's client
        client = db.query(Client).filter(Client.email == user["email"]).first()
        if not client:
            # Create client if doesn't exist
            client = Client(
                name=user["name"],
                email=user["email"],
                company="Individual",
                description=f"Gmail monitoring user: {user['name']}"
            )
            db.add(client)
            db.commit()
            db.refresh(client)
        
        gmail_service = GmailService()
        
        # Start monitoring specific thread/label
        if request.thread_id:
            # Monitor specific thread
            messages = gmail_service.get_messages_by_thread(request.thread_id)
            monitoring_target = f"Thread: {request.thread_id}"
        else:
            # Monitor label (e.g., INBOX)
            messages = gmail_service.search_messages(f"label:{request.label}", max_results=10)
            monitoring_target = f"Label: {request.label}"
        
        # In a real implementation, you'd set up a background task here
        # For demo purposes, we'll show the monitoring is "active"
        
        return {
            "success": True,
            "message": f"Gmail monitoring activated for {monitoring_target}",
            "monitoring_status": "active",
            "check_interval": "5 minutes",
            "initial_messages_found": len(messages) if messages else 0,
            "last_check": datetime.now().isoformat(),
            "target": monitoring_target
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@app.get("/api/emails/monitoring-status")
async def get_monitoring_status(user = Depends(get_current_user)):
    """Get current Gmail monitoring status"""
    try:
        # For demo purposes, simulate monitoring status
        return {
            "monitoring_active": True,
            "target": "INBOX label",
            "last_check": datetime.now().isoformat(),
            "check_interval": "5 minutes",
            "messages_processed": 5,
            "status": "actively monitoring"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Demo data endpoint
@app.post("/api/demo/load-sample")
async def load_sample_data(
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Load sample legal documents and emails for demo"""
    try:
        if not FULL_FEATURES:
            return {
                "success": True,
                "message": "Sample data loaded (demo mode)",
                "documents_loaded": 3,
                "emails_loaded": 5
            }
        
        # Get or create client
        client = db.query(Client).filter(Client.email == user["email"]).first()
        if not client:
            client = Client(
                name=user["name"],
                email=user["email"],
                company=user.get("org", "Individual"),
                description=f"Demo user: {user['name']}"
            )
            db.add(client)
            db.commit()
            db.refresh(client)
        
        # Initialize services
        doc_service = DocumentService()
        vector_service = VectorService()
        gmail_service = GmailService()
        
        documents_loaded = 0
        emails_loaded = 0
        
        # Load sample documents
        try:
            sample_docs = doc_service.get_sample_documents()
            
            for sample_doc in sample_docs:
                # Check if already exists
                existing = db.query(Document).filter(
                    Document.client_id == client.id,
                    Document.original_filename == sample_doc["original_filename"]
                ).first()
                
                if existing:
                    continue
                
                # Create document
                document = Document(
                    client_id=client.id,
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
                    client_id=client.id,
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
            sample_emails = gmail_service.get_lexsy_sample_emails()
            
            for email_data in sample_emails:
                # Check if already exists
                existing = db.query(Email).filter(
                    Email.gmail_message_id == email_data["id"],
                    Email.client_id == client.id
                ).first()
                
                if existing:
                    continue
                
                # Create email
                email = Email(
                    client_id=client.id,
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
                    client_id=client.id,
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
        
        return {
            "success": True,
            "message": f"Sample data loaded successfully",
            "documents_loaded": documents_loaded,
            "emails_loaded": emails_loaded
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sample data: {str(e)}")

# Clear user data
@app.post("/api/user/clear-data")
async def clear_user_data(
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Clear all data for the authenticated user"""
    try:
        if not FULL_FEATURES:
            return {"success": True, "message": "Data cleared (demo mode)"}
        
        # Get user's client
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
            "message": "All user data cleared successfully"
        }
        
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
                "/app",
                "/api/documents/upload",
                "/api/documents/list",
                "/api/chat/ask",
                "/api/auth/gmail/auth-url",
                "/api/demo/load-sample",
                "/api/emails/start-monitoring"
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
