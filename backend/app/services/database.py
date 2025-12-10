from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import datetime

# 1. ตั้งค่าการเชื่อมต่อ SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./ucb_database.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 2. สร้างตาราง Candidates (รวมทุกอย่างไว้ที่นี่)
class CandidateDB(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    candidate_name = Column(String, index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    final_score = Column(Float, default=0.0)
    
    # เก็บ JSON ก้อนใหญ่ทั้งหมดไว้เผื่อดึงรายละเอียด
    full_json_data = Column(JSON) 
    
    created_at = Column(DateTime, default=datetime.datetime.now)

# 3. สั่งสร้างตารางถ้ายังไม่มี
Base.metadata.create_all(bind=engine)

# 4. Dependency สำหรับใช้ใน Router
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()