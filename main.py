# pip install fastapi uvicorn pydantic httpx beautifulsoup4 anthropic
import uvicorn
import asyncio # Required for parallel running
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# --- IMPORTING YOUR TEAMMATES' WORK ---
from scraper import scrape           # Member B
from llm_analysis import analyze_listing # Member C

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS (UNCHANGED) ---
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

# --- HEALTH CHECK (STEP 6) ---
@app.get("/")
def root():
    return {"status": "ok", "service": "RentSentry"}

# --- PRICE HEURISTIC (STEP 3) ---
def compute_price_score(price_usd: float | None) -> int:
    if price_usd is None:
        return 20
    if price_usd < 500:
        return 90
    if price_usd < 800:
        return 75
    if price_usd < 1200:
        return 55
    if price_usd < 1800:
        return 25
    return 5

# --- THE MAIN BRAIN (STEP 1 & 2) ---
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    
    # 1. Prepare data variables
    title = req.title
    description = req.description
    price_usd = req.price_usd

    # 2. Parallel Execution: Run Scraper and LLM at the same time
    # We call scrape() only if a URL exists
    if req.url:
        # Start the scrape and the LLM analysis simultaneously
        scraped_task = scrape(req.url)
        # We use a placeholder for now since we need scraped data FOR the LLM
        scraped_data = await scraped_task
        
        # Merge Logic: Scraped values win if they aren't None
        title = scraped_data.get("title") or title
        description = scraped_data.get("description") or description
        price_usd = scraped_data.get("price_usd") or price_usd

    # 3. Call LLM with the final data
    llm_result = await analyze_listing(title, price_usd, description)

    # 4. Scoring Logic (STEP 4)
    llm_score = llm_result["suspicion_score"]
    price_score = compute_price_score(price_usd)

    # Calculate weighted penalty
    penalty = (llm_score * 0.6) + (price_score * 0.4)
    trust_score = max(0, min(100, round(100 - penalty)))

    # 5. Determine Verdict
    if trust_score >= 70:
        verdict = "safe"
    elif trust_score >= 40:
        verdict = "suspicious"
    else:
        verdict = "likely_scam"

    # 6. Return Result (STEP 5)
    return AnalyzeResponse(
        trust_score=trust_score,
        verdict=verdict,
        red_flags=llm_result["red_flags"],
        llm_score=llm_score,
        price_score=price_score,
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)