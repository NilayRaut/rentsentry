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
      │        └─► suspicion_score, red_flags, reasoning, accessibility_signals
      │
      └─► main.py           orchestration + response (Member A)
               │
               └─► trust_score, verdict, red_flags, llm_score, price_score,
                   accessibility_signals
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
  "accessibility_signals": []
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

**Response**
| Field | Type | Notes |
|-------|------|-------|
| `trust_score` | `integer 0–100` | Higher = safer |
| `verdict` | `"safe" \| "suspicious" \| "likely_scam"` | |
| `red_flags` | `string[]` | Always an array, never null |
| `llm_score` | `integer 0–100` | Higher = more suspicious |
| `price_score` | `integer 0–100` | Higher = more suspicious |
| `accessibility_signals` | `string[]` | Positive location signals; empty if none found |

---

## Module: `llm_analysis.py`

```python
from llm_analysis import analyze_listing

result = await analyze_listing(title, price_usd, description)
# {
#   "suspicion_score": int,            # 0-100
#   "red_flags": list[str],
#   "reasoning": str,
#   "accessibility_signals": list[str] # positive location signals
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
