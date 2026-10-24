# ForgetGuard

**IoT‑Based Forgotten Object and Last‑Person‑Out Detection System**

## Overview
ForgetGuard is a web application that monitors classroom / laboratory spaces, detects when the room becomes empty, and alerts users about:
- Objects that may have been left behind (bags, keys, chargers, etc.)
- Electrical devices that remain powered on (lights, fans, projectors)

The system is built with:
- **Frontend:** HTML + CSS + JavaScript (responsive dashboard)
- **Backend:** Python Flask with SQLite
- **IoT hardware (optional):** ESP32, PIR/mmWave occupancy sensors, RFID/BLE tags, Wi‑Fi
- **Simulation:** a Python script that generates realistic sensor data so the app can be tested without any hardware.

## Repository Structure
```
ForgetGuard/
├─ app.py                 # Flask entry point
├─ config.py              # Configuration constants
├─ models.py              # SQLAlchemy models
├─ requirements.txt       # Python dependencies
├─ README.md              # (this file)
├─ simulate/
│   └─ simulate.py        # Generates fake sensor data
├─ esp32/
│   └─ firmware.ino      # Example ESP32 sketch
├─ static/
│   ├─ css/
│   │   └─ style.css
│   └─ js/
│       └─ main.js
└─ templates/
    └─ index.html         # Dashboard UI
```

## Installation
1. **Clone the repository** (or copy the folder you receive).
   ```bash
   git clone <repo‑url> ForgetGuard
   cd ForgetGuard
   ```
2. **Create a virtual environment** (recommended).
   ```bash
   python -m venv venv
   venv\Scripts\activate   # on Windows
   ```
3. **Install dependencies**.
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the Flask app**.
   ```bash
   python app.py
   ```
   The server starts on `http://127.0.0.1:5000`.
5. **Open the dashboard** in a browser.
   Visit `http://127.0.0.1:5000` – you will see the modern dashboard showing rooms, objects, devices, and recent alerts.

## Simulating Sensor Data (no hardware required)
A lightweight simulator sends periodic POST requests to the Flask API, mimicking ESP32 sensor payloads.
```bash
python simulate/simulate.py
```
The simulator randomly toggles occupancy, device power state, and object presence. Alerts appear on the dashboard after the configurable *waiting period* (default 30 seconds).

## ESP32 Integration (real hardware)
1. **Hardware requirements**
   - ESP32 development board
   - Occupancy sensor (PIR or mmWave)
   - RFID/BLE tag readers for object identification
   - Optional relays to read device power state
2. **Network** – the ESP32 must be on the same Wi‑Fi network as the Flask server.
3. **Authentication** – each ESP32 is assigned an `api_key` stored in the `DeviceAuth` table. The sample key is `sample_key_123` (created on first run). Replace it with a secure random string for production.
4. **Upload the sketch** found in `esp32/firmware.ino` using the Arduino IDE or PlatformIO.
5. **Configure** the Wi‑Fi SSID/password and the server URL (`SERVER_URL`) inside the sketch.

## Configuration
All configurable values are in `config.py`.
- `WAIT_PERIOD_SECONDS` – how long the system waits after the last occupancy reading before declaring the room empty (default 30 s).
- `SECRET_KEY` – Flask secret; set the environment variable `FORGETGUARD_SECRET` for production.

## Extending the System
- **Add more rooms** – Insert rows into the `Room` table via the Flask shell or admin UI.
- **Register new objects** – Create entries in the `Object` table with the tag ID of the RFID/BLE tag.
- **Integrate notification services** – The `generate_alert` helper can be extended to send emails, push notifications, or Slack messages.

## Limitations & Future Work
- The current prototype uses simple occupancy boolean; real deployments should replace it with validated sensor fusion (PIR + mmWave).
- Alerts are stored locally; a production system would likely push them to a cloud service.
- Device authentication is static; consider implementing token‑based OAuth for large fleets.

---
*Enjoy testing ForgetGuard! Feel free to open issues or submit pull requests for enhancements.*
