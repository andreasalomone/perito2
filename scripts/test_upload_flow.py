import os
import sys
import time

import requests
from dotenv import load_dotenv

# Add project root to path to ensure we can import if needed, though requests is external
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

BASE_URL = "http://127.0.0.1:5000"
# Fallback to defaults if not in env, but env should be loaded
USERNAME = os.getenv("AUTH_USERNAME", "roberto")
PASSWORD = os.getenv("AUTH_PASSWORD", "1965")


def test_upload_flow():
    print(f"Using credentials: {USERNAME} / {'*' * len(PASSWORD)}")

    # 1. Login (Basic Auth is used, so we just pass auth to requests)
    auth = (USERNAME, PASSWORD)

    # 2. Prepare files
    # Ensure these files exist
    files_to_upload = [
        ("tests/temp_extraction_test/native.pdf", "application/pdf"),
        (
            "tests/temp_extraction_test/test.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ]

    files = []
    opened_files = []

    try:
        for path, mime in files_to_upload:
            if not os.path.exists(path):
                print(f"Error: File not found: {path}")
                return
            f = open(path, "rb")
            opened_files.append(f)
            files.append(("files", (os.path.basename(path), f, mime)))

        print(f"Uploading files to {BASE_URL}/upload...")
        try:
            response = requests.post(f"{BASE_URL}/upload", files=files, auth=auth)
        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to server. Is it running?")
            return

        if response.status_code != 202:
            print(f"Upload failed: {response.status_code} - {response.text}")
            return

        data = response.json()
        report_id = data.get("report_id")
        task_id = data.get("task_id")
        print(f"Upload successful. Report ID: {report_id}, Task ID: {task_id}")

        # 3. Poll status
        print(f"Polling status for report {report_id}...")
        start_time = time.time()
        while True:
            # Timeout after 5 minutes
            if time.time() - start_time > 300:
                print("Timeout waiting for report generation.")
                break

            try:
                status_response = requests.get(
                    f"{BASE_URL}/report/status/{report_id}", auth=auth
                )
            except requests.exceptions.ConnectionError:
                print("Connection lost during polling.")
                time.sleep(2)
                continue

            if status_response.status_code != 200:
                print(f"Error checking status: {status_response.status_code}")
                break

            status_data = status_response.json()
            status = status_data.get("status")
            error = status_data.get("error")

            print(f"Current status: {status}")

            if status == "completed":
                print("Report generation COMPLETED!")
                print(f"Check report at: {BASE_URL}/report/{report_id}")
                break
            elif status == "error":
                print(f"Report generation FAILED: {error}")
                break

            time.sleep(2)

    finally:
        for f in opened_files:
            f.close()


if __name__ == "__main__":
    test_upload_flow()
