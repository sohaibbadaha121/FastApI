from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    file_path = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed_date = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, processed, error
    raw_text = Column(Text, nullable=True)
    
    # Relationships
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    relationships = relationship("EntityRelationship", back_populates="document", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    # Core case information
    case_number = Column(String, nullable=True)
    court_name = Column(String, nullable=True)
    judgment_date = Column(String, nullable=True)
    session_date = Column(String, nullable=True)
    case_type = Column(String, nullable=True)
    case_subject = Column(Text, nullable=True)
    
    # Parties (stored as JSON arrays for multiple values)
    plaintiff = Column(JSON, nullable=True)
    defendant = Column(JSON, nullable=True)
    plaintiff_lawyer = Column(JSON, nullable=True)
    defendant_lawyer = Column(JSON, nullable=True)
    witnesses = Column(JSON, nullable=True)
    experts = Column(JSON, nullable=True)
    
    # Court officials
    judge = Column(JSON, nullable=True)
    chief_judge = Column(String, nullable=True)
    court_members = Column(JSON, nullable=True)
    court_clerk = Column(String, nullable=True)
    
    # Legal references
    legal_articles = Column(JSON, nullable=True)
    precedents = Column(JSON, nullable=True)
    applied_laws = Column(JSON, nullable=True)
    
    # Financial & Property
    financial_amounts = Column(JSON, nullable=True)
    properties = Column(JSON, nullable=True)
    compensations = Column(JSON, nullable=True)
    
    # Locations
    locations = Column(JSON, nullable=True)
    
    # Dates
    important_dates = Column(JSON, nullable=True)
    
    # Decision
    decision = Column(Text, nullable=True)
    verdict = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    # Store all extracted data as JSON for flexibility
    raw_entities = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document = relationship("Document", back_populates="entities")


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    from_entity = Column(String)
    relationship_type = Column(String)
    to_entity = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document = relationship("Document", back_populates="relationships")
