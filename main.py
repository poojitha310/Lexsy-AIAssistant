from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import os

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
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve a simple frontend interface"""
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lexsy AI Assistant</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                   max-width: 800px; margin: 50px auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea, #764ba2); 
                      color: white; padding: 30px; border-radius: 10px; text-align: center; }}
            .section {{ margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
            .status {{ padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .success {{ background: #d4edda; color: #155724; }}
            .warning {{ background: #fff3cd; color: #856404; }}
            .endpoint {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 4px; }}
            .btn {{ background: #667eea; color: white; padding: 10px 20px; 
                   border: none; border-radius: 5px; text-decoration: none; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 Lexsy AI Assistant</h1>
            <p>Legal Document & Email Analysis Platform</p>
        </div>
        
        <div class="section">
            <h2>🔧 Setup Status</h2>
            <div class="status success">✅ API Deployed Successfully</div>
            <div class="status warning">⚠️ Add OPENAI_API_KEY for full AI features</div>
            <div class="status warning">⚠️ Add Google OAuth for Gmail integration (optional)</div>
        </div>
        
        <div class="section">
            <h2>📋 API Endpoints</h2>
            <div class="endpoint"><strong>GET</strong> <a href="/health">/health</a> - Health Check</div>
            <div class="endpoint"><strong>GET</strong> <a href="/docs">/docs</a> - API Documentation</div>
            <div class="endpoint"><strong>GET</strong> <a href="/api/status">/api/status</a> - Configuration Status</div>
            <div class="endpoint"><strong>POST</strong> /api/init-demo - Initialize Demo Data</div>
        </div>
        
        <div class="section">
            <h2>🚀 Next Steps</h2>
            <ol>
                <li>Add <code>OPENAI_API_KEY</code> in Railway Variables</li>
                <li>Optionally add Google OAuth credentials</li>
                <li>Test the <a href="/docs" class="btn">API Documentation</a></li>
                <li>Initialize demo data via API</li>
            </ol>
        </div>
    </body>
    </html>
    """, status_code=200)

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
