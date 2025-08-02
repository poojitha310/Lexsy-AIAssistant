from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    gmail_message_id = Column(String(255), unique=True, index=True)
    gmail_thread_id = Column(String(255), index=True)
    subject = Column(String(500))
    sender = Column(String(255))
    recipient = Column(String(255))
    body = Column(Text)
    snippet = Column(Text)
    date_sent = Column(DateTime(timezone=True))
    labels = Column(Text)  # JSON array of Gmail labels
    chunk_ids = Column(Text)  # JSON array of ChromaDB IDs
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    client = relationship("Client", back_populates="emails")
    
    def __repr__(self):
        return f"<Email(subject='{self.subject}', sender='{self.sender}')>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "gmail_message_id": self.gmail_message_id,
            "gmail_thread_id": self.gmail_thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipient": self.recipient,
            "body": self.body,
            "snippet": self.snippet,
            "date_sent": self.date_sent.isoformat() if self.date_sent else None,
            "is_processed": self.is_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }