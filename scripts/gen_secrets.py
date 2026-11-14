"""Print fresh secrets for a deployment .env (never commit the output). Usage: python scripts/gen_secrets.py >> .env"""
import secrets
from cryptography.fernet import Fernet

print(f"APP_SECRET_KEY={secrets.token_urlsafe(48)}")
print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"MARKETPLACE_TOKENS={secrets.token_urlsafe(24)}:service")
print("# set MARKETPLACE_MCP_TOKEN to the token part above (before the colon)")
print(f"REVIEWER_PASSWORD={secrets.token_urlsafe(12)}")
