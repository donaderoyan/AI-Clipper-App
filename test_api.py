#!/usr/bin/env python3
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_root():
    print("Testing GET /")
    r = requests.get(f"{BASE_URL}/")
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}\n")

def test_process(video_url: str):
    print(f"Testing POST /api/v1/process with URL: {video_url}")
    payload = {
        "url": video_url,
        "aspect_ratio": "9:16",
        "prompt_context": "Cari momen yang menarik dan absurd"
    }
    
    r = requests.post(f"{BASE_URL}/api/v1/process", json=payload)
    print(f"Status: {r.status_code}")
    response = r.json()
    print(f"Response: {json.dumps(response, indent=2)}\n")
    return response.get("job_id")

def test_status(job_id: str):
    print(f"Testing GET /api/v1/status/{job_id}")
    r = requests.get(f"{BASE_URL}/api/v1/status/{job_id}")
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}\n")
    return r.json()

if __name__ == "__main__":
    try:
        # Test 1: Check API is alive
        test_root()
        
        # Test 2: Submit a job (ganti URL dengan video real atau test)
        # Untuk testing, coba gunakan video lokal atau URL publik
        test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # placeholder
        job_id = test_process(test_video_url)
        
        # Test 3: Poll status beberapa kali
        print("Polling status setiap 2 detik...")
        for i in range(5):
            time.sleep(2)
            status_resp = test_status(job_id)
            status = status_resp.get("status")
            message = status_resp.get("message")
            print(f"[{i+1}] Status: {status} | Message: {message}")
            
            if status in ["success", "failed"]:
                break
                
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Backend tidak running di localhost:8000")
        print("Jalankan: docker-compose up --build")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
