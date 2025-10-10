from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="UCB Backend", version="0.1.0")

class ParsedResume(BaseModel):
    name: str
    education: list = []
    skills: list = []
    evidence: list = []

class UCBPayload(BaseModel):
    name: str
    skills: list
    fit_score: float
    gaps: list
    evidence: list

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse-resume")
async def parse_resume(file: UploadFile = File(None), data: dict | None = None):
    # dummy: คืนตัวอย่างจาก sample
    sample = {
        "name": "Jane Doe",
        "education": [{"degree": "B.Eng", "year": 2023}],
        "skills": ["Python", "FastAPI", "SQL"],
        "evidence": [{"type": "pdf", "page": 2}]
    }
    return JSONResponse(sample)

@app.post("/score", response_model=UCBPayload)
async def score(parsed: ParsedResume):
    # dummy scoring
    fit = min(1.0, 0.2 + 0.1*len(parsed.skills))
    gaps = ["Docker"] if "Docker" not in parsed.skills else []
    return UCBPayload(
        name=parsed.name,
        skills=parsed.skills,
        fit_score=round(fit, 2),
        gaps=gaps,
        evidence=parsed.evidence
    )
