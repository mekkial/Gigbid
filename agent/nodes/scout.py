import hashlib
import re


def fingerprint(job: dict) -> str:
    norm = re.sub(r"\W+", " ", (job["title"] + job["description"]).lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()


async def scout(tools, query: str, seen: set[str], limit: int = 20) -> list[dict]:
    """Run a saved search through the marketplace tools, de-duplicate and queue new jobs."""
    out = []
    for j in await tools.call("scout", "search_jobs", query=query, limit=limit):
        fp = fingerprint(j)
        if fp not in seen and "duplicate_of" not in j:
            seen.add(fp); out.append(j)
    return out
