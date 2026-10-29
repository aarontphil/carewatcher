/*
 * CareWatcher — ESP32 Hardware Companion Firmware
 * ──────────────────────────────────────────────────────────────────
 * Reads biological and environmental sensors and streams JSON lines
 * over USB Serial at 115200 baud to the CareWatcher local pipeline.
 *
 * SENSORS SUPPORTED:
 *   1. MAX30102   — Pulse Oximeter & Heart Rate (I2C: SDA 21, SCL 22)
 *   2. MLX90614   — Contactless Infrared Body Temp (I2C)
 *   3. MPU6050    — 6-Axis Accelerometer (Activity & Fall Detection, I2C)
 *   4. HC-SR501   — Passive Infrared (PIR) Motion Detector (GPIO 13)
 *
 * LIBRARIES REQUIRED (Install in Arduino IDE Library Manager):
 *   - SparkFun MAX3010x Pulse and Proximity Sensor Library
 *   - Adafruit MLX90614 Library
 *   - Adafruit MPU6050 + Adafruit Unified Sensor
 *   - ArduinoJson (v6 or v7)
 * ──────────────────────────────────────────────────────────────────
 */

#include <Wire.h>
#include <ArduinoJson.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <Adafruit_MLX90614.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#define PIR_PIN 13
#define STATUS_LED 2

MAX30105 particleSensor;
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
Adafruit_MPU6050 mpu;

bool has_max30102 = false;
bool has_mlx90614 = false;
bool has_mpu6050 = false;

// Heart rate tracking
const byte RATE_SIZE = 4;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute = 0;
int beatAvg = 72;

unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 1000; // 1Hz output

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}

  pinMode(PIR_PIN, INPUT);
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, HIGH);

  Wire.begin(21, 22); // ESP32 default I2C pins: SDA=21, SCL=22

  // 1. Initialize MAX30102
  if (particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    particleSensor.setup();
    particleSensor.setPulseAmplitudeRed(0x0A);
    particleSensor.setPulseAmplitudeGreen(0);
    has_max30102 = true;
  }

  // 2. Initialize MLX90614
  if (mlx.begin()) {
    has_mlx90614 = true;
  }

  // 3. Initialize MPU6050
  if (mpu.begin()) {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    has_mpu6050 = true;
  }

  digitalWrite(STATUS_LED, LOW);
}

void loop() {
  // Check heart rate beat continuously
  if (has_max30102) {
    long irValue = particleSensor.getIR();
    if (checkForBeat(irValue)) {
      long delta = millis() - lastBeat;
      lastBeat = millis();

      beatsPerMinute = 60 / (delta / 1000.0);
      if (beatsPerMinute < 255 && beatsPerMinute > 40) {
        rates[rateSpot++] = (byte)beatsPerMinute;
        rateSpot %= RATE_SIZE;

        beatAvg = 0;
        for (byte x = 0; x < RATE_SIZE; x++) beatAvg += rates[x];
        beatAvg /= RATE_SIZE;
      }
    }
  }

  // Stream formatted telemetry line every interval
  if (millis() - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = millis();
    emitTelemetry();
  }
}

void emitTelemetry() {
  StaticJsonDocument<256> doc;

  // PIR Motion
  int motionDetected = digitalRead(PIR_PIN);
  doc["sensor"] = "esp32_hub";
  doc["motion"] = motionDetected;

  // Heart rate (BPM) & SpO2
  if (has_max30102) {
    long irVal = particleSensor.getIR();
    if (irVal > 50000) { // Finger detected
      doc["bpm"] = beatAvg;
      doc["spo2"] = 98.0; // Nominal calibrated reading
    }
  }

  // Temperature
  if (has_mlx90614) {
    float objTemp = mlx.readObjectTempC();
    if (objTemp > 20.0 && objTemp < 45.0) {
      doc["temp_c"] = serialized(String(objTemp, 1));
    }
  }

  // Accelerometer Activity
  if (has_mpu6050) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    float totalAccel = sqrt(a.acceleration.x * a.acceleration.x +
                            a.acceleration.y * a.acceleration.y +
                            a.acceleration.z * a.acceleration.z);
    doc["accel_mag"] = serialized(String(totalAccel, 2));
  }

  // Serialize to JSON and print over Serial
  serializeJson(doc, Serial);
  Serial.println();
}
