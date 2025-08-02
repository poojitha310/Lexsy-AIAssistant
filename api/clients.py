from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
from database import get_db
from models.client import Client
from services.vector_service import VectorService

router = APIRouter()

# Pydantic models for request/response
class ClientCreate(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    description: Optional[str] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    company: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: Optional[str]

@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all clients"""
    try:
        clients = db.query(Client).filter(Client.is_active == True).offset(skip).limit(limit).all()
        return [ClientResponse(**client.to_dict()) for client in clients]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch clients: {str(e)}")

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db)):
    """Get a specific client"""
    try:
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return ClientResponse(**client.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch client: {str(e)}")

@router.post("/", response_model=ClientResponse)
async def create_client(client_data: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client"""
    try:
        # Check if email already exists
        existing_client = db.query(Client).filter(Client.email == client_data.email).first()
        if existing_client:
            raise HTTPException(status_code=400, detail="Client with this email already exists")
        
        # Create new client
        client = Client(
            name=client_data.name,
            email=client_data.email,
            company=client_data.company,
            description=client_data.description
        )
        
        db.add(client)
        db.commit()
        db.refresh(client)
        
        return ClientResponse(**client.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    db: Session = Depends(get_db)
):
    """Update a client"""
    try:
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Update fields if provided
        if client_data.name is not None:
            client.name = client_data.name
        if client_data.email is not None:
            # Check if new email already exists
            existing_client = db.query(Client).filter(
                Client.email == client_data.email,
                Client.id != client_id
            ).first()
            if existing_client:
                raise HTTPException(status_code=400, detail="Email already exists")
            client.email = client_data.email
        if client_data.company is not None:
            client.company = client_data.company
        if client_data.description is not None:
            client.description = client_data.description
        if client_data.is_active is not None:
            client.is_active = client_data.is_active
        
        db.commit()
        db.refresh(client)
        
        return ClientResponse(**client.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update client: {str(e)}")

@router.delete("/{client_id}")
async def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Soft delete a client"""
    try:
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Soft delete
        client.is_active = False
        db.commit()
        
        # Also clean up vector store data
        vector_service = VectorService()
        vector_service.reset_client_data(client_id)
        
        return {"success": True, "message": "Client deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete client: {str(e)}")

@router.get("/{client_id}/stats")
async def get_client_stats(client_id: int, db: Session = Depends(get_db)):
    """Get statistics for a client"""
    try:
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get vector store stats
        vector_service = VectorService()
        vector_stats = vector_service.get_client_content_stats(client_id)
        
        # Get database stats
        documents_count = len(client.documents)
        emails_count = len(client.emails)
        conversations_count = len(client.conversations)
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "documents_uploaded": documents_count,
            "emails_ingested": emails_count,
            "conversations": conversations_count,
            "vector_store": vector_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client stats: {str(e)}")

@router.post("/init-sample-clients")
async def init_sample_clients(db: Session = Depends(get_db)):
    """Initialize sample clients for demo"""
    try:
        sample_clients = [
            {
                "name": "Lexsy, Inc.",
                "email": "legal@lexsy.com",
                "company": "Lexsy, Inc.",
                "description": "AI-powered legal technology startup. Focus on equity grants, advisor agreements, and corporate governance."
            },
            {
                "name": "TechCorp LLC", 
                "email": "counsel@techcorp.com",
                "company": "TechCorp LLC",
                "description": "Enterprise software company. Focus on employment agreements, vendor contracts, and compliance matters."
            }
        ]
        
        created_clients = []
        
        for client_data in sample_clients:
            # Check if client already exists
            existing_client = db.query(Client).filter(Client.email == client_data["email"]).first()
            if not existing_client:
                client = Client(**client_data)
                db.add(client)
                db.commit()
                db.refresh(client)
                created_clients.append(client.to_dict())
            else:
                created_clients.append(existing_client.to_dict())
        
        return {
            "success": True,
            "message": f"Initialized {len(created_clients)} sample clients",
            "clients": created_clients
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to initialize sample clients: {str(e)}")

@router.post("/{client_id}/reset-data")
async def reset_client_data(client_id: int, db: Session = Depends(get_db)):
    """Reset all data for a client (documents, emails, vector store)"""
    try:
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Delete all related data
        for document in client.documents:
            db.delete(document)
        for email in client.emails:
            db.delete(email)
        for conversation in client.conversations:
            db.delete(conversation)
        
        db.commit()
        
        # Reset vector store
        vector_service = VectorService()
        vector_service.reset_client_data(client_id)
        
        return {
            "success": True,
            "message": f"Reset all data for client {client.name}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset client data: {str(e)}")