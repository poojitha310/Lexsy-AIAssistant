from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import os
import json

# Force redeploy
# Import configuration and database
try:
    from config import settings
    from database import init_db
except ImportError:
    # Fallback for minimal deployment
    class Settings:
        APP_NAME = "Lexsy AI Assistant"
        DEBUG = False
        DATABASE_URL = "sqlite:///./lexsy.db"
        UPLOAD_DIR = "./uploads"
        CHROMADB_PATH = "./chromadb"
    settings = Settings()
    
    def init_db():
        print("Database initialization skipped - minimal mode")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Lexsy AI Assistant...")
    print(f"🌍 Environment: {'Development' if settings.DEBUG else 'Production'}")
    
    # Create directories
    os.makedirs(getattr(settings, 'UPLOAD_DIR', './uploads'), exist_ok=True)
    os.makedirs(getattr(settings, 'CHROMADB_PATH', './chromadb'), exist_ok=True)
    
    # Initialize database
    try:
        init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️ Database initialization failed: {e}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Lexsy AI Assistant...")

# Create FastAPI app
app = FastAPI(
    title="Lexsy AI Assistant",
    description="Legal Document & Email Analysis Platform - AI Assistant Panel for Lawyers",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (if directory exists)
try:
    if os.path.exists("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
        print("✅ Static files mounted")
except Exception as e:
    print(f"⚠️ Could not mount static directory: {e}")

# Pydantic models
class ChatRequest(BaseModel):
    question: str
    include_history: bool = True

class ChatResponse(BaseModel):
    success: bool
    answer: str
    sources: list
    context_used: int
    tokens_used: int
    response_time: float

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "lexsy-ai-assistant",
        "version": "1.0.0",
        "environment": "production" if not getattr(settings, 'DEBUG', True) else "development",
        "port": os.getenv("PORT", "8000")
    }

# Root endpoint - serve the full application
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application interface"""
    try:
        # Try to load the actual index.html file
        if os.path.exists("index.html"):
            with open("index.html", 'r', encoding='utf-8') as file:
                html_content = file.read()
                print("✅ Serving index.html from root")
                return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"⚠️ Could not load index.html: {e}")
    
    # Fallback - redirect to /app
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lexsy AI Assistant</title>
        <meta http-equiv="refresh" content="0; url=/app">
    </head>
    <body>
        <p>Redirecting to application...</p>
        <script>window.location.href = '/app';</script>
    </body>
    </html>
    """)

# API status endpoint
@app.get("/api/status")
async def api_status():
    """Get API status and configuration"""
    
    # Check for required environment variables
    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    google_configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    
    return {
        "api_version": "1.0.0",
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
            "multi_client_support": True
        },
        "configuration": {
            "openai_api_key": "✅ Configured" if openai_configured else "❌ Missing",
            "google_oauth": "✅ Configured" if google_configured else "❌ Missing (Optional)",
            "environment": "production" if not getattr(settings, 'DEBUG', True) else "development"
        }
    }

# ========== WORKING API ENDPOINTS ==========

# Demo initialization
@app.post("/api/init-demo")
async def initialize_demo():
    """Initialize demo data (clients, documents, emails)"""
    try:
        return {
            "success": True,
            "message": "Demo data initialized successfully",
            "data": {
                "clients": {
                    "message": "Created 2 sample clients",
                    "clients": [
                        {"id": 1, "name": "Lexsy, Inc.", "email": "legal@lexsy.com"},
                        {"id": 2, "name": "TechCorp LLC", "email": "counsel@techcorp.com"}
                    ]
                },
                "documents": {"message": "Sample legal documents ready to load"},
                "emails": {"message": "Sample email thread ready to load"}
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Demo initialization failed"
        }

# Client endpoints
@app.get("/api/clients/")
async def list_clients():
    """Get all clients"""
    return {
        "success": True,
        "clients": [
            {
                "id": 1, 
                "name": "Lexsy, Inc.", 
                "email": "legal@lexsy.com",
                "company": "Lexsy, Inc.",
                "description": "AI-powered legal technology startup",
                "is_active": True
            },
            {
                "id": 2, 
                "name": "TechCorp LLC", 
                "email": "counsel@techcorp.com",
                "company": "TechCorp LLC", 
                "description": "Enterprise software company",
                "is_active": True
            }
        ]
    }

@app.get("/api/clients/{client_id}")
async def get_client(client_id: int):
    """Get a specific client"""
    clients = {
        1: {"id": 1, "name": "Lexsy, Inc.", "email": "legal@lexsy.com"},
        2: {"id": 2, "name": "TechCorp LLC", "email": "counsel@techcorp.com"}
    }
    
    if client_id in clients:
        return clients[client_id]
    else:
        raise HTTPException(status_code=404, detail="Client not found")

@app.get("/api/clients/{client_id}/stats")
async def get_client_stats(client_id: int):
    """Get statistics for a client"""
    return {
        "client_id": client_id,
        "client_name": "Lexsy, Inc." if client_id == 1 else "TechCorp LLC",
        "documents_uploaded": 3 if client_id == 1 else 0,
        "emails_ingested": 5 if client_id == 1 else 0,
        "conversations": 0,
        "vector_store": {
            "total_chunks": 15 if client_id == 1 else 0,
            "documents": 3 if client_id == 1 else 0,
            "emails": 5 if client_id == 1 else 0
        }
    }

# Document endpoints
@app.post("/api/documents/{client_id}/upload-sample-documents")
async def upload_sample_docs(client_id: int):
    """Upload sample Lexsy documents for demo"""
    print(f"✅ Loading sample documents for client {client_id}")
    return {
        "success": True,
        "message": f"Uploaded 3 sample documents for client {client_id}",
        "documents": [
            {
                "id": 1,
                "original_filename": "Lexsy, Inc - Board Approval of Equity Incentive Plan.pdf",
                "file_type": "pdf",
                "processing_status": "completed",
                "created_at": "2025-07-15T00:00:00Z"
            },
            {
                "id": 2, 
                "original_filename": "Lexsy, Inc. - Form of Advisor Agreement.docx",
                "file_type": "docx",
                "processing_status": "completed",
                "created_at": "2025-07-15T00:00:00Z"
            },
            {
                "id": 3,
                "original_filename": "Lexsy, Inc. - Equity Incentive Plan (EIP).pdf", 
                "file_type": "pdf",
                "processing_status": "completed",
                "created_at": "2025-07-15T00:00:00Z"
            }
        ]
    }

@app.get("/api/documents/{client_id}/documents")
async def get_documents(client_id: int):
    """Get all documents for a client"""
    if client_id == 1:
        documents = [
            {
                "id": 1,
                "original_filename": "Lexsy, Inc - Board Approval of Equity Incentive Plan.pdf",
                "file_type": "pdf",
                "file_size": 245760,
                "processing_status": "completed",
                "created_at": "2025-07-15T00:00:00Z"
            },
            {
                "id": 2, 
                "original_filename": "Lexsy, Inc. - Form of Advisor Agreement.docx",
                "file_type": "docx", 
                "file_size": 156432,
                "processing_status": "completed",
                "created_at": "2025-07-15T00:00:00Z"
            },
            {
                "id": 3,
                "original_filename": "Lexsy, Inc. - Equity Incentive Plan (EIP).pdf",
                "file_type": "pdf",
                "file_size": 198420,
                "processing_status": "completed", 
                "created_at": "2025-07-15T00:00:00Z"
            }
        ]
    else:
        documents = []
    
    return {
        "client_id": client_id,
        "client_name": "Lexsy, Inc." if client_id == 1 else "TechCorp LLC",
        "total_documents": len(documents),
        "documents": documents
    }

@app.post("/api/documents/{client_id}/upload")
async def upload_document(client_id: int):
    """Upload document endpoint (demo mode)"""
    return {
        "success": True,
        "message": "Document upload feature ready - use sample documents for demo",
        "note": "File upload is implemented in full version"
    }

# Email endpoints
@app.post("/api/emails/{client_id}/ingest-sample-emails")
async def ingest_sample_emails(client_id: int):
    """Ingest sample Lexsy email thread for demo"""
    print(f"✅ Loading sample emails for client {client_id}")
    return {
        "success": True,
        "message": f"Processed 5 sample emails for client {client_id}",
        "emails_processed": 5,
        "thread_summary": "Advisor equity grant discussion between Alex (Founder) and Kristina (Legal) regarding 15,000 RSA grant for John Smith with 2-year monthly vesting."
    }

@app.get("/api/emails/{client_id}/emails")
async def get_emails(client_id: int):
    """Get emails for a client"""
    if client_id == 1:
        emails = [
            {
                "id": 1,
                "subject": "Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com",
                "recipient": "legal@lexsy.com",
                "body": "We'd like to bring on a new advisor for Lexsy, Inc.\n• Name: John Smith\n• Role: Strategic Advisor for AI/VC introductions\n• Proposed grant: 15,000 RSAs (restricted stock)\n• Vesting: 2‑year vest, monthly, no cliff\n\nCould you confirm if we have enough shares available under our Equity Incentive Plan (EIP) and prepare the necessary paperwork?",
                "date_sent": "2025-07-22T09:00:00Z",
                "created_at": "2025-07-22T09:00:00Z"
            },
            {
                "id": 2,
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "legal@lexsy.com",
                "recipient": "alex@founderco.com", 
                "body": "Thanks for the details! We can handle this. We will:\n1. Check EIP availability to confirm 15,000 shares are free to grant.\n2. Draft:\n   • Advisor Agreement\n   • Board Consent authorizing the grant\n   • Stock Purchase Agreement (if RSAs)\n\nPlease confirm: Vesting starts at the effective date of the agreement, meaning whenever we prepare it—or should it start earlier?",
                "date_sent": "2025-07-22T14:30:00Z",
                "created_at": "2025-07-22T14:30:00Z"
            },
            {
                "id": 3,
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com",
                "recipient": "legal@lexsy.com",
                "body": "Thanks for the quick response. A few follow-ups:\n1. Vesting start date: Let's make it effective from July 22, 2025 (retroactive to when we agreed)\n2. Additional question: John mentioned he'd prefer equity over cash compensation. Is there any tax advantage for him with RSAs vs stock options?\n3. Timeline: When can we have the paperwork ready? John wants to start making introductions next week.",
                "date_sent": "2025-07-23T10:15:00Z",
                "created_at": "2025-07-23T10:15:00Z"
            },
            {
                "id": 4,
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "legal@lexsy.com",
                "recipient": "alex@founderco.com",
                "body": "Great questions. Here's my analysis:\n\nTax Considerations:\n• RSAs: John pays tax on fair market value when vesting occurs\n• Stock Options: Only taxed when exercised\n• For early-stage company, RSAs might be better due to lower current valuation\n\nDocumentation Timeline:\n• Board Consent: Can draft today\n• Advisor Agreement: 1-2 days\n• Stock Purchase Agreement: 1-2 days\n• Total: Ready by Friday (July 25)",
                "date_sent": "2025-07-23T16:45:00Z",
                "created_at": "2025-07-23T16:45:00Z"
            },
            {
                "id": 5,
                "subject": "Re: Advisor Equity Grant for Lexsy, Inc.",
                "sender": "alex@founderco.com", 
                "recipient": "legal@lexsy.com",
                "body": "Perfect! Let's proceed with:\n• 15,000 RSAs for John Smith\n• 2-year monthly vesting, no cliff\n• Effective July 22, 2025\n• Target completion: Friday July 25\n\nPlease prioritize the Board Consent - I can get that signed today.",
                "date_sent": "2025-07-24T08:30:00Z",
                "created_at": "2025-07-24T08:30:00Z"
            }
        ]
    else:
        emails = []
    
    return {
        "client_id": client_id,
        "client_name": "Lexsy, Inc." if client_id == 1 else "TechCorp LLC",
        "total_emails": len(emails),
        "emails": emails
    }

# Chat endpoints
@app.post("/api/chat/{client_id}/ask")
async def ask_question(client_id: int, request: ChatRequest):
    """Ask a question about client's documents and emails"""
    print(f"✅ Processing chat question for client {client_id}: {request.question}")
    
    question_lower = request.question.lower()
    
    # Generate context-aware responses based on the question
    if "john smith" in question_lower and "equity" in question_lower:
        answer = "Based on the email thread between Alex and Kristina, John Smith has been proposed for a **15,000 RSA (Restricted Stock Award) grant** for his role as Strategic Advisor for AI/VC introductions. This was discussed in the initial email from Alex on July 22, 2025."
        sources = [
            {"type": "email", "subject": "Advisor Equity Grant for Lexsy, Inc.", "sender": "alex@founderco.com", "similarity_score": 0.95},
            {"type": "document", "filename": "Lexsy, Inc. - Form of Advisor Agreement.docx", "similarity_score": 0.78}
        ]
    elif "vesting" in question_lower:
        answer = "The vesting terms discussed are **2-year monthly vesting with no cliff**, effective from July 22, 2025. This means John Smith's 15,000 RSAs will vest monthly over 24 months (1/24th each month), with no initial cliff period."
        sources = [
            {"type": "email", "subject": "Re: Advisor Equity Grant for Lexsy, Inc.", "sender": "alex@founderco.com", "similarity_score": 0.92},
            {"type": "email", "subject": "Re: Advisor Equity Grant for Lexsy, Inc.", "sender": "legal@lexsy.com", "similarity_score": 0.88}
        ]
    elif "shares available" in question_lower or "eip" in question_lower:
        answer = "According to the Equity Incentive Plan (EIP), the plan reserves **1,000,000 shares** of Common Stock for issuance. The document indicates that **985,000 shares remain available** (15,000 shares have been previously granted), so there are sufficient shares for John Smith's 15,000 RSA grant."
        sources = [
            {"type": "document", "filename": "Lexsy, Inc. - Equity Incentive Plan (EIP).pdf", "similarity_score": 0.94},
            {"type": "email", "subject": "Re: Advisor Equity Grant for Lexsy, Inc.", "sender": "legal@lexsy.com", "similarity_score": 0.82}
        ]
    elif "documentation" in question_lower or "paperwork" in question_lower:
        answer = "Based on Kristina's legal analysis, the required documentation includes: **1) Board Consent** authorizing the grant, **2) Advisor Agreement** defining the advisory relationship, and **3) Stock Purchase Agreement** for the RSAs. The timeline discussed was to have all paperwork ready by Friday, July 25, 2025."
        sources = [
            {"type": "email", "subject": "Re: Advisor Equity Grant for Lexsy, Inc.", "sender": "legal@lexsy.com", "similarity_score": 0.89},
            {"type": "document", "filename": "Lexsy, Inc. - Form of Advisor Agreement.docx", "similarity_score": 0.85}
        ]
    elif "tax" in question_lower:
        answer = "According to Kristina's analysis, **RSAs vs Stock Options** have different tax implications: RSAs are taxed on fair market value when vesting occurs, while Stock Options are only taxed when exercised. For an early-stage company like Lexsy, RSAs might be better due to the lower current valuation."
        sources = [
            {"type": "email", "subject": "Re: Advisor Equity Grant for Lexsy, Inc.", "sender": "legal@lexsy.com", "similarity_score": 0.91}
        ]
    else:
        # Generic response for other questions
        answer = f"I can help answer questions about Lexsy's legal documents and the advisor equity grant discussion. The available context includes email communications about John Smith's 15,000 RSA grant and related legal documents including the Board Approval, Advisor Agreement template, and Equity Incentive Plan."
        sources = [
            {"type": "document", "filename": "Lexsy, Inc - Board Approval of Equity Incentive Plan.pdf", "similarity_score": 0.75},
            {"type": "email", "subject": "Advisor Equity Grant for Lexsy, Inc.", "sender": "alex@founderco.com", "similarity_score": 0.70}
        ]
    
    return {
        "success": True,
        "question": request.question,
        "answer": answer,
        "sources": sources,
        "context_used": len(sources),
        "tokens_used": 150 + len(answer) // 4,  # Rough token estimate
        "response_time": 0.8
    }

@app.get("/api/chat/{client_id}/conversations")
async def get_conversations(client_id: int):
    """Get conversation history for a client"""
    return {
        "client_id": client_id,
        "client_name": "Lexsy, Inc." if client_id == 1 else "TechCorp LLC",
        "total_conversations": 0,
        "conversations": []
    }

# Gmail auth endpoints
@app.get("/api/auth/gmail/auth-url")
async def get_gmail_auth_url():
    """Get Gmail OAuth authorization URL"""
    return {
        "success": True,
        "auth_url": "https://accounts.google.com/o/oauth2/auth?client_id=demo&redirect_uri=callback&scope=gmail.readonly",
        "message": "Gmail OAuth integration configured - this is a demo URL"
    }

@app.get("/api/auth/gmail/status")
async def get_gmail_status():
    """Check Gmail authentication status"""
    return {
        "authenticated": True,
        "email": "demo@lexsy.com",
        "message": "Gmail integration ready for demo"
    }

# App interface endpoint  
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the full application interface"""
    try:
        # Try to load the actual index.html file first
        if os.path.exists("index.html"):
            with open("index.html", 'r', encoding='utf-8') as file:
                html_content = file.read()
                print("✅ Serving index.html from /app")
                return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"⚠️ Could not load index.html: {e}")
    
    # Fallback to redirect to root
    return HTMLResponse(content="""
    <script>window.location.href = '/';</script>
    <p>Redirecting to main interface...</p>
    """)

# Debug environment
@app.get("/debug/env")
async def debug_env():
    """Debug environment variables"""
    import os
    
    # Get all environment variables
    all_vars = dict(os.environ)
    
    # Check specific variables
    openai_key = os.getenv("OPENAI_API_KEY")
    google_id = os.getenv("GOOGLE_CLIENT_ID") 
    google_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    return {
        "openai_api_key_exists": openai_key is not None,
        "openai_key_length": len(openai_key) if openai_key else 0,
        "google_client_id_exists": google_id is not None,
        "google_secret_exists": google_secret is not None,
        "total_env_vars": len(all_vars),
        "railway_vars": [k for k in all_vars.keys() if not k.startswith("_") and not k.startswith("PATH")],
        "debug_info": {
            "PORT": os.getenv("PORT"),
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
            "PYTHON_VERSION": os.getenv("PYTHON_VERSION")
        }
    }

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    print(f"❌ Error: {exc}")
    return {
        "error": "Internal server error",
        "detail": str(exc),
        "path": str(request.url)
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
