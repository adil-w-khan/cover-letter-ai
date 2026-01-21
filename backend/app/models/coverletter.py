from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    input_full_name = Column(String(200), nullable=False)
    job_title = Column(String(200), nullable=False)
    company_name = Column(String(200), nullable=False)
    tone = Column(String(50), nullable=False)  # "professional" | "friendly"
    job_description = Column(Text, nullable=False)
    extra_notes = Column(Text, nullable=True)

    resume_text = Column(Text, nullable=False)   # extracted text only
    ai_draft = Column(Text, nullable=False)
    edited_final = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    user = relationship("User")
