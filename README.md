# RentSentry

Rental listing fraud detector. Paste a Craigslist URL or raw listing text — get back a trust score, red flags, and positive location signals.

---

## Architecture

```
POST /analyze
      │
      ├─► scraper.py        fetch + parse listing from URL (Member B)
      │        │
      │        └─► title, price_usd, description, image_urls
      │
      ├─► llm_analysis.py   LLM scam detection (Member C)
      │        │
      │        └─► suspicion_score, red_flags, reasoning, accessibility_signals,
      │            formatted_description
      │
      └─► main.py           orchestration + response (Member A)
               │
               └─► trust_score, verdict, red_flags, llm_score, price_score,
                   accessibility_signals, market_price_score, neighborhood_note,
                   neighborhood_info, listing_title, listing_description,
                   listing_price_usd, listing_image_urls
```

**Trust score formula:**
```
trust_score = 100 - ((llm_score * 0.6) + (price_score * 0.4))
```

---

## Team

| Member | File | Responsibility |
|--------|------|----------------|
| A | `main.py` | FastAPI server, orchestration, scoring |
| B | `scraper.py` | Craigslist scraper (httpx + BeautifulSoup) |
| C | `llm_analysis.py` | LLM fraud analysis (OpenAI primary, Anthropic fallback) |
| D | `frontend/index.html` | Vanilla JS/HTML UI |

---

## Features

- **Trust score (0–100)** — weighted composite of LLM analysis + price heuristic
- **Red flags** — short, plain-English fraud signals extracted by the LLM
- **Accessibility signals** — positive location signals extracted from listing text (transit, ADA, parking, walkability, elevator)
- **Listing preview** — scraped title, price, and paraphrased description shown in a clean card above the result; image gallery with thumbnails
- **Reverse image search** — Google Lens + TinEye links under each listing photo; no API key needed
- **Paraphrased descriptions** — LLM rewrites raw Craigslist text (ALL CAPS, separator lines, emoji spam) into clean professional prose
- **Clickable history URLs** — listing URLs in the history panel are hyperlinked back to the original listing page
- **Demo mode** — keyword-based frontend analysis with no backend required
- **Analysis history** — last 50 analyses stored in localStorage
- **Dual LLM** — OpenAI `gpt-4o-mini` primary, Anthropic `claude-haiku-4-5` fallback

---

## Setup

**1. Clone and enter the repo**
```bash
git clone https://github.com/NilayRaut/rentsentry.git
cd rentsentry
```

**2. Create the conda environment**
```bash
conda create -n rentsentry python=3.11 -y
conda activate rentsentry
```

**3. Install dependencies**
```bash
pip install -r requirements.txt anthropic httpx beautifulsoup4 lxml
```

**4. Add your API keys**

```bash
cp .env.example .env   # or create .env manually
```

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...   # optional — used as fallback only
```

---

## Running

**Start the API server**
```bash
conda activate rentsentry
uvicorn main:app --reload
```

Open `frontend/index.html` directly in a browser — no build step needed.

**Test with curl**
```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "url": null,
    "description": "Wire transfer only, I am overseas on a missionary trip",
    "price_usd": 600,
    "image_urls": []
  }'
```

**Expected response shape**
```json
{
  "trust_score": 10,
  "verdict": "likely_scam",
  "red_flags": ["Payment via wire transfer", "Landlord claims to be overseas"],
  "llm_score": 88,
  "price_score": 70,
  "accessibility_signals": [],
  "listing_title": null,
  "listing_description": "Wire transfer payment required. Landlord states they are currently overseas.",
  "listing_price_usd": 600,
  "listing_image_urls": []
}
```

---

## API Contract

### `POST /analyze`

**Request**
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `url` | `string \| null` | `null` | Craigslist listing URL |
| `title` | `string \| null` | `null` | Listing title |
| `description` | `string \| null` | `null` | Listing body text |
| `price_usd` | `number \| null` | `null` | Monthly rent |
| `image_urls` | `string[]` | `[]` | Always an array |
| `mode` | `"rent" \| "buy"` | `"rent"` | Analysis mode |

**Response**
| Field | Type | Notes |
|-------|------|-------|
| `trust_score` | `integer 0–100` | Higher = safer |
| `verdict` | `"safe" \| "suspicious" \| "likely_scam"` | |
| `red_flags` | `string[]` | Always an array, never null |
| `llm_score` | `integer 0–100` | Higher = more suspicious |
| `price_score` | `integer 0–100` | Higher = more suspicious |
| `accessibility_signals` | `string[]` | Positive location signals; empty if none found |
| `mode` | `"rent" \| "buy"` | Echo of requested mode |
| `market_price_score` | `integer 0–100 \| null` | Market price comparison; null if neighborhood unknown |
| `neighborhood_note` | `string \| null` | Human-readable price context |
| `neighborhood_info` | `object \| null` | Nearby amenities from LLM |
| `listing_title` | `string \| null` | Scraped or provided title |
| `listing_description` | `string \| null` | LLM-paraphrased description (falls back to raw) |
| `listing_price_usd` | `number \| null` | Scraped or provided price |
| `listing_image_urls` | `string[]` | Scraped images; always an array |
| `meta` | `object \| null` | Debug metadata (scrape attempted, price source, etc.) |

---

## Module: `llm_analysis.py`

```python
from llm_analysis import analyze_listing

result = await analyze_listing(title, price_usd, description)
# {
#   "suspicion_score": int,            # 0-100
#   "red_flags": list[str],
#   "reasoning": str,
#   "accessibility_signals": list[str], # positive location signals
#   "formatted_description": str | None  # LLM-cleaned description prose
# }
```

- Primary model: `gpt-4o-mini` (OpenAI)
- Fallback model: `claude-haiku-4-5` (Anthropic)
- Never raises — returns a safe default dict on any failure
- Run self-tests: `python llm_analysis.py`

---

## Module: `scraper.py`

```python
from scraper import scrape

data = await scrape("https://boston.craigslist.org/...")
# {
#   "title": str | None,
#   "description": str | None,
#   "price_usd": float | None,
#   "image_urls": list[str],
#   "phones_found": list[str]
# }
```

- Strips Craigslist QR footer from description automatically
- Test directly: `python scraper.py` (prompts for a URL)

---

## Suspicion Score Guide

| Score | Meaning |
|-------|---------|
| 0–20 | Looks legitimate |
| 21–40 | Minor concerns |
| 41–65 | Suspicious — verify carefully |
| 66–85 | Likely scam |
| 86–100 | Almost certainly a scam |

---

## Verdict Thresholds

| Trust Score | Verdict |
|-------------|---------|
| 70–100 | `safe` |
| 40–69 | `suspicious` |
| 0–39 | `likely_scam` |

---

## Future Scope

- **More listing platforms** — Facebook Marketplace, Apartments.com, Zillow (currently blocked by anti-scraping), HotPads; each needs a site-specific parser in `scraper.py`
- **More cities / regions** — price heuristics and neighborhood data are currently Boston-only; extend `_BOSTON_MEDIANS` pattern to other metro areas
- **Image fraud detection** — send listing photos to a vision model to flag stock images, digitally altered photos, or mismatched locations
- **Phone number lookup** — cross-reference scraped phone numbers against known scam databases (e.g. 800notes)
- **Landlord reputation layer** — crowdsourced reports tied to phone number, email, or address; flag repeat offenders
- **Cloud history sync** — replace localStorage with a user account so history persists across devices
- **PDF / shareable report** — one-click export of the full analysis as a PDF or shareable link
- **Email / push alerts** — notify a user when a saved search URL changes trust score or gets flagged
