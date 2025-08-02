from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    context_sources = Column(Text)  # JSON array of source document/email IDs
    similarity_scores = Column(Text)  # JSON array of similarity scores
    response_time = Column(Float)  # Response time in seconds
    tokens_used = Column(Integer)  # Number of tokens consumed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    client = relationship("Client", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(client_id={self.client_id}, question='{self.question[:50]}...')>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "question": self.question,
            "answer": self.answer,
            "response_time": self.response_time,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }