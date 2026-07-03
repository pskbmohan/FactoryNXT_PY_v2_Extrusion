#!/usr/bin/env python3
"""
Quick smoke test for the new /api/csv-upload endpoint.

Run this locally to verify the API is responding correctly:
    python scripts/test_api_csv_upload.py
"""
import requests

# Test payloads
TEST_KEY = "9C-95-6E-53-28-17"
TEST_CSV = """ts,m_schneider_540420085805_AC_Active_Power,m_schneider_540420085805_kWh_Total_Active,m_schneider_540420085805_AC_PF
1723087604,0.000,0.000,0.000
1723087620,485.337,0.000,0.000
1723087680,0.000,0.000,0.000"""

ENDPOINTS = [
    "http://localhost:5555/api/csv-upload",  # Local HTTPS port
    "http://localhost:80/api/csv-upload",     # Local HTTP port 80
    "http://127.0.0.1:5555/api/csv-upload",  # localhost via IP
]

def test_payload(endpoint):
    """Test a single endpoint with form-encoded payload."""
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {endpoint}")
        print(f"{'='*60}")

        # Send form-encoded payload (like the device)
        response = requests.post(
            endpoint,
            data={
                "key": TEST_KEY,
                "data": TEST_CSV
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response JSON: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                upload_id = data.get("upload_id")
                print(f"✓ Upload ID: {upload_id}")
                return upload_id
            else:
                print(f"✗ Unexpected response: {data}")
        else:
            print(f"✗ Status {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to {endpoint}")
    except Exception as e:
        print(f"✗ Error: {e}")

    return None

def test_older_endpoint():
    """Test backward compatibility with /integrations/csv-upload."""
    endpoint = "http://localhost:5555/integrations/csv-upload"
    print(f"\n{'='*60}")
    print(f"Testing backward compatibility: {endpoint}")
    print(f"{'='*60}")

    try:
        response = requests.post(
            endpoint,
            data={
                "key": TEST_KEY,
                "data": TEST_CSV
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")

        if response.status_code == 200:
            print("✓ Old endpoint still works")
            return True
        else:
            print(f"✗ Old endpoint returned {response.status_code}")

    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to {endpoint}")
    except Exception as e:
        print(f"✗ Error: {e}")

    return False

def main():
    print("Wattmon API Endpoint Smoke Test")
    print("="*60)

    # Test new API endpoint
    print("\n1. Testing new /api/csv-upload endpoint...")
    for endpoint in ENDPOINTS:
        upload_id = test_payload(endpoint)
        if upload_id:
            print(f"\n✓ SUCCESS: Upload accepted with ID {upload_id}")
            break
    else:
        print("\n✗ No endpoints responded successfully")
        return 1

    # Test backward compatibility
    print("\n2. Testing backward compatibility...")
    if test_older_endpoint():
        print("✓ Backward compatibility confirmed")
    else:
        print("✗ Backward compatibility broken")
        return 1

    print("\n" + "="*60)
    print("✓ All tests passed")
    print("="*60)
    return 0

if __name__ == "__main__":
    exit(main())
