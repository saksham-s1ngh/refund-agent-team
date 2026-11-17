import os
from pathlib import Path

# Load .env into os.environ without overriding variables already set.
# ponytail: minimal KEY=VALUE parser (no quotes/export); swap for python-dotenv if .env grows.
_env = Path(__file__).with_name(".env")
if _env.exists():
    for line in _env.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
