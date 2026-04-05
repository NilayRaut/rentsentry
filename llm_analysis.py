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

_SYSTEM_PROMPT_RENT = """You are a rental fraud analyst specializing in detecting apartment listing scams.

You will be given a rental listing's title, price, and description. Analyze it for fraud indicators.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, no code fences. Just raw JSON.

The JSON must have exactly these fields:
{
  "suspicion_score": <integer 0-100>,
  "red_flags": [<short plain-English string>, ...],
  "reasoning": "<one sentence summary>",
  "accessibility_signals": [<short plain-English string>, ...]
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
- No verifiable address, building name, or unit number — listing cannot be searched, reviewed, or confirmed to exist

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
Never return null for red_flags.

Also extract accessibility_signals: a list of positive location/accessibility signals found in the listing text.
Examples: "mentions transit access", "ADA accessible", "elevator building", "parking included", "high walkability score mentioned".
Return an empty list if none found. Never return null for accessibility_signals."""

_SYSTEM_PROMPT_BUY = """You are a real estate fraud analyst specializing in detecting home purchase listing scams.

You will be given a property listing's title, price, and description. Analyze it for fraud indicators.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, no code fences. Just raw JSON.

The JSON must have exactly these fields:
{
  "suspicion_score": <integer 0-100>,
  "red_flags": [<short plain-English string>, ...],
  "reasoning": "<one sentence summary>",
  "accessibility_signals": [<short plain-English string>, ...]
}

Scoring guide:
- 0-20: Looks legitimate. Normal language, reasonable price, no pressure tactics, allows inspection.
- 21-40: Minor concerns. One or two soft signals worth noting.
- 41-65: Suspicious. Multiple red flags present. Buyer should verify carefully.
- 66-85: Likely scam. Strong fraud indicators present.
- 86-100: Almost certainly a scam. Classic fraud pattern: multiple buy-specific fraud signals present together.

Red flags to look for (each one found raises the score significantly):
- Deed or title fraud indicators (seller can't produce clear title, title company unverifiable)
- Fake or unknown escrow company — always verify escrow independently
- "As-is" sale combined with high-pressure tactics to close quickly
- Refuses to allow home inspection or no inspection contingency permitted
- Wire transfer demanded for closing costs or earnest money
- Unusually fast closing pressure ("must close in 5 days", "cash only, no contingencies")
- Seller claims to be overseas or unavailable for any in-person meetings
- Price dramatically below comparable sales in the area
- Requests personal financial information (SSN, bank account) before any formal agreement
- Vague or missing property disclosures

Legitimate signals that LOWER the score (do NOT treat these as red flags):
- Standard escrow process with a recognized title company
- Allows home inspection contingency — this is a strong legitimacy signal
- Reasonable price for comparable sales in the neighborhood
- Specific, verifiable property details (lot size, year built, permits)
- No urgency language, no overseas story, no unusual payment demands

CRITICAL RULES:
1. Multiple strong red flags together (title fraud + fake escrow + no inspection + wire transfer) → score must be 86+
2. Zero red flags with legitimate signals → score must be 20 or below
3. A single soft signal alone should not push a score above 35

red_flags must be short (under 10 words each), specific, and plain English.
If no red flags are found, red_flags must be an empty list [].
Never return null for red_flags.

Also extract accessibility_signals: a list of positive location/accessibility signals found in the listing text.
Examples: "mentions transit access", "ADA accessible", "elevator building", "parking included", "high walkability score mentioned".
Return an empty list if none found. Never return null for accessibility_signals."""


async def _call_openai(user_message: str, system_prompt: str) -> str:
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY not set")
    response = await openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


async def _call_anthropic(user_message: str, system_prompt: str) -> str:
    if anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    response = await anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=512,
        system=system_prompt,
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
        "accessibility_signals": [str(s) for s in parsed.get("accessibility_signals", []) if s][:10],
    }


async def analyze_listing(
    title: str | None,
    price_usd: float | None,
    description: str | None,
    mode: str = "rent",
) -> dict:
    """
    Analyze a listing for scam indicators.
    Primary: OpenAI gpt-4o-mini. Fallback: Claude Haiku.

    Args:
        mode: "rent" (default) or "buy" — selects the appropriate red-flag set.

    Returns:
        {
            "suspicion_score": int (0-100),
            "red_flags": list[str],
            "reasoning": str,
            "accessibility_signals": list[str]
        }
    Returns safe default on any error — never raises.
    """
    DEFAULT = {"suspicion_score": 50, "red_flags": [], "reasoning": "Analysis unavailable.", "accessibility_signals": []}

    if not description and not title:
        return DEFAULT

    # Select prompt based on mode
    system_prompt = _SYSTEM_PROMPT_BUY if mode == "buy" else _SYSTEM_PROMPT_RENT

    price_label = "Price" if mode == "rent" else "Listing price"
    price_str = f"${price_usd:,.0f}" + ("/mo" if mode == "rent" else "") if price_usd else "Not listed"
    listing_type = "rental" if mode == "rent" else "property purchase"
    user_message = f"""Analyze this {listing_type} listing for fraud:

Title: {title or 'Not provided'}
{price_label}: {price_str}
Description:
{(description or 'Not provided')[:3000]}

Return only the JSON object."""

    # Try OpenAI first
    try:
        raw = await _call_openai(user_message, system_prompt)
        return _parse_raw(raw)
    except Exception:
        pass

    # Fallback to Anthropic
    try:
        raw = await _call_anthropic(user_message, system_prompt)
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
    "medford": 2400,
    "malden": 2100,
    "quincy": 2200,
    "waltham": 2300,
    "newton": 2800,
    "brookline": 3000,
    "watertown": 2500,
    "everett": 2000,
    "revere": 2000,
}


def _neighborhood_median(neighborhood: str) -> int | None:
    """Return the hardcoded median rent for a Boston neighborhood, or None if unknown."""
    key = neighborhood.lower().strip()
    if not key:
        return None
    # Exact match first
    if key in _BOSTON_MEDIANS:
        return _BOSTON_MEDIANS[key]
    # Partial match (e.g. "Back Bay, Boston" → "back bay") — only if key is non-empty
    for k, v in _BOSTON_MEDIANS.items():
        if k in key or key in k:
            return v
    return None


def _extract_neighborhood(title: str | None, description: str | None) -> str:
    """Scan listing text for a known Boston neighborhood. Returns lowercase match or ''."""
    combined = " ".join(filter(None, [title, description])).lower()
    if not combined:
        return ""
    for neighborhood in _BOSTON_MEDIANS:
        if neighborhood in combined:
            return neighborhood
    return ""


async def _do_amenities_fetch(neighborhood: str) -> dict:
    """Inner fetch — geocode neighborhood then query OSM for nearby amenities."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(4.0),
        follow_redirects=True,
        headers={"User-Agent": "RentSentry/1.0 (rental-fraud-detector)"},
    ) as client:
        # Geocode via Nominatim
        geo_resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{neighborhood}, Boston, MA", "format": "json", "limit": "1"},
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            return {"grocery_stores": None, "transit_stops": None,
                    "restaurants": None, "walkability": "unknown"}

        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])

        # Three named sets, each with own `out count` → 3 count elements in response
        query = (
            f"[out:json][timeout:4];\n"
            f'node["shop"~"supermarket|convenience"](around:1000,{lat},{lon})->.g;\n'
            f".g out count;\n"
            f"(\n"
            f'  node["public_transport"="stop_position"](around:600,{lat},{lon});\n'
            f'  node["highway"="bus_stop"](around:600,{lat},{lon});\n'
            f'  node["railway"="subway_entrance"](around:600,{lat},{lon});\n'
            f")->.t;\n"
            f".t out count;\n"
            f"(\n"
            f'  node["amenity"~"restaurant|fast_food"](around:500,{lat},{lon});\n'
            f")->.r;\n"
            f".r out count;\n"
        )
        op_resp = await client.post(
            "https://overpass-api.de/api/interpreter",
            content=query,
            headers={"Content-Type": "text/plain"},
        )
        op_resp.raise_for_status()
        op_data = op_resp.json()

        counts = [
            int(el.get("tags", {}).get("total", 0))
            for el in op_data.get("elements", [])
            if el.get("type") == "count"
        ]
        if len(counts) < 3:
            return {"grocery_stores": None, "transit_stops": None,
                    "restaurants": None, "walkability": "unknown"}

        grocery, transit, restaurants = counts[0], counts[1], counts[2]
        if grocery >= 2 and transit >= 3:
            walkability = "high"
        elif grocery == 0 and transit < 2:
            walkability = "low"
        else:
            walkability = "medium"

        return {
            "grocery_stores": grocery,
            "transit_stops": transit,
            "restaurants": restaurants,
            "walkability": walkability,
        }


async def neighborhood_amenities(neighborhood: str) -> dict:
    """Fetch nearby grocery, transit, and restaurant counts via free OSM APIs.

    Returns:
        {"grocery_stores": int|None, "transit_stops": int|None,
         "restaurants": int|None, "walkability": "high"|"medium"|"low"|"unknown"}
    Never raises.
    """
    FALLBACK = {"grocery_stores": None, "transit_stops": None,
                "restaurants": None, "walkability": "unknown"}
    if not neighborhood or not _HTTPX_AVAILABLE:
        return FALLBACK
    try:
        return await asyncio.wait_for(_do_amenities_fetch(neighborhood), timeout=5.0)
    except Exception:
        return FALLBACK


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
    hood_label = f" {neighborhood}" if neighborhood else ""
    note = (
        f"Price is {abs(z):.1f} SD {direction}{hood_label} median "
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
