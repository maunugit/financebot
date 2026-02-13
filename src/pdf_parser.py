"""
Nordnet salkkuraportti PDF parser.

Extracts holdings from Nordnet portfolio report PDFs, including:
- Stocks (Osakkeet)
- ETFs (pörssilistatut arvopaperit)
- Funds (Rahastot)
"""

import re
import pdfplumber
from pathlib import Path
from typing import Optional


def clean_name(name: str) -> str:
    """Clean instrument name by removing flags and extra whitespace."""
    # Remove flag emojis and special characters at the start
    name = re.sub(r'^[🇩🇪🇫🇮🇺🇸🇬🇧\s+\-]+', '', name)
    # Remove trailing ellipsis or truncation
    name = re.sub(r'\.{3,}$', '', name)
    name = re.sub(r'…$', '', name)
    return name.strip()


def generate_search_term(name: str, asset_type: str) -> str:
    """
    Generate a search-friendly term for news lookup.
    Handles fuzzy matching challenge by simplifying company names.
    """
    # Clean the name first
    term = clean_name(name)

    # Remove common suffixes that don't help with search
    suffixes_to_remove = [
        r'\s+Corporation\s*[A-Z]?$',
        r'\s+Corp\.?\s*[A-Z]?$',
        r'\s+Oyj$',
        r'\s+Abp$',
        r'\s+PLC\s*-?\s*[A-Z]?$',
        r'\s+Ltd\.?$',
        r'\s+Inc\.?$',
        r'\s+UCITS\s+ETF.*$',
        r'\s+ETF.*$',
        r'\s+Indeksi$',
        r'\s+Index$',
        r'\s+USD\s*\(.*\)$',
        r'\s+-\s+USD\s+Acc$',
    ]

    for suffix in suffixes_to_remove:
        term = re.sub(suffix, '', term, flags=re.IGNORECASE)

    # Special handling for known instruments
    term_mappings = {
        'iShares Automation & Robotics': 'automation robotics ETF',
        'VanEck Gold Miners': 'gold miners ETF',
        'iShares Core MSCI EM IMI': 'emerging markets ETF',
        'VanEck Semiconductor': 'semiconductor ETF',
        'Nordnet Maailma': 'global index fund',
        'Nordnet Teknologia': 'technology index fund',
    }

    for key, value in term_mappings.items():
        if key.lower() in term.lower():
            return value

    # For stocks, add "stock" to improve search relevance
    if asset_type == 'stock':
        return f"{term} stock"

    return term.strip()


def parse_number(value: str) -> Optional[float]:
    """Parse Finnish number format (comma as decimal separator)."""
    if not value or value == '-':
        return None
    # Remove spaces used as thousand separators
    value = value.replace(' ', '').replace('\xa0', '')
    # Handle Finnish decimal format
    value = value.replace(',', '.')
    # Remove currency symbols and percentage signs
    value = re.sub(r'[€%EURAD]', '', value)
    # Handle plus/minus signs
    value = value.replace('+', '').strip()
    try:
        return float(value)
    except ValueError:
        return None


def extract_holdings_from_text(text: str) -> list[dict]:
    """
    Extract holdings by parsing the raw text content.
    This is a fallback method if table extraction fails.
    """
    holdings = []
    lines = text.split('\n')

    current_account = None
    current_section = None  # 'stocks', 'etfs', 'funds'

    for i, line in enumerate(lines):
        line = line.strip()

        # Detect account headers
        if 'Osakesäästötili' in line:
            current_account = 'stock_savings'
        elif 'Osake- ja rahastosalkku' in line:
            current_account = 'investment'

        # Detect section headers
        if 'Osakkeet ja pörssilistatut arvopaperit' in line:
            current_section = 'stocks_etfs'
        elif line == 'Rahastot' or line.startswith('Rahastot '):
            current_section = 'funds'

        # Skip headers and non-data lines
        if any(skip in line for skip in ['Markk.hinta', 'Hank.hinta', 'Yhteensä', 'Likvidit varat', 'Muut sijoitukset']):
            continue

    return holdings


def parse_nordnet_pdf(pdf_path: Path) -> dict:
    """
    Parse a Nordnet salkkuraportti PDF and extract all holdings.

    Returns:
        dict with structure:
        {
            "source": "nordnet",
            "accounts": [
                {
                    "account_id": "...",
                    "account_type": "...",
                    "holdings": [...]
                }
            ],
            "timestamp": "..."
        }
    """
    holdings_data = {
        "source": "nordnet",
        "accounts": [],
        "timestamp": None
    }

    with pdfplumber.open(pdf_path) as pdf:
        current_account = None
        current_account_id = None
        current_section = None

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            lines = text.split('\n')

            # Extract tables from page
            tables = page.extract_tables()

            for line in lines:
                line = line.strip()

                # Detect account headers with ID
                if 'Osakesäästötili' in line:
                    # Save previous account if exists
                    if current_account:
                        holdings_data["accounts"].append(current_account)

                    # Extract account ID (e.g., "62656327")
                    id_match = re.search(r'(\d{8})', line)
                    current_account_id = id_match.group(1) if id_match else None
                    current_account = {
                        "account_id": current_account_id,
                        "account_type": "stock_savings",
                        "account_name": "Osakesäästötili",
                        "holdings": []
                    }
                    current_section = "stocks"

                elif 'Osake- ja rahastosalkku' in line:
                    if current_account:
                        holdings_data["accounts"].append(current_account)

                    id_match = re.search(r'(\d{8})', line)
                    current_account_id = id_match.group(1) if id_match else None
                    current_account = {
                        "account_id": current_account_id,
                        "account_type": "investment",
                        "account_name": "Osake- ja rahastosalkku",
                        "holdings": []
                    }
                    current_section = "etfs"

                # Detect section changes within account
                if 'Rahastot' in line and 'Markk.hinta' in line:
                    current_section = "funds"

            # Process tables
            for table in tables:
                if not table or len(table) < 2:
                    continue

                for row in table:
                    if not row or len(row) < 4:
                        continue

                    # Skip header rows
                    first_cell = str(row[0] or '').strip()
                    if any(skip in first_cell for skip in ['Markk.hinta', 'Osakkeet ja', 'Rahastot', 'Muut sijoitukset', 'Yhteensä', 'Likvidit']):
                        continue

                    # Try to parse as holding row
                    # Expected format: Name, Price, Purchase Price, Quantity, Market Value, P/L, Share%
                    if len(row) >= 6 and current_account:
                        name = clean_name(str(row[0] or ''))
                        if not name or len(name) < 2:
                            continue

                        # Determine asset type based on section and name patterns
                        if current_section == "stocks":
                            asset_type = "stock"
                        elif current_section == "funds":
                            asset_type = "fund"
                        elif 'ETF' in name or 'UCITS' in name:
                            asset_type = "etf"
                        elif 'Indeksi' in name or 'Index' in name:
                            asset_type = "fund"
                        else:
                            asset_type = "stock"

                        holding = {
                            "name": name,
                            "asset_type": asset_type,
                            "market_price": parse_number(str(row[1] or '')),
                            "purchase_price": parse_number(str(row[2] or '')),
                            "quantity": parse_number(str(row[3] or '')),
                            "market_value_eur": parse_number(str(row[4] or '')),
                            "unrealized_pl": parse_number(str(row[5] or '')),
                            "portfolio_share_pct": parse_number(str(row[6] or '')) if len(row) > 6 else None,
                            "search_term": generate_search_term(name, asset_type)
                        }

                        # Only add if we have meaningful data
                        if holding["name"] and holding["quantity"]:
                            current_account["holdings"].append(holding)

        # Don't forget the last account
        if current_account:
            holdings_data["accounts"].append(current_account)

    return holdings_data


def parse_pdf_simple(pdf_path: Path) -> dict:
    """
    Simplified parser that extracts text and uses pattern matching.
    More robust for varied PDF structures.
    """
    holdings_data = {
        "source": "nordnet",
        "accounts": [],
        "timestamp": None
    }

    # Known holdings patterns based on the PDF structure we've seen
    # Format: (name_pattern, asset_type, search_term)
    known_patterns = [
        # ETFs from Osake- ja rahastosalkku
        (r'iShares Automation.*?Robotics.*?UCITS', 'etf', 'automation robotics ETF'),
        (r'VanEck Gold Miners UCITS ETF', 'etf', 'gold miners ETF VanEck'),
        (r'iShares Core MSCI EM.*?UCITS', 'etf', 'emerging markets ETF iShares'),
        (r'VanEck Semiconductor UCITS ETF', 'etf', 'semiconductor ETF VanEck'),
        # Funds
        (r'Nordnet Maailma Indeksi', 'fund', 'Nordnet global index fund'),
        (r'Nordnet Teknologia Indeksi', 'fund', 'Nordnet technology index fund'),
        # Finnish stocks from Osakesäästötili
        (r'Bittium Corporation', 'stock', 'Bittium stock'),
        (r'Fortum Corporation', 'stock', 'Fortum stock'),
        (r'Mandatum Oyj', 'stock', 'Mandatum stock'),
        (r'Nordea Bank Abp', 'stock', 'Nordea Bank stock'),
        (r'Orion Corporation', 'stock', 'Orion Corporation stock Finland'),
    ]

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

        # Extract holdings using pattern matching with context
        investment_account = {
            "account_id": None,
            "account_type": "investment",
            "account_name": "Osake- ja rahastosalkku",
            "holdings": []
        }

        stock_savings_account = {
            "account_id": None,
            "account_type": "stock_savings",
            "account_name": "Osakesäästötili",
            "holdings": []
        }

        # Extract account IDs
        osake_match = re.search(r'Osake- ja rahastosalkku\s*(\d{8})', full_text)
        if osake_match:
            investment_account["account_id"] = osake_match.group(1)

        ost_match = re.search(r'Osakesäästötili\s*(\d{8})', full_text)
        if ost_match:
            stock_savings_account["account_id"] = ost_match.group(1)

        # Parse each line looking for holdings
        # Pattern: Name followed by price data
        # Example: "Bittium Corporation 37,60 EUR 21,38 12 451,20 +194,60 15,45%"
        holding_pattern = re.compile(
            r'^(.+?)\s+'  # Name
            r'(\d+[,\.]\d+)\s*EUR?\s+'  # Market price
            r'(\d+[,\.]\d+)\s+'  # Purchase price
            r'(\d+[,\.]*\d*)\s+'  # Quantity
            r'(\d[\d\s]*[,\.]\d+)\s+'  # Market value
            r'([+\-]?\d+[,\.]\d+)\s+'  # P/L
            r'(\d+[,\.]\d+)\s*%'  # Portfolio share
        )

        lines = full_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            # Track which section we're in
            if 'Osake- ja rahastosalkku' in line:
                current_section = 'investment'
            elif 'Osakesäästötili' in line:
                current_section = 'stock_savings'
            elif 'Rahastot' in line and 'Markk.hinta' not in line:
                # Switch to funds section within investment account
                pass

            # Try to match holding pattern
            match = holding_pattern.match(line)
            if match:
                name = clean_name(match.group(1))

                # Determine asset type
                if 'ETF' in name or 'UCITS' in name:
                    asset_type = 'etf'
                elif 'Indeksi' in name:
                    asset_type = 'fund'
                elif current_section == 'stock_savings':
                    asset_type = 'stock'
                else:
                    asset_type = 'stock'

                holding = {
                    "name": name,
                    "asset_type": asset_type,
                    "market_price": parse_number(match.group(2)),
                    "purchase_price": parse_number(match.group(3)),
                    "quantity": parse_number(match.group(4)),
                    "market_value_eur": parse_number(match.group(5)),
                    "unrealized_pl": parse_number(match.group(6)),
                    "portfolio_share_pct": parse_number(match.group(7)),
                    "search_term": generate_search_term(name, asset_type)
                }

                if current_section == 'investment':
                    investment_account["holdings"].append(holding)
                elif current_section == 'stock_savings':
                    stock_savings_account["holdings"].append(holding)

        if investment_account["holdings"]:
            holdings_data["accounts"].append(investment_account)
        if stock_savings_account["holdings"]:
            holdings_data["accounts"].append(stock_savings_account)

    return holdings_data


if __name__ == "__main__":
    import json
    from config import PROJECT_ROOT

    pdf_path = PROJECT_ROOT / "salkkuraportti.pdf"

    if pdf_path.exists():
        print(f"Parsing: {pdf_path}")

        # Try table-based parsing first
        result = parse_nordnet_pdf(pdf_path)

        # If no holdings found, try simple pattern matching
        total_holdings = sum(len(acc["holdings"]) for acc in result["accounts"])
        if total_holdings == 0:
            print("Table parsing found no holdings, trying pattern matching...")
            result = parse_pdf_simple(pdf_path)

        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"PDF not found: {pdf_path}")
