"""
scraper.py — Member B only
Given a URL, returns a dict matching the AnalyzeRequest fields.
Returns None for any field it cannot extract — never throws.
"""
from typing import Optional, List, Dict, Any


def scrape(url: str) -> Dict[str, Any]:
    """
    Scrape listing data from url.

    Returns dict with keys: title, description, price_usd, image_urls
    All values may be None except image_urls which must be a list.
    """
    # TODO Member B: implement scraping logic
    return {
        "title": None,
        "description": None,
        "price_usd": None,
        "image_urls": [],
    }
