import flet as ft
import cv2
import numpy as np
import socket
import threading
import platform
import os
import time
import base64
from flask import Flask, Response, render_template

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

# 影像流生成器
def generate_frames():
    global capture, is_running
    while is_running and capture.isOpened():
        success, frame = capture.read()
        if not success:
            continue

        # 灰階轉換與人臉檢測
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # 將影像編碼為 JPEG 格式
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # 使用 multipart/x-mixed-replace 來提供影像流
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# 設定路由來提供影像流
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Flask 主頁面路由
@app.route('/')
def home():
    return render_template('index.html')

# 啟動 Flask 伺服器的執行緒
def run_flask():
    app.run(host='0.0.0.0', debug=False, use_reloader=False)

# 開始攝影機
def start_camera():
    global capture, is_running
    if capture is None or not capture.isOpened():
        # 根據作業系統設定攝影機
        num = 0 if platform.system() == 'Windows' else 2 if platform.system() == 'Linux' and 'ANDROID_ARGUMENT' in os.environ else 0
        capture = cv2.VideoCapture(num)

    if not capture.isOpened():
        print("無法啟動攝影機")
        return

    is_running = True

# 停止攝影機
def stop_camera():
    global is_running, capture
    if is_running:
        is_running = False
        if capture:
            capture.release()

# 藍牙連接
def connect_bluetooth(address):
    global bluetooth_socket
    try:
        bluetooth_socket = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        bluetooth_socket.connect((address, 1))  # 1 is the port number for RFCOMM
        print(f"成功連接到藍牙設備: {address}")
    except Exception as e:
        print(f"無法連接到藍牙設備: {e}")
        bluetooth_socket = None

# Flet 介面部分
async def main(page: ft.Page):
    page.title = "Ball Face Detection App"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # 使用 Flet 建立 UI
    # 開始攝影機按鈕
    def start_camera_button_click(e):
        start_camera()
        threading.Thread(target=update_image_view, daemon=True).start()
        page.update()

    # 停止攝影機按鈕
    def stop_camera_button_click(e):
        stop_camera()
        page.update()

    # 藍牙連接按鈕
    def connect_bluetooth_button_click(e):
        address = "00:14:03:05:59:02"  # Example Bluetooth address, change it accordingly
        connect_bluetooth(address)
        if bluetooth_socket:
            page.snack_bar = ft.SnackBar(ft.Text("已成功連接到藍牙設備"))
        else:
            page.snack_bar = ft.SnackBar(ft.Text("藍牙連接失敗"))
        page.snack_bar.open = True
        page.update()

    # 添加視頻流的 iframe
    video_frame = ft.IFrame(src="http://127.0.0.1:5000/video_feed", width=640, height=480)

    start_camera_button = ft.ElevatedButton("開始攝影機", on_click=start_camera_button_click)
    stop_camera_button = ft.ElevatedButton("停止攝影機", on_click=stop_camera_button_click)
    connect_bluetooth_button = ft.ElevatedButton("連接藍牙", on_click=connect_bluetooth_button_click)

    # 主頁佈局
    page.add(
        ft.Column(
            [
                video_frame,
                start_camera_button,
                stop_camera_button,
                connect_bluetooth_button,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
    )

if __name__ == "__main__":
    # 啟動 Flask 伺服器和 Flet UI
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    ft.app(target=main, view=ft.WEB_BROWSER, host='0.0.0.0')
