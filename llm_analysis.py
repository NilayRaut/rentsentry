"""
llm_analysis.py — Member C only
Takes listing fields, returns llm_score (0–100) and red_flags list.
Higher llm_score = more suspicious. Never throws.
"""
from typing import Optional, List, Dict, Any


def analyze(
    title: Optional[str],
    description: Optional[str],
    price_usd: Optional[float],
    image_urls: List[str],
) -> Dict[str, Any]:
    """
    Analyze listing text with LLM.

    Returns:
        {
            "llm_score":  int 0-100  (higher = more suspicious),
            "red_flags":  list[str]  (never null, may be empty),
        }
    """
    # TODO Member C: implement LLM analysis
    return {
        "llm_score": 50,
        "red_flags": ["Test flag"],
    }
