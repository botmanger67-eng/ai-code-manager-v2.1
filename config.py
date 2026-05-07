import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file if present

# API keys and tokens (sensitive)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Model and database configuration
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-v4-flash")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///sessions.db")
PORT = int(os.environ.get("PORT", 5000))

# Status message on import
def _print_config_status():
    print("Config loaded:")
    print(f"  DEEPSEEK_API_KEY: {'present' if DEEPSEEK_API_KEY else 'MISSING'}")
    print(f"  GITHUB_TOKEN: {'present' if GITHUB_TOKEN else 'MISSING'}")
    print(f"  MODEL_NAME: {MODEL_NAME}")
    print(f"  DATABASE_URL: {DATABASE_URL}")
    print(f"  PORT: {PORT}")

_print_config_status()