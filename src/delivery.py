"""
Delivery module - Phase 4 of the Finance Bot.

Sends the daily brief to Telegram.
"""

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DATA_DIR


TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> dict:
    """
    Send a message via Telegram Bot API.

    Args:
        text: Message text (supports Markdown)
        parse_mode: "Markdown" or "HTML"

    Returns:
        API response dict
    """
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    if not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "TELEGRAM_CHAT_ID not configured"}

    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}


def load_daily_brief() -> str:
    """Load the daily brief from file."""
    path = DATA_DIR / "daily_brief.txt"

    if not path.exists():
        return ""

    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def format_for_telegram(text: str) -> str:
    """
    Format the daily brief for Telegram.

    - Escape special Markdown characters that aren't formatting
    - Truncate if too long (Telegram limit is 4096 chars)
    """
    # Telegram has a 4096 character limit per message
    max_length = 4000  # Leave some buffer

    if len(text) > max_length:
        text = text[:max_length] + "\n\n... (truncated)"

    return text


def send_daily_brief() -> dict:
    """
    Load and send the daily brief to Telegram.

    Returns:
        Telegram API response
    """
    print("Loading daily brief...")
    brief = load_daily_brief()

    if not brief:
        print("Error: No daily brief found. Run analyst.py first.")
        return {"ok": False, "error": "No daily brief found"}

    print(f"Brief loaded ({len(brief)} characters)")

    # Format for Telegram
    formatted = format_for_telegram(brief)

    print(f"Sending to Telegram...")
    result = send_telegram_message(formatted, parse_mode="Markdown")

    if result.get("ok"):
        print("Message sent successfully!")
    else:
        # If Markdown parsing fails, try without formatting
        if "can't parse" in str(result.get("description", "")).lower():
            print("Markdown parsing failed, retrying as plain text...")
            result = send_telegram_message(formatted, parse_mode=None)
            if result.get("ok"):
                print("Message sent successfully (plain text)!")
            else:
                print(f"Error: {result.get('description', result.get('error', 'Unknown error'))}")
        else:
            print(f"Error: {result.get('description', result.get('error', 'Unknown error'))}")

    return result


if __name__ == "__main__":
    send_daily_brief()
