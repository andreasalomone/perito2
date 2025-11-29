import os
import sys

# Add the backend directory to sys.path so we can import config
sys.path.append(os.path.abspath("/Users/andreasalomone/perito-wrap/robotperizia/report-ai-v2/perito/backend"))

# Simulate the environment variable that caused the crash
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"

try:
    from config import Settings
    settings = Settings()
    print("Success: Settings initialized correctly.")
except Exception as e:
    print(f"Failure: {e}")
    sys.exit(1)
