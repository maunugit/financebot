"""
Analyst module - Phase 3 of the Finance Bot.

Uses local Ollama LLM or Claude API to analyze news and generate portfolio insights.
"""

import argparse
import json
import re
from datetime import datetime

import requests

from config import DATA_DIR, ANTHROPIC_API_KEY

# Ollama API endpoint
OLLAMA_API = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "deepseek-r1:7b"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are a concise financial analyst assistant. Your job is to review news about a user's portfolio holdings AND macro themes, then identify what matters for a multi-decade investment horizon.

PART 1 - HOLDINGS ANALYSIS:
Focus on:
- Thesis-changing news (earnings surprises, major contracts, regulatory changes, management changes)
- Sector-wide impacts (interest rates, commodity prices, geopolitical events)
- Significant price movements with clear catalysts

Ignore:
- Minor daily price fluctuations without news
- Generic market commentary
- Repeated/duplicate news items
- Irrelevant articles that don't actually relate to the holding

PART 2 - MACRO NARRATIVE ANALYSIS:
For each macro theme, evaluate whether recent developments represent:
- STRUCTURAL TAILWIND: Long-term positive catalyst for the portfolio thesis
- EXISTENTIAL RISK: Threat that could fundamentally undermine the investment thesis
- NEUTRAL/NOISE: No meaningful signal for long-term positioning

Provide actionable implications:
- "Consider accumulating X because..."
- "Watch for entry point in Y as..."
- "Reduce exposure to Z if..."

Output format:
1. Start with a 1-2 sentence overall market summary if relevant
2. Holdings section: bullet points grouped by holding (only noteworthy news)
3. "Nothing notable" section listing holdings with no significant news
4. Macro section header: "🌍 MACRO NARRATIVE UPDATE"
5. For each macro theme: signal classification + 1-2 sentence rationale + actionable implication
6. Keep it concise - this is a daily brief, not a research report"""


def clean_deepseek_output(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from DeepSeek output."""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = cleaned.strip()
    return cleaned


def load_news_buffer() -> dict:
    """Load the news buffer from researcher output."""
    path = DATA_DIR / "news_buffer.json"
    if not path.exists():
        return {"error": "news_buffer.json not found. Run researcher.py first."}

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_holdings_summary() -> dict:
    """Load holdings summary for context."""
    path = DATA_DIR / "holdings.json"
    if not path.exists():
        return {}

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("summary", {})


def load_macro_news() -> dict:
    """Load the macro news buffer from macro_researcher output."""
    path = DATA_DIR / "macro_news.json"
    if not path.exists():
        return {"themes": [], "total_articles": 0}

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_news_for_llm(news_buffer: dict) -> str:
    """Format the news buffer into a prompt for the LLM."""
    lines = []

    for item in news_buffer.get("news", []):
        holding = item["holding"]
        articles = item["articles"]

        lines.append(f"\n## {holding['name']} ({holding['asset_type'].upper()})")
        lines.append(f"Value: €{holding.get('market_value_eur', 0):.2f}")

        if not articles:
            lines.append("No recent news found.")
        else:
            for i, article in enumerate(articles, 1):
                lines.append(f"\n{i}. {article['title']}")
                if article.get('description'):
                    desc = article['description'][:300]
                    if len(article['description']) > 300:
                        desc += "..."
                    lines.append(f"   {desc}")
                lines.append(f"   Source: {article.get('source', 'unknown')} | {article.get('age', '')}")

    return "\n".join(lines)


def format_macro_news_for_llm(macro_buffer: dict) -> str:
    """Format the macro news buffer into a prompt section for the LLM."""
    if not macro_buffer.get("themes"):
        return ""

    lines = ["\n\n" + "=" * 50]
    lines.append("MACRO THEMES (Long-term narrative tracking)")
    lines.append("=" * 50)

    for theme in macro_buffer.get("themes", []):
        lines.append(f"\n## {theme['name']}")
        lines.append(f"Tracking: {theme['description']}")

        articles = theme.get("articles", [])
        if not articles:
            lines.append("No recent news found.")
        else:
            for i, article in enumerate(articles[:20], 1):  # Cap at 20
                lines.append(f"\n{i}. {article['title']}")
                if article.get('description'):
                    desc = article['description'][:300]
                    if len(article['description']) > 300:
                        desc += "..."
                    lines.append(f"   {desc}")
                lines.append(f"   Source: {article.get('source', 'unknown')} | {article.get('age', '')}")

    return "\n".join(lines)


def build_user_prompt(news_text: str, summary: dict, macro_text: str = "") -> str:
    """Build the user prompt with portfolio context, holdings news, and macro news."""
    prompt = f"""Here is my portfolio summary:
- Total value: €{summary.get('total_value_eur', 0):,.2f}
- Holdings: {summary.get('holdings_count', 0)} positions
- Breakdown: {', '.join(f"{k}: €{v:,.2f}" for k, v in summary.get('by_asset_type', {}).items())}
- Investment horizon: 20-30 years (long-term accumulation)

Here is the recent news for each holding:
{news_text}"""

    if macro_text:
        prompt += f"""
{macro_text}

Please analyze BOTH the holdings news AND the macro themes. For macro themes, classify each as STRUCTURAL TAILWIND, EXISTENTIAL RISK, or NEUTRAL, and provide actionable implications for my long-term portfolio positioning."""
    else:
        prompt += """

Please analyze this news and provide a daily brief. Focus on what actually matters for my portfolio."""

    return prompt


def analyze_with_ollama(news_text: str, summary: dict, model: str = DEFAULT_OLLAMA_MODEL, macro_text: str = "") -> dict:
    """
    Send news to Ollama for analysis.

    Args:
        news_text: Formatted news text
        summary: Portfolio summary for context
        model: Ollama model to use
        macro_text: Formatted macro news text (optional)

    Returns:
        Dict with analysis results or error
    """
    user_prompt = build_user_prompt(news_text, summary, macro_text)

    payload = {
        "model": model,
        "prompt": user_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1500
        }
    }

    try:
        print(f"Sending to Ollama ({model})...")
        print("This may take a moment while the model loads and generates...\n")

        response = requests.post(OLLAMA_API, json=payload, timeout=300)
        response.raise_for_status()

        result = response.json()

        raw_response = result.get("response", "")
        cleaned_response = clean_deepseek_output(raw_response)

        return {
            "analysis": cleaned_response,
            "model": model,
            "backend": "ollama",
            "eval_count": result.get("eval_count", 0),
            "eval_duration_ms": result.get("eval_duration", 0) / 1_000_000,
            "error": None
        }

    except requests.exceptions.ConnectionError:
        return {"analysis": "", "error": "Cannot connect to Ollama. Is it running? Try: ollama serve"}
    except requests.exceptions.Timeout:
        return {"analysis": "", "error": "Ollama request timed out (>5 min)"}
    except requests.exceptions.RequestException as e:
        return {"analysis": "", "error": f"Request failed: {str(e)}"}


def analyze_with_claude(news_text: str, summary: dict, model: str = DEFAULT_CLAUDE_MODEL, macro_text: str = "") -> dict:
    """
    Send news to Claude API for analysis.

    Args:
        news_text: Formatted news text
        summary: Portfolio summary for context
        model: Claude model to use
        macro_text: Formatted macro news text (optional)

    Returns:
        Dict with analysis results or error
    """
    if not ANTHROPIC_API_KEY:
        return {"analysis": "", "error": "ANTHROPIC_API_KEY not configured in .env"}

    # Import here to avoid requiring anthropic for local-only usage
    try:
        import anthropic
    except ImportError:
        return {"analysis": "", "error": "anthropic package not installed. Run: pip install anthropic"}

    user_prompt = build_user_prompt(news_text, summary, macro_text)

    try:
        print(f"Sending to Claude API ({model})...")

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        analysis = message.content[0].text

        return {
            "analysis": analysis,
            "model": model,
            "backend": "claude",
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
            "error": None
        }

    except anthropic.APIConnectionError:
        return {"analysis": "", "error": "Cannot connect to Claude API"}
    except anthropic.AuthenticationError:
        return {"analysis": "", "error": "Invalid ANTHROPIC_API_KEY"}
    except anthropic.APIError as e:
        return {"analysis": "", "error": f"Claude API error: {str(e)}"}


def run_analysis(backend: str = "local", model: str = None, include_macro: bool = True) -> dict:
    """
    Run the full analysis pipeline.

    Args:
        backend: "local" for Ollama, "cloud" for Claude API
        model: Model to use (defaults based on backend)
        include_macro: Whether to include macro news in analysis

    Returns:
        Analysis results dict
    """
    print("Loading news buffer...")
    news_buffer = load_news_buffer()

    if news_buffer.get("error"):
        print(f"Error: {news_buffer['error']}")
        return news_buffer

    print(f"Found {news_buffer.get('total_articles', 0)} articles for {news_buffer.get('holdings_searched', 0)} holdings")

    # Load macro news if available and requested
    macro_text = ""
    macro_buffer = {"total_articles": 0, "themes_searched": 0}
    if include_macro:
        macro_buffer = load_macro_news()
        if macro_buffer.get("themes"):
            print(f"Found {macro_buffer.get('total_articles', 0)} macro articles for {macro_buffer.get('themes_searched', 0)} themes")
            macro_text = format_macro_news_for_llm(macro_buffer)
        else:
            print("No macro news found (run macro_researcher.py to fetch)")

    # Load portfolio summary for context
    summary = load_holdings_summary()

    # Format news for LLM
    news_text = format_news_for_llm(news_buffer)

    # Run analysis with selected backend
    if backend == "cloud":
        model = model or DEFAULT_CLAUDE_MODEL
        result = analyze_with_claude(news_text, summary, model, macro_text)
    else:
        model = model or DEFAULT_OLLAMA_MODEL
        result = analyze_with_ollama(news_text, summary, model, macro_text)

    if result.get("error"):
        print(f"Error: {result['error']}")
        return result

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "model": result.get("model", model),
        "backend": result.get("backend", backend),
        "holdings_analyzed": news_buffer.get("holdings_searched", 0),
        "articles_processed": news_buffer.get("total_articles", 0),
        "macro_themes_analyzed": macro_buffer.get("themes_searched", 0),
        "macro_articles_processed": macro_buffer.get("total_articles", 0),
        "analysis": result["analysis"],
        "stats": {}
    }

    # Add backend-specific stats
    if result.get("backend") == "ollama":
        output["stats"]["tokens_generated"] = result.get("eval_count", 0)
        output["stats"]["generation_time_ms"] = result.get("eval_duration_ms", 0)
    else:
        output["stats"]["input_tokens"] = result.get("input_tokens", 0)
        output["stats"]["output_tokens"] = result.get("output_tokens", 0)

    # Save to file
    output_path = DATA_DIR / "analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Also save a plain text version for easy reading
    text_path = DATA_DIR / "daily_brief.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(f"Daily Portfolio Brief - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Generated by: {result.get('model', model)}\n")
        f.write("=" * 50 + "\n\n")
        f.write(result["analysis"])

    print("\n" + "=" * 50)
    print("DAILY BRIEF")
    print("=" * 50)
    print(result["analysis"])
    print("\n" + "=" * 50)
    print(f"Backend: {result.get('backend', backend)}")
    print(f"Model: {result.get('model', model)}")
    if result.get("backend") == "claude":
        print(f"Tokens: {result.get('input_tokens', 0)} in / {result.get('output_tokens', 0)} out")
    print(f"Saved to: {output_path}")
    print(f"Text version: {text_path}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze portfolio news with LLM")
    parser.add_argument(
        "--backend", "-b",
        choices=["local", "cloud"],
        default="local",
        help="Backend to use: 'local' for Ollama, 'cloud' for Claude API (default: local)"
    )
    parser.add_argument(
        "--model", "-m",
        help="Model to use (default: deepseek-r1:7b for local, claude-sonnet-4-20250514 for cloud)"
    )

    args = parser.parse_args()
    run_analysis(backend=args.backend, model=args.model)
