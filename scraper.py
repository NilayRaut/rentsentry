# pip install httpx beautifulsoup4 lxml
"""
scraper.py — Member B only
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


def extract_phones(text: str) -> List[str]:
    """Return all phone numbers found in text."""
    try:
        return [m.group().strip() for m in _PHONE_RE.finditer(text)]
    except Exception:
        return []


async def fetch_listing(url: str) -> Dict[str, Any]:
    """Fetch a Craigslist listing page and return parsed fields."""
    result: Dict[str, Any] = {
        "url": url,
        "title": None,
        "description": None,
        "price_usd": None,
        "image_urls": [],
        "phones_found": [],
    }
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "lxml")

        # Title
        try:
            title_tag = soup.select_one("#titletextonly")
            if title_tag:
                result["title"] = title_tag.get_text(strip=True)
        except Exception:
            pass

        # Price (raw string and parsed float)
        price_raw: Optional[str] = None
        try:
            price_tag = soup.select_one(".price")
            if price_tag:
                price_raw = price_tag.get_text(strip=True)
                result["price_usd"] = float(
                    price_raw.replace("$", "").replace(",", "").strip()
                )
        except Exception:
            pass

        # Description — strip everything after "QR Code Link to This Post"
        try:
            body_tag = soup.select_one("#postingbody")
            if body_tag:
                full_text = body_tag.get_text("\n", strip=True)
                qr_marker = "QR Code Link to This Post"
                idx = full_text.find(qr_marker)
                if idx != -1:
                    full_text = full_text[:idx].strip()
                result["description"] = full_text or None
        except Exception:
            pass

        # Image URLs from thumbs strip
        try:
            thumb_tags = soup.select("#thumbs a")
            result["image_urls"] = [
                a["href"] for a in thumb_tags if a.get("href")
            ]
        except Exception:
            result["image_urls"] = []

        # Phones found in description
        if result["description"]:
            result["phones_found"] = extract_phones(result["description"])

    except Exception:
        pass

    return result


def scrape(url: str) -> Dict[str, Any]:
    """
    Synchronous wrapper around fetch_listing for use by main.py.

    Returns dict with keys: url, title, description, price_usd, image_urls, phones_found
    All values may be None except image_urls/phones_found which are lists.
    """
    return asyncio.run(fetch_listing(url))


if __name__ == "__main__":
    url = sys.stdin.readline().strip()
    data = asyncio.run(fetch_listing(url))
    print(json.dumps(data, indent=2))
