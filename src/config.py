"""Configuration loader for API keys and settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Kraken API
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "").strip().strip('"')
KRAKEN_PRIVATE_KEY = os.getenv("KRAKEN_PRIVATE_KEY", "").strip().strip('"')

# Brave Search API
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip().strip('"')

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"')

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"')
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip().strip('"')

# Paths
INPUTS_DIR = PROJECT_ROOT / "inputs"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
DATA_DIR = PROJECT_ROOT / "data"

# Ensure directories exist
INPUTS_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
