from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from database import get_db
from models.client import Client
from models.document import Document
from services.document_service import DocumentService
from services.vector_service import VectorService
from services.ai_service import AIService

router = APIRouter()

@router.post("/{client_id}/upload")
async def upload_document(
    client_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a document for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Read file content
        file_content = await file.read()
        
        # Initialize services
        doc_service = DocumentService()
        vector_service = VectorService()
        ai_service = AIService()
        
        # Save uploaded file
        save_result = await doc_service.save_uploaded_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type
        )
        
        if not save_result["success"]:
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
        
        try:
            # Extract text from document
            extraction_result = doc_service.extract_text_from_file(
                file_path=save_result["file_path"],
                file_type=save_result["file_type"]
            )
            
            if not extraction_result["success"]:
                document.processing_status = "failed"
                db.commit()
                raise HTTPException(status_code=500, detail=f"Text extraction failed: {extraction_result['error']}")
            
            # Update document with extracted text
            document.extracted_text = extraction_result["text"]
            document.metadata = json.dumps(extraction_result["metadata"])
            
            # Add to vector store
            chunk_ids = vector_service.add_document_to_vector_store(
                client_id=client_id,
                document_id=document.id,
                text=extraction_result["text"],
                metadata={
                    "filename": document.original_filename,
                    "file_type": document.file_type,
                    "created_at": document.created_at.isoformat()
                }
            )
            
            if chunk_ids:
                document.chunk_ids = json.dumps(chunk_ids)
                document.processing_status = "completed"
            else:
                document.processing_status = "failed"
            
            db.commit()
            
            # Generate document summary
            summary_result = ai_service.generate_document_summary(
                text=extraction_result["text"],
                filename=document.original_filename
            )
            
            return {
                "success": True,
                "document": document.to_dict(),
                "extraction": {
                    "word_count": extraction_result["word_count"],
                    "char_count": extraction_result["char_count"]
                },
                "vector_store": {
                    "chunks_created": len(chunk_ids) if chunk_ids else 0
                },
                "summary": summary_result.get("summary", "Summary not available")
            }
            
        except Exception as e:
            # Update document status on processing failure
            document.processing_status = "failed"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/{client_id}/documents")
async def get_client_documents(
    client_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all documents for a client"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get documents
        documents = db.query(Document).filter(
            Document.client_id == client_id
        ).offset(skip).limit(limit).all()
        
        return {
            "client_id": client_id,
            "client_name": client.name,
            "total_documents": len(documents),
            "documents": [doc.to_dict() for doc in documents]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")

@router.get("/{client_id}/documents/{document_id}")
async def get_document(
    client_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific document"""
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Parse metadata
        metadata = {}
        if document.metadata:
            try:
                metadata = json.loads(document.metadata)
            except:
                pass
        
        return {
            "document": document.to_dict(),
            "metadata": metadata,
            "text_preview": document.extracted_text[:500] + "..." if document.extracted_text and len(document.extracted_text) > 500 else document.extracted_text
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch document: {str(e)}")

@router.delete("/{client_id}/documents/{document_id}")
async def delete_document(
    client_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document"""
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector store
        vector_service = VectorService()
        vector_service.delete_document_chunks(client_id, document_id)
        
        # Delete file from filesystem
        doc_service = DocumentService()
        if document.file_path:
            doc_service.cleanup_file(document.file_path)
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        return {
            "success": True,
            "message": "Document deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.post("/{client_id}/upload-sample-documents")
async def upload_sample_documents(client_id: int, db: Session = Depends(get_db)):
    """Upload sample Lexsy documents for demo"""
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
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
            
            # Add to vector store
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
        
        return {
            "success": True,
            "message": f"Uploaded {len(uploaded_docs)} sample documents",
            "documents": uploaded_docs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload sample documents: {str(e)}")

@router.get("/{client_id}/documents/{document_id}/text")
async def get_document_text(
    client_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get the full extracted text of a document"""
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "document_id": document_id,
            "filename": document.original_filename,
            "text": document.extracted_text,
            "word_count": len(document.extracted_text.split()) if document.extracted_text else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch document text: {str(e)}")

@router.post("/{client_id}/documents/{document_id}/reprocess")
async def reprocess_document(
    client_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Reprocess a document (re-extract text and update vector store)"""
    try:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.client_id == client_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document.file_path:
            raise HTTPException(status_code=400, detail="No file path available for reprocessing")
        
        # Initialize services
        doc_service = DocumentService()
        vector_service = VectorService()
        
        # Update status
        document.processing_status = "processing"
        db.commit()
        
        try:
            # Re-extract text
            extraction_result = doc_service.extract_text_from_file(
                file_path=document.file_path,
                file_type=document.file_type
            )
            
            if not extraction_result["success"]:
                document.processing_status = "failed"
                db.commit()
                raise HTTPException(status_code=500, detail=f"Text extraction failed: {extraction_result['error']}")
            
            # Delete old chunks from vector store
            vector_service.delete_document_chunks(client_id, document_id)
            
            # Update document with new text
            document.extracted_text = extraction_result["text"]
            document.metadata = json.dumps(extraction_result["metadata"])
            
            # Add new chunks to vector store
            chunk_ids = vector_service.add_document_to_vector_store(
                client_id=client_id,
                document_id=document.id,
                text=extraction_result["text"],
                metadata={
                    "filename": document.original_filename,
                    "file_type": document.file_type,
                    "reprocessed_at": document.updated_at.isoformat() if document.updated_at else None
                }
            )
            
            if chunk_ids:
                document.chunk_ids = json.dumps(chunk_ids)
                document.processing_status = "completed"
            else:
                document.processing_status = "failed"
            
            db.commit()
            
            return {
                "success": True,
                "message": "Document reprocessed successfully",
                "document": document.to_dict(),
                "chunks_created": len(chunk_ids) if chunk_ids else 0
            }
            
        except Exception as e:
            document.processing_status = "failed"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reprocess document: {str(e)}")