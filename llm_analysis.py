# pip install openai anthropic python-dotenv
import os
import json
import re
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

load_dotenv()

openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
anthropic_client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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
- 0-20: Looks legitimate. Normal language, reasonable price, no pressure tactics.
- 21-40: Minor concerns. One or two soft signals worth noting.
- 41-65: Suspicious. Multiple red flags present. Renter should verify carefully.
- 66-85: Likely scam. Strong fraud indicators present.
- 86-100: Almost certainly a scam. Classic fraud pattern detected.

Red flags to look for (each one found raises the score):
- Payment via wire transfer, Western Union, Zelle, gift cards, or cryptocurrency
- Landlord claims to be overseas, out of country, in military, or on missionary trip
- Religious appeals like "God-fearing" or "honest Christian"
- Refuses or discourages in-person viewing
- Asks to contact outside the listing platform (email/text directly)
- Urgency pressure: "must decide today", "many people interested", "first come first served"
- Requests deposit or rent payment before signing a lease or seeing the property
- Unusually detailed personal story from the landlord (overcompensating)
- Grammar that suggests machine translation (e.g., stiff formal phrasing in odd places)
- Price that seems impossibly low for the claimed location (if price is provided)
- Requests personal information (SSN, bank info) upfront
- Photos described as "not available right now" or "will send later"

red_flags must be short (under 10 words each), specific, and plain English.
If no red flags are found, red_flags must be an empty list [].
Never return null for red_flags."""


async def _call_openai(user_message: str) -> str:
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
