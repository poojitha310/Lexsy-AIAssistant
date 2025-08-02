from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import json
from database import get_db
from models.client import Client
from models.conversation import Conversation
from services.ai_service import AIService
from services.vector_service import VectorService

router = APIRouter()

# Pydantic models
class ChatRequest(BaseModel):
    question: str
    include_history: bool = True

class ChatResponse(BaseModel):
    success: bool
    question: str
    answer: str
    sources: List[dict]
    context_used: int
    tokens_used: int
    response_time: float
    conversation_id: int

class SearchRequest(BaseModel):
    query: str
    source_filter: Optional[str] = None  # "document" or "email"
    n_results: int = 5

@router.post("/{client_id}/ask", response_model=ChatResponse)
async def ask_question(
    client_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """Ask a question about client's documents and emails"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize AI service
        ai_service = AIService()
        
        # Get conversation history if requested
        conversation_history = None
        if request.include_history:
            recent_conversations = db.query(Conversation).filter(
                Conversation.client_id == client_id
            ).order_by(Conversation.created_at.desc()).limit(6).all()
            
            conversation_history = [
                {
                    "question": conv.question,
                    "answer": conv.answer
                }
                for conv in reversed(recent_conversations)  # Reverse to get chronological order
            ]
        
        # Generate AI response
        response = ai_service.generate_response(
            client_id=client_id,
            question=request.question,
            conversation_history=conversation_history
        )
        
        if not response["success"]:
            raise HTTPException(status_code=500, detail=response.get("error", "AI response generation failed"))
        
        # Save conversation to database
        conversation = Conversation(
            client_id=client_id,
            question=request.question,
            answer=response["answer"],
            context_sources=json.dumps([src["type"] + ":" + str(src.get("document_id", src.get("email_id", ""))) for src in response["sources"]]),
            similarity_scores=json.dumps([src["similarity_score"] for src in response["sources"]]),
            response_time=response["response_time"],
            tokens_used=response["tokens_used"]
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        return ChatResponse(
            success=True,
            question=request.question,
            answer=response["answer"],
            sources=response["sources"],
            context_used=response["context_used"],
            tokens_used=response["tokens_used"],
            response_time=response["response_time"],
            conversation_id=conversation.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(e)}")

@router.post("/{client_id}/search")
async def search_content(
    client_id: int,
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Search through client's documents and emails"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize vector service
        vector_service = VectorService()
        
        # Search for similar content
        results = vector_service.search_similar_content(
            client_id=client_id,
            query=request.query,
            n_results=request.n_results,
            source_filter=request.source_filter
        )
        
        return {
            "success": True,
            "query": request.query,
            "source_filter": request.source_filter,
            "results_count": len(results),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/{client_id}/conversations")
async def get_conversations(
    client_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get conversation history for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        conversations = db.query(Conversation).filter(
            Conversation.client_id == client_id
        ).order_by(Conversation.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "total_conversations": len(conversations),
            "conversations": [conv.to_dict() for conv in conversations]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")

@router.get("/{client_id}/conversations/{conversation_id}")
async def get_conversation(
    client_id: int,
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific conversation"""
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.client_id == client_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Parse sources and scores
        sources = []
        similarity_scores = []
        
        try:
            if conversation.context_sources:
                sources = json.loads(conversation.context_sources)
            if conversation.similarity_scores:
                similarity_scores = json.loads(conversation.similarity_scores)
        except:
            pass
        
        return {
            "conversation": conversation.to_dict(),
            "sources": sources,
            "similarity_scores": similarity_scores
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversation: {str(e)}")

@router.delete("/{client_id}/conversations/{conversation_id}")
async def delete_conversation(
    client_id: int,
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """Delete a conversation"""
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.client_id == client_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        db.delete(conversation)
        db.commit()
        
        return {
            "success": True,
            "message": "Conversation deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

@router.delete("/{client_id}/conversations")
async def clear_conversation_history(client_id: int, db: Session = Depends(get_db)):
    """Clear all conversation history for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Delete all conversations
        deleted_count = db.query(Conversation).filter(
            Conversation.client_id == client_id
        ).delete()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} conversations",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear conversations: {str(e)}")

@router.get("/{client_id}/suggestions")
async def get_question_suggestions(client_id: int, db: Session = Depends(get_db)):
    """Get suggested questions based on client's content"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get basic suggestions based on available content
        suggestions = []
        
        # Check what content is available
        documents_count = len(client.documents)
        emails_count = len(client.emails)
        
        if documents_count > 0:
            suggestions.extend([
                "What are the key terms in our agreements?",
                "Summarize the main legal documents",
                "What compliance requirements do we have?",
                "What are the important dates and deadlines?"
            ])
        
        if emails_count > 0:
            suggestions.extend([
                "What decisions were made in recent email discussions?",
                "What action items are pending?",
                "Who are the key people involved in our legal matters?",
                "What approvals or signatures are needed?"
            ])
        
        # Add client-specific suggestions for Lexsy
        if client.name == "Lexsy, Inc." or "lexsy" in client.email.lower():
            suggestions.extend([
                "What equity grant was proposed for John Smith?",
                "What are the vesting terms discussed in emails?", 
                "How many shares are available in our equity incentive plan?",
                "What documentation is needed for the advisor agreement?",
                "What board approvals are required?"
            ])
        
        # Limit to 8 suggestions
        suggestions = suggestions[:8]
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "suggestions": suggestions,
            "content_available": {
                "documents": documents_count,
                "emails": emails_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")

@router.post("/{client_id}/quick-summary")
async def get_quick_summary(client_id: int, db: Session = Depends(get_db)):
    """Get a quick summary of client's content"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize services
        ai_service = AIService()
        vector_service = VectorService()
        
        # Get stats
        stats = vector_service.get_client_content_stats(client_id)
        
        # Generate summary question
        summary_question = f"Please provide a brief overview of the key legal matters, important documents, and current status for {client.name}."
        
        # Get AI summary
        response = ai_service.generate_response(
            client_id=client_id,
            question=summary_question
        )
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "stats": stats,
            "summary": response.get("answer", "No summary available"),
            "sources_used": len(response.get("sources", [])),
            "last_updated": client.updated_at.isoformat() if client.updated_at else client.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")