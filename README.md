# Lexsy AI Assistant - Legal Document & Email Analysis Platform

A comprehensive AI-powered assistant for lawyers to analyze legal documents and email communications. Built with FastAPI, ChromaDB, and OpenAI.

## 🚀 Features

### ✅ Core Requirements Implemented

1. **Gmail Integration**
   - OAuth 2.0 authentication with Google
   - Monitor and fetch Gmail messages
   - Sample Lexsy email thread with 5 back-and-forth messages
   - Real-time email ingestion

2. **Document Ingestion**
   - Support for PDF, DOCX, and TXT files
   - Intelligent text extraction with metadata
   - Sample Lexsy legal documents included

3. **Indexing & Search**
   - Text chunking with semantic overlap
   - OpenAI embeddings (text-embedding-3-small)
   - ChromaDB vector store with client isolation
   - Similarity search across documents and emails

4. **Chat Interface**
   - AI-powered Q&A with legal context
   - GPT-4 responses with source citations
   - Conversation history and context awareness

5. **Multi-Client Support**
   - Client-isolated data storage
   - Easy switching between client contexts
   - Separate vector stores per client

6. **Deployment Ready**
   - Railway deployment configuration
   - Environment variable management
   - Health checks and monitoring

## 🏗️ Architecture

```
Frontend (React/HTML) 
    ↕ 
FastAPI Backend
    ↕
├── Gmail API (OAuth 2.0)
├── Document Processing (PyPDF2, python-docx)
├── Vector Store (ChromaDB)
└── AI Services (OpenAI GPT-4)
    ↕
SQLite Database
```

## 📋 Requirements

- Python 3.9+
- OpenAI API key
- Google OAuth credentials (for Gmail integration)
- 2GB+ RAM for vector operations

## 🔧 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd lexsy-ai-assistant
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup
Copy `.env.example` to `.env` and configure:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Google OAuth (for Gmail)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Optional: Customize paths
DATABASE_URL=sqlite:///./lexsy.db
CHROMADB_PATH=./chromadb
UPLOAD_DIR=./uploads
```

### 4. Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:8000/api/auth/callback`

## 🚀 Running the Application

### Development
```bash
python main.py
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Docs**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/health
- **Frontend**: http://localhost:8000/app

## 📊 API Endpoints

### Authentication
- `GET /api/auth/gmail/auth-url` - Get Gmail OAuth URL
- `GET /api/auth/gmail/callback` - OAuth callback handler
- `GET /api/auth/gmail/status` - Check authentication status

### Clients
- `GET /api/clients/` - List all clients
- `POST /api/clients/` - Create new client
- `GET /api/clients/{id}/stats` - Get client statistics
- `POST /api/clients/init-sample-clients` - Initialize demo clients

### Documents
- `POST /api/documents/{client_id}/upload` - Upload document
- `GET /api/documents/{client_id}/documents` - List client documents
- `POST /api/documents/{client_id}/upload-sample-documents` - Load sample docs

### Emails
- `POST /api/emails/{client_id}/ingest-gmail` - Import Gmail messages
- `POST /api/emails/{client_id}/ingest-sample-emails` - Load sample emails
- `GET /api/emails/{client_id}/emails` - List client emails

### Chat
- `POST /api/chat/{client_id}/ask` - Ask AI question
- `POST /api/chat/{client_id}/search` - Search content
- `GET /api/chat/{client_id}/conversations` - Get chat history

## 🎯 Demo Usage

### 1. Initialize Demo Data
```bash
curl -X POST http://localhost:8000/api/init-demo
```

This creates:
- **Lexsy, Inc.** client with sample legal documents
- **TechCorp LLC** client for comparison
- Sample email thread about advisor equity grants
- Vector embeddings for all content

### 2. Sample Questions to Try

**For Lexsy, Inc.:**
- "What equity grant was proposed for John Smith?"
- "What are the vesting terms discussed in emails?"
- "How many shares are available in our equity incentive plan?"
- "What documentation is needed for the advisor agreement?"
- "What board approvals are required?"

**General Legal Questions:**
- "Summarize the key legal documents"
- "What compliance requirements do we have?"
- "What decisions were made in recent emails?"
- "What action items are pending?"

## 📁 Project Structure

```
lexsy-ai-assistant/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── database.py            # Database setup
├── requirements.txt       # Python dependencies
├── railway.json          # Railway deployment config
├── models/               # SQLAlchemy models
│   ├── client.py
│   ├── document.py
│   ├── email.py
│   └── conversation.py
├── services/             # Business logic
│   ├── gmail_service.py
│   ├── document_service.py
│   ├── vector_service.py
│   └── ai_service.py
├── api/                  # FastAPI routes
│   ├── auth.py
│   ├── clients.py
│   ├── documents.py
│   ├── emails.py
│   └── chat.py
├── uploads/              # Uploaded files
├── chromadb/             # Vector database
└── static/               # Frontend files
```

## 🚀 Deployment

### Railway Deployment

1. **Connect Repository**
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli
   
   # Login and deploy
   railway login
   railway link
   railway up
   ```

2. **Set Environment Variables**
   ```bash
   railway variables set OPENAI_API_KEY=your_key_here
   railway variables set GOOGLE_CLIENT_ID=your_client_id
   railway variables set GOOGLE_CLIENT_SECRET=your_secret
   ```

3. **Update OAuth Redirect URI**
   - Update Google OAuth settings with your Railway domain
   - Set redirect URI to: `https://your-app.railway.app/api/auth/callback`

### Alternative Deployments
- **Render**: Works with included `requirements.txt`
- **Heroku**: Add `Procfile` with `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- **DigitalOcean**: Use Docker with provided configuration

## 🔍 Sample Data

### Email Thread: Advisor Equity Grant
- 5-message conversation between Alex (Founder) and Kristina (Legal)
- Discusses 15,000 RSA grant for advisor John Smith
- Covers vesting terms, tax implications, and documentation needs

### Legal Documents
- **Board Approval**: Equity Incentive Plan approval
- **Advisor Agreement**: Template for advisor relationships  
- **Equity Incentive Plan**: 1M share pool with current availability

## 🛠️ Development

### Adding New Features
1. **Models**: Add to `models/` directory
2. **Services**: Implement business logic in `services/`
3. **API Routes**: Create endpoints in `api/`
4. **Database**: Run `alembic` migrations for schema changes

### Testing
```bash
# Run tests (when implemented)
pytest

# API testing
curl -X GET http://localhost:8000/health
```

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For questions or issues:
- Check the API documentation at `/api/docs`
- Review the health check at `/health`
- Examine logs for debugging information

---

**Built for Lexsy - Empowering lawyers with AI-powered document and email analysis.**