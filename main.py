"""
main.py — Member A only
FastAPI server. Imports scrape() from scraper.py and analyze() from llm_analysis.py.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price_usd: Optional[float] = None
    image_urls: List[str] = []


class AnalyzeResponse(BaseModel):
    trust_score: int
    verdict: str
    red_flags: List[str]
    llm_score: int
    price_score: int


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    # TODO Member A: import and wire up scraper + llm_analysis
    # from scraper import scrape
    # from llm_analysis import analyze as llm_analyze

    # Stub response — replace with real logic
    llm_score = 50
    price_score = 50
    trust_score = 100 - int((llm_score * 0.6) + (price_score * 0.4))

    return AnalyzeResponse(
        trust_score=trust_score,
        verdict="suspicious",
        red_flags=["Test flag"],
        llm_score=llm_score,
        price_score=price_score,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
