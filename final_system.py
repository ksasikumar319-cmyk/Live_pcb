import cv2
import serial
import os
import csv
from ultralytics import YOLO
from datetime import datetime

# ======================
# CONFIG
# ======================
MODEL_PATH = "runs/detect/uno_final/weights/best.pt"
IP_CAM = "https://10.51.168.15:8080//video"
ESP32_PORT = "COM6"

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 600

# ======================
# EXPECTED COUNTS
# ======================
expected = {
    "IC": 2,
    "Capacitor": 2,
    "Crystal": 2,
    "Regulator": 1,
    "Connector": 2,
    "Button": 1
}

# ======================
# INIT
# ======================
model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(IP_CAM)

try:
    ser = serial.Serial(ESP32_PORT, 115200, timeout=1)
    print("✅ ESP32 Connected")
except:
    ser = None
    print("⚠️ ESP32 NOT connected")

os.makedirs("data/images", exist_ok=True)
log_file = "data/log.csv"

if not os.path.exists(log_file):
    with open(log_file, "w", newline="") as f:
        csv.writer(f).writerow(["ID", "Status", "Time", "Image"])

board_id = 0

print("System Ready...")
print("👉 Press SPACE to capture and detect")

# ======================
# LOOP
# ======================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    cv2.imshow("Live Feed", display)

    key = cv2.waitKey(1) & 0xFF

    if key == 32:
        print("\n📸 Capturing...")

        results = model(frame)[0]

        detected = {}
        for box in results.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            detected[label] = detected.get(label, 0) + 1

        missing = {}
        total_missing = 0

        for comp, req in expected.items():
            det = detected.get(comp, 0)
            if det < req:
                diff = req - det
                missing[comp] = diff
                total_missing += diff

        message = "NONE" if not missing else ",".join([f"{k}={v}" for k,v in missing.items()])

        print("Detected:", detected)
        print("Missing:", message)
        print("Total Missing:", total_missing)

        # SAVE IMAGE
        board_id += 1
        img_path = f"data/images/board_{board_id}.jpg"
        annotated = results.plot()
        cv2.imwrite(img_path, annotated)

        # SAVE LOG
        with open(log_file, "a", newline="") as f:
            csv.writer(f).writerow([
                board_id,
                message,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                img_path
            ])

        # SEND TO ESP32
        if ser:
            if message == "NONE":
                ser.write(f"PASS|COUNT={board_id}\n".encode())
            else:
                ser.write(f"FAIL:{message}|TOTAL={total_missing}|COUNT={board_id}\n".encode())

        print("✅ Done\n")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
if ser:
    ser.close()