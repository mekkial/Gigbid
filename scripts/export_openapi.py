"""Export FastAPI's OpenAPI schema; the TypeScript client (apps/web/src/lib/api/schema.d.ts) is generated from it."""
import json, os
os.environ.setdefault("DATABASE_URL", "postgresql://gigbid@localhost:5433/gigbid")
from apps.api.main import app
json.dump(app.openapi(), open("apps/web/openapi.json", "w"), indent=1)
print("wrote apps/web/openapi.json")
