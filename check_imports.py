import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("backend"))

print("Checking imports...")

try:
    import backend.deps
    print("✅ backend.deps imported successfully")
except Exception as e:
    print(f"❌ Failed to import backend.deps: {e}")

try:
    import backend.routes.tasks
    print("✅ backend.routes.tasks imported successfully")
except Exception as e:
    print(f"❌ Failed to import backend.routes.tasks: {e}")

try:
    import backend.services.generation_service
    print("✅ backend.services.generation_service imported successfully")
except Exception as e:
    print(f"❌ Failed to import backend.services.generation_service: {e}")
