# pip install httpx beautifulsoup4 lxml
"""
scraper.py 
Given a URL, returns a dict matching the AnalyzeRequest fields.
Returns None for any field it cannot extract — never throws.
"""
import asyncio
import json
import re
import sys
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(\+?1[\s.\-]?)?"
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
    r"(?!\d)"
)

_QR_MARKER = "QR Code Link to This Post"


def extract_phones(text: str) -> List[str]:
    """Return all phone numbers found in text."""
    try:
        return [m.group().strip() for m in _PHONE_RE.finditer(text)]
    except Exception:
        return []


def _empty(url: str) -> Dict[str, Any]:
    return {
        "url": url,
        "title": None,
        "description": None,
        "price_usd": None,
        "image_urls": [],
        "phones_found": [],
    }


async def fetch_listing(url: str) -> Dict[str, Any]:
    """Fetch a Craigslist listing page and return parsed fields."""
    result = _empty(url)
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.TimeoutException:
        return result
    except Exception:
        return result

    try:
        soup = BeautifulSoup(html, "lxml")

        # Title
        try:
            tag = soup.select_one("#titletextonly")
            if tag:
                result["title"] = tag.get_text(strip=True)
        except Exception:
            pass

        # Price
        try:
            tag = soup.select_one(".price")
            if tag:
                raw = tag.get_text(strip=True)
                result["price_usd"] = float(raw.replace("$", "").replace(",", "").strip())
        except Exception:
            pass

        # Description — strip QR marker (appears at start or anywhere) and keep the rest
        try:
            tag = soup.select_one("#postingbody")
            if tag:
                full_text = tag.get_text("\n", strip=True)
                idx = full_text.find(_QR_MARKER)
                if idx != -1:
                    full_text = full_text[idx + len(_QR_MARKER):].strip()
                result["description"] = full_text or None
        except Exception:
            pass

        # Image URLs
        try:
            result["image_urls"] = [
                a["href"] for a in soup.select("#thumbs a") if a.get("href")
            ]
        except Exception:
            result["image_urls"] = []

        # Phones in description
        if result["description"]:
            result["phones_found"] = extract_phones(result["description"])

    except Exception:
        pass

    return result


def scrape(url: str) -> Dict[str, Any]:
    """
    Entry point imported by main.py.

    If url doesn't start with http, treat it as raw pasted text:
    return it directly as description with all other fields null.

    Returns dict: url, title, description, price_usd, image_urls, phones_found
    """
    if not url.startswith("http"):
        result = _empty(url)
        result["description"] = url
        result["phones_found"] = extract_phones(url)
        return result
    return asyncio.run(fetch_listing(url))


if __name__ == "__main__":
    url = sys.stdin.readline().strip()
    if url.startswith("http"):
        data = asyncio.run(fetch_listing(url))
    else:
        data = scrape(url)
    print(json.dumps(data, indent=2))
