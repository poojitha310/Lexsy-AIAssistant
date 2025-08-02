from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
app.mount("/static", StaticFiles(directory="static"), name="static")
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

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Lexsy AI Assistant API",
        "version": "1.0.0",
        "description": "Legal Document & Email Analysis Platform",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api_status": "/api/status"
        }
    }

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

# Try to import and include API routers
try:
    from api import (
        auth_router,
        clients_router, 
        documents_router,
        emails_router,
        chat_router
    )
    
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(clients_router, prefix="/api/clients", tags=["Clients"])
    app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
    app.include_router(emails_router, prefix="/api/emails", tags=["Emails"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    
    print("✅ All API routes loaded successfully")
    
except ImportError as e:
    print(f"⚠️ Some API routes not available: {e}")
    
    # Add basic placeholder endpoints
    @app.get("/api/clients/")
    async def list_clients():
        return {"message": "Clients endpoint - full features loading..."}
    
    @app.post("/api/init-demo")
    async def init_demo_placeholder():
        return {"message": "Demo initialization - dependencies loading..."}

# Demo initialization endpoint (simplified version)
@app.post("/api/init-demo")
async def initialize_demo():
    """Initialize demo data (clients, documents, emails)"""
    try:
        return {
            "success": True,
            "message": "Demo data initialized successfully",
            "note": "This is a simplified version. Full features will be available once all dependencies are loaded.",
            "next_steps": [
                "Add OPENAI_API_KEY to environment variables",
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET for Gmail (optional)",
                "All dependencies will be loaded automatically"
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Demo initialization failed"
        }

# Simple frontend placeholder
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
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the actual index.html file"""
    html_file_path = "index.html"
    
    if os.path.exists(html_file_path):
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        return HTMLResponse(content=html_content)
    else:
        # Fallback to the basic HTML if file not found
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Lexsy AI Assistant</title></head>
        <body>
            <h1>Frontend Loading...</h1>
            <p>The index.html file was not found. Please check the file structure.</p>
            <a href="/docs">View API Documentation</a>
        </body>
        </html>
        """)
    
        
@app.get("/", response_class=HTMLResponse)
async def root_redirect():
    """Redirect root to the app interface"""
    return HTMLResponse(content="""
    <script>window.location.href = '/app';</script>
    <p>Redirecting to app...</p>
    """)        

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return {
        "error": "Internal server error",
        "detail": str(exc),
        "path": str(request.url)
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
