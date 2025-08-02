from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from database import get_db
from models.client import Client
from models.email import Email
from services.gmail_service import GmailService
from services.vector_service import VectorService
from services.ai_service import AIService

router = APIRouter()

@router.post("/{client_id}/ingest-gmail")
async def ingest_gmail_messages(
    client_id: int,
    query: str = Query("in:inbox", description="Gmail search query"),
    max_results: int = Query(50, description="Maximum number of emails to ingest"),
    db: Session = Depends(get_db)
):
    """Ingest Gmail messages for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize services
        gmail_service = GmailService()
        vector_service = VectorService()
        
        # Check Gmail authentication
        if not gmail_service.service:
            raise HTTPException(status_code=401, detail="Gmail not authenticated")
        
        # Search for messages
        messages = gmail_service.search_messages(query, max_results)
        
        if not messages:
            return {
                "success": True,
                "message": "No new messages found",
                "emails_processed": 0
            }
        
        processed_emails = []
        
        for gmail_msg in messages:
            # Check if email already exists
            existing_email = db.query(Email).filter(
                Email.gmail_message_id == gmail_msg["id"],
                Email.client_id == client_id
            ).first()
            
            if existing_email:
                continue
            
            # Create email record
            email = Email(
                client_id=client_id,
                gmail_message_id=gmail_msg["id"],
                gmail_thread_id=gmail_msg["thread_id"],
                subject=gmail_msg["subject"],
                sender=gmail_msg["sender"],
                recipient=gmail_msg["recipient"],
                body=gmail_msg["body"],
                snippet=gmail_msg["snippet"],
                date_sent=datetime.fromisoformat(gmail_msg["date"].replace("Z", "+00:00")) if gmail_msg.get("date") else None,
                labels=json.dumps(gmail_msg.get("label_ids", [])),
                is_processed=False
            )
            
            db.add(email)
            db.commit()
            db.refresh(email)
            
            # Add to vector store
            email_content = f"Subject: {gmail_msg['subject']}\nFrom: {gmail_msg['sender']}\nTo: {gmail_msg['recipient']}\n\n{gmail_msg['body']}"
            
            chunk_ids = vector_service.add_email_to_vector_store(
                client_id=client_id,
                email_id=email.id,
                email_content=email_content,
                metadata={
                    "subject": gmail_msg["subject"],
                    "sender": gmail_msg["sender"],
                    "recipient": gmail_msg["recipient"],
                    "date": gmail_msg.get("date", ""),
                    "thread_id": gmail_msg["thread_id"]
                }
            )
            
            if chunk_ids:
                email.chunk_ids = json.dumps(chunk_ids)
                email.is_processed = True
                db.commit()
            
            processed_emails.append(email.to_dict())
        
        return {
            "success": True,
            "message": f"Processed {len(processed_emails)} emails",
            "emails_processed": len(processed_emails),
            "emails": processed_emails
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail ingestion failed: {str(e)}")

@router.post("/{client_id}/ingest-sample-emails")
async def ingest_sample_emails(client_id: int, db: Session = Depends(get_db)):
    """Ingest sample Lexsy email thread for demo"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize services
        gmail_service = GmailService()
        vector_service = VectorService()
        ai_service = AIService()
        
        # Get sample emails
        sample_emails = gmail_service.get_lexsy_sample_emails()
        
        processed_emails = []
        
        for gmail_msg in sample_emails:
            # Check if email already exists
            existing_email = db.query(Email).filter(
                Email.gmail_message_id == gmail_msg["id"],
                Email.client_id == client_id
            ).first()
            
            if existing_email:
                processed_emails.append(existing_email.to_dict())
                continue
            
            # Parse date
            date_sent = None
            if gmail_msg.get("date"):
                try:
                    date_sent = datetime.fromisoformat(gmail_msg["date"].replace("Z", "+00:00"))
                except:
                    pass
            
            # Create email record
            email = Email(
                client_id=client_id,
                gmail_message_id=gmail_msg["id"],
                gmail_thread_id=gmail_msg["thread_id"],
                subject=gmail_msg["subject"],
                sender=gmail_msg["sender"],
                recipient=gmail_msg["recipient"],
                body=gmail_msg["body"],
                snippet=gmail_msg["snippet"],
                date_sent=date_sent,
                labels=json.dumps([]),
                is_processed=False
            )
            
            db.add(email)
            db.commit()
            db.refresh(email)
            
            # Add to vector store
            email_content = f"Subject: {gmail_msg['subject']}\nFrom: {gmail_msg['sender']}\nTo: {gmail_msg['recipient']}\nDate: {gmail_msg.get('date', '')}\n\n{gmail_msg['body']}"
            
            chunk_ids = vector_service.add_email_to_vector_store(
                client_id=client_id,
                email_id=email.id,
                email_content=email_content,
                metadata={
                    "subject": gmail_msg["subject"],
                    "sender": gmail_msg["sender"],
                    "recipient": gmail_msg["recipient"],
                    "date": gmail_msg.get("date", ""),
                    "thread_id": gmail_msg["thread_id"],
                    "sample_email": True
                }
            )
            
            if chunk_ids:
                email.chunk_ids = json.dumps(chunk_ids)
                email.is_processed = True
                db.commit()
            
            processed_emails.append(email.to_dict())
        
        # Generate thread summary
        thread_summary = ai_service.generate_email_thread_summary(sample_emails)
        
        return {
            "success": True,
            "message": f"Processed {len(processed_emails)} sample emails",
            "emails_processed": len(processed_emails),
            "emails": processed_emails,
            "thread_summary": thread_summary.get("summary", "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sample email ingestion failed: {str(e)}")

@router.get("/{client_id}/emails")
async def get_client_emails(
    client_id: int,
    skip: int = 0,
    limit: int = 50,
    thread_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get emails for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Build query
        query = db.query(Email).filter(Email.client_id == client_id)
        
        if thread_id:
            query = query.filter(Email.gmail_thread_id == thread_id)
        
        emails = query.order_by(Email.date_sent.desc()).offset(skip).limit(limit).all()
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "total_emails": len(emails),
            "thread_filter": thread_id,
            "emails": [email.to_dict() for email in emails]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")

@router.get("/{client_id}/emails/{email_id}")
async def get_email(
    client_id: int,
    email_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific email"""
    try:
        email = db.query(Email).filter(
            Email.id == email_id,
            Email.client_id == client_id
        ).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return {
            "email": email.to_dict(),
            "full_body": email.body
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch email: {str(e)}")

@router.get("/{client_id}/email-threads")
async def get_email_threads(client_id: int, db: Session = Depends(get_db)):
    """Get all email threads for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get unique threads
        threads = db.query(Email.gmail_thread_id, 
                          db.func.count(Email.id).label('message_count'),
                          db.func.max(Email.date_sent).label('latest_date'),
                          db.func.group_concat(Email.subject.distinct()).label('subjects')
                         ).filter(
            Email.client_id == client_id
        ).group_by(Email.gmail_thread_id).all()
        
        thread_list = []
        for thread in threads:
            # Get first email in thread for preview
            first_email = db.query(Email).filter(
                Email.client_id == client_id,
                Email.gmail_thread_id == thread.gmail_thread_id
            ).order_by(Email.date_sent.asc()).first()
            
            thread_list.append({
                "thread_id": thread.gmail_thread_id,
                "message_count": thread.message_count,
                "latest_date": thread.latest_date.isoformat() if thread.latest_date else None,
                "subject": first_email.subject if first_email else "Unknown",
                "participants": f"{first_email.sender} ↔ {first_email.recipient}" if first_email else "Unknown",
                "snippet": first_email.snippet if first_email else ""
            })
        
        return {
            "client_id": client_id,
            "total_threads": len(thread_list),
            "threads": thread_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch email threads: {str(e)}")

@router.delete("/{client_id}/emails/{email_id}")
async def delete_email(
    client_id: int,
    email_id: int,
    db: Session = Depends(get_db)
):
    """Delete an email"""
    try:
        email = db.query(Email).filter(
            Email.id == email_id,
            Email.client_id == client_id
        ).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Delete from vector store
        vector_service = VectorService()
        vector_service.delete_email_chunks(client_id, email_id)
        
        # Delete from database
        db.delete(email)
        db.commit()
        
        return {
            "success": True,
            "message": "Email deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete email: {str(e)}")

@router.post("/{client_id}/emails/{email_id}/reprocess")
async def reprocess_email(
    client_id: int,
    email_id: int,
    db: Session = Depends(get_db)
):
    """Reprocess an email (update vector store)"""
    try:
        email = db.query(Email).filter(
            Email.id == email_id,
            Email.client_id == client_id
        ).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Initialize services
        vector_service = VectorService()
        
        # Delete old chunks from vector store
        vector_service.delete_email_chunks(client_id, email_id)
        
        # Re-add to vector store
        email_content = f"Subject: {email.subject}\nFrom: {email.sender}\nTo: {email.recipient}\n\n{email.body}"
        
        chunk_ids = vector_service.add_email_to_vector_store(
            client_id=client_id,
            email_id=email.id,
            email_content=email_content,
            metadata={
                "subject": email.subject,
                "sender": email.sender,
                "recipient": email.recipient,
                "date": email.date_sent.isoformat() if email.date_sent else "",
                "thread_id": email.gmail_thread_id,
                "reprocessed": True
            }
        )
        
        if chunk_ids:
            email.chunk_ids = json.dumps(chunk_ids)
            email.is_processed = True
            db.commit()
        
        return {
            "success": True,
            "message": "Email reprocessed successfully",
            "chunks_created": len(chunk_ids) if chunk_ids else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reprocess email: {str(e)}")

@router.get("/{client_id}/gmail-search")
async def search_gmail(
    client_id: int,
    query: str = Query(..., description="Gmail search query"),
    max_results: int = Query(10, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Search Gmail messages (without importing)"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Initialize Gmail service
        gmail_service = GmailService()
        
        # Check authentication
        if not gmail_service.service:
            raise HTTPException(status_code=401, detail="Gmail not authenticated")
        
        # Search messages
        messages = gmail_service.search_messages(query, max_results)
        
        return {
            "success": True,
            "query": query,
            "results_count": len(messages),
            "messages": messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail search failed: {str(e)}")