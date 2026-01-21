from pydantic import BaseModel, Field
from typing import Optional, Literal

Tone = Literal["professional", "friendly"]

class GenerateCoverLetterRequest(BaseModel):
    input_full_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    tone: Tone
    job_description: str = Field(min_length=20, max_length=20000)
    extra_notes: Optional[str] = Field(default=None, max_length=5000)

class CoverLetterOut(BaseModel):
    id: int
    input_full_name: str
    job_title: str
    company_name: str
    tone: str
    job_description: str
    extra_notes: Optional[str]
    resume_text: str
    ai_draft: str
    edited_final: Optional[str]

    class Config:
        from_attributes = True

class UpdateEditedFinalRequest(BaseModel):
    edited_final: str = Field(min_length=1, max_length=30000)
