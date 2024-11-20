from flask import Flask, render_template_string
from flask_socketio import SocketIO
import cv2
import numpy as np
import base64
import socket
import threading

app = Flask(__name__)
socketio = SocketIO(app)

# 加载人脸检测模型
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# 蓝牙连接状态
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
        <title>WebSocket Detection with Bluetooth</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
    </head>
    <body>
        <h1>Camera Detection with Bluetooth</h1>
        <video id="video" autoplay playsinline width="640" height="480"></video>
        <canvas id="canvas" width="640" height="480" style="display:none;"></canvas>
        <p id="result">Result: Waiting...</p>
        <p id="bluetooth-status">Bluetooth: Not connected</p>
        <button onclick="connectBluetooth()">Connect to Bluetooth</button>
        <script>
            const video = document.getElementById("video");
            const canvas = document.getElementById("canvas");
            const context = canvas.getContext("2d");
            const result = document.getElementById("result");
            const bluetoothStatus = document.getElementById("bluetooth-status");
            const socket = io();

            // 获取摄像头权限
            navigator.mediaDevices.getUserMedia({ video: true })
                .then((stream) => {
                    video.srcObject = stream;
                })
                .catch((err) => {
                    console.error("Camera access denied:", err);
                });

            // 每 100ms 将视频帧发送到服务器
            setInterval(() => {
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataURL = canvas.toDataURL("image/jpeg");
                socket.emit("frame", dataURL);
            }, 100);

            // 接收服务器返回的人脸检测结果
            socket.on("result", (data) => {
                result.textContent = "Result: X coordinate of face: " + (data.x ?? "None");
            });

            // 连接蓝牙设备
            async function connectBluetooth() {
                const address = prompt("Enter the Bluetooth device address (e.g., 00:14:03:05:59:02):");
                if (address) {
                    socket.emit("connect_bluetooth", { address: address });
                }
            }

            // 更新蓝牙连接状态
            socket.on("bluetooth_status", (data) => {
                bluetoothStatus.textContent = "Bluetooth: " + data.status;
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)

@socketio.on("frame")
def handle_frame(data):
    # 解码 Base64 图像为 OpenCV 格式
    image_data = base64.b64decode(data.split(",")[1])
    np_image = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

    # 人脸检测
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    x_coordinate = None
    if len(faces) > 0:
        x_coordinate = faces[0][0]  # 取第一个人脸的 X 坐标

    # 发送检测结果回客户端
    socketio.emit("result", {"x": x_coordinate})

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

            # 创建蓝牙连接
            bluetooth_socket = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            bluetooth_socket.connect((address, 1))  # 通常 RFCOMM 端口为 1
            socketio.emit("bluetooth_status", {"status": f"Connected to {address}"})
            print(f"成功连接到蓝牙设备: {address}")

    except Exception as e:
        print(f"蓝牙连接失败: {e}")
        socketio.emit("bluetooth_status", {"status": f"Connection failed: {e}"})
        bluetooth_socket = None

@socketio.on("disconnect")
def handle_disconnect():
    global bluetooth_socket
    with bluetooth_lock:
        if bluetooth_socket:
            bluetooth_socket.close()
            bluetooth_socket = None
            print("蓝牙连接已断开")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
