# pip install fastapi uvicorn pydantic httpx beautifulsoup4 anthropic
import uvicorn
import asyncio # Required for parallel running
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# --- IMPORTING YOUR TEAMMATES' WORK ---
from scraper import fetch_listing       # Member B
from llm_analysis import analyze_listing, price_analysis, neighborhood_amenities, _extract_neighborhood  # Member C

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
    mode: str = "rent"  # "rent" or "buy"

class AnalyzeResponse(BaseModel):
    trust_score: int
    verdict: str
    red_flags: List[str]
    llm_score: int
    price_score: int
    accessibility_signals: List[str] = []
    mode: str = "rent"
    market_price_score: Optional[int] = None
    neighborhood_note: Optional[str] = None
    neighborhood_info: Optional[dict] = None
    meta: Optional[dict] = None

# --- HEALTH CHECK (STEP 6) ---
@app.get("/")
def root():
    return {"status": "ok", "service": "RentSentry"}

# --- GEOGRAPHY CHECK ---
def _is_boston_area(url: str | None, neighborhood: str) -> bool:
    """Return True if the listing is in the Greater Boston area.

    Uses two signals: detected neighborhood (already covers Boston + suburbs
    in _BOSTON_MEDIANS) and Craigslist subdomain from the URL.
    """
    if neighborhood:
        return True
    if url and "boston.craigslist.org" in url:
        return True
    return False

# --- PRICE HEURISTIC (Boston-calibrated) ---
def compute_price_score(price_usd: float | None) -> int:
    if price_usd is None:
        return 20
    if price_usd < 700:
        return 90   # impossibly low anywhere in Boston
    if price_usd < 1100:
        return 75   # scam-range for Boston
    if price_usd < 1500:
        return 55   # suspicious — very cheap for Boston
    if price_usd < 2200:
        return 25   # below average but plausible
    return 5        # normal Boston rent range

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
        scraped_data = await fetch_listing(req.url)

        # Merge logic: scraped values win if they aren't None
        title = scraped_data.get("title") or title
        description = scraped_data.get("description") or description
        price_usd = scraped_data.get("price_usd") or price_usd

        # If scraper got nothing (Zillow/blocked site), fall back to pasted text.
        # If there's no pasted text either, return a clear error instead of a
        # meaningless hardcoded 62.
        if not any([title, description, price_usd]):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail="Could not extract listing data from this URL. The site may block scrapers (e.g. Zillow). Try pasting the listing text directly."
            )

    # 3. Call LLM with the final data
    llm_result = await analyze_listing(title, price_usd, description, mode=req.mode)

    # 3b. Market price + neighborhood amenities (parallel when neighborhood found)
    hood = _extract_neighborhood(title, description)
    if hood:
        market_result, amenities = await asyncio.gather(
            price_analysis(price_usd, hood),
            neighborhood_amenities(hood),
        )
    else:
        market_result = await price_analysis(price_usd, hood)
        amenities = None

    # 4. Scoring Logic (STEP 4)
    llm_score = llm_result["suspicion_score"]
    in_boston = _is_boston_area(req.url, hood)
    price_score = compute_price_score(price_usd) if in_boston else 20

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
    meta = {
        "description_found": bool(description),
        "price_found": price_usd is not None,
        "neighborhood_detected": hood or None,
        "scrape_attempted": bool(req.url),
        "price_data_source": market_result.get("note", "").split("source=")[-1].rstrip(")") if market_result.get("note") and "source=" in market_result.get("note", "") else None,
        "in_boston_area": in_boston,
    }
    return AnalyzeResponse(
        trust_score=trust_score,
        verdict=verdict,
        red_flags=llm_result["red_flags"],
        llm_score=llm_score,
        price_score=price_score,
        accessibility_signals=llm_result.get("accessibility_signals", []),
        mode=req.mode,
        market_price_score=market_result.get("price_score"),
        neighborhood_note=market_result.get("note"),
        neighborhood_info=amenities,
        meta=meta,
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
