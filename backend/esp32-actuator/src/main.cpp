#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// --- Configuration ---
// Wi-Fi settings (change to match your lab/home network)
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT settings
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port     = 1883;
const char* mqtt_topic  = "oracle_rohan_123/node1/actuation";
const char* client_id   = "esp32-actuator";

// --- GPIO Pin Mappings ---
const int SERVO_PIN  = 13;
const int LED_PIN    = 25; // Single LED indicator
const int BUZZER_PIN = 14;

// --- Global Objects ---
WiFiClient espClient;
PubSubClient client(espClient);
Servo myServo;

// --- State Machine for Single LED ---
enum GateState {
    STATE_OPEN,
    STATE_HALF,
    STATE_CLOSE
};
GateState currentGateState = STATE_OPEN;
unsigned long lastBlinkTime = 0;
bool ledState = false;

// --- Function Declarations ---
void setupWiFi();
void connectMQTT();
void callback(char* topic, byte* payload, unsigned int length);
void handleGateActuation(const char* command);
void updateLED();

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n====================================");
    Serial.println("🏟️ Crowd Safety Oracle - ESP32 Booting");
    Serial.println("====================================");

    // Pin Modes
    pinMode(LED_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);

    // Initial State: LED off, buzzer off
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);

    // Allow allocation of all timers for servo
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    ESP32PWM::allocateTimer(2);
    ESP32PWM::allocateTimer(3);
    
    // Standard SG90 servo uses 50Hz, pulse width 500us to 2400us
    myServo.setPeriodHertz(50);
    myServo.attach(SERVO_PIN, 500, 2400);
    
    // Set initial servo position to OPEN (0 degrees)
    myServo.write(0);
    currentGateState = STATE_OPEN;
    digitalWrite(LED_PIN, HIGH); // Default safe state: LED solidly ON
    Serial.println("[SYSTEM] Initialised gate: OPEN (0 degrees), Single LED active.");

    setupWiFi();
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(callback);
}

void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        setupWiFi();
    }
    if (!client.connected()) {
        connectMQTT();
    }
    client.loop();
    updateLED();
    delay(10); // yields to background RTOS tasks
}

void setupWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.print("[WIFI] Connecting to SSID: ");
    Serial.println(ssid);
    
    WiFi.begin(ssid, password);
    
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 20) {
        delay(500);
        Serial.print(".");
        retries++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected successfully!");
        Serial.print("[WIFI] IP Address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[WIFI] Failed to connect. Will retry in loop.");
    }
}

void connectMQTT() {
    while (!client.connected()) {
        Serial.print("[MQTT] Connecting to broker at ");
        Serial.print(mqtt_server);
        Serial.print("...");
        
        if (client.connect(client_id)) {
            Serial.println(" Connected!");
            client.subscribe(mqtt_topic);
            Serial.print("[MQTT] Subscribed to topic: ");
            Serial.println(mqtt_topic);
        } else {
            Serial.print(" Failed, rc=");
            Serial.print(client.state());
            Serial.println(". Retrying in 5 seconds...");
            delay(5000);
        }
    }
}

void callback(char* topic, byte* payload, unsigned int length) {
    Serial.println("\n------------------------------------");
    Serial.print("[MQTT] Incoming Message on topic: ");
    Serial.println(topic);

    // Convert payload to string
    String message = "";
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    Serial.print("[MQTT] Raw Payload: ");
    Serial.println(message);

    // Parse JSON
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, message);

    if (error) {
        Serial.print("[JSON] Deserialisation failed: ");
        Serial.println(error.c_str());
        return;
    }

    const char* command = doc["command"];
    if (command != nullptr) {
        handleGateActuation(command);
    } else {
        Serial.println("[JSON] Field 'command' missing from payload.");
    }
}

void handleGateActuation(const char* command) {
    Serial.print("[ACTUATOR] Processing command: ");
    Serial.println(command);

    if (strcmp(command, "GATE_OPEN") == 0) {
        myServo.write(0);
        digitalWrite(BUZZER_PIN, LOW);
        currentGateState = STATE_OPEN;
        Serial.println("[ACTUATOR] Gate is OPEN (0°). LED Solidly ON. Buzzer OFF.");
    } 
    else if (strcmp(command, "GATE_HALF") == 0) {
        myServo.write(90);
        digitalWrite(BUZZER_PIN, LOW);
        currentGateState = STATE_HALF;
        Serial.println("[ACTUATOR] Gate is HALF-OPEN (90°). LED Blinking Slowly. Buzzer OFF.");
    } 
    else if (strcmp(command, "GATE_CLOSE") == 0) {
        myServo.write(180);
        digitalWrite(BUZZER_PIN, HIGH);
        currentGateState = STATE_CLOSE;
        Serial.println("[ACTUATOR] Gate is CLOSED (180°). LED Blinking Rapidly. Buzzer sounding!");
    } 
    else {
        Serial.print("[ACTUATOR] Unknown command received: ");
        Serial.println(command);
    }
}

void updateLED() {
    unsigned long currentMillis = millis();
    if (currentGateState == STATE_OPEN) {
        // Keep LED solidly ON
        digitalWrite(LED_PIN, HIGH);
    } 
    else if (currentGateState == STATE_HALF) {
        // Slow blink: 500ms intervals
        if (currentMillis - lastBlinkTime >= 500) {
            lastBlinkTime = currentMillis;
            ledState = !ledState;
            digitalWrite(LED_PIN, ledState);
        }
    } 
    else if (currentGateState == STATE_CLOSE) {
        // Rapid blink: 150ms intervals
        if (currentMillis - lastBlinkTime >= 150) {
            lastBlinkTime = currentMillis;
            ledState = !ledState;
            digitalWrite(LED_PIN, ledState);
        }
    }
}
