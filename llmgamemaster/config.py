import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configurations
SILVER_DB_HOST = os.getenv("SILVER_DB_HOST", "datareference_silver_postgres")
SILVER_DB_PORT = os.getenv("SILVER_DB_PORT", "5432")
SILVER_DB_NAME = os.getenv("SILVER_DB_NAME", "silver_db")
DB_READ_USER = os.getenv("DB_READ_USER")
DB_READ_PASSWORD = os.getenv("DB_READ_PASSWORD")

# Database configurations
# Configuration pour les opérations normales (gamemaster user - accès limité)
GAME_DB_HOST = os.getenv("APP_DB_HOST", "webapp_postgres")
GAME_DB_PORT = os.getenv("APP_DB_PORT", "5432")
GAME_DB_NAME = os.getenv("APP_DB_NAME", "app_db")
GAME_DB_USER = os.getenv("GAME_DB_USER")
GAME_DB_PASSWORD = os.getenv("GAME_DB_PASSWORD")

# Configuration pour l'authentification JWT SEULEMENT (superuser - accès complet)
AUTH_DB_HOST = os.getenv("APP_DB_HOST", "webapp_postgres")  
AUTH_DB_PORT = os.getenv("APP_DB_PORT", "5432")
AUTH_DB_NAME = os.getenv("APP_DB_NAME", "app_db")
AUTH_DB_USER = os.getenv("AUTH_DB_USER")  # Superuser pour authentification
AUTH_DB_PASSWORD = os.getenv("AUTH_DB_PASSWORD")  # SEULEMENT pour JWT

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY", "")
OPENAI_MODEL = os.getenv("OPEN_AI_MODEL", "gpt-4")
# Maximum tokens limit for GPT-4o is 16384 but we use the value from ENV_INFOS (13000)
OPENAI_MAX_TOKENS = int(os.getenv("OPEN_AI_MAX_TOKEN", "13000"))

# Anthropic configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKEN", "20000"))

# Preferred LLM provider (openai or anthropic)
# This can be set in several ways:
# 1. Environment variable: LLM_PROVIDER=anthropic
# 2. .env file in the application directory
# 3. Docker run -e LLM_PROVIDER=anthropic
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# API configurations
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("LLM_GAMEMASTER_EXTERNAL_PORT", "5001"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "logs/llm_gamemaster.log"

# Prompt templates directory
TEMPLATES_DIR = "templates"

# Campaign context window size (number of messages to include)
CAMPAIGN_CONTEXT_WINDOW = int(os.getenv("CAMPAIGN_CONTEXT_WINDOW", "20"))

# API Rate limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # requests per minute
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # window in seconds

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET", os.getenv("LLM_JWT_SECRET_KEY", "test_jwt_secret_key_for_ci_cd"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# Security settings
# CORS : Autoriser uniquement les requêtes depuis l'application webapp
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:80,https://localhost,https://localhost:443,http://127.0.0.1,https://127.0.0.1").split(",")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"  # Compatible avec webapp LLM_ENABLE_AUTH 