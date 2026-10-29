# CareWatcher — Hardware Blueprint & Sensor Integration Guide

This guide details the physical hardware architecture for running **CareWatcher** as a 100% on-device, privacy-preserving ambient healthcare companion with **zero cloud dependencies**.

---

## 1. Laptop Built-In Sensors (Zero Extra Hardware Required)

You can immediately run and test CareWatcher using the sensors already built into your laptop:

| Built-in Sensor | Driver in Code | Purpose | Privacy Preservation |
|---|---|---|---|
| **Laptop Microphone** | [`carewatcher/sources/mic.py`](file:///c:/Users/aaron/main%20project/carewatcher/sources/mic.py) | Conversational voice, medication logging, distress detection | Audio frames gated behind `PrivacyShutter`. Audio destroyed after STT. |
| **Laptop Webcam** | [`carewatcher/sources/webcam.py`](file:///c:/Users/aaron/main%20project/carewatcher/sources/webcam.py) | Resident presence, room occupancy, fall/sedentary monitoring | Uses local OpenCV Haar Cascade on CPU. **Zero images/video are saved or transmitted.** Only scalar numbers (`face_count`, `brightness`) exit the method. |

---

## 2. Recommended External Biological Sensors

To capture external biological inputs (Heart Rate, SpO2, Temperature, Non-invasive Blood Pressure, Inactivity), connect an **ESP32 microcontroller** (NodeMCU ESP32-WROOM-32) via USB to your laptop. The ESP32 communicates with the laptop through a USB Virtual COM port (`COM3` on Windows) at **115200 baud**.

### A. Heart Rate & Blood Oxygen (BPM & SpO2)
* **Sensor Model**: **MAX30102** (or **MAX30100**)
* **Interface**: I2C (SDA=GPIO 21, SCL=GPIO 22)
* **Mechanism**: Dual-wavelength (Red 660nm & Infrared 880nm) Photoplethysmography (PPG). It measures pulsatile blood volume changes in the microvascular bed of finger tissue.
* **Output**: Real-time Pulse Rate (40–220 BPM) and Blood Oxygen Saturation (SpO2, 70–100%).
* **Wiring**:
  * `VIN` → 3.3V
  * `GND` → GND
  * `SDA` → ESP32 GPIO 21
  * `SCL` → ESP32 GPIO 22

---

### B. Non-Invasive Blood Pressure (NIBP)
Non-invasive blood pressure measurement can be implemented using two practical approaches:

#### Approach 1: Optical Pulse Transit Time (PTT) / Pulse Wave Analysis (PWA) [Cuffless & Continuous]
* **How it works**: Uses the time difference between the electrical heart contraction (R-peak on ECG) and the peripheral pulse wave arrival at the fingertip (PPG peak on MAX30102).
* **Hardware Needed**:
  * **AD8232 ECG Lead Sensor** (or **MAX30003** ultra-low power biopotential AFE)
  * **MAX30102 PPG Optical Sensor**
* **Calculation**:
  $$\text{PTT} = t_{\text{PPG\_peak}} - t_{\text{ECG\_Rpeak}}$$
  Blood pressure is inversely proportional to PTT via Moens-Korteweg elasticity equations:
  $$\text{SBP} \approx a \cdot \ln(\text{PTT}) + b$$
  *(Calibrated once against the resident's baseline blood pressure reading).*

#### Approach 2: Certified Cuffless / Bluetooth Low Energy (BLE) Medical Monitor [Plug-and-Play]
* If you require medical-grade accuracy without manual calibration:
  * **Omron HEM-9210T / Omron Complete** or **Contec CMS50D-BT**
  * Connects over **Local Bluetooth (BLE)** directly to your laptop via Python `bleak` package.
  * Zero internet required — reads standard GATT Blood Pressure Service (`0x1810`).

---

### C. Contactless Body Temperature
* **Sensor Model**: **MLX90614-DCI** (Infrared Thermometer)
* **Interface**: I2C (SDA=GPIO 21, SCL=GPIO 22)
* **Mechanism**: Stefan-Boltzmann infrared radiation detection with medical accuracy (±0.2°C in the 36°C–39°C range).
* **Benefit**: Non-contact measurement — detects resident forehead or skin temperature as they approach the device.

---

### D. Motion, Activity & Fall Detection
* **Sensor Model 1**: **MPU-6050** (6-axis Accelerometer & Gyroscope, I2C)
  * Measures resident physical tremors, activity magnitude, or rapid impact acceleration indicating a fall.
* **Sensor Model 2**: **HC-SR501** (or **RCWL-0516 Microwave Radar**)
  * Detects whole-room presence and room motion across 7 meters without cameras.

---

## 3. Hardware Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CAREWATCHER HARDWARE HUB                 │
└─────────────────────────────────────────────────────────────┘

    [ Laptop Webcam ] ──> Local OpenCV Haar ──┐
                                              │
    [ Laptop Mic ] ────> PyAudio / NumPy ─────┼──> [ PRIVACY SHUTTER ]
                                              │      (Hardware Gate)
    ┌───────────────────────────────────┐     │             │
    │        ESP32 Sensor Hub           │     │             ▼
    │  MAX30102 (BPM & SpO2) [I2C]      │     │    [ Whisper STT ]
    │  MLX90614 (Body Temp)  [I2C]      ├─────┘             │
    │  MPU6050  (Activity)   [I2C]      │                   ▼
    │  HC-SR501 (PIR Motion) [GPIO 13]  │           [ LLM Reasoning ]
    └─────────────────┬─────────────────┘                   │
                      │ USB Virtual COM                     ▼
                      │ (115200 Baud JSON)          [ Resident Memory ]
                      ▼                                     │
           [ serial_sensor.py ]                             ▼
                      │                             [ Trend Engine ]
                      ▼                                     │
         [ Memory / Trend Engine ]                          ▼
                                                    [ Safety Verifier ]
                                                            │
                                                            ▼
                                                    [ Audio TTS Output ]
```

---

## 4. How to Flash the ESP32 Firmware

1. Install [Arduino IDE](https://www.arduino.cc/en/software).
2. Open `firmware/esp32_carewatcher/esp32_carewatcher.ino`.
3. In Arduino IDE **Library Manager** (`Ctrl+Shift+I`), install:
   - `SparkFun MAX3010x Pulse and Proximity Sensor Library`
   - `Adafruit MLX90614 Library`
   - `Adafruit MPU6050`
   - `ArduinoJson` (v6 or v7)
4. Connect your ESP32 board to your PC with a micro-USB / USB-C cable.
5. Select **Tools > Board > ESP32 Dev Module** and choose your COM port (e.g. `COM3`).
6. Click **Upload**.

Once uploaded, the ESP32 streams clean JSON telemetry lines at 115200 baud:
```json
{"sensor":"esp32_hub","motion":1,"bpm":74,"spo2":98.5,"temp_c":36.6,"accel_mag":9.81}
```

The CareWatcher [`carewatcher/sources/serial_sensor.py`](file:///c:/Users/aaron/main%20project/carewatcher/sources/serial_sensor.py) driver automatically ingests these lines into the local SQLite memory store and trend engine!
