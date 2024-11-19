import flet as ft
import cv2
import socket
import threading
import platform
import os
import time
import numpy as np
import base64
from flask import Flask, Response

# 建立 Flask 應用
app = Flask(__name__)
capture = None
is_running = False

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

# 啟動 Flask 伺服器的執行緒
def run_flask(port):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# 開始攝影機
def start_camera(port):
    global capture, is_running
    if capture is None or not capture.isOpened():
        # 根據作業系統設定攝影機
        num = 0 if platform.system() == 'Windows' else 2 if platform.system() == 'Linux' and 'ANDROID_ARGUMENT' in os.environ else 0
        capture = cv2.VideoCapture(num)

    if not capture.isOpened():
        print("無法啟動攝影機")
        return

    is_running = True
    threading.Thread(target=run_flask, args=(port,), daemon=True).start()

# 停止攝影機
def stop_camera():
    global is_running, capture
    if is_running:
        is_running = False
        if capture:
            capture.release()

# Flet 介面部分
def main(page: ft.Page):
    page.title = "Ball Face Detection App"

    # 初始顯示用的空白影像
    init_image = np.zeros((480, 640, 3), dtype=np.uint8) + 128
    init_base64_image = to_base64(init_image)

    # 顯示影像的區域
    image_view = ft.Image(src_base64=init_base64_image, width=640, height=480)

    # 手動輸入 HC-05 地址
    device_address_input = ft.TextField(label="輸入 HC-05 地址 (如 00:14:03:05:59:02)", width=400)

    # 連接按鈕
    def connect_device(e):
        address = device_address_input.value.strip()
        if not address:
            page.dialog = ft.AlertDialog(title=ft.Text("錯誤"), content=ft.Text("請輸入 HC-05 的藍牙地址"))
            page.dialog.open = True
            page.update()
            return

        try:
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            sock.connect((address, 1))  # HC-05 默認埠為 1
            send_message.sock = sock
            page.dialog = ft.AlertDialog(title=ft.Text("成功"), content=ft.Text(f"已連接到 {address}"))
            page.dialog.open = True
            page.update()
        except Exception as e:
            page.dialog = ft.AlertDialog(title=ft.Text("連接失敗"), content=ft.Text(str(e)))
            page.dialog.open = True
            page.update()

    connect_button = ft.ElevatedButton("連接 HC-05", on_click=connect_device)

    # 發送訊息輸入框
    message_input = ft.TextField(label="輸入要發送的訊息", width=400)

    # 發送按鈕
    def send_message(e=None, message=''):
        if not hasattr(send_message, "sock") or send_message.sock is None:
            page.dialog = ft.AlertDialog(title=ft.Text("錯誤"), content=ft.Text("未連接到任何設備"))
            page.dialog.open = True
            page.update()
            return

        if not message:
            message = message_input.value.strip()

        if not message:
            page.dialog = ft.AlertDialog(title=ft.Text("錯誤"), content=ft.Text("請輸入訊息"))
            page.dialog.open = True
            page.update()
            return

        try:
            send_message.sock.send((message + '\n').encode())
            page.dialog = ft.AlertDialog(title=ft.Text("成功"), content=ft.Text(f"已發送訊息：{message}"))
            page.dialog.open = True
            page.update()
        except Exception as e:
            page.dialog = ft.AlertDialog(title=ft.Text("發送失敗"), content=ft.Text(str(e)))
            page.dialog.open = True
            page.update()

    send_button = ft.ElevatedButton("發送訊息", on_click=send_message)

    # 開始攝影機按鈕
    def start_camera_button_click(e):
        port = int(os.environ.get('PORT', 5000))
        start_camera(port)
        page.update()
        threading.Thread(target=update_image_view, daemon=True).start()

    # 停止攝影機按鈕
    def stop_camera_button_click(e):
        stop_camera()
        page.update()

    start_camera_button = ft.ElevatedButton("開始攝影機", on_click=start_camera_button_click)
    stop_camera_button = ft.ElevatedButton("停止攝影機", on_click=stop_camera_button_click)

    # 請求權限按鈕
    def request_permissions(e):
        page.dialog = ft.AlertDialog(title=ft.Text("請求權限"), content=ft.Text("請允許攝影機與藍牙的使用權限"))
        page.dialog.open = True
        page.update()

    request_permissions_button = ft.ElevatedButton("請求攝影機與藍牙權限", on_click=request_permissions)

    # 更新影像視圖
    def update_image_view():
        while is_running:
            try:
                # 從攝影機獲取當前幀
                ret, frame = capture.read()
                if not ret:
                    continue

                # 將影像轉換為 base64 並更新 ImageView
                base64_image = to_base64(frame)
                image_view.src_base64 = base64_image
                page.update()
                time.sleep(1 / 30)  # 每秒約 30 幀
            except Exception as e:
                print(f"更新影像時發生錯誤: {e}")

    # 主頁佈局
    page.add(
        request_permissions_button,
        device_address_input,
        connect_button,
        message_input,
        send_button,
        start_camera_button,
        stop_camera_button,
        image_view,
    )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    ft.app(target=main, host='0.0.0.0', port=port)
