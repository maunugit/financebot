"""
Main pipeline - runs all phases of the Finance Bot.

Usage:
    python src/main.py              # Run with local LLM (default)
    python src/main.py --cloud      # Run with Claude API
    python src/main.py --no-send    # Skip Telegram delivery
"""

import argparse
import sys
from datetime import datetime

from config import DATA_DIR


def main():
    parser = argparse.ArgumentParser(
        description="Personal Finance Bot - Daily Brief Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py              Run full pipeline with local Ollama
  python src/main.py --cloud      Run with Claude API (better quality)
  python src/main.py --no-send    Run analysis but don't send to Telegram
        """
    )
    parser.add_argument(
        "--cloud", "-c",
        action="store_true",
        help="Use Claude API instead of local Ollama"
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Skip sending to Telegram"
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip portfolio ingestion (use existing holdings.json)"
    )
    parser.add_argument(
        "--skip-research",
        action="store_true",
        help="Skip news research (use existing news_buffer.json)"
    )
    parser.add_argument(
        "--skip-macro",
        action="store_true",
        help="Skip macro research (use existing macro_news.json)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("PERSONAL FINANCE BOT - DAILY BRIEF")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Phase 1: Ingestion
    if not args.skip_ingestion:
        print("\n[1/5] INGESTION - Updating portfolio data...")
        print("-" * 40)
        from ingestion import run_ingestion
        run_ingestion(archive_pdf_after=False)
    else:
        print("\n[1/5] INGESTION - Skipped (using existing holdings.json)")

    # Phase 2: Research (Holdings)
    if not args.skip_research:
        print("\n[2/5] RESEARCH - Fetching holdings news...")
        print("-" * 40)
        from researcher import run_research
        run_research()
    else:
        print("\n[2/5] RESEARCH - Skipped (using existing news_buffer.json)")

    # Phase 3: Macro Research
    if not args.skip_macro:
        print("\n[3/5] MACRO RESEARCH - Fetching narrative news...")
        print("-" * 40)
        from macro_researcher import run_macro_research
        run_macro_research()
    else:
        print("\n[3/5] MACRO RESEARCH - Skipped (using existing macro_news.json)")

    # Phase 4: Analysis
    print("\n[4/5] ANALYSIS - Generating daily brief...")
    print("-" * 40)
    from analyst import run_analysis
    backend = "cloud" if args.cloud else "local"
    include_macro = not args.skip_macro or (DATA_DIR / "macro_news.json").exists()
    result = run_analysis(backend=backend, include_macro=include_macro)

    if result.get("error"):
        print(f"\nAnalysis failed: {result['error']}")
        sys.exit(1)

    # Phase 5: Delivery
    if not args.no_send:
        print("\n[5/5] DELIVERY - Sending to Telegram...")
        print("-" * 40)
        from delivery import send_daily_brief
        send_result = send_daily_brief()

        if not send_result.get("ok"):
            print(f"\nTelegram delivery failed: {send_result.get('error', 'Unknown error')}")
    else:
        print("\n[5/5] DELIVERY - Skipped (--no-send flag)")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
