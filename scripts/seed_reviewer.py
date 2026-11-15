"""Create the reviewer account (credentials come from env, never committed): REVIEWER_EMAIL / REVIEWER_PASSWORD / REVIEWER_PERSONA."""
import asyncio, os
from dotenv import load_dotenv; load_dotenv(".env")
from apps.api import db
from apps.api.auth.security import hash_password
from apps.api.schemas.models import Settings


async def main():
    email = os.environ.get("REVIEWER_EMAIL", "reviewer@gigbid.dev"); pw = os.environ.get("REVIEWER_PASSWORD")
    if not pw:
        raise SystemExit("set REVIEWER_PASSWORD in the environment (do not commit it)")
    await db.init()
    if not await db.one("SELECT 1 FROM users WHERE email=%s", email):
        await db.run("INSERT INTO users(id,email,pw_hash,persona,settings) VALUES(%s,%s,%s,%s,%s)", "u_reviewer", email, hash_password(pw),
                     os.environ.get("REVIEWER_PERSONA", "ai_ml"), db.J(Settings().model_dump()))
        print("created", email)
    else:                                                     # keep the reviewer password equal to REVIEWER_PASSWORD (it may have been rotated)
        await db.run("UPDATE users SET pw_hash=%s WHERE email=%s", hash_password(pw), email)
        print("reviewer already exists; password synced from REVIEWER_PASSWORD")
    await db.close()

asyncio.run(main())
