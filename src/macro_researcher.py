"""
Macro Researcher module - Tracks long-term investment narratives.

Fetches news for thesis-level queries (Fed policy, AI agents, quantum/L2)
that aren't tied to specific holdings but affect multi-decade portfolios.
"""

import json
from datetime import datetime

from ratelimit import limits, sleep_and_retry
import requests

from config import BRAVE_SEARCH_API_KEY, DATA_DIR


# Brave Search API endpoint (News search)
BRAVE_NEWS_API = "https://api.search.brave.com/res/v1/news/search"

# Thesis queries
THESIS_QUERIES = [
    {
        "id": "fed_policy",
        "name": "Fed Policy & Warsh Era",
        "query": "Federal Reserve monetary policy interest rates Kevin Warsh",
        "description": "Fed policy direction, rate decisions, and potential Warsh chairmanship impact"
    },
    {
        "id": "ai_agents",
        "name": "AI Agents On-Chain",
        "query": "AI agents cryptocurrency blockchain autonomous transactions DeFi",
        "description": "AI agents as economic actors on blockchain, autonomous DeFi, agent-to-agent payments"
    },
    {
        "id": "quantum_l2",
        "name": "Quantum Resistance & L2 Infrastructure",
        "query": "quantum computing cryptography resistance blockchain Layer 2 infrastructure",
        "description": "Quantum threats to crypto, post-quantum cryptography, L2 scaling milestones"
    },
    {
        "id": "tungsten_market",
        "name": "Tungsten Strategic Supply & Almonty Industries",
        "query": "tungsten price trends 2026 ALmonty Industries Sangdong mine supply deficit critical minerals",
        "description": "Global tungsten supply/demand, Sangdong mine production milestones, and strategic metal stockpiling news"
    }
]


@sleep_and_retry
@limits(calls=1, period=2)
def search_brave_news(query: str, count: int = 20) -> dict:
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
        "count": min(count, 20),  # Brave API max is 20
        "freshness": "pw"  # Past week (more results for macro themes)
    }

    try:
        response = requests.get(BRAVE_NEWS_API, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

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


def get_thesis_queries() -> list:
    """Return the current list of thesis queries."""
    return THESIS_QUERIES.copy()


def run_macro_research() -> dict:
    """
    Run the macro research pipeline - fetch news for all thesis queries.

    Returns:
        Macro news buffer dict with all results
    """
    queries = get_thesis_queries()

    print(f"Fetching macro news for {len(queries)} thesis themes...")
    print(f"Rate limited to 1 request per 2 seconds\n")

    macro_buffer = {
        "timestamp": datetime.now().isoformat(),
        "themes_searched": 0,
        "total_articles": 0,
        "themes": []
    }

    for i, theme in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Searching: {theme['name']}...", end=" ")

        result = search_brave_news(theme["query"], count=20)

        if result.get("error"):
            print(f"Error: {result['error']}")
        else:
            article_count = len(result["results"])
            print(f"Found {article_count} articles")

            macro_buffer["themes"].append({
                "id": theme["id"],
                "name": theme["name"],
                "description": theme["description"],
                "query": theme["query"],
                "articles": result["results"]
            })

            macro_buffer["themes_searched"] += 1
            macro_buffer["total_articles"] += article_count

    # Save to macro_news.json
    output_path = DATA_DIR / "macro_news.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(macro_buffer, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Macro research complete!")
    print(f"  Themes searched: {macro_buffer['themes_searched']}")
    print(f"  Total articles: {macro_buffer['total_articles']}")
    print(f"  Output saved to: {output_path}")

    return macro_buffer


if __name__ == "__main__":
    if not BRAVE_SEARCH_API_KEY:
        print("Error: BRAVE_SEARCH_API_KEY not set in .env")
        print("Get your free API key at: https://brave.com/search/api/")
    else:
        run_macro_research()
