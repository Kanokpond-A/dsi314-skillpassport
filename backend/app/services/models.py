from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.services.database import Base

class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # เชื่อมโยงกับตารางผลวิเคราะห์
    analysis = relationship("ResumeAnalysis", back_populates="candidate", uselist=False, cascade="all, delete-orphan")

class ResumeAnalysis(Base):
    __tablename__ = "resume_analysis"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    
    fit_score = Column(Float)
    matched_skills = Column(JSON)  # เก็บเป็น JSON Array เช่น ["Python", "SQL"]
    missing_gaps = Column(JSON)    # เก็บเป็น JSON Array
    summary = Column(Text)
    
    created_at = Column(DateTime, default=datetime.now)

    candidate = relationship("Candidate", back_populates="analysis")