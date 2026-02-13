"""
Ingestion module - Phase 1 of the Finance Bot.

Combines Nordnet PDF parsing and Kraken API fetching into a unified holdings.json.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from config import (
    INPUTS_DIR, ARCHIVE_DIR, DATA_DIR,
    KRAKEN_API_KEY, KRAKEN_PRIVATE_KEY, PROJECT_ROOT
)
from pdf_parser import parse_nordnet_pdf, parse_pdf_simple
from kraken_fetcher import fetch_kraken_balances_with_prices


def find_nordnet_pdf() -> Path | None:
    """Find a Nordnet PDF in inputs directory or project root."""
    # Check inputs directory first
    for pdf in INPUTS_DIR.glob("*.pdf"):
        if "salkku" in pdf.name.lower() or "portfolio" in pdf.name.lower():
            return pdf

    # Also check project root for convenience
    for pdf in PROJECT_ROOT.glob("*.pdf"):
        if "salkku" in pdf.name.lower() or "portfolio" in pdf.name.lower():
            return pdf

    return None


def archive_pdf(pdf_path: Path) -> Path:
    """Move processed PDF to archive with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{pdf_path.stem}_{timestamp}{pdf_path.suffix}"
    archive_path = ARCHIVE_DIR / archive_name
    shutil.move(str(pdf_path), str(archive_path))
    return archive_path


def run_ingestion(archive_pdf_after: bool = True) -> dict:
    """
    Run the full ingestion pipeline.

    Args:
        archive_pdf_after: Whether to move the PDF to archive after processing

    Returns:
        Combined holdings data from all sources
    """
    timestamp = datetime.now().isoformat()

    combined_holdings = {
        "timestamp": timestamp,
        "sources": [],
        "all_holdings": [],
        "summary": {
            "total_value_eur": 0,
            "by_asset_type": {},
            "holdings_count": 0
        }
    }

    # 1. Parse Nordnet PDF
    pdf_path = find_nordnet_pdf()
    if pdf_path:
        print(f"Found Nordnet PDF: {pdf_path}")

        # Try table-based parsing first, fall back to pattern matching
        nordnet_data = parse_nordnet_pdf(pdf_path)
        total_nordnet = sum(len(acc["holdings"]) for acc in nordnet_data["accounts"])

        if total_nordnet == 0:
            print("Table parsing found no holdings, trying pattern matching...")
            nordnet_data = parse_pdf_simple(pdf_path)
            total_nordnet = sum(len(acc["holdings"]) for acc in nordnet_data["accounts"])

        nordnet_data["timestamp"] = timestamp
        combined_holdings["sources"].append(nordnet_data)

        # Flatten holdings for easy iteration
        for account in nordnet_data["accounts"]:
            for holding in account["holdings"]:
                holding["source"] = "nordnet"
                holding["account_id"] = account["account_id"]
                holding["account_name"] = account["account_name"]
                combined_holdings["all_holdings"].append(holding)

                # Update summary
                value = holding.get("market_value_eur", 0) or 0
                combined_holdings["summary"]["total_value_eur"] += value
                asset_type = holding.get("asset_type", "unknown")
                if asset_type not in combined_holdings["summary"]["by_asset_type"]:
                    combined_holdings["summary"]["by_asset_type"][asset_type] = 0
                combined_holdings["summary"]["by_asset_type"][asset_type] += value

        print(f"Extracted {total_nordnet} holdings from Nordnet PDF")

        # Archive the PDF
        if archive_pdf_after:
            archived = archive_pdf(pdf_path)
            print(f"Archived PDF to: {archived}")
    else:
        print("No Nordnet PDF found in inputs/ or project root")

    # 2. Fetch Kraken balances
    if KRAKEN_API_KEY and KRAKEN_PRIVATE_KEY:
        print("Fetching Kraken balances...")
        kraken_data = fetch_kraken_balances_with_prices(KRAKEN_API_KEY, KRAKEN_PRIVATE_KEY)
        kraken_data["timestamp"] = timestamp
        combined_holdings["sources"].append(kraken_data)

        if kraken_data.get("error"):
            print(f"Kraken API error: {kraken_data['error']}")
        else:
            # Add crypto holdings to combined list (skip fiat with no search term)
            for holding in kraken_data["holdings"]:
                if holding.get("search_term"):  # Skip EUR/USD balances
                    holding["source"] = "kraken"
                    combined_holdings["all_holdings"].append(holding)

                    # Update summary
                    value = holding.get("market_value_eur", 0) or 0
                    combined_holdings["summary"]["total_value_eur"] += value
                    if "crypto" not in combined_holdings["summary"]["by_asset_type"]:
                        combined_holdings["summary"]["by_asset_type"]["crypto"] = 0
                    combined_holdings["summary"]["by_asset_type"]["crypto"] += value

            print(f"Fetched {len(kraken_data['holdings'])} assets from Kraken")
    else:
        print("Kraken API keys not configured, skipping crypto fetch")

    # Update holdings count
    combined_holdings["summary"]["holdings_count"] = len(combined_holdings["all_holdings"])

    # Round summary values
    combined_holdings["summary"]["total_value_eur"] = round(
        combined_holdings["summary"]["total_value_eur"], 2
    )
    for asset_type in combined_holdings["summary"]["by_asset_type"]:
        combined_holdings["summary"]["by_asset_type"][asset_type] = round(
            combined_holdings["summary"]["by_asset_type"][asset_type], 2
        )

    # 3. Save to holdings.json
    output_path = DATA_DIR / "holdings.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_holdings, f, indent=2, ensure_ascii=False)

    print(f"\nSaved combined holdings to: {output_path}")
    print(f"\nSummary:")
    print(f"  Total holdings: {combined_holdings['summary']['holdings_count']}")
    print(f"  Total value: {combined_holdings['summary']['total_value_eur']:.2f} EUR")
    print(f"  By asset type:")
    for asset_type, value in combined_holdings["summary"]["by_asset_type"].items():
        print(f"    {asset_type}: {value:.2f} EUR")

    return combined_holdings


if __name__ == "__main__":
    # Run with archive disabled for testing (so we can re-run)
    result = run_ingestion(archive_pdf_after=False)
