import flet as ft
import cv2
import numpy as np
import socket
import threading
import platform
import os
import time
import base64
from flask import Flask, Response, render_template_string

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
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ball Face Detection App</title>
    </head>
    <body>
        <h1>Ball Face Detection App</h1>
        <iframe src="http://127.0.0.1:8550" width="100%" height="600" style="border:none;"></iframe>
        <h2>Video Stream:</h2>
        <img src="/video_feed" width="640" height="480">
    </body>
    </html>
    """
    return render_template_string(html_content)

# 啟動 Flask 伺服器的執行緒
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Flet 介面部分
def flet_ui():
    def main(page: ft.Page):
        page.title = "Ball Face Detection Control"
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

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

        start_camera_button = ft.ElevatedButton("開始攝影機", on_click=start_camera_button_click)
        stop_camera_button = ft.ElevatedButton("停止攝影機", on_click=stop_camera_button_click)
        connect_bluetooth_button = ft.ElevatedButton("連接藍牙", on_click=connect_bluetooth_button_click)

        # 主頁佈局
        page.add(
            ft.Column(
                [
                    start_camera_button,
                    stop_camera_button,
                    connect_bluetooth_button,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        )

    ft.app(target=main, view=ft.WEB_BROWSER, port=8550)

if __name__ == "__main__":
    # 啟動 Flask 伺服器和 Flet UI
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    flet_ui()
