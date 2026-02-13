"""
Kraken API fetcher for cryptocurrency balances.

Uses read-only API access to fetch current holdings.
"""

import krakenex
from typing import Optional


# Mapping of Kraken asset codes to readable names and search terms
ASSET_INFO = {
    # Major cryptocurrencies
    "XXBT": {"name": "Bitcoin", "symbol": "BTC", "search_term": "Bitcoin BTC crypto"},
    "XETH": {"name": "Ethereum", "symbol": "ETH", "search_term": "Ethereum ETH crypto"},
    "XBT": {"name": "Bitcoin", "symbol": "BTC", "search_term": "Bitcoin BTC crypto"},
    "ETH": {"name": "Ethereum", "symbol": "ETH", "search_term": "Ethereum ETH crypto"},
    "XXRP": {"name": "Ripple", "symbol": "XRP", "search_term": "Ripple XRP crypto"},
    "XRP": {"name": "Ripple", "symbol": "XRP", "search_term": "Ripple XRP crypto"},
    "XLTC": {"name": "Litecoin", "symbol": "LTC", "search_term": "Litecoin LTC crypto"},
    "LTC": {"name": "Litecoin", "symbol": "LTC", "search_term": "Litecoin LTC crypto"},
    "XXLM": {"name": "Stellar", "symbol": "XLM", "search_term": "Stellar XLM crypto"},
    "XLM": {"name": "Stellar", "symbol": "XLM", "search_term": "Stellar XLM crypto"},
    "XDOT": {"name": "Polkadot", "symbol": "DOT", "search_term": "Polkadot DOT crypto"},
    "DOT": {"name": "Polkadot", "symbol": "DOT", "search_term": "Polkadot DOT crypto"},
    "ATOM": {"name": "Cosmos", "symbol": "ATOM", "search_term": "Cosmos ATOM crypto"},
    "ADA": {"name": "Cardano", "symbol": "ADA", "search_term": "Cardano ADA crypto"},
    "SOL": {"name": "Solana", "symbol": "SOL", "search_term": "Solana SOL crypto"},
    "LINK": {"name": "Chainlink", "symbol": "LINK", "search_term": "Chainlink LINK crypto"},
    "MATIC": {"name": "Polygon", "symbol": "MATIC", "search_term": "Polygon MATIC crypto"},
    "AVAX": {"name": "Avalanche", "symbol": "AVAX", "search_term": "Avalanche AVAX crypto"},
    "UNI": {"name": "Uniswap", "symbol": "UNI", "search_term": "Uniswap UNI crypto"},
    "AAVE": {"name": "Aave", "symbol": "AAVE", "search_term": "Aave AAVE crypto"},
    "SAND": {"name": "The Sandbox", "symbol": "SAND", "search_term": "The Sandbox SAND crypto"},
    "MANA": {"name": "Decentraland", "symbol": "MANA", "search_term": "Decentraland MANA crypto"},
    "SHIB": {"name": "Shiba Inu", "symbol": "SHIB", "search_term": "Shiba Inu SHIB crypto"},
    "DOGE": {"name": "Dogecoin", "symbol": "DOGE", "search_term": "Dogecoin DOGE crypto"},
    "PEPE": {"name": "Pepe", "symbol": "PEPE", "search_term": "Pepe PEPE crypto"},
    # Stablecoins (usually not interesting for news, but include for completeness)
    "ZUSD": {"name": "US Dollar", "symbol": "USD", "search_term": None},
    "ZEUR": {"name": "Euro", "symbol": "EUR", "search_term": None},
    "USD": {"name": "US Dollar", "symbol": "USD", "search_term": None},
    "EUR": {"name": "Euro", "symbol": "EUR", "search_term": None},
    "USDT": {"name": "Tether", "symbol": "USDT", "search_term": "Tether USDT stablecoin"},
    "USDC": {"name": "USD Coin", "symbol": "USDC", "search_term": "USD Coin USDC stablecoin"},
    "DAI": {"name": "Dai", "symbol": "DAI", "search_term": "Dai DAI stablecoin"},
}


def get_asset_info(kraken_code: str) -> dict:
    """Get readable name and search term for a Kraken asset code."""
    if kraken_code in ASSET_INFO:
        return ASSET_INFO[kraken_code]

    # Fallback for unknown assets
    # Remove common prefixes/suffixes
    clean_code = kraken_code
    if clean_code.startswith('X') or clean_code.startswith('Z'):
        clean_code = clean_code[1:]

    return {
        "name": clean_code,
        "symbol": clean_code,
        "search_term": f"{clean_code} crypto"
    }


def fetch_kraken_balances(api_key: str, private_key: str) -> dict:
    """
    Fetch current balances from Kraken.

    Returns:
        dict with structure:
        {
            "source": "kraken",
            "holdings": [
                {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "asset_type": "crypto",
                    "quantity": 0.5,
                    "search_term": "Bitcoin BTC crypto"
                }
            ],
            "error": None or error message
        }
    """
    result = {
        "source": "kraken",
        "holdings": [],
        "error": None
    }

    try:
        # Initialize Kraken API
        api = krakenex.API()
        api.key = api_key
        api.secret = private_key

        # Fetch account balance
        response = api.query_private('Balance')

        if response.get('error'):
            result["error"] = str(response['error'])
            return result

        balances = response.get('result', {})

        for asset_code, balance_str in balances.items():
            balance = float(balance_str)

            # Skip zero or near-zero balances
            if balance < 0.00000001:
                continue

            asset_info = get_asset_info(asset_code)

            holding = {
                "name": asset_info["name"],
                "symbol": asset_info["symbol"],
                "kraken_code": asset_code,
                "asset_type": "crypto",
                "quantity": balance,
                "search_term": asset_info["search_term"]
            }

            result["holdings"].append(holding)

    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_kraken_balances_with_prices(api_key: str, private_key: str) -> dict:
    """
    Fetch balances with current EUR prices from Kraken.

    Returns holdings with market_value_eur populated.
    """
    result = fetch_kraken_balances(api_key, private_key)

    if result["error"] or not result["holdings"]:
        return result

    try:
        api = krakenex.API()
        api.key = api_key
        api.secret = private_key

        # Get ticker prices for each asset
        for holding in result["holdings"]:
            symbol = holding["symbol"]

            # Skip fiat currencies
            if symbol in ["EUR", "USD"]:
                holding["market_price_eur"] = 1.0 if symbol == "EUR" else None
                holding["market_value_eur"] = holding["quantity"] if symbol == "EUR" else None
                continue

            # Try to get EUR price
            pair = f"{symbol}EUR"
            ticker_response = api.query_public('Ticker', {'pair': pair})

            if not ticker_response.get('error') and ticker_response.get('result'):
                # Get the first result (handle Kraken's weird key naming)
                for key, data in ticker_response['result'].items():
                    price = float(data['c'][0])  # 'c' is the last trade closed [price, lot volume]
                    holding["market_price_eur"] = price
                    holding["market_value_eur"] = price * holding["quantity"]
                    break

    except Exception as e:
        # Don't fail the whole request if price fetching fails
        result["price_error"] = str(e)

    return result


if __name__ == "__main__":
    import json
    from config import KRAKEN_API_KEY, KRAKEN_PRIVATE_KEY

    if KRAKEN_API_KEY and KRAKEN_PRIVATE_KEY:
        print("Fetching Kraken balances...")
        result = fetch_kraken_balances_with_prices(KRAKEN_API_KEY, KRAKEN_PRIVATE_KEY)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Kraken API keys not configured in .env")
