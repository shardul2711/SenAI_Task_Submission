import os
import json
import time
import argparse
import httpx

# Ingestion target endpoint
INGEST_URL = "http://localhost:8000/api/ingest"

def replay_emails(file_path: str, speed: float):
    if not os.path.exists(file_path):
        print(f"Dataset file '{file_path}' not found.")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        emails = json.load(f)
        
    print(f"Loaded {len(emails)} emails from dataset.")
    print(f"Replaying at speed: {speed} email(s) per second. Target endpoint: {INGEST_URL}")
    print("-" * 60)
    
    interval = 1.0 / speed
    client = httpx.Client()
    
    success_count = 0
    fail_count = 0
    
    start_time = time.time()
    for idx, email in enumerate(emails):
        # Format payload to match EmailIngestRequest schema
        payload = {
            "message_id": email["message_id"],
            "sender": email["sender"],
            "subject": email.get("subject", ""),
            "body": email.get("body", ""),
            "timestamp": email["timestamp"],
            "thread_id": email["thread_id"]
        }
        
        try:
            response = client.post(INGEST_URL, json=payload, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                print(f"[{idx+1}/{len(emails)}] Sent message {payload['message_id']} (Thread: {payload['thread_id']}) -> Status: {data.get('status')} (Job ID: {data.get('job_id')})")
                success_count += 1
            else:
                print(f"[{idx+1}/{len(emails)}] Failed to send {payload['message_id']} -> HTTP Status {response.status_code}: {response.text}")
                fail_count += 1
        except Exception as e:
            print(f"[{idx+1}/{len(emails)}] Connection error for {payload['message_id']} -> {e}")
            fail_count += 1
            
        time.sleep(interval)
        
    duration = time.time() - start_time
    print("-" * 60)
    print("Replay simulation completed.")
    print(f"Total Sent: {len(emails)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Total time elapsed: {duration:.2f} seconds")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay emails from JSON dataset to ingestion endpoint.")
    parser.add_argument(
        "--file", 
        type=str, 
        default="documents/68da89af-0a56-490d-93ac-f180673b26c9.json", 
        help="Path to JSON dataset file"
    )
    parser.add_argument(
        "--speed", 
        type=float, 
        default=1.0, 
        help="Emails per second to replay (e.g. 1.0, 5.0, 10.0)"
    )
    
    args = parser.parse_args()
    
    # Adjust path if relative from root
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(script_dir, args.file) if not os.path.isabs(args.file) else args.file
    
    replay_emails(file_path, args.speed)
