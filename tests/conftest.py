import os

# Pin test credentials before any module reads the environment (.env is loaded by the API on import).
os.environ["GIGSIM_API_TOKEN"] = "dev-token"
os.environ["GIGSIM_BASE_URL"] = "http://127.0.0.1:8081"
