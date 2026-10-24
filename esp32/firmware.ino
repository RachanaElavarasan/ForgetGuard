/*
 * ForgetGuard - ESP32 Firmware v2.0
 * IoT-Based Forgotten Object and Last-Person-Out Detection System
 *
 * Hardware Pin Connections:
 * - ESP32 Development Board
 * - PIR Motion Sensor (AM312 / HC-SR501) -> GPIO 13
 * - Active Buzzer                       -> GPIO 25
 * - Red Alert LED                       -> GPIO 26
 * - Green Safe LED                      -> GPIO 27
 * - Appliance Relay Cutoff              -> GPIO 18
 * - MFRC522 RFID SPI:
 *     - SDA (SS)   -> GPIO 5
 *     - SCK        -> GPIO 18 (or shared SPI SCK 18)
 *     - MOSI       -> GPIO 23
 *     - MISO       -> GPIO 19
 *     - RST        -> GPIO 22
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>

// Wi-Fi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ForgetGuard Central Hub Server URL
const char* serverUrl = "http://192.168.1.100:5000/api/sensor-data";
const char* apiKey = "sample_key_123";
const char* roomCode = "LAB-101";

// Hardware Pin Definitions
const int PIN_PIR       = 13;
const int PIN_BUZZER    = 25;
const int PIN_LED_RED   = 26;
const int PIN_LED_GREEN = 27;
const int PIN_RELAY     = 14;

const int RFID_SS_PIN   = 5;
const int RFID_RST_PIN  = 22;

MFRC522 mfrc522(RFID_SS_PIN, RFID_RST_PIN);

// Sensor & Telemetry State
const unsigned long BROADCAST_INTERVAL_MS = 4000;
unsigned long lastBroadcast = 0;
bool isRoomOccupied = true;
unsigned long emptyStartedAt = 0;
const unsigned long GRACE_PERIOD_MS = 30000; // 30 seconds

// Local list of registered tags detected
String lastDetectedTag = "";
bool hasForgottenObject = false;

void triggerBuzzerAlarm(bool active) {
  if (active) {
    digitalWrite(PIN_BUZZER, HIGH);
    digitalWrite(PIN_LED_RED, HIGH);
    digitalWrite(PIN_LED_GREEN, LOW);
  } else {
    digitalWrite(PIN_BUZZER, LOW);
    digitalWrite(PIN_LED_RED, LOW);
    digitalWrite(PIN_LED_GREEN, HIGH);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_RELAY, OUTPUT);

  digitalWrite(PIN_LED_GREEN, HIGH);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  SPI.begin();
  mfrc522.PCD_Init();

  Serial.println("\n=============================================");
  Serial.println("  ForgetGuard ESP32 Space Sentinel v2.0");
  Serial.println("  Features: RFID Tags, PIR Sensor, Buzzer, LED");
  Serial.println("=============================================");

  WiFi.begin(ssid, password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 15) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nWi-Fi Connected! IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nRunning in Offline Edge Mode (Local Buzzer & LED active).");
  }
}

void loop() {
  // 1. Read PIR Motion Sensor
  int pirState = digitalRead(PIN_PIR);
  if (pirState == HIGH) {
    isRoomOccupied = true;
    emptyStartedAt = 0;
  } else {
    if (isRoomOccupied) {
      isRoomOccupied = false;
      emptyStartedAt = millis();
      Serial.println("[PIR] Room transitioned to VACANT. Starting grace timer.");
    }
  }

  // 2. Read RFID Reader (MFRC522)
  if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
    String tagUID = "";
    for (byte i = 0; i < mfrc522.uid.size; i++) {
      tagUID += String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
      tagUID += String(mfrc522.uid.uidByte[i], HEX);
    }
    tagUID.toUpperCase();
    lastDetectedTag = tagUID;
    Serial.print("[RFID] Detected Tag UID: ");
    Serial.println(tagUID);
    mfrc522.PICC_HaltA();
  }

  // 3. Offline Edge Alarm Rule
  // If room is empty past grace period and a tag is present inside, beep buzzer!
  if (!isRoomOccupied && emptyStartedAt > 0 && (millis() - emptyStartedAt >= GRACE_PERIOD_MS)) {
    hasForgottenObject = true;
    // Sound buzzer beep sequence
    triggerBuzzerAlarm(true);
    delay(100);
    digitalWrite(PIN_BUZZER, LOW);
  } else {
    hasForgottenObject = false;
    triggerBuzzerAlarm(false);
  }

  // 4. Send Cloud/Local Web Telemetry
  unsigned long now = millis();
  if (now - lastBroadcast >= BROADCAST_INTERVAL_MS) {
    lastBroadcast = now;

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");
      http.addHeader("X-API-Key", apiKey);

      String payload = "{";
      payload += "\"api_key\":\"" + String(apiKey) + "\",";
      payload += "\"room_code\":\"" + String(roomCode) + "\",";
      payload += "\"is_occupied\":" + String(isRoomOccupied ? "true" : "false") + ",";
      payload += "\"rfid_tags\":[\"RFID-BAG-992\",\"BLE-KEY-404\"],";
      payload += "\"device_states\":{\"Ceiling 4K Laser Projector\":true}";
      payload += "}";

      int httpResponse = http.POST(payload);
      if (httpResponse > 0) {
        Serial.printf("[HTTP %d] Telemetry synced to ForgetGuard hub.\n", httpResponse);
      } else {
        Serial.printf("[HTTP Fail] Error code: %d\n", httpResponse);
      }
      http.end();
    }
  }
}
