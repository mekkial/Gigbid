# Deploy the light version on Render (free, 512 MB)

**What runs on Render:** one container with GigSim and the API (which also serves the web app). Retrieval is **BM25 keyword search only** (`RAG_VARIANT=v6_bm25`): no PyTorch, no embedding model, no reranker, and the tools run in-process (`GIGBID_TOOLS=local`). Measured memory: about 220 MB (`scripts/measure_light_memory.sh`). The language model is Groq (open profile) and the database is Neon.

**What does not run on Render:** the full system. The evaluated, shipped configuration (hybrid search plus a cross-encoder reranker, V3, MRR 0.92) and the separate MCP servers run locally with `scripts/dev.sh` or Docker Compose. Use that for an in-person demo. The report states this split.

## Steps (about 15 minutes)
1. The GitHub repo must be reachable by Render (public, or grant Render access to the private repo).
2. render.com: sign in with GitHub, **New > Blueprint**, pick `mekkial/gigbid`. It reads `render.yaml` and creates a free web service named `gigbid`.
3. Fill the six secret values when asked (or later under **Environment**):

| Key | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string (the pooled one) |
| `GROQ_API_KEY` | your Groq key |
| `APP_SECRET_KEY` | any long random string (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `TOKEN_ENCRYPTION_KEY` | a Fernet key (`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`) |
| `GIGSIM_API_TOKEN` | any random string |
| `REVIEWER_PASSWORD` | the password you will give the reviewer |

4. Wait for the build (about 5 to 8 minutes). Open `https://gigbid.onrender.com` (the exact URL is on the service page). Sign in as `reviewer@gigbid.dev` with the password above, press **Scout now**, and open a job once it says **Ready for you**.
5. Put the URL in the README and in the Classroom submission; put the reviewer login in the **private** comment only.

## Things to know
* **Sleeping:** the free service sleeps after 15 minutes without traffic and takes 30 to 60 seconds to wake. Open the link once shortly before you submit, and again before any grading window.
* **Reset on restart:** the simulator's state (balance, submitted proposals) lives in memory and resets when the service restarts. Users, runs and approvals live in Neon and persist.
* **Quota:** Groq's free tier allows about 200,000 tokens per day per model (roughly a dozen proposals).
* **Reviewer account:** it is created at each start if missing (`scripts/seed_reviewer.py`).
