import cv2
import numpy as np
import socket
import threading
import platform
import os
import time
from flask import Flask, Response, render_template_string, request

# 建立 Flask 應用
app = Flask(__name__)
capture = None
is_running = False
bluetooth_socket = None

# 轉換影像為 base64 格式
def to_base64(image):
    _, buffer = cv2.imencode('.png', image)
    base64_image = base64.b64encode(buffer).decode('utf-8')
    return base64_image

# 攝影機啟動邏輯
def start_camera():
    global capture, is_running
    if is_running:
        print("攝影機已經啟動")
        return

    try:
        # 根據操作系統設定攝影機
        camera_index = 0 if platform.system() == 'Windows' else 2 if platform.system() == 'Linux' and 'ANDROID_ARGUMENT' in os.environ else 0
        capture = cv2.VideoCapture(camera_index)

        if not capture.isOpened():
            print("無法啟動攝影機：請檢查設備或驅動")
            return

        is_running = True
        print("攝影機成功啟動")

    except Exception as e:
        print(f"攝影機啟動失敗: {e}")

# 攝影機停止邏輯
def stop_camera():
    global is_running, capture
    if not is_running:
        print("攝影機已經停止")
        return

    try:
        is_running = False
        if capture and capture.isOpened():
            capture.release()
            print("攝影機已成功停止")
    except Exception as e:
        print(f"停止攝影機時出現錯誤: {e}")

# 影像流生成器
def generate_frames():
    global capture, is_running
    while True:
        if not is_running or capture is None:
            time.sleep(0.1)
            continue

        try:
            success, frame = capture.read()
            if not success:
                print("無法讀取攝影機幀，可能已被釋放")
                stop_camera()
                break

            # 灰階處理並檢測人臉
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # 將影像編碼為 JPEG 格式
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        except Exception as e:
            print(f"生成影像流時出現錯誤: {e}")
            stop_camera()
            break

# 藍牙連接邏輯
def connect_bluetooth(address):
    global bluetooth_socket
    try:
        bluetooth_socket = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        bluetooth_socket.connect((address, 1))  # 1 是 RFCOMM 的默認埠
        print(f"成功連接到藍牙設備: {address}")
    except Exception as e:
        print(f"無法連接到藍牙設備: {e}")
        bluetooth_socket = None

# Flask 主頁面
@app.route('/')
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ball Face Detection App</title>
        <script>
            async function requestPermissions() {
                try {
                    // 請求相機權限
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    console.log('相機已啟動');
                    stream.getTracks().forEach(track => track.stop());

                    // 請求藍牙權限
                    const device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true });
                    console.log('已連接到藍牙設備：', device.name);
                } catch (err) {
                    console.error('權限請求失敗：', err);
                }
            }
            async function startCamera() {
                fetch('/start_camera');
            }
            async function stopCamera() {
                fetch('/stop_camera');
            }
            async function connectBluetooth() {
                const address = prompt('請輸入藍牙地址 (例如: 00:14:03:05:59:02)');
                if (address) {
                    fetch('/connect_bluetooth?address=' + address);
                }
            }
        </script>
    </head>
    <body onload="requestPermissions()">
        <h1>Ball Face Detection App</h1>
        <div>
            <button onclick="startCamera()">開始攝影機</button>
            <button onclick="stopCamera()">停止攝影機</button>
            <button onclick="connectBluetooth()">連接藍牙</button>
        </div>
        <h2>Video Stream:</h2>
        <img src="/video_feed" width="640" height="480">
    </body>
    </html>
    """
    return render_template_string(html_content)

# 路由：影像流
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 路由：開始攝影機
@app.route('/start_camera')
def start_camera_route():
    start_camera()
    return "攝影機已啟動"

# 路由：停止攝影機
@app.route('/stop_camera')
def stop_camera_route():
    stop_camera()
    return "攝影機已停止"

# 路由：藍牙連接
@app.route('/connect_bluetooth')
def connect_bluetooth_route():
    address = request.args.get('address')
    if address:
        connect_bluetooth(address)
        return f"嘗試連接藍牙設備: {address}"
    return "未提供藍牙地址"

# 主程序入口
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
