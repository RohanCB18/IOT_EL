#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- Configuration ---
// Wi-Fi settings (change to match your lab/home network)
const char* ssid     = "NothingPhone2";
const char* password = "Asitis@123";

// MQTT settings
const char* mqtt_server   = "ef2d24edcf5c48c1b545f8200582e03b.s1.eu.hivemq.cloud";
const int mqtt_port       = 8883;
const char* mqtt_username = "oracle_node";
const char* mqtt_password = "Hello@123";
const char* mqtt_topic    = "oracle_rohan_123/node1/actuation";
const char* client_id     = "esp32-actuator";

// --- GPIO Pin Mappings ---
const int SERVO_PIN      = 13;
const int GREEN_LED_PIN  = 25;
const int YELLOW_LED_PIN = 26;
const int RED_LED_PIN    = 27;
const int BUZZER_PIN     = 14;

// --- OLED Settings ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- Global Objects ---
WiFiClientSecure espClient;
PubSubClient client(espClient);
Servo myServo;

// --- Servo Movement State ---
int targetServoAngle = 0;
int currentServoAngle = 0;
unsigned long lastServoUpdateTime = 0;
const unsigned long SERVO_UPDATE_INTERVAL = 15; // time in ms per 1 degree step (lower = faster, higher = slower)

// --- State Machine ---
enum GateState {
    STATE_OPEN,
    STATE_HALF,
    STATE_CLOSE
};
GateState currentGateState = STATE_OPEN;

// --- Display State ---
String currentDisplayText = "BOOTING...";
unsigned long lastDisplayTime = 0;

// --- Buzzer State ---
unsigned long lastBuzzerTime = 0;
bool buzzerState = false;
const unsigned long BUZZER_INTERVAL = 500; // 500ms on/off

// --- Function Declarations ---
void setupWiFi();
void connectMQTT();
void callback(char* topic, byte* payload, unsigned int length);
void handleGateActuation(const char* command);
void updateLED();
void updateBuzzer();
void updateServo();
void updateDisplay(String text);
void refreshDisplay();

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n====================================");
    Serial.println("🏟️ Crowd Safety Oracle - ESP32 Booting");
    Serial.println("====================================");

    // Pin Modes
    pinMode(GREEN_LED_PIN, OUTPUT);
    pinMode(YELLOW_LED_PIN, OUTPUT);
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);

    // Initial State: LEDs off, buzzer off
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(YELLOW_LED_PIN, LOW);
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);

    // OLED Initialization
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println(F("SSD1306 allocation failed"));
    } else {
        display.clearDisplay();
        display.display();
    }
    updateDisplay("BOOTING...");

    // Allow allocation of all timers for servo
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    ESP32PWM::allocateTimer(2);
    ESP32PWM::allocateTimer(3);
    
    // Standard SG90 servo uses 50Hz, pulse width 500us to 2400us
    myServo.setPeriodHertz(50);
    myServo.attach(SERVO_PIN, 500, 2400);
    
    // Set initial servo position to OPEN (90 degrees)
    myServo.write(90);
    currentServoAngle = 90;
    targetServoAngle = 90;
    currentGateState = STATE_OPEN;
    updateLED();
    
    Serial.println("[SYSTEM] Initialised gate: OPEN (90 degrees).");
    updateDisplay("OPEN");

    setupWiFi();
    espClient.setInsecure(); // Skip certificate verification for development
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
    updateServo();
    updateLED();
    updateBuzzer();
    
    unsigned long currentMillis = millis();
    if (currentMillis - lastDisplayTime >= 1000) {
        lastDisplayTime = currentMillis;
        refreshDisplay();
    }
    
    delay(10); // yields to background RTOS tasks
}

void setupWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.print("[WIFI] Connecting to SSID: ");
    Serial.println(ssid);
    updateDisplay("WiFi...");
    
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
        updateDisplay("WiFi OK");
        delay(1000);
        // Restore display state based on gate
        if (currentGateState == STATE_OPEN) updateDisplay("OPEN");
        else if (currentGateState == STATE_HALF) updateDisplay("HALF OPEN");
        else updateDisplay("CLOSED");
    } else {
        Serial.println("\n[WIFI] Failed to connect. Will retry in loop.");
        updateDisplay("WiFi Fail");
    }
}

void connectMQTT() {
    while (!client.connected()) {
        Serial.print("[MQTT] Connecting to broker at ");
        Serial.print(mqtt_server);
        Serial.print("...");
        updateDisplay("MQTT...");
        
        if (client.connect(client_id, mqtt_username, mqtt_password)) {
            Serial.println(" Connected!");
            client.subscribe(mqtt_topic);
            Serial.print("[MQTT] Subscribed to topic: ");
            Serial.println(mqtt_topic);
            // Restore display state
            if (currentGateState == STATE_OPEN) updateDisplay("OPEN");
            else if (currentGateState == STATE_HALF) updateDisplay("HALF OPEN");
            else updateDisplay("CLOSED");
        } else {
            Serial.print(" Failed, rc=");
            Serial.print(client.state());
            Serial.println(". Retrying in 5 seconds...");
            updateDisplay("MQTT Fail");
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
        targetServoAngle = 90; // 90 is fully open
        currentGateState = STATE_OPEN;
        Serial.println("[ACTUATOR] Target set to OPEN (90°). Green LED ON.");
        updateDisplay("OPEN");
    } 
    else if (strcmp(command, "GATE_HALF") == 0) {
        targetServoAngle = 45; // 45 is half open
        currentGateState = STATE_HALF;
        Serial.println("[ACTUATOR] Target set to HALF-OPEN (45°). Yellow LED ON.");
        updateDisplay("HALF OPEN");
    } 
    else if (strcmp(command, "GATE_CLOSE") == 0) {
        targetServoAngle = 0; // 0 is closed
        currentGateState = STATE_CLOSE;
        Serial.println("[ACTUATOR] Target set to CLOSED (0°). Red LED ON, Buzzer ON!");
        updateDisplay("CLOSED");
    } 
    else {
        Serial.print("[ACTUATOR] Unknown command received: ");
        Serial.println(command);
    }
}

void updateLED() {
    digitalWrite(GREEN_LED_PIN, currentGateState == STATE_OPEN ? HIGH : LOW);
    digitalWrite(YELLOW_LED_PIN, currentGateState == STATE_HALF ? HIGH : LOW);
    digitalWrite(RED_LED_PIN, currentGateState == STATE_CLOSE ? HIGH : LOW);
}

void updateBuzzer() {
    if (currentGateState == STATE_CLOSE) {
        unsigned long currentMillis = millis();
        if (currentMillis - lastBuzzerTime >= BUZZER_INTERVAL) {
            lastBuzzerTime = currentMillis;
            buzzerState = !buzzerState;
            digitalWrite(BUZZER_PIN, buzzerState ? HIGH : LOW);
        }
    } else {
        digitalWrite(BUZZER_PIN, LOW);
        buzzerState = false;
    }
}

void updateServo() {
    if (currentServoAngle == targetServoAngle) return;

    unsigned long currentMillis = millis();
    if (currentMillis - lastServoUpdateTime >= SERVO_UPDATE_INTERVAL) {
        lastServoUpdateTime = currentMillis;
        int step = (targetServoAngle > currentServoAngle) ? 1 : -1;
        currentServoAngle += step;
        myServo.write(currentServoAngle);
    }
}

void updateDisplay(String text) {
    currentDisplayText = text;
    refreshDisplay();
}

void refreshDisplay() {
    display.clearDisplay();
    
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("Gate Status:");
    
    display.setCursor(0, 16);
    display.setTextSize(2);
    display.println(currentDisplayText);
    
    // Uptime
    unsigned long uptimeSec = millis() / 1000;
    int mins = (uptimeSec / 60) % 60;
    int hrs = (uptimeSec / 3600);
    int secs = uptimeSec % 60;
    char uptimeStr[20];
    if (hrs > 0) {
        sprintf(uptimeStr, "Up: %dh %02dm %02ds", hrs, mins, secs);
    } else {
        sprintf(uptimeStr, "Up: %02dm %02ds", mins, secs);
    }
    
    display.setCursor(0, 48);
    display.setTextSize(1);
    display.println(uptimeStr);
    
    display.display();
}
