# RentSentry

Rental listing fraud detector. Paste a Craigslist URL or raw listing text — get back a trust score and a list of red flags.

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
      │        └─► suspicion_score, red_flags, reasoning
      │
      └─► main.py           orchestration + response (Member A)
               │
               └─► trust_score, verdict, red_flags, llm_score, price_score
```

**Trust score formula:**
```
trust_score = 100 - ((llm_score * 0.6) + (price_score * 0.4))
```

---

## Team

| Member | File | Status |
|--------|------|--------|
| A | `main.py` | FastAPI server, orchestration |
| B | `scraper.py` | Craigslist scraper (httpx + BeautifulSoup) |
| C | `llm_analysis.py` | LLM fraud analysis (OpenAI primary, Anthropic fallback) |
| D | `frontend/index.html` | UI |

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

Copy `.env` and fill in your keys:
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

**Test with curl**
```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "url": null,
    "description": "Wire transfer only, I am overseas",
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
  "price_score": 70
}
```

---

## API Contract

Defined in [`contract.json`](contract.json).

### `POST /analyze`

**Request**
| Field | Type | Notes |
|-------|------|-------|
| `url` | `string \| null` | Craigslist listing URL |
| `title` | `string \| null` | Listing title |
| `description` | `string \| null` | Listing body text |
| `price_usd` | `number \| null` | Monthly rent |
| `image_urls` | `string[]` | Always an array |

**Response**
| Field | Type | Notes |
|-------|------|-------|
| `trust_score` | `integer 0–100` | Higher = safer |
| `verdict` | `safe \| suspicious \| likely_scam` | |
| `red_flags` | `string[]` | Always an array, never null |
| `llm_score` | `integer 0–100` | Higher = more suspicious |
| `price_score` | `integer 0–100` | Higher = more suspicious |

---

## Module: `llm_analysis.py`

```python
from llm_analysis import analyze_listing

result = await analyze_listing(title, price_usd, description)
# {
#   "suspicion_score": int,   # 0-100
#   "red_flags": list[str],
#   "reasoning": str
# }
```

- Primary model: `gpt-4o-mini` (OpenAI)
- Fallback model: `claude-haiku-4-5` (Anthropic)
- Never raises — returns `{"suspicion_score": 50, "red_flags": [], "reasoning": "Analysis unavailable."}` on any failure
- Run self-tests: `python llm_analysis.py`

---

## Module: `scraper.py`

```python
from scraper import scrape

data = scrape("https://craigslist.org/...")
# {
#   "title": str | None,
#   "description": str | None,
#   "price_usd": float | None,
#   "image_urls": list[str],
#   "phones_found": list[str]
# }
```

Test directly:
```bash
echo "https://craigslist.org/..." | python scraper.py
```

---

## Suspicion Score Guide

| Score | Meaning |
|-------|---------|
| 0–20 | Looks legitimate |
| 21–40 | Minor concerns |
| 41–65 | Suspicious — verify carefully |
| 66–85 | Likely scam |
| 86–100 | Almost certainly a scam |
