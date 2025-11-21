"""
Simple server runner for local development.
For production, use Gunicorn directly via docker-compose or:
    gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""

import os

if __name__ == "__main__":
    from app import app
    from core.config import settings

    port = int(os.environ.get("PORT", 5000))

    print(f"Starting Flask development server on port {port}...")
    print("⚠️  WARNING: This is for development only!")
    print("   For production, use: docker compose up or gunicorn")
    print(f"   Max upload size: {settings.MAX_TOTAL_UPLOAD_SIZE_BYTES} bytes")

    # Flask built-in development server
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
