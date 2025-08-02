import os
import uuid
import json
from typing import List, Dict, Optional, Tuple
import chromadb
from chromadb.config import Settings
import openai
from config import settings

class VectorService:
    def __init__(self):
        # Initialize OpenAI
        openai.api_key = settings.OPENAI_API_KEY
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMADB_PATH,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Collection names for different clients
        self.collections = {}
        
    def get_or_create_collection(self, client_id: int) -> chromadb.Collection:
        """Get or create a ChromaDB collection for a specific client"""
        collection_name = f"client_{client_id}"
        
        if collection_name not in self.collections:
            try:
                # Try to get existing collection
                collection = self.chroma_client.get_collection(name=collection_name)
            except:
                # Create new collection if it doesn't exist
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": f"Documents and emails for client {client_id}"}
                )
            
            self.collections[collection_name] = collection
        
        return self.collections[collection_name]
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using OpenAI"""
        try:
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            return []
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict]:
        """Split text into overlapping chunks"""
        if not text or len(text.strip()) == 0:
            return []
        
        # Split by sentences first to avoid breaking mid-sentence
        sentences = text.replace('\n', ' ').split('. ')
        
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_size = len(sentence.split())
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "word_count": current_size
                })
                
                # Start new chunk with overlap from previous chunk
                if overlap > 0:
                    words = current_chunk.split()
                    overlap_text = ' '.join(words[-overlap:]) if len(words) > overlap else current_chunk
                    current_chunk = overlap_text + " " + sentence
                    current_size = len(current_chunk.split())
                else:
                    current_chunk = sentence
                    current_size = sentence_size
            else:
                current_chunk += (" " if current_chunk else "") + sentence
                current_size += sentence_size
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "word_count": current_size
            })
        
        return chunks
    
    def add_document_to_vector_store(self, 
                                   client_id: int, 
                                   document_id: int,
                                   text: str, 
                                   metadata: Dict) -> List[str]:
        """Add document chunks to vector store"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Chunk the text
            chunks = self.chunk_text(text)
            if not chunks:
                print("⚠️ No chunks created from text")
                return []
            
            # Generate embeddings for chunks
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.generate_embeddings(chunk_texts)
            
            if not embeddings:
                print("❌ Failed to generate embeddings")
                return []
            
            # Create unique IDs for chunks
            chunk_ids = []
            documents = []
            metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"doc_{document_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                chunk_ids.append(chunk_id)
                documents.append(chunk["text"])
                
                chunk_metadata = {
                    "client_id": client_id,
                    "document_id": document_id,
                    "chunk_index": i,
                    "word_count": chunk["word_count"],
                    "source_type": "document",
                    **metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to ChromaDB
            collection.add(
                ids=chunk_ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            print(f"✅ Added {len(chunk_ids)} chunks to vector store for document {document_id}")
            return chunk_ids
            
        except Exception as e:
            print(f"❌ Error adding document to vector store: {e}")
            return []
    
    def add_email_to_vector_store(self,
                                 client_id: int,
                                 email_id: int, 
                                 email_content: str,
                                 metadata: Dict) -> List[str]:
        """Add email content to vector store"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # For emails, we typically treat each email as one chunk unless very long
            if len(email_content.split()) > 800:
                chunks = self.chunk_text(email_content, chunk_size=800, overlap=50)
            else:
                chunks = [{"text": email_content, "word_count": len(email_content.split())}]
            
            if not chunks:
                print("⚠️ No chunks created from email")
                return []
            
            # Generate embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.generate_embeddings(chunk_texts)
            
            if not embeddings:
                print("❌ Failed to generate embeddings for email")
                return []
            
            # Create unique IDs for chunks
            chunk_ids = []
            documents = []
            metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"email_{email_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                chunk_ids.append(chunk_id)
                documents.append(chunk["text"])
                
                chunk_metadata = {
                    "client_id": client_id,
                    "email_id": email_id,
                    "chunk_index": i,
                    "word_count": chunk["word_count"],
                    "source_type": "email",
                    **metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to ChromaDB
            collection.add(
                ids=chunk_ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            print(f"✅ Added {len(chunk_ids)} email chunks to vector store for email {email_id}")
            return chunk_ids
            
        except Exception as e:
            print(f"❌ Error adding email to vector store: {e}")
            return []
    
    def search_similar_content(self, 
                              client_id: int, 
                              query: str, 
                              n_results: int = 5,
                              source_filter: Optional[str] = None) -> List[Dict]:
        """Search for similar content in the vector store"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Generate embedding for query
            query_embedding = self.generate_embeddings([query])
            if not query_embedding:
                print("❌ Failed to generate query embedding")
                return []
            
            # Prepare where clause for filtering
            where_clause = {"client_id": client_id}
            if source_filter:
                where_clause["source_type"] = source_filter
            
            # Search in ChromaDB
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results and results["documents"]:
                for i in range(len(results["documents"][0])):
                    result = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity_score": 1 - results["distances"][0][i]  # Convert distance to similarity
                    }
                    formatted_results.append(result)
            
            print(f"🔍 Found {len(formatted_results)} similar chunks for query")
            return formatted_results
            
        except Exception as e:
            print(f"❌ Error searching vector store: {e}")
            return []
    
    def get_client_content_stats(self, client_id: int) -> Dict:
        """Get statistics about content stored for a client"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Get all items for this client
            results = collection.get(
                where={"client_id": client_id},
                include=["metadatas"]
            )
            
            if not results or not results["metadatas"]:
                return {
                    "total_chunks": 0,
                    "documents": 0,
                    "emails": 0,
                    "total_words": 0
                }
            
            # Count different content types
            document_chunks = 0
            email_chunks = 0
            total_words = 0
            unique_documents = set()
            unique_emails = set()
            
            for metadata in results["metadatas"]:
                if metadata.get("source_type") == "document":
                    document_chunks += 1
                    unique_documents.add(metadata.get("document_id"))
                elif metadata.get("source_type") == "email":
                    email_chunks += 1
                    unique_emails.add(metadata.get("email_id"))
                
                total_words += metadata.get("word_count", 0)
            
            return {
                "total_chunks": len(results["metadatas"]),
                "documents": len(unique_documents),
                "emails": len(unique_emails),
                "document_chunks": document_chunks,
                "email_chunks": email_chunks,
                "total_words": total_words
            }
            
        except Exception as e:
            print(f"❌ Error getting client stats: {e}")
            return {
                "total_chunks": 0,
                "documents": 0,
                "emails": 0,
                "total_words": 0
            }
    
    def delete_document_chunks(self, client_id: int, document_id: int) -> bool:
        """Delete all chunks for a specific document"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Get all chunk IDs for this document
            results = collection.get(
                where={
                    "client_id": client_id,
                    "document_id": document_id,
                    "source_type": "document"
                }
            )
            
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                print(f"✅ Deleted {len(results['ids'])} chunks for document {document_id}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error deleting document chunks: {e}")
            return False
    
    def delete_email_chunks(self, client_id: int, email_id: int) -> bool:
        """Delete all chunks for a specific email"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Get all chunk IDs for this email
            results = collection.get(
                where={
                    "client_id": client_id,
                    "email_id": email_id,
                    "source_type": "email"
                }
            )
            
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                print(f"✅ Deleted {len(results['ids'])} chunks for email {email_id}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error deleting email chunks: {e}")
            return False
    
    def reset_client_data(self, client_id: int) -> bool:
        """Delete all data for a specific client"""
        try:
            collection_name = f"client_{client_id}"
            
            # Delete the entire collection
            try:
                self.chroma_client.delete_collection(name=collection_name)
                if collection_name in self.collections:
                    del self.collections[collection_name]
                print(f"✅ Reset all data for client {client_id}")
                return True
            except:
                # Collection might not exist
                print(f"⚠️ No data found for client {client_id}")
                return True
                
        except Exception as e:
            print(f"❌ Error resetting client data: {e}")
            return False