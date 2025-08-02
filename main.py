from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import os
from pathlib import Path

from config import settings
from database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Lexsy AI Assistant...")
    print(f"📁 Upload directory: {settings.UPLOAD_DIR}")
    print(f"🗄️ Database: {settings.DATABASE_URL}")
    print(f"🧠 Vector store: {settings.CHROMADB_PATH}")
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMADB_PATH, exist_ok=True)
    print("✅ Directories created")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Lexsy AI Assistant...")

# Create FastAPI app
app = FastAPI(
    title="Lexsy AI Assistant",
    description="Legal Document & Email Analysis Platform - AI Assistant Panel for Lawyers",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "lexsy-ai-assistant",
        "version": "1.0.0",
        "environment": "development" if settings.DEBUG else "production"
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Lexsy AI Assistant API",
        "version": "1.0.0",
        "description": "Legal Document & Email Analysis Platform",
        "endpoints": {
            "docs": "/api/docs",
            "health": "/health",
            "frontend": "/app"
        }
    }

# API status endpoint
@app.get("/api/status")
async def api_status():
    """Get API status and configuration"""
    return {
        "api_version": "1.0.0",
        "services": {
            "database": "SQLite" if "sqlite" in settings.DATABASE_URL else "PostgreSQL",
            "vector_store": "ChromaDB",
            "ai_model": settings.OPENAI_MODEL,
            "embedding_model": settings.OPENAI_EMBEDDING_MODEL
        },
        "features": {
            "gmail_integration": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            "openai_integration": bool(settings.OPENAI_API_KEY),
            "document_upload": True,
            "multi_client_support": True
        },
        "limits": {
            "max_file_size_mb": settings.MAX_FILE_SIZE / (1024 * 1024),
            "upload_directory": settings.UPLOAD_DIR
        }
    }

# Import and include API routers
from api import auth, documents, clients, emails, chat

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

# Serve static files for frontend
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the frontend application
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend application"""
    frontend_file = Path("static/index.html")
    if frontend_file.exists():
        return HTMLResponse(content=frontend_file.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Lexsy AI Assistant</title></head>
                <body>
                    <h1>Lexsy AI Assistant</h1>
                    <p>Frontend not yet deployed. API is running at <a href="/api/docs">/api/docs</a></p>
                </body>
            </html>
            """,
            status_code=200
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for better error responses"""
    if settings.DEBUG:
        import traceback
        return {
            "error": "Internal server error",
            "detail": str(exc),
            "traceback": traceback.format_exc() if settings.DEBUG else None
        }
    else:
        return {
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }

# Demo initialization endpoint
@app.post("/api/init-demo")
async def initialize_demo():
    """Initialize demo data (clients, documents, emails)"""
    try:
        from sqlalchemy.orm import Session
        from database import SessionLocal
        from api.clients import init_sample_clients
        from api.documents import upload_sample_documents
        from api.emails import ingest_sample_emails
        
        db = SessionLocal()
        
        try:
            # Initialize sample clients
            clients_response = await init_sample_clients(db=db)
            
            # Get Lexsy client ID
            lexsy_client = None
            for client in clients_response["clients"]:
                if "lexsy" in client["email"].lower():
                    lexsy_client = client
                    break
            
            if not lexsy_client:
                raise Exception("Lexsy client not found")
            
            lexsy_client_id = lexsy_client["id"]
            
            # Upload sample documents for Lexsy
            docs_response = await upload_sample_documents(client_id=lexsy_client_id, db=db)
            
            # Ingest sample emails for Lexsy
            emails_response = await ingest_sample_emails(client_id=lexsy_client_id, db=db)
            
            return {
                "success": True,
                "message": "Demo data initialized successfully",
                "data": {
                    "clients": clients_response,
                    "documents": docs_response,
                    "emails": emails_response
                }
            }
            
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo initialization failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )