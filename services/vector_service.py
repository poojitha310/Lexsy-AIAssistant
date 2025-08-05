import os
import uuid
import json
from typing import List, Dict, Optional, Tuple
import chromadb
from chromadb.config import Settings
import openai
from datetime import datetime
from config import settings

class VectorService:
    def __init__(self):
        # Initialize OpenAI
        openai.api_key = settings.OPENAI_API_KEY
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        
        # Initialize ChromaDB with better persistence settings
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMADB_PATH,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                persist_directory=settings.CHROMADB_PATH
            )
        )
        
        # Collection cache for better performance
        self.collections = {}
        
        print(f"✅ VectorService initialized with ChromaDB at: {settings.CHROMADB_PATH}")
        
    def get_or_create_collection(self, client_id: int) -> chromadb.Collection:
        """Get or create a ChromaDB collection for a specific client with strict isolation"""
        collection_name = f"client_{client_id}_legal_docs"
        
        if collection_name not in self.collections:
            try:
                # Try to get existing collection
                collection = self.chroma_client.get_collection(name=collection_name)
                print(f"📂 Retrieved existing collection for client {client_id}")
            except Exception:
                # Create new collection if it doesn't exist
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={
                        "description": f"Legal documents and emails for client {client_id}",
                        "client_id": client_id,
                        "created_at": datetime.now().isoformat(),
                        "content_types": ["documents", "emails"]
                    }
                )
                print(f"🆕 Created new collection for client {client_id}")
            
            self.collections[collection_name] = collection
        
        return self.collections[collection_name]
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using OpenAI with error handling"""
        if not texts:
            return []
            
        try:
            # Clean and validate texts
            clean_texts = []
            for text in texts:
                if isinstance(text, str) and text.strip():
                    # Truncate very long texts to avoid API limits
                    clean_text = text.strip()[:8000]  # OpenAI has token limits
                    clean_texts.append(clean_text)
                else:
                    clean_texts.append("Empty content")
            
            if not clean_texts:
                return []
            
            print(f"🔄 Generating embeddings for {len(clean_texts)} text chunks...")
            
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=clean_texts,
                encoding_format="float"
            )
            
            embeddings = [item.embedding for item in response.data]
            print(f"✅ Generated {len(embeddings)} embeddings successfully")
            return embeddings
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            # Return zero embeddings as fallback
            return [[0.0] * 1536 for _ in texts]  # text-embedding-3-small has 1536 dimensions
    
    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> List[Dict]:
        """Split text into overlapping chunks with better sentence handling"""
        if not text or len(text.strip()) == 0:
            return []
        
        # Clean the text
        text = text.replace('\n', ' ').replace('\t', ' ').strip()
        while '  ' in text:  # Remove multiple spaces
            text = text.replace('  ', ' ')
        
        # Split by sentences first to avoid breaking mid-sentence
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_words = sentence.split()
            sentence_size = len(sentence_words)
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "word_count": current_size,
                    "char_count": len(current_chunk)
                })
                
                # Start new chunk with overlap from previous chunk
                if overlap > 0 and current_size > overlap:
                    words = current_chunk.split()
                    overlap_text = ' '.join(words[-overlap:])
                    current_chunk = overlap_text + " " + sentence
                    current_size = len(overlap_text.split()) + sentence_size
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
                "word_count": current_size,
                "char_count": len(current_chunk)
            })
        
        print(f"📄 Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def add_document_to_vector_store(self, 
                                   client_id: int, 
                                   document_id: int,
                                   text: str, 
                                   metadata: Dict) -> List[str]:
        """Add document chunks to client-specific vector store"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Chunk the text
            chunks = self.chunk_text(text)
            if not chunks:
                print("⚠️ No chunks created from document text")
                return []
            
            # Generate embeddings for chunks
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.generate_embeddings(chunk_texts)
            
            if not embeddings or len(embeddings) != len(chunk_texts):
                print("❌ Failed to generate embeddings for document")
                return []
            
            # Create unique IDs and metadata for chunks
            chunk_ids = []
            documents = []
            metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"doc_{document_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                chunk_ids.append(chunk_id)
                documents.append(chunk["text"])
                
                chunk_metadata = {
                    "client_id": str(client_id),
                    "document_id": document_id,
                    "chunk_index": i,
                    "word_count": chunk["word_count"],
                    "char_count": chunk["char_count"],
                    "source_type": "document",
                    "content_type": "legal_document",
                    **metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to ChromaDB with client isolation
            collection.add(
                ids=chunk_ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            print(f"✅ Added {len(chunk_ids)} document chunks to vector store for client {client_id}, document {document_id}")
            return chunk_ids
            
        except Exception as e:
            print(f"❌ Error adding document to vector store: {e}")
            return []
    
    def add_email_to_vector_store(self,
                                 client_id: int,
                                 email_id: int, 
                                 email_content: str,
                                 metadata: Dict) -> List[str]:
        """Add email content to client-specific vector store"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # For emails, we typically treat each email as one chunk unless very long
            if len(email_content.split()) > 600:
                chunks = self.chunk_text(email_content, chunk_size=600, overlap=50)
            else:
                chunks = [{"text": email_content, "word_count": len(email_content.split()), "char_count": len(email_content)}]
            
            if not chunks:
                print("⚠️ No chunks created from email content")
                return []
            
            # Generate embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.generate_embeddings(chunk_texts)
            
            if not embeddings or len(embeddings) != len(chunk_texts):
                print("❌ Failed to generate embeddings for email")
                return []
            
            # Create unique IDs and metadata for chunks
            chunk_ids = []
            documents = []
            metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"email_{email_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                chunk_ids.append(chunk_id)
                documents.append(chunk["text"])
                
                chunk_metadata = {
                    "client_id": str(client_id),
                    "email_id": email_id,
                    "chunk_index": i,
                    "word_count": chunk["word_count"],
                    "char_count": chunk["char_count"],
                    "source_type": "email",
                    "content_type": "legal_email",
                    **metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to ChromaDB with client isolation
            collection.add(
                ids=chunk_ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            print(f"✅ Added {len(chunk_ids)} email chunks to vector store for client {client_id}, email {email_id}")
            return chunk_ids
            
        except Exception as e:
            print(f"❌ Error adding email to vector store: {e}")
            return []
    
    def search_similar_content(self, 
                              client_id: int, 
                              query: str, 
                              n_results: int = 5,
                              source_filter: Optional[str] = None) -> List[Dict]:
        """Search for similar content in client-specific vector store with enhanced filtering"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Generate embedding for query
            query_embedding = self.generate_embeddings([query])
            if not query_embedding:
                print("❌ Failed to generate query embedding")
                return []
            
            # Prepare where clause for client isolation and filtering
            where_clause = {"client_id": client_id}
            if source_filter:
                where_clause["source_type"] = source_filter
            
            print(f"🔍 Searching client {client_id} vector store with filter: {where_clause}")
            
            # Search in ChromaDB with client isolation
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=min(n_results, 20),  # Limit to prevent too many results
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results with enhanced metadata
            formatted_results = []
            if results and results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    similarity_score = 1 - results["distances"][0][i]  # Convert distance to similarity
                    
                    # Only include results with reasonable similarity
                    if similarity_score > 0.1:  # Filter out very poor matches
                        result = {
                            "id": results["ids"][0][i],
                            "content": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "similarity_score": round(similarity_score, 3),
                            "distance": round(results["distances"][0][i], 3)
                        }
                        formatted_results.append(result)
            
            # Sort by similarity score (highest first)
            formatted_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            print(f"🔍 Found {len(formatted_results)} similar chunks for client {client_id}")
            return formatted_results[:n_results]  # Return only requested number
            
        except Exception as e:
            print(f"❌ Error searching vector store for client {client_id}: {e}")
            return []
    
    def get_client_content_stats(self, client_id: int) -> Dict:
        """Get comprehensive statistics about content stored for a client"""
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
                    "total_words": 0,
                    "total_chars": 0,
                    "document_chunks": 0,
                    "email_chunks": 0
                }
            
            # Analyze content statistics
            document_chunks = 0
            email_chunks = 0
            total_words = 0
            total_chars = 0
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
                total_chars += metadata.get("char_count", 0)
            
            stats = {
                "total_chunks": len(results["metadatas"]),
                "documents": len(unique_documents),
                "emails": len(unique_emails),
                "document_chunks": document_chunks,
                "email_chunks": email_chunks,
                "total_words": total_words,
                "total_chars": total_chars,
                "avg_words_per_chunk": round(total_words / len(results["metadatas"]), 1) if results["metadatas"] else 0
            }
            
            print(f"📊 Client {client_id} stats: {stats}")
            return stats
            
        except Exception as e:
            print(f"❌ Error getting client stats for {client_id}: {e}")
            return {
                "total_chunks": 0,
                "documents": 0,
                "emails": 0,
                "total_words": 0,
                "total_chars": 0
            }
    
    def delete_document_chunks(self, client_id: int, document_id: int) -> bool:
        """Delete all chunks for a specific document with client isolation"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Get all chunk IDs for this document with client verification
            results = collection.get(
                where={
                    "client_id": client_id,
                    "document_id": document_id,
                    "source_type": "document"
                }
            )
            
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                print(f"✅ Deleted {len(results['ids'])} chunks for client {client_id}, document {document_id}")
                return True
            else:
                print(f"⚠️ No chunks found for client {client_id}, document {document_id}")
                return False
            
        except Exception as e:
            print(f"❌ Error deleting document chunks for client {client_id}, document {document_id}: {e}")
            return False
    
    def delete_email_chunks(self, client_id: int, email_id: int) -> bool:
        """Delete all chunks for a specific email with client isolation"""
        try:
            collection = self.get_or_create_collection(client_id)
            
            # Get all chunk IDs for this email with client verification
            results = collection.get(
                where={
                    "client_id": client_id,
                    "email_id": email_id,
                    "source_type": "email"
                }
            )
            
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                print(f"✅ Deleted {len(results['ids'])} chunks for client {client_id}, email {email_id}")
                return True
            else:
                print(f"⚠️ No chunks found for client {client_id}, email {email_id}")
                return False
            
        except Exception as e:
            print(f"❌ Error deleting email chunks for client {client_id}, email {email_id}: {e}")
            return False
    
    def reset_client_data(self, client_id: int) -> bool:
        """Delete all data for a specific client with complete isolation"""
        try:
            collection_name = f"client_{client_id}_legal_docs"
            
            # Delete the entire collection for this client
            try:
                self.chroma_client.delete_collection(name=collection_name)
                if collection_name in self.collections:
                    del self.collections[collection_name]
                print(f"✅ Reset all vector data for client {client_id}")
                return True
            except Exception as e:
                # Collection might not exist, which is fine
                print(f"⚠️ No vector data found for client {client_id} (collection doesn't exist)")
                return True
                
        except Exception as e:
            print(f"❌ Error resetting client data for {client_id}: {e}")
            return False
    
    def list_all_collections(self) -> List[Dict]:
        """List all collections for debugging purposes"""
        try:
            collections = self.chroma_client.list_collections()
            collection_info = []
            
            for collection in collections:
                try:
                    count = collection.count()
                    collection_info.append({
                        "name": collection.name,
                        "count": count,
                        "metadata": collection.metadata
                    })
                except:
                    collection_info.append({
                        "name": collection.name,
                        "count": 0,
                        "metadata": {}
                    })
            
            return collection_info
            
        except Exception as e:
            print(f"❌ Error listing collections: {e}")
            return []
    
    def health_check(self) -> Dict:
        """Check the health of the vector service"""
        try:
            # Test embedding generation
            test_embeddings = self.generate_embeddings(["test text"])
            
            # Test ChromaDB connection
            collections = self.chroma_client.list_collections()
            
            return {
                "status": "healthy",
                "embedding_service": "working" if test_embeddings else "failed",
                "chromadb_connection": "working",
                "total_collections": len(collections),
                "embedding_model": self.embedding_model
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "embedding_service": "unknown",
                "chromadb_connection": "failed"
            }
