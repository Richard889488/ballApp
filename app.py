from flask import Flask, render_template_string
from flask_socketio import SocketIO
import cv2
import numpy as np
import base64
import mediapipe as mp
import socket
import threading

app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet")

# 初始化 MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils
face_detection = mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)

# 藍牙相關
bluetooth_socket = None
bluetooth_lock = threading.Lock()

@app.route('/')
def index():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Webcam Detection with Bluetooth</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 20px;
            }
            video, canvas {
                border: 1px solid #ccc;
                border-radius: 8px;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h1>Webcam Detection with Bluetooth</h1>
        <video id="video" autoplay playsinline width="640" height="480"></video>
        <canvas id="canvas" width="640" height="480"></canvas>
        <p id="result">Face Detection Result: Waiting...</p>
        <p id="bluetooth-status">Bluetooth: Not connected</p>
        <button onclick="connectBluetooth()">Connect to Bluetooth</button>
        <div>
            <h3>Send Message to Bluetooth Device</h3>
            <input id="message-box" type="text" placeholder="Enter message">
            <button onclick="sendMessage()">Send</button>
        </div>
        <script>
            const video = document.getElementById("video");
            const canvas = document.getElementById("canvas");
            const context = canvas.getContext("2d");
            const result = document.getElementById("result");
            const bluetoothStatus = document.getElementById("bluetooth-status");
            const socket = io();

            // 獲取攝像頭權限
            navigator.mediaDevices.getUserMedia({ video: true })
                .then((stream) => {
                    video.srcObject = stream;
                })
                .catch((err) => {
                    alert("Camera access denied: " + err.message);
                });

            // 每 100ms 傳送影像至伺服器
            setInterval(() => {
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataURL = canvas.toDataURL("image/jpeg");
                socket.emit("frame", dataURL);
            }, 100);

            // 接收伺服器傳回的檢測結果
            socket.on("result", (data) => {
                context.clearRect(0, 0, canvas.width, canvas.height);
                context.drawImage(video, 0, 0, canvas.width, canvas.height);

                const faces = data.faces || [];
                faces.forEach(face => {
                    context.strokeStyle = "red";
                    context.lineWidth = 2;
                    context.strokeRect(face.x, face.y, face.w, face.h);
                });

                if (faces.length > 0) {
                    const facePositions = faces.map((f, idx) => `Face ${idx + 1}: (${f.x}, ${f.y})`);
                    result.textContent = `Face Detection Result: ` + facePositions.join(", ");
                } else {
                    result.textContent = "Face Detection Result: No face detected";
                }
            });

            // 連接藍牙設備
            function connectBluetooth() {
                const address = prompt("Enter the Bluetooth device address (e.g., 00:14:03:05:59:02):");
                if (address) {
                    socket.emit("connect_bluetooth", { address: address });
                }
            }

            // 更新藍牙連接狀態
            socket.on("bluetooth_status", (data) => {
                bluetoothStatus.textContent = "Bluetooth: " + data.status;
            });

            // 傳送訊息至藍牙設備
            function sendMessage() {
                const message = document.getElementById("message-box").value;
                if (message) {
                    socket.emit("send_message", { message: message });
                }
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)

@socketio.on("frame")
def handle_frame(data):
    global bluetooth_socket

    # 解碼 Base64 圖像為 OpenCV 格式
    image_data = base64.b64decode(data.split(",")[1])
    np_image = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

    # 檢測人臉
    faces_data = []
    results = face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if results.detections:
        for detection in results.detections:
            bboxC = detection.location_data.relative_bounding_box
            ih, iw, _ = frame.shape
            x = int(bboxC.xmin * iw)
            y = int(bboxC.ymin * ih)
            w = int(bboxC.width * iw)
            h = int(bboxC.height * ih)
            faces_data.append({"x": x, "y": y, "w": w, "h": h})

            # 在影像上畫框
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 如果檢測到人臉，發送 X 座標至藍牙設備
        if len(faces_data) > 0 and bluetooth_socket:
            try:
                x_coordinate = faces_data[0]["x"]
                bluetooth_socket.send(f"{x_coordinate}\n".encode("utf-8"))
            except Exception as e:
                print(f"Failed to send Bluetooth data: {e}")

    # 傳送結果回前端
    socketio.emit("result", {"faces": faces_data})

@socketio.on("connect_bluetooth")
def handle_bluetooth_connection(data):
    global bluetooth_socket
    address = data.get("address")
    if not address:
        socketio.emit("bluetooth_status", {"status": "Invalid address"})
        return

    try:
        with bluetooth_lock:
            if bluetooth_socket:
                bluetooth_socket.close()

            bluetooth_socket = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            bluetooth_socket.connect((address, 1))
            socketio.emit("bluetooth_status", {"status": f"Connected to {address}"})
    except Exception as e:
        socketio.emit("bluetooth_status", {"status": f"Connection failed: {e}"})
        bluetooth_socket = None

@socketio.on("send_message")
def send_bluetooth_message(data):
    global bluetooth_socket
    message = data.get("message", "")
    if not bluetooth_socket:
        socketio.emit("bluetooth_status", {"status": "Not connected"})
        return

    try:
        bluetooth_socket.send(message.encode("utf-8"))
        socketio.emit("bluetooth_status", {"status": "Message sent"})
    except Exception as e:
        socketio.emit("bluetooth_status", {"status": f"Failed to send message: {e}"})

if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host="0.0.0.0", port=5000)
