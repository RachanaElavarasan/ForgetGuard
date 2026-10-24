"""
ForgetGuard Hardware Simulator
Mimics ESP32 microcontrollers sending occupancy, RFID/BLE, and relay telemetry over Wi-Fi.
"""

import time
import random
import requests

SERVER_URL = "http://127.0.0.1:5000/api/sensor-data"
API_KEY = "sample_key_123"

SCENARIOS = [
    {
        "name": "Alex exits LAB-101, forgetting Laptop Bag while Projector is still ON",
        "room_code": "LAB-101",
        "is_occupied": False,
        "rfid_tags": ["RFID-BAG-992"],
        "device_states": {
            "Ceiling 4K Laser Projector": True,
            "Daikin Inverter AC 2.0 Ton": True
        }
    },
    {
        "name": "Students working actively in Embedded Systems Lab (LAB-204)",
        "room_code": "LAB-204",
        "is_occupied": True,
        "rfid_tags": ["RFID-CHG-102"],
        "device_states": {
            "Benchtop DC Power Supply #4": True,
            "Soldering Extraction Fan": True
        }
    },
    {
        "name": "Class finishes in Lecture Hall Alpha (LH-301) - Clean exit, all devices off",
        "room_code": "LH-301",
        "is_occupied": False,
        "rfid_tags": [],
        "device_states": {
            "Auditorium Sound System Amplifier": False
        }
    }
]

def send_telemetry(payload):
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    payload["api_key"] = API_KEY
    try:
        response = requests.post(SERVER_URL, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            new_alerts = data.get('new_alerts_triggered', 0)
            status_symbol = "🚨" if new_alerts > 0 else "✅"
            print(f"[{status_symbol}] Sent for {payload['room_code']}: Occupied={payload['is_occupied']} | Tags={payload.get('rfid_tags')} | New Alerts={new_alerts}")
        else:
            print(f"[❌ Error {response.status_code}] {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"[⚠️ Connection Failed] Cannot reach {SERVER_URL}. Is Flask running?")
    except Exception as e:
        print(f"[❌ Error] {e}")

def run_simulation(loop=False, interval=5):
    print("=" * 65)
    print(" 📡 ForgetGuard ESP32 Sensor Simulator")
    print(f" Target Server: {SERVER_URL}")
    print(f" API Key: {API_KEY}")
    print("=" * 65)

    iteration = 1
    while True:
        print(f"\n--- Simulation Cycle #{iteration} ---")
        for sc in SCENARIOS:
            print(f"Scenario: {sc['name']}")
            send_telemetry({
                "room_code": sc["room_code"],
                "is_occupied": sc["is_occupied"],
                "rfid_tags": sc["rfid_tags"],
                "device_states": sc["device_states"]
            })
            time.sleep(1)

        if not loop:
            print("\n✅ Single-pass simulation complete.")
            break

        iteration += 1
        print(f"Sleeping {interval} seconds until next sensor broadcast...")
        time.sleep(interval)

if __name__ == '__main__':
    import sys
    continuous = "--loop" in sys.argv
    run_simulation(loop=continuous, interval=6)
