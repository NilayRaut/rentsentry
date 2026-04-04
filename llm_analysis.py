# pip install openai anthropic python-dotenv httpx
from __future__ import annotations
import os
import re
import json
import asyncio
import statistics
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from dotenv import load_dotenv
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

load_dotenv()

_openai_key = os.environ.get("OPENAI_API_KEY")
_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

openai_client = AsyncOpenAI(api_key=_openai_key) if _openai_key else None
anthropic_client = AsyncAnthropic(api_key=_anthropic_key) if _anthropic_key else None

OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are a rental fraud analyst specializing in detecting apartment listing scams.

You will be given a rental listing's title, price, and description. Analyze it for fraud indicators.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, no code fences. Just raw JSON.

The JSON must have exactly these fields:
{
  "suspicion_score": <integer 0-100>,
  "red_flags": [<short plain-English string>, ...],
  "reasoning": "<one sentence summary>"
}

Scoring guide:
- 0-20: Looks legitimate. Normal language, reasonable price, no pressure tactics, offers in-person viewing.
- 21-40: Minor concerns. One or two soft signals worth noting.
- 41-65: Suspicious. Multiple red flags present. Renter should verify carefully.
- 66-85: Likely scam. Strong fraud indicators present.
- 86-100: Almost certainly a scam. Classic fraud pattern: overseas landlord + wire transfer + no viewing + urgency pressure all present together.

Red flags to look for (each one found raises the score significantly):
- Payment via wire transfer, Western Union, Zelle, gift cards, or cryptocurrency
- Landlord claims to be overseas, out of country, in military, or on a missionary trip
- Religious appeals like "God-fearing", "honest Christian", or similar to establish false trust
- Refuses or discourages in-person viewing ("no viewings", "currently traveling so viewing not possible")
- Urgency pressure: "must decide today", "many people interested", "first come first served"
- Requests deposit or rent payment before signing a lease or seeing the property
- Asks to contact ONLY via personal email/phone, explicitly avoiding the listing platform
- Unusually detailed personal backstory from landlord (overcompensating with sympathy)
- Grammar suggesting machine translation or non-native scripted text
- Price impossibly low for the claimed location (e.g., $650/mo for a 2BR near downtown Boston)
- Requests personal information (SSN, bank info) upfront before any showing
- Photos described as "not available right now" or "will send later"

Legitimate signals that LOWER the score (do NOT treat these as red flags):
- Offers to schedule a showing, open house, or in-person visit — this is a strong legitimacy signal
- Standard lease terms: first month, last month, security deposit — this is normal in Boston/Northeast, NOT suspicious
- Mentioning contact by email or text FOR SCHEDULING A SHOWING is completely normal — only flag off-platform contact when the landlord insists on it to AVOID accountability
- Reasonable price for the stated neighborhood and city
- Specific, realistic details about the unit (floor, building type, transit, laundry)
- No urgency language, no overseas story, no unusual payment requests

CRITICAL RULES:
1. Multiple strong red flags together (overseas + wire transfer + no viewing + urgency) → score must be 86+
2. Zero red flags with legitimate signals → score must be 20 or below
3. Offering email/text to schedule a showing is NOT the same as demanding off-platform contact to avoid the platform
4. "First, last, and security required" is standard Boston rental practice — do NOT flag it
5. A single soft signal alone should not push a score above 35

red_flags must be short (under 10 words each), specific, and plain English.
If no red flags are found, red_flags must be an empty list [].
Never return null for red_flags."""


async def _call_openai(user_message: str) -> str:
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY not set")
    response = await openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


async def _call_anthropic(user_message: str) -> str:
    if anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    response = await anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def _parse_raw(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw.strip())
    return {
        "suspicion_score": max(0, min(100, int(parsed.get("suspicion_score", 50)))),
        "red_flags": [str(f) for f in parsed.get("red_flags", []) if f][:10],
        "reasoning": str(parsed.get("reasoning", ""))[:300],
    }


async def analyze_listing(
    title: str | None,
    price_usd: float | None,
    description: str | None,
) -> dict:
    """
    Analyze a rental listing for scam indicators.
    Primary: OpenAI gpt-4o-mini. Fallback: Claude Haiku.

    Returns:
        {
            "suspicion_score": int (0-100),
            "red_flags": list[str],
            "reasoning": str
        }
    Returns safe default on any error — never raises.
    """
    DEFAULT = {"suspicion_score": 50, "red_flags": [], "reasoning": "Analysis unavailable."}

    if not description and not title:
        return DEFAULT

    price_str = f"${price_usd:,.0f}/mo" if price_usd else "Not listed"
    user_message = f"""Analyze this rental listing for fraud:

Title: {title or 'Not provided'}
Price: {price_str}
Description:
{(description or 'Not provided')[:3000]}

Return only the JSON object."""

    # Try OpenAI first
    try:
        raw = await _call_openai(user_message)
        return _parse_raw(raw)
    except Exception:
        pass

    # Fallback to Anthropic
    try:
        raw = await _call_anthropic(user_message)
        return _parse_raw(raw)
    except Exception:
        return DEFAULT


# Approximate median monthly rents (USD) for Boston-area neighborhoods, 2024-2025.
# Used as fallback when the Craigslist RSS feed is unavailable (403/timeout).
# stdev is estimated as 20% of median for a typical spread.
_BOSTON_MEDIANS: dict[str, int] = {
    "back bay": 3400,
    "beacon hill": 2900,
    "south end": 3200,
    "fenway": 2500,
    "downtown": 3300,
    "north end": 2800,
    "seaport": 3600,
    "financial district": 3500,
    "cambridge": 2900,
    "somerville": 2500,
    "allston": 2100,
    "brighton": 2000,
    "jamaica plain": 2300,
    "roxbury": 1900,
    "dorchester": 2000,
    "south boston": 2800,
    "charlestown": 2700,
    "east boston": 2200,
    "hyde park": 1800,
    "roslindale": 1900,
    "mattapan": 1700,
}


def _neighborhood_median(neighborhood: str) -> int | None:
    """Return the hardcoded median rent for a Boston neighborhood, or None if unknown."""
    key = neighborhood.lower().strip()
    # Exact match first
    if key in _BOSTON_MEDIANS:
        return _BOSTON_MEDIANS[key]
    # Partial match (e.g. "Back Bay, Boston" → "back bay")
    for k, v in _BOSTON_MEDIANS.items():
        if k in key or key in k:
            return v
    return None


async def _fetch_craigslist_prices(neighborhood: str) -> list[float]:
    """Fetch up to 20 apartment listing prices from Craigslist Boston RSS."""
    if not _HTTPX_AVAILABLE:
        return []

    params = {"format": "rss"}
    if neighborhood:
        params["query"] = neighborhood
    url = "https://boston.craigslist.org/search/aap?" + urlencode(params)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        xml_text = resp.text

    root = ET.fromstring(xml_text)
    # RSS 2.0: items are under channel/item
    prices: list[float] = []

    for item in root.iter("item"):
        if len(prices) >= 20:
            break
        # Price usually appears in the title like "2BR - $1,500/mo" or "$1500 cozy studio"
        title_el = item.find("title")
        text = title_el.text if title_el is not None else ""
        matches = re.findall(r"\$(\d[\d,]*)", text or "")
        for m in matches:
            val = float(m.replace(",", ""))
            if 300 <= val <= 20000:
                prices.append(val)
                break  # one price per item

    return prices


async def price_analysis(price_usd: float | None, neighborhood: str) -> dict:
    """
    Compare price_usd against live Craigslist Boston market data and return a
    penalty score indicating how suspiciously low the price is.

    Args:
        price_usd:    Asking price from the listing (None → neutral score).
        neighborhood: Neighborhood name used to narrow the Craigslist search
                      (e.g. "Back Bay", "Allston", "South End").

    Returns:
        {
            "price_score":   int (0–100),   # 80+ means suspiciously cheap
            "median_price":  int | None,     # market median from fetched data
            "note":          str             # human-readable explanation
        }
    Never raises — returns neutral score on any error.
    """
    NEUTRAL = {"price_score": 50, "median_price": None, "note": "Market data unavailable."}

    if price_usd is None:
        return {"price_score": 50, "median_price": None, "note": "No price provided."}

    # Try live Craigslist RSS first
    source = "Craigslist RSS"
    try:
        prices = await _fetch_craigslist_prices(neighborhood)
    except Exception:
        prices = []

    if len(prices) < 5:
        # Fall back to hardcoded Boston neighborhood medians
        hardcoded = _neighborhood_median(neighborhood)
        if hardcoded is None:
            return NEUTRAL
        median = float(hardcoded)
        stdev = median * 0.20
        source = "neighborhood median estimate"
    else:
        median = statistics.median(prices)
        stdev = statistics.stdev(prices) if len(prices) >= 2 else median * 0.20
        if stdev == 0:
            stdev = median * 0.20

    z = (median - price_usd) / stdev  # positive → price is below market median

    if z >= 2.0:
        score = min(100, 80 + int((z - 2.0) * 10))
    elif z >= 1.0:
        score = 40 + int((z - 1.0) * 40)
    elif z >= 0.0:
        score = int(z * 40)
    else:
        score = 0  # price at or above median — not suspicious

    direction = "below" if z >= 0 else "above"
    note = (
        f"Price is {abs(z):.1f} SD {direction} {neighborhood} median "
        f"(median=${int(median):,}, source={source})"
    )

    return {"price_score": score, "median_price": int(median), "note": note}


TEST_CASES = [
    {
        "label": "Classic scam",
        "title": "Beautiful 2BR near downtown — must rent ASAP",
        "price_usd": 650.0,
        "description": (
            "I am a God-fearing widow currently on a missionary trip abroad. "
            "The apartment is available immediately. I will mail you the keys once "
            "you send the first month rent and deposit via Western Union. "
            "No time for viewings as I am overseas. Many people have expressed interest "
            "so you must decide today. Contact me directly at my email only."
        ),
        "expect_score_above": 80,
    },
    {
        "label": "Legitimate listing",
        "title": "Sunny 1BR in Allston — available Sept 1",
        "price_usd": 1950.0,
        "description": (
            "Newly renovated 1 bedroom on the 2nd floor of a well-maintained triple decker. "
            "Hardwood floors, updated kitchen, coin-op laundry in building. "
            "Close to the B and C Green Line. No pets, no smoking. "
            "Happy to schedule a showing this weekend. First, last, and security required. "
            "Email or text to arrange a visit."
        ),
        "expect_score_below": 25,
    },
    {
        "label": "Suspicious but not definite",
        "title": "Spacious studio — all utilities included",
        "price_usd": 800.0,
        "description": (
            "Nice studio apartment in great neighborhood. "
            "Currently traveling for work so viewing not possible right now. "
            "Price is firm, looking for responsible tenant who can move in quickly. "
            "Please send your details and we can arrange everything by email."
        ),
        "expect_score_above": 40,
    },
    {
        "label": "No description",
        "title": None,
        "price_usd": None,
        "description": None,
        "expect_score_below": 55,  # should return default (50)
    },
]


async def run_tests():
    print("Running llm_analysis.py tests...\n")
    passed = 0
    for t in TEST_CASES:
        result = await analyze_listing(t["title"], t["price_usd"], t["description"])
        score = result["suspicion_score"]
        flags = result["red_flags"]

        above = t.get("expect_score_above")
        below = t.get("expect_score_below")
        ok = True
        if above and score <= above:
            ok = False
        if below and score >= below:
            ok = False

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1

        print(f"[{status}] {t['label']}")
        print(f"       Score: {score}/100")
        print(f"       Flags: {flags}")
        print(f"       Reasoning: {result['reasoning']}\n")

    print(f"Results: {passed}/{len(TEST_CASES)} passed")


if __name__ == "__main__":
    asyncio.run(run_tests())
