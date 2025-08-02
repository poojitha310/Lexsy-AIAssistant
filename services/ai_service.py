import time
from typing import List, Dict, Optional
import openai
from config import settings
from .vector_service import VectorService

class AIService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.vector_service = VectorService()
        
        # System prompt for legal assistant
        self.system_prompt = """You are a helpful AI assistant for lawyers working with legal documents and email communications. 

Your role is to:
1. Analyze legal documents and email threads accurately
2. Provide clear, professional responses about legal matters
3. Extract key information from contracts, agreements, and correspondence
4. Help lawyers understand complex legal relationships and requirements

Guidelines:
- Be precise and factual in your responses
- Reference specific documents or emails when providing information
- Use professional legal language when appropriate
- If you're unsure about something, clearly state that
- Focus on the most relevant information for the lawyer's query
- When discussing legal matters, remind users to verify important details

You have access to the client's documents and email communications. Use this context to provide accurate, helpful responses."""
    
    def generate_response(self, 
                         client_id: int,
                         question: str, 
                         conversation_history: Optional[List[Dict]] = None) -> Dict:
        """Generate AI response using retrieved context"""
        start_time = time.time()
        
        try:
            # Search for relevant context
            context_results = self.vector_service.search_similar_content(
                client_id=client_id,
                query=question,
                n_results=5
            )
            
            # Build context from search results
            context_text = self._build_context_from_results(context_results)
            
            # Prepare messages for ChatGPT
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history if provided
            if conversation_history:
                for entry in conversation_history[-6:]:  # Last 6 exchanges
                    messages.append({"role": "user", "content": entry.get("question", "")})
                    messages.append({"role": "assistant", "content": entry.get("answer", "")})
            
            # Add current context and question
            user_message = f"""Context from documents and emails:
{context_text}

Question: {question}

Please provide a helpful response based on the available context."""

            messages.append({"role": "user", "content": user_message})
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.3,  # Lower temperature for more consistent responses
                top_p=0.9
            )
            
            # Extract response
            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Prepare source information
            sources = self._format_sources(context_results)
            
            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "context_used": len(context_results),
                "tokens_used": tokens_used,
                "response_time": round(response_time, 2)
            }
            
        except Exception as e:
            print(f"❌ Error generating AI response: {e}")
            return {
                "success": False,
                "error": str(e),
                "answer": "I apologize, but I encountered an error while processing your question. Please try again.",
                "sources": [],
                "context_used": 0,
                "tokens_used": 0,
                "response_time": time.time() - start_time
            }
    
    def _build_context_from_results(self, results: List[Dict]) -> str:
        """Build context text from search results"""
        if not results:
            return "No relevant context found."
        
        context_parts = []
        
        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            content = result.get("content", "")
            similarity = result.get("similarity_score", 0)
            
            # Format source information
            source_type = metadata.get("source_type", "unknown")
            if source_type == "document":
                source_info = f"Document: {metadata.get('filename', 'Unknown')}"
            elif source_type == "email":
                source_info = f"Email: {metadata.get('subject', 'Unknown Subject')} from {metadata.get('sender', 'Unknown')}"
            else:
                source_info = f"Source: {source_type}"
            
            context_parts.append(f"""[{i}] {source_info} (Relevance: {similarity:.2f})
{content}
""")
        
        return "\n".join(context_parts)
    
    def _format_sources(self, results: List[Dict]) -> List[Dict]:
        """Format source information for the frontend"""
        sources = []
        
        for result in results:
            metadata = result.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            
            source_info = {
                "type": source_type,
                "similarity_score": result.get("similarity_score", 0),
                "content_preview": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", "")
            }
            
            if source_type == "document":
                source_info.update({
                    "filename": metadata.get("filename", "Unknown"),
                    "document_id": metadata.get("document_id"),
                    "chunk_index": metadata.get("chunk_index", 0)
                })
            elif source_type == "email":
                source_info.update({
                    "subject": metadata.get("subject", "Unknown Subject"),
                    "sender": metadata.get("sender", "Unknown"),
                    "date": metadata.get("date", "Unknown"),
                    "email_id": metadata.get("email_id"),
                    "chunk_index": metadata.get("chunk_index", 0)
                })
            
            sources.append(source_info)
        
        return sources
    
    def generate_document_summary(self, text: str, filename: str) -> Dict:
        """Generate a summary of a document"""
        try:
            messages = [
                {"role": "system", "content": "You are a legal document analysis assistant. Provide clear, concise summaries of legal documents, highlighting key terms, parties, dates, and important provisions."},
                {"role": "user", "content": f"""Please provide a summary of this legal document titled "{filename}":

{text[:4000]}  

Include:
1. Document type and purpose
2. Key parties involved
3. Important dates
4. Main terms and provisions
5. Any notable requirements or obligations

Keep the summary professional and concise."""}
            ]
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            
            return {
                "success": True,
                "summary": summary,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            print(f"❌ Error generating document summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": "Unable to generate summary."
            }
    
    def generate_email_thread_summary(self, emails: List[Dict]) -> Dict:
        """Generate a summary of an email thread"""
        try:
            # Combine emails into a conversation
            thread_text = ""
            for email in emails:
                thread_text += f"""
From: {email.get('sender', 'Unknown')}
To: {email.get('recipient', 'Unknown')}
Date: {email.get('date', 'Unknown')}
Subject: {email.get('subject', 'Unknown')}

{email.get('body', '')}

---
"""
            
            messages = [
                {"role": "system", "content": "You are a legal communication analysis assistant. Summarize email threads focusing on key decisions, action items, legal requirements, and important deadlines."},
                {"role": "user", "content": f"""Please provide a summary of this email thread:

{thread_text[:4000]}

Include:
1. Main topic and purpose of the communication
2. Key decisions made
3. Action items and responsibilities
4. Important deadlines or dates
5. Legal or business requirements discussed

Keep the summary professional and focused on actionable information."""}
            ]
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            
            return {
                "success": True,
                "summary": summary,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            print(f"❌ Error generating email thread summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": "Unable to generate email thread summary."
            }
    
    def suggest_follow_up_questions(self, question: str, answer: str, context_results: List[Dict]) -> List[str]:
        """Suggest relevant follow-up questions"""
        try:
            # Analyze available context to suggest questions
            context_types = set()
            for result in context_results:
                metadata = result.get("metadata", {})
                if metadata.get("source_type") == "document":
                    context_types.add(f"document: {metadata.get('filename', 'unknown')}")
                elif metadata.get("source_type") == "email":
                    context_types.add("email thread")
            
            suggestions = []
            
            # General follow-up questions based on legal context
            if "equity" in question.lower() or "stock" in question.lower():
                suggestions.extend([
                    "What are the vesting requirements for this equity grant?",
                    "Are there any performance milestones or conditions?",
                    "What documentation is needed to complete this grant?"
                ])
            
            if "agreement" in question.lower() or "contract" in question.lower():
                suggestions.extend([
                    "What are the key terms and conditions?",
                    "What are the termination provisions?",
                    "Are there any compliance requirements?"
                ])
            
            if "board" in question.lower():
                suggestions.extend([
                    "What board approvals are required?",
                    "When is the next board meeting?",
                    "What documentation needs board review?"
                ])
            
            # Limit to 3 most relevant suggestions
            return suggestions[:3]
            
        except Exception as e:
            print(f"❌ Error generating follow-up questions: {e}")
            return []