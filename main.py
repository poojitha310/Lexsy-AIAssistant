from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends, Request, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import time
from api.auth import router as auth_router
from api.clients import router as clients_router
from api.chat import router as chat_router  # ← Add this line
from api.documents import router as documents_router
from api.emails import router as emails_router
from api.demo import router as demo_router

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Mount all routes
app.include_router(auth_router, prefix="/api/auth")
app.include_router(clients_router, prefix="/api/clients")
app.include_router(documents_router, prefix="/api/documents")
app.include_router(emails_router, prefix="/api/emails")
app.include_router(chat_router, prefix="/api/chat")      
app.include_router(demo_router, prefix="/api/demo")

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

# In-memory user sessions
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
    if FULL_FEATURES:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.CHROMADB_PATH, exist_ok=True)
        
        try:
            init_db()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")

# Serve the main application
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application"""
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

# ======================
# CLIENT MANAGEMENT ENDPOINTS
# ======================

@app.get("/api/clients")
async def list_clients():
    """List all available clients"""
    if not FULL_FEATURES:
        # Return demo clients with sample data indicators
        return {
            "success": True,
            "clients": [
                {
                    "id": 1,
                    "name": "Lexsy, Inc.",
                    "email": "legal@lexsy.com",
                    "company": "Lexsy, Inc.",
                    "description": "AI-powered legal technology startup",
                    "is_active": True,
                    "created_at": datetime.now().isoformat(),
                    "has_documents": True,
                    "has_emails": True
                },
                {
                    "id": 2,
                    "name": "TechCorp LLC",
                    "email": "counsel@techcorp.com", 
                    "company": "TechCorp LLC",
                    "description": "Enterprise software company",
                    "is_active": True,
                    "created_at": datetime.now().isoformat(),
                    "has_documents": False,
                    "has_emails": False
                }
            ]
        }
    
    try:
        db = SessionLocal()
        clients = db.query(Client).filter(Client.is_active == True).all()
        
        client_list = []
        for client in clients:
            client_dict = client.to_dict()
            # Add content indicators
            client_dict["has_documents"] = len(client.documents) > 0
            client_dict["has_emails"] = len(client.emails) > 0
            client_list.append(client_dict)
        
        db.close()
        
        return {
            "success": True,
            "clients": client_list
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
    description: str = Form("")
):
    """Create a new client"""
    if not FULL_FEATURES:
        return {
            "success": True,
            "client": {
                "id": len(user_sessions) + 3,  # Fake incremental ID
                "name": name,
                "email": email,
                "company": company,
                "description": description,
                "is_active": True,
                "created_at": datetime.now().isoformat()
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
        
        client_dict = client.to_dict()
        client_dict["has_documents"] = False
        client_dict["has_emails"] = False
        
        db.close()
        
        return {
            "success": True,
            "client": client_dict
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/clients/{client_id}")
async def get_client(client_id: int):
    """Get specific client details with stats"""
    if not FULL_FEATURES:
        demo_clients = {
            1: {
                "id": 1, 
                "name": "Lexsy, Inc.", 
                "email": "legal@lexsy.com", 
                "company": "Lexsy, Inc.",
                "description": "AI-powered legal technology startup",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "stats": {
                    "documents": 3,
                    "emails": 6,
                    "conversations": 0
                }
            },
            2: {
                "id": 2, 
                "name": "TechCorp LLC", 
                "email": "counsel@techcorp.com", 
                "company": "TechCorp LLC",
                "description": "Enterprise software company",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "stats": {
                    "documents": 0,
                    "emails": 0,
                    "conversations": 0
                }
            }
        }
        return {"success": True, "client": demo_clients.get(client_id)}
    
    try:
        db = SessionLocal()
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        
        if not client:
            db.close()
            return {"success": False, "error": "Client not found"}
        
        client_dict = client.to_dict()
        client_dict["stats"] = {
            "documents": len(client.documents),
            "emails": len(client.emails),
            "conversations": len(client.conversations)
        }
        
        db.close()
        
        return {"success": True, "client": client_dict}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: int):
    """Soft delete a client"""
    if not FULL_FEATURES:
        return {"success": True, "message": f"Client {client_id} deleted (demo mode)"}
    
    try:
        db = SessionLocal()
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        
        if not client:
            db.close()
            return {"success": False, "error": "Client not found"}
        
        # Soft delete
        client.is_active = False
        db.commit()
        
        # Clean up vector store data
        try:
            vector_service = VectorService()
            vector_service.reset_client_data(client_id)
        except:
            pass
        
        db.close()
        
        return {"success": True, "message": "Client deleted successfully"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ======================
# DOCUMENT ENDPOINTS
# ======================

@app.post("/api/documents/{client_id}/upload")
async def upload_document(
    client_id: int,
    file: UploadFile = File(...),
    user = Depends(get_current_user)
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
        
        if FULL_FEATURES and len(file_content) > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max size is 10MB")
        
        if not FULL_FEATURES:
            # Demo mode response
            return {
                "success": True,
                "message": f"File uploaded successfully for client {client_id}",
                "document": {
                    "id": str(uuid.uuid4()),
                    "filename": file.filename,
                    "client_id": client_id,
                    "processing_status": "completed",
                    "file_type": file.content_type.split('/')[-1],
                    "file_size": len(file_content),
                    "created_at": datetime.now().isoformat()
                }
            }
        
        # Verify client exists
        db = SessionLocal()
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            raise HTTPException(status_code=404, detail="Client not found")
        
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
            db.close()
            raise HTTPException(status_code=400, detail=save_result["error"])
        
        # Create document record
        document = Document(
            client_id=client_id,
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
                document.metadata = json.dumps(extraction_result["metadata"])
                document.processing_status = "completed"
                db.commit()
                
                # Add to client-specific vector store
                chunk_ids = vector_service.add_document_to_vector_store(
                    client_id=client_id,
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
        
        result_dict = document.to_dict()
        db.close()
        
        return {
            "success": True,
            "message": "Document uploaded and processed successfully",
            "document": result_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/documents/{client_id}/documents")
async def get_client_documents(
    client_id: int,
    skip: int = 0,
    limit: int = 50
):
    """Get documents for specific client"""
    try:
        if not FULL_FEATURES:
            if client_id == 1:  # Lexsy sample documents
                return {
                    "client_id": client_id,
                    "client_name": "Lexsy, Inc.",
                    "total_documents": 3,
                    "documents": [
                        {
                            "id": 1, 
                            "filename": "lexsy-board-approval.pdf", 
                            "original_filename": "Lexsy Board Approval - Equity Incentive Plan.pdf", 
                            "client_id": 1, 
                            "processing_status": "completed", 
                            "file_type": "pdf", 
                            "file_size": 245760,
                            "created_at": datetime.now().isoformat()
                        },
                        {
                            "id": 2, 
                            "filename": "lexsy-advisor-agreement.docx", 
                            "original_filename": "Lexsy Advisor Agreement Template.docx", 
                            "client_id": 1, 
                            "processing_status": "completed", 
                            "file_type": "docx", 
                            "file_size": 87320,
                            "created_at": datetime.now().isoformat()
                        },
                        {
                            "id": 3, 
                            "filename": "lexsy-equity-plan.pdf", 
                            "original_filename": "Lexsy Equity Incentive Plan (EIP).pdf", 
                            "client_id": 1, 
                            "processing_status": "completed", 
                            "file_type": "pdf", 
                            "file_size": 156890,
                            "created_at": datetime.now().isoformat()
                        }
                    ]
                }
            else:
                return {
                    "client_id": client_id,
                    "client_name": f"Client {client_id}",
                    "total_documents": 0,
                    "documents": []
                }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            return {"client_id": client_id, "total_documents": 0, "documents": [], "error": "Client not found"}
        
        # Get client documents
        documents = db.query(Document).filter(
            Document.client_id == client_id
        ).offset(skip).limit(limit).all()
        
        result = {
            "client_id": client_id,
            "client_name": client.name,
            "total_documents": len(documents),
            "documents": [doc.to_dict() for doc in documents]
        }
        
        db.close()
        return result
        
    except Exception as e:
        return {
            "client_id": client_id,
            "total_documents": 0,
            "documents": [],
            "error": str(e)
        }

@app.post("/api/documents/{client_id}/upload-sample-documents")
async def upload_sample_documents(client_id: int):
    """Upload sample documents for demo client"""
    try:
        if not FULL_FEATURES:
            return {
                "success": True,
                "message": f"Uploaded sample documents for client {client_id} (demo mode)",
                "documents": []
            }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            return {"success": False, "error": "Client not found"}
        
        # Initialize services
        vector_service = VectorService()
        doc_service = DocumentService()
        
        # Get sample documents
        sample_docs = doc_service.get_sample_documents()
        
        uploaded_docs = []
        
        for sample_doc in sample_docs:
            # Check if document already exists
            existing_doc = db.query(Document).filter(
                Document.client_id == client_id,
                Document.original_filename == sample_doc["original_filename"]
            ).first()
            
            if existing_doc:
                uploaded_docs.append(existing_doc.to_dict())
                continue
            
            # Create document record
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
            
            # Add to vector store with client isolation
            chunk_ids = vector_service.add_document_to_vector_store(
                client_id=client_id,
                document_id=document.id,
                text=sample_doc["content"],
                metadata={
                    "filename": document.original_filename,
                    "file_type": document.file_type,
                    "created_at": document.created_at.isoformat(),
                    "sample_document": True
                }
            )
            
            if chunk_ids:
                document.chunk_ids = json.dumps(chunk_ids)
                db.commit()
            
            uploaded_docs.append(document.to_dict())
        
        db.close()
        
        return {
            "success": True,
            "message": f"Uploaded {len(uploaded_docs)} sample documents",
            "documents": uploaded_docs
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ======================
# EMAIL ENDPOINTS
# ======================

@app.get("/api/emails/{client_id}/emails")
async def get_client_emails(
    client_id: int,
    skip: int = 0,
    limit: int = 50,
    thread_id: Optional[str] = None
):
    """Get emails for specific client"""
    try:
        if not FULL_FEATURES:
            if client_id == 1:  # Lexsy sample emails
                sample_emails = []
                if gmail_service:
                    sample_emails = gmail_service.simulate_mock_conversation("equity_grant")
                
                # Filter by thread if specified
                if thread_id:
                    sample_emails = [email for email in sample_emails if email.get("thread_id") == thread_id]
                
                return {
                    "client_id": client_id,
                    "client_name": "Lexsy, Inc.",
                    "total_emails": len(sample_emails),
                    "thread_filter": thread_id,
                    "emails": sample_emails
                }
            else:
                return {
                    "client_id": client_id,
                    "client_name": f"Client {client_id}",
                    "total_emails": 0,
                    "emails": []
                }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            return {"client_id": client_id, "total_emails": 0, "emails": [], "error": "Client not found"}
        
        # Build query for client emails
        query = db.query(Email).filter(Email.client_id == client_id)
        
        if thread_id:
            query = query.filter(Email.gmail_thread_id == thread_id)
        
        emails = query.order_by(Email.date_sent.desc()).offset(skip).limit(limit).all()
        
        result = {
            "client_id": client_id,
            "client_name": client.name,
            "total_emails": len(emails),
            "thread_filter": thread_id,
            "emails": [email.to_dict() for email in emails]
        }
        
        db.close()
        return result
        
    except Exception as e:
        return {
            "client_id": client_id,
            "total_emails": 0,
            "emails": [],
            "error": str(e)
        }

@app.post("/api/emails/{client_id}/ingest-sample-emails")
async def ingest_sample_emails(client_id: int):
    """Ingest sample Lexsy email thread for demo"""
    try:
        if not FULL_FEATURES:
            return {
                "success": True,
                "message": f"Processed sample emails for client {client_id} (demo mode)",
                "emails_processed": 6,
                "emails": []
            }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            return {"success": False, "error": "Client not found"}
        
        # Initialize services
        vector_service = VectorService()
        ai_service = AIService()
        
        # Get sample emails
        sample_emails = []
        if gmail_service:
            sample_emails = gmail_service.simulate_mock_conversation("equity_grant")
        
        processed_emails = []
        
        for email_data in sample_emails:
            # Check if email already exists
            existing_email = db.query(Email).filter(
                Email.gmail_message_id == email_data["id"],
                Email.client_id == client_id
            ).first()
            
            if existing_email:
                processed_emails.append(existing_email.to_dict())
                continue
            
            # Parse date
            date_sent = None
            if email_data.get("date"):
                try:
                    date_sent = datetime.fromisoformat(email_data["date"].replace("Z", "+00:00"))
                except:
                    pass
            
            # Create email record
            email = Email(
                client_id=client_id,
                gmail_message_id=email_data["id"],
                gmail_thread_id=email_data["thread_id"],
                subject=email_data["subject"],
                sender=email_data["sender"],
                recipient=email_data["recipient"],
                body=email_data["body"],
                snippet=email_data["snippet"],
                date_sent=date_sent,
                labels=json.dumps([]),
                is_processed=False
            )
            
            db.add(email)
            db.commit()
            db.refresh(email)
            
            # Add to client-specific vector store
            email_content = f"Subject: {email_data['subject']}\nFrom: {email_data['sender']}\nTo: {email_data['recipient']}\nDate: {email_data.get('date', '')}\n\n{email_data['body']}"
            
            chunk_ids = vector_service.add_email_to_vector_store(
                client_id=client_id,
                email_id=email.id,
                email_content=email_content,
                metadata={
                    "subject": email_data["subject"],
                    "sender": email_data["sender"],
                    "recipient": email_data["recipient"],
                    "date": email_data.get("date", ""),
                    "thread_id": email_data["thread_id"],
                    "sample_email": True
                }
            )
            
            if chunk_ids:
                email.chunk_ids = json.dumps(chunk_ids)
                email.is_processed = True
                db.commit()
            
            processed_emails.append(email.to_dict())
        
        # Generate thread summary
        thread_summary = ""
        if ai_service and sample_emails:
            summary_result = ai_service.generate_email_thread_summary(sample_emails)
            thread_summary = summary_result.get("summary", "")
        
        db.close()
        
        return {
            "success": True,
            "message": f"Processed {len(processed_emails)} sample emails",
            "emails_processed": len(processed_emails),
            "emails": processed_emails,
            "thread_summary": thread_summary
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/emails/{client_id}/email-threads")
async def get_email_threads(client_id: int):
    """Get all email threads for a client"""
    try:
        if not FULL_FEATURES:
            if client_id == 1:  # Lexsy threads
                return {
                    "client_id": client_id,
                    "total_threads": 1,
                    "threads": [
                        {
                            "thread_id": "mock_thread_equity_001",
                            "message_count": 6,
                            "latest_date": datetime.now().isoformat(),
                            "subject": "Advisor Equity Grant for Lexsy, Inc.",
                            "participants": "alex@founderco.com ↔ legal@lexsy.com",
                            "snippet": "We'd like to bring on a new advisor for Lexsy, Inc..."
                        }
                    ]
                }
            else:
                return {"client_id": client_id, "total_threads": 0, "threads": []}
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            return {"client_id": client_id, "total_threads": 0, "threads": [], "error": "Client not found"}
        
        # Get unique threads with aggregated data
        from sqlalchemy import func
        threads = db.query(
            Email.gmail_thread_id,
            func.count(Email.id).label('message_count'),
            func.max(Email.date_sent).label('latest_date'),
            func.max(Email.subject).label('subject')  # Get one subject per thread
        ).filter(
            Email.client_id == client_id
        ).group_by(Email.gmail_thread_id).all()
        
        thread_list = []
        for thread in threads:
            # Get first email in thread for more details
            first_email = db.query(Email).filter(
                Email.client_id == client_id,
                Email.gmail_thread_id == thread.gmail_thread_id
            ).order_by(Email.date_sent.asc()).first()
            
            thread_list.append({
                "thread_id": thread.gmail_thread_id,
                "message_count": thread.message_count,
                "latest_date": thread.latest_date.isoformat() if thread.latest_date else None,
                "subject": thread.subject or (first_email.subject if first_email else "Unknown"),
                "participants": f"{first_email.sender} ↔ {first_email.recipient}" if first_email else "Unknown",
                "snippet": first_email.snippet if first_email else ""
            })
        
        db.close()
        
        return {
            "client_id": client_id,
            "total_threads": len(thread_list),
            "threads": thread_list
        }
        
    except Exception as e:
        return {
            "client_id": client_id,
            "total_threads": 0,
            "threads": [],
            "error": str(e)
        }

# ======================
# CHAT ENDPOINTS
# ======================

@app.post("/api/chat/{client_id}/ask")
async def ask_question(
    client_id: int,
    question: str = Form(...),
    include_history: bool = Form(True),
    user = Depends(get_current_user)
):
    """Ask a question about client's documents and emails"""
    try:
        if not FULL_FEATURES:
            # Demo responses based on client and question
            question_lower = question.lower()
            
            if client_id == 1:  # Lexsy responses
                if "john smith" in question_lower or "equity" in question_lower:
                    answer = "Based on the email thread between Alex Rodriguez (CEO) and Kristina Chen (Legal Counsel), Alex proposed a **15,000 RSA equity grant** for John Smith as Strategic Advisor. John Smith is a former VP of AI at Google and current partner at Andreessen Horowitz. The grant includes:\n\n• **15,000 Restricted Stock Awards (RSAs)**\n• **2-year monthly vesting** with no cliff\n• **Board observer rights** for quarterly meetings\n• **Expected commitment**: 4-6 hours per month\n\nThe legal team confirmed this grant is **well within the available share pool** (915,000 shares available out of 1M total EIP)."
                    
                elif "vesting" in question_lower:
                    answer = "The **vesting terms** discussed in the email thread are:\n\n• **Duration**: 2-year monthly vesting\n• **Schedule**: 625 shares vest each month (15,000 ÷ 24 months)\n• **Cliff**: No cliff period\n• **Start date**: July 22, 2025 (retroactive to verbal agreement)\n• **Acceleration**: Single trigger acceleration for 25% of unvested shares if terminated without cause\n\nKristina (Legal) confirmed this is **standard for advisor agreements** and recommended including an 83(b) election to minimize tax impact."
                    
                elif "tax" in question_lower or "83(b)" in question_lower:
                    answer = "**Tax implications** explained by Legal Counsel:\n\n**RSAs vs Stock Options for John:**\n• **RSAs**: Taxed on fair market value when vesting (ordinary income rates)\n• **Current tax impact**: ~$7,500 ordinary income spread over 24 months\n• **Recommendation**: RSAs are better given early stage and low current FMV (~$0.50/share)\n\n**83(b) Election Benefits:**\n• Pay tax on current FMV now ($300 total)\n• All future appreciation taxed as capital gains\n• **Must file within 30 days** of grant\n• Minimal upfront tax burden at current valuation"
                    
                elif "documentation" in question_lower or "paperwork" in question_lower:
                    answer = "**Required documentation** as outlined by Legal:\n\n**Primary Documents:**\n1. **Board Consent** - Authorization for the equity grant\n2. **Advisor Agreement** - Including IP assignment, confidentiality, board observer rights\n3. **Restricted Stock Award Agreement** - Formal grant terms\n4. **83(b) Election Form** - Tax optimization\n\n**Timeline:**\n• Board Consent ready for Thursday's meeting\n• All agreements drafted by Wednesday\n• Full execution package ready Friday\n• **Target completion**: Tuesday, July 29th\n\n**Special provisions**: A16z portfolio introduction rights with conflict disclosures"
                    
                elif "shares" in question_lower and ("available" in question_lower or "pool" in question_lower):
                    answer = "**Share availability confirmed** by Legal team:\n\n**Current EIP Status:**\n• **Total EIP pool**: 1,000,000 shares\n• **Previously granted**: 85,000 shares  \n• **Available for grant**: 915,000 shares\n• **Requested for John Smith**: 15,000 shares\n• **Status**: ✅ **APPROVED** - Well within available pool\n\n**Grant represents**: 1.5% of total company\n**Remaining after grant**: 900,000 shares available for future grants"
                    
                elif "board" in question_lower:
                    answer = "**Board approval process** from the email thread:\n\n**Board Meeting Details:**\n• **Date**: Thursday (July 25th)\n• **Agenda item**: \"Advisor Equity Grant Authorization\"\n• **Attendees**: All directors confirmed\n• **Priority**: This will be prioritized agenda item\n\n**Board Observer Rights for John:**\n• **Quarterly board meetings** access\n• **Formal observer rights** included in Advisor Agreement\n• **A16z portfolio introduction** rights with conflict disclosures\n\n**Current Status**: Board Consent prepared and ready for Thursday's meeting approval"
                
                else:
                    answer = "I can help analyze **Lexsy's legal documents and email discussions**. I have access to:\n\n📄 **Legal Documents:**\n• Board Approval for Equity Incentive Plan\n• Advisor Agreement Template  \n• Complete Equity Incentive Plan (EIP)\n\n📧 **Email Thread:**\n• 6-message conversation about John Smith's advisor equity grant\n• Discussion between Alex Rodriguez (CEO) and Kristina Chen (Legal)\n\n**Try asking about:**\n• John Smith's equity grant details\n• Vesting terms and tax implications\n• Required documentation and timeline\n• Share availability in the EIP\n• Board approval process"
            else:
                answer = f"I don't see any documents or emails for **Client {client_id}** yet. To analyze legal matters, please:\n\n1. **Upload documents** (PDF, DOCX, TXT)\n2. **Connect Gmail** and ingest email threads\n3. Or **switch to Lexsy, Inc.** which has sample legal data loaded\n\nOnce you have content uploaded, I can help analyze contracts, agreements, compliance requirements, and email discussions."
            
            # Mock sources for Lexsy
            sources = []
            if client_id == 1:
                if "john smith" in question_lower or "equity" in question_lower or "vesting" in question_lower:
                    sources = [
                        {"type": "email", "subject": "Advisor Equity Grant for Lexsy, Inc.", "sender": "alex@founderco.com", "similarity_score": 0.95},
                        {"type": "email", "subject": "Re: Advisor Equity Grant - Legal Review", "sender": "legal@lexsy.com", "similarity_score": 0.92},
                        {"type": "document", "filename": "Lexsy Equity Incentive Plan.pdf", "similarity_score": 0.88}
                    ]
            
            return {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": sources,
                "context_used": len(sources),
                "tokens_used": len(answer.split()) * 1.3,  # Rough estimate
                "response_time": 0.8,
                "conversation_id": int(time.time())
            }
        
        # Full features mode
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize AI service
        ai_service = AIService()
        
        # Get conversation history if requested
        conversation_history = None
        if include_history:
            recent_conversations = db.query(Conversation).filter(
                Conversation.client_id == client_id
            ).order_by(Conversation.created_at.desc()).limit(6).all()
            
            conversation_history = [
                {
                    "question": conv.question,
                    "answer": conv.answer
                }
                for conv in reversed(recent_conversations)
            ]
        
        # Generate AI response with client-specific context
        response = ai_service.generate_response(
            client_id=client_id,
            question=question,
            conversation_history=conversation_history
        )
        
        if not response["success"]:
            db.close()
            raise HTTPException(status_code=500, detail=response.get("error", "AI response generation failed"))
        
        # Save conversation to database
        conversation = Conversation(
            client_id=client_id,
            question=question,
            answer=response["answer"],
            context_sources=json.dumps([src["type"] + ":" + str(src.get("document_id", src.get("email_id", ""))) for src in response["sources"]]),
            similarity_scores=json.dumps([src["similarity_score"] for src in response["sources"]]),
            response_time=response["response_time"],
            tokens_used=response["tokens_used"]
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        db.close()
        
        return {
            "success": True,
            "question": question,
            "answer": response["answer"],
            "sources": response["sources"],
            "context_used": response["context_used"],
            "tokens_used": response["tokens_used"],
            "response_time": response["response_time"],
            "conversation_id": conversation.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(e)}")

@app.post("/api/chat/{client_id}/search")
async def search_content(
    client_id: int,
    query: str = Form(...),
    source_filter: Optional[str] = Form(None),
    n_results: int = Form(5)
):
    """Search through client's documents and emails"""
    try:
        if not FULL_FEATURES:
            # Demo search results for Lexsy
            if client_id == 1:
                demo_results = [
                    {
                        "content": "We'd like to bring on a new advisor for Lexsy, Inc. Name: John Smith, Role: Strategic Advisor, Proposed grant: 15,000 RSAs",
                        "metadata": {"source_type": "email", "subject": "Advisor Equity Grant", "sender": "alex@founderco.com"},
                        "similarity_score": 0.95
                    },
                    {
                        "content": "The Company's 2025 Equity Incentive Plan reserves 1,000,000 shares of Common Stock for issuance.",
                        "metadata": {"source_type": "document", "filename": "Lexsy Equity Incentive Plan.pdf"},
                        "similarity_score": 0.87
                    }
                ]
                
                # Filter by source type if specified
                if source_filter:
                    demo_results = [r for r in demo_results if r["metadata"]["source_type"] == source_filter]
                
                return {
                    "success": True,
                    "query": query,
                    "source_filter": source_filter,
                    "results_count": len(demo_results),
                    "results": demo_results
                }
            else:
                return {
                    "success": True,
                    "query": query,
                    "source_filter": source_filter,
                    "results_count": 0,
                    "results": []
                }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize vector service
        vector_service = VectorService()
        
        # Search for similar content in client-specific store
        results = vector_service.search_similar_content(
            client_id=client_id,
            query=query,
            n_results=n_results,
            source_filter=source_filter
        )
        
        db.close()
        
        return {
            "success": True,
            "query": query,
            "source_filter": source_filter,
            "results_count": len(results),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/chat/{client_id}/conversations")
async def get_conversations(
    client_id: int,
    skip: int = 0,
    limit: int = 50
):
    """Get conversation history for a client"""
    try:
        if not FULL_FEATURES:
            return {
                "client_id": client_id,
                "client_name": f"Client {client_id}",
                "total_conversations": 0,
                "conversations": []
            }
        
        db = SessionLocal()
        
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            db.close()
            raise HTTPException(status_code=404, detail="Client not found")
        
        conversations = db.query(Conversation).filter(
            Conversation.client_id == client_id
        ).order_by(Conversation.created_at.desc()).offset(skip).limit(limit).all()
        
        result = {
            "client_id": client_id,
            "client_name": client.name,
            "total_conversations": len(conversations),
            "conversations": [conv.to_dict() for conv in conversations]
        }
        
        db.close()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")

# ======================
# GMAIL AUTHENTICATION ENDPOINTS
# ======================

@app.get("/api/auth/gmail/auth-url")
async def get_gmail_auth_url():
    """Get Gmail OAuth URL"""
    try:
        # Check if we have Google OAuth credentials configured
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not google_client_id or not google_client_secret:
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
            <head><title>Gmail Authentication Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                <h2 style="color: #dc3545;">❌ Gmail Authentication Error</h2>
                <p>Error: {error}</p>
                <p>You can close this window and try again.</p>
                <script>
                    setTimeout(() => {{
                        window.close();
                    }}, 3000);
                </script>
            </body>
            </html>
            """)
        
        # For demo mode, always return success
        return HTMLResponse(content="""
        <html>
        <head><title>Gmail Connected Successfully</title></head>
        <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
            <h2 style="color: #28a745;">✅ Gmail Connected Successfully!</h2>
            <p>OAuth authentication completed successfully.</p>
            <p><strong>Demo Mode:</strong> Mock email conversations are now available for analysis.</p>
            <p style="color: #6c757d;">You can close this window and return to the app.</p>
            <script>
                // Notify parent window of success
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'GMAIL_AUTH_SUCCESS',
                        email: 'demo@gmail.com',
                        demo_mode: true
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
        <head><title>Authentication Error</title></head>
        <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
            <h2 style="color: #dc3545;">❌ Authentication Error</h2>
            <p>Error: {str(e)}</p>
            <p>You can close this window and try again.</p>
            <script>
                setTimeout(() => {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """)

# ======================
# DEMO AND INITIALIZATION ENDPOINTS  
# ======================

@app.post("/api/demo/initialize-full")
async def initialize_full_demo():
    """Initialize complete demo with sample clients and data"""
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
                    # Load sample documents
                    doc_result = await upload_sample_documents(lexsy_client["id"])
                    # Load sample emails  
                    email_result = await ingest_sample_emails(lexsy_client["id"])
                    
                    results["sample_data_loaded"] = {
                        "documents": doc_result.get("success", False),
                        "emails": email_result.get("success", False),
                        "documents_count": len(doc_result.get("documents", [])),
                        "emails_count": email_result.get("emails_processed", 0)
                    }
                except Exception as e:
                    print(f"Error loading sample data: {e}")
        else:
            # Demo mode
            results["clients_created"] = [
                {"id": 1, "name": "Lexsy, Inc.", "email": "legal@lexsy.com"},
                {"id": 2, "name": "TechCorp LLC", "email": "counsel@techcorp.com"}
            ]
            results["sample_data_loaded"] = {
                "documents": True,
                "emails": True,
                "documents_count": 3,
                "emails_count": 6
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

# ======================
# GMAIL MONITORING ENDPOINTS
# ======================

@app.post("/api/emails/{client_id}/start-thread-monitoring")
async def start_thread_monitoring(
    client_id: int,
    thread_id: str = Form("mock_thread_equity_001"),
    check_interval: int = Form(300)
):
    """Start monitoring a specific Gmail thread for a client"""
    try:
        if not FULL_FEATURES or not gmail_service:
            return {
                "success": True,
                "message": f"Started monitoring thread {thread_id} for client {client_id} (demo mode)",
                "monitoring": {
                    "thread_id": thread_id,
                    "client_id": client_id,
                    "check_interval": check_interval,
                    "status": "active",
                    "demo_mode": True
                }
            }
        
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
async def get_monitoring_status():
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

# ======================
# ERROR HANDLERS AND DEBUG
# ======================

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
                "/api/documents/{client_id}/upload",
                "/api/documents/{client_id}/documents",
                "/api/emails/{client_id}/emails",
                "/api/chat/{client_id}/ask",
                "/api/auth/gmail/auth-url",
                "/api/demo/initialize-full"
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
        reload=False
    )
    # Add these debug endpoints to your main.py

@app.get("/api/debug/system-status")
async def debug_system_status():
    """Debug endpoint to check system status"""
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "openai_api_key": "✅ Set" if os.getenv("OPENAI_API_KEY") else "❌ Missing",
                "openai_key_length": len(os.getenv("OPENAI_API_KEY", "")) if os.getenv("OPENAI_API_KEY") else 0,
                "google_client_id": "✅ Set" if os.getenv("GOOGLE_CLIENT_ID") else "❌ Missing",
                "upload_dir": settings.UPLOAD_DIR,
                "chromadb_path": settings.CHROMADB_PATH,
                "upload_dir_exists": os.path.exists(settings.UPLOAD_DIR),
                "chromadb_path_exists": os.path.exists(settings.CHROMADB_PATH)
            },
            "services": {
                "full_features": FULL_FEATURES,
                "database": "available" if FULL_FEATURES else "limited"
            }
        }
        
        # Test OpenAI connection
        if os.getenv("OPENAI_API_KEY"):
            try:
                import openai
                openai.api_key = os.getenv("OPENAI_API_KEY")
                
                # Test embeddings
                response = openai.embeddings.create(
                    model="text-embedding-3-small",
                    input=["test"]
                )
                status["services"]["openai_embeddings"] = "✅ Working"
                status["services"]["openai_embedding_dimensions"] = len(response.data[0].embedding)
            except Exception as e:
                status["services"]["openai_embeddings"] = f"❌ Error: {str(e)}"
        else:
            status["services"]["openai_embeddings"] = "❌ No API key"
        
        # Test ChromaDB
        if FULL_FEATURES:
            try:
                from services.vector_service import VectorService
                vector_service = VectorService()
                health = vector_service.health_check()
                status["services"]["chromadb"] = health
            except Exception as e:
                status["services"]["chromadb"] = f"❌ Error: {str(e)}"
        else:
            status["services"]["chromadb"] = "❌ Full features not available"
        
        return status
        
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/debug/documents/{client_id}")
async def debug_client_documents(client_id: int):
    """Debug endpoint to check client documents and processing status"""
    try:
        if not FULL_FEATURES:
            return {"error": "Full features not available for debugging"}
        
        db = SessionLocal()
        
        # Get client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            db.close()
            return {"error": "Client not found"}
        
        # Get all documents for this client
        documents = db.query(Document).filter(Document.client_id == client_id).all()
        
        debug_info = {
            "client": {
                "id": client.id,
                "name": client.name,
                "created_at": client.created_at.isoformat() if client.created_at else None
            },
            "documents": []
        }
        
        for doc in documents:
            doc_info = {
                "id": doc.id,
                "filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "processing_status": doc.processing_status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "file_path_exists": os.path.exists(doc.file_path) if doc.file_path else False,
                "has_extracted_text": bool(doc.extracted_text),
                "text_length": len(doc.extracted_text) if doc.extracted_text else 0,
                "has_chunk_ids": bool(doc.chunk_ids),
                "chunk_count": len(json.loads(doc.chunk_ids)) if doc.chunk_ids else 0
            }
            
            # Try to get vector store stats
            try:
                from services.vector_service import VectorService
                vector_service = VectorService()
                collection = vector_service.get_or_create_collection(client_id)
                
                # Try to find chunks for this document
                results = collection.get(
                    where={
                        "client_id": client_id,
                        "document_id": doc.id,
                        "source_type": "document"
                    }
                )
                doc_info["vector_chunks_found"] = len(results["ids"]) if results and results["ids"] else 0
                
            except Exception as e:
                doc_info["vector_error"] = str(e)
            
            debug_info["documents"].append(doc_info)
        
        db.close()
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/reprocess-document/{client_id}/{document_id}")
async def debug_reprocess_document(client_id: int, document_id: int):
    """Debug endpoint to manually reprocess a stuck document"""
    try:
        if not FULL_FEATURES:
            return {"error": "Full features not available"}
        
        db = SessionLocal()
        
        # Get document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client_id
        ).first()
        
        if not document:
            db.close()
            return {"error": "Document not found"}
        
        # Initialize services
        from services.document_service import DocumentService
        from services.vector_service import VectorService
        
        doc_service = DocumentService()
        vector_service = VectorService()
        
        processing_log = []
        
        # Step 1: Check file exists
        if document.file_path and os.path.exists(document.file_path):
            processing_log.append("✅ File exists on disk")
        else:
            processing_log.append("❌ File missing on disk")
            db.close()
            return {"error": "File missing", "log": processing_log}
        
        # Step 2: Update status to processing
        document.processing_status = "processing"
        db.commit()
        processing_log.append("🔄 Status updated to processing")
        
        try:
            # Step 3: Extract text
            extraction_result = doc_service.extract_text_from_file(
                file_path=document.file_path,
                file_type=document.file_type
            )
            
            if extraction_result["success"]:
                processing_log.append(f"✅ Text extracted: {extraction_result['word_count']} words")
                document.extracted_text = extraction_result["text"]
                document.metadata = json.dumps(extraction_result["metadata"])
            else:
                processing_log.append(f"❌ Text extraction failed: {extraction_result['error']}")
                document.processing_status = "failed"
                db.commit()
                db.close()
                return {"error": "Text extraction failed", "log": processing_log}
            
            # Step 4: Clear old vector data
            try:
                vector_service.delete_document_chunks(client_id, document_id)
                processing_log.append("🗑️ Cleared old vector chunks")
            except Exception as e:
                processing_log.append(f"⚠️ Error clearing old chunks: {str(e)}")
            
            # Step 5: Add to vector store
            chunk_ids = vector_service.add_document_to_vector_store(
                client_id=client_id,
                document_id=document.id,
                text=extraction_result["text"],
                metadata={
                    "filename": document.original_filename,
                    "file_type": document.file_type,
                    "reprocessed_at": datetime.now().isoformat()
                }
            )
            
            if chunk_ids:
                document.chunk_ids = json.dumps(chunk_ids)
                document.processing_status = "completed"
                processing_log.append(f"✅ Vector chunks created: {len(chunk_ids)}")
            else:
                document.processing_status = "failed"
                processing_log.append("❌ Failed to create vector chunks")
            
            db.commit()
            
            result = {
                "success": document.processing_status == "completed",
                "document": document.to_dict(),
                "processing_log": processing_log,
                "chunks_created": len(chunk_ids) if chunk_ids else 0
            }
            
            db.close()
            return result
            
        except Exception as e:
            document.processing_status = "failed"
            db.commit()
            db.close()
            processing_log.append(f"❌ Processing failed: {str(e)}")
            return {"error": str(e), "log": processing_log}
        
    except Exception as e:
        return {"error": str(e)}

# Also add this test endpoint for OpenAI
@app.get("/api/debug/test-openai")
async def test_openai_api():
    """Test OpenAI API connection"""
    try:
        if not os.getenv("OPENAI_API_KEY"):
            return {"error": "No OpenAI API key found"}
        
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # Test embeddings
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=["This is a test"]
        )
        
        return {
            "success": True,
            "model": "text-embedding-3-small",
            "embedding_dimensions": len(response.data[0].embedding),
            "usage": response.usage.total_tokens if hasattr(response, 'usage') else "N/A"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
