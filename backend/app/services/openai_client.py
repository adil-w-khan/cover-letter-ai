from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are an assistant that writes tailored cover letters.
Rules:
- Do NOT invent experience, companies, degrees, or metrics not supported by the resume text.
- Use only information found in the resume text and user inputs.
- Keep it concise, confident, and specific.
- Avoid buzzword spam and generic filler.
- Output ONLY the cover letter text (no markdown fences, no commentary).
"""

def build_user_prompt(input_full_name: str, job_title: str, company_name: str, tone: str,
                      job_description: str, resume_text: str, extra_notes: str | None) -> str:
    tone_guide = "Professional, formal, and polished." if tone == "professional" else "Warm, friendly, and approachable (still professional)."
    extra = extra_notes.strip() if extra_notes else "None"
    return f"""
Write a cover letter for:
- Candidate name: {input_full_name}
- Target job title: {job_title}
- Company: {company_name}
Tone: {tone_guide}

Job description:
{job_description}

Resume text:
{resume_text}

Anything else to include:
{extra}

Constraints:
- 250–400 words
- 3–4 short paragraphs + closing
- Mention company and role explicitly
- Make 2–3 specific connections between resume and job description
"""

def generate_cover_letter(payload: dict) -> str:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",  # strong + cost-effective (you can change later)
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(**payload)},
        ],
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()
