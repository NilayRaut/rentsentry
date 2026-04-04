# pip install fastapi uvicorn pydantic

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ListingPayload(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price_usd: Optional[float] = None
    image_urls: list[str] = []


class AnalysisResult(BaseModel):
    trust_score: int
    verdict: str
    red_flags: list[str]
    llm_score: int
    price_score: int


@app.post("/analyze", response_model=AnalysisResult)
def analyze(payload: ListingPayload):
    return AnalysisResult(
        trust_score=72,
        verdict="suspicious",
        red_flags=["Price unusually low", "Test flag"],
        llm_score=60,
        price_score=40,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
