"""
Researcher module - Phase 2 of the Finance Bot.

Fetches news for each holding using Brave Search API.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests
from ratelimit import limits, sleep_and_retry

from config import BRAVE_SEARCH_API_KEY, DATA_DIR


# Brave Search API endpoint (News search)
BRAVE_NEWS_API = "https://api.search.brave.com/res/v1/news/search"

# Rate limiting: 1 request per 2 seconds (Brave free tier is restrictive)
@sleep_and_retry
@limits(calls=1, period=2)
def search_brave_news(query: str, count: int = 5) -> dict:
    """
    Search Brave News API for a query.

    Args:
        query: Search query string
        count: Number of results to return (max 20)

    Returns:
        Dict with results or error
    """
    if not BRAVE_SEARCH_API_KEY:
        return {"error": "BRAVE_SEARCH_API_KEY not configured", "results": []}

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY
    }

    params = {
        "q": query,
        "count": count,
        "freshness": "pd"  # Past day
    }

    try:
        response = requests.get(BRAVE_NEWS_API, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract relevant news items
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "url": item.get("url", ""),
                "age": item.get("age", ""),
                "source": item.get("meta_url", {}).get("netloc", "")
            })

        return {"results": results, "error": None}

    except requests.exceptions.HTTPError as e:
        return {"results": [], "error": f"HTTP error: {e.response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"results": [], "error": f"Request failed: {str(e)}"}
    except json.JSONDecodeError:
        return {"results": [], "error": "Invalid JSON response"}


def load_holdings() -> list:
    """Load holdings from holdings.json."""
    holdings_path = DATA_DIR / "holdings.json"

    if not holdings_path.exists():
        print(f"Error: {holdings_path} not found. Run ingestion.py first.")
        return []

    with open(holdings_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("all_holdings", [])


def run_research() -> dict:
    """
    Run the research pipeline - fetch news for all holdings.

    Returns:
        News buffer dict with all results
    """
    holdings = load_holdings()

    if not holdings:
        return {"error": "No holdings found", "news": []}

    print(f"Fetching news for {len(holdings)} holdings...")
    print(f"Rate limited to 1 request per 2 seconds\n")

    news_buffer = {
        "timestamp": datetime.now().isoformat(),
        "holdings_searched": 0,
        "total_articles": 0,
        "news": []
    }

    for i, holding in enumerate(holdings, 1):
        search_term = holding.get("search_term")

        if not search_term:
            print(f"[{i}/{len(holdings)}] Skipping {holding.get('name', 'unknown')} - no search term")
            continue

        print(f"[{i}/{len(holdings)}] Searching: {search_term}...", end=" ")

        result = search_brave_news(search_term)

        if result.get("error"):
            print(f"Error: {result['error']}")
        else:
            article_count = len(result["results"])
            print(f"Found {article_count} articles")

            # Add to news buffer
            news_buffer["news"].append({
                "holding": {
                    "name": holding.get("name"),
                    "asset_type": holding.get("asset_type"),
                    "market_value_eur": holding.get("market_value_eur"),
                    "search_term": search_term
                },
                "articles": result["results"]
            })

            news_buffer["holdings_searched"] += 1
            news_buffer["total_articles"] += article_count

    # Save to news_buffer.json
    output_path = DATA_DIR / "news_buffer.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(news_buffer, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Research complete!")
    print(f"  Holdings searched: {news_buffer['holdings_searched']}")
    print(f"  Total articles: {news_buffer['total_articles']}")
    print(f"  Output saved to: {output_path}")

    return news_buffer


if __name__ == "__main__":
    if not BRAVE_SEARCH_API_KEY:
        print("Error: BRAVE_SEARCH_API_KEY not set in .env")
        print("Get your free API key at: https://brave.com/search/api/")
    else:
        run_research()
