import os
import time
import subprocess
import requests
from flask import Flask, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
os.makedirs(PROFILE_DIR, exist_ok=True)

def wait_for_chrome(port=9222, timeout=20):
    """Chờ Chromium bind port 9222 và sẵn sàng nhận CDP"""
    url = f"http://127.0.0.1:{port}/json/version"
    for i in range(timeout):
        try:
            res = requests.get(url, timeout=1)
            if res.status_code == 200:
                print(f"✅ Chrome đã sẵn sàng trên port {port} sau {i}s.")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    print("❌ Chrome không thể khởi động.")
    return False

def spawn_chrome():
    """Khởi động Chrome subprocess nếu chưa chạy"""
    # 1. Kiểm tra xem đã có Chrome nào đang chạy ở port 9222 chưa
    try:
        res = requests.get(f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=1)
        if res.status_code == 200:
            print("Chrome is already running.")
            return True
    except requests.exceptions.RequestException:
        pass

    print("🚀 Spawning Chrome subprocess...")
    subprocess.Popen([
        CHROME_PATH,
        f'--remote-debugging-port={DEBUG_PORT}',
        f'--user-data-dir={PROFILE_DIR}',
        '--headless=new',
        '--no-first-run',
        '--no-default-browser-check',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1920,1080',
        # Các flag chống fingerprinting quan trọng
        '--disable-features=IsolateOrigins,site-per-process,BlockInsecurePrivateNetworkRequests',
        '--disable-site-isolation-trials',
        '--disable-web-security',
        '--disable-features=TranslateUI'
    ])

    # 2. ⏳ CHỜ CHROME BIND PORT (Fix lỗi BrowserConnectError)
    return wait_for_chrome(DEBUG_PORT)

def get_driver():
    """Attach DrissionPage vào Chrome subprocess"""
    co = ChromiumOptions()
    co.set_local_port(DEBUG_PORT)
    co.auto_port(False)  # Bắt buộc dùng port 9222, không tự nhảy port khác
    
    # Ép DrissionPage KHÔNG được tự launch browser mới
    # Nếu port 9222 đã sẵn sàng, nó sẽ chỉ attach
    return ChromiumPage(co)

@app.route('/test-widget')
def test_widget():
    try:
        if not spawn_chrome():
            return jsonify({"error": "Failed to start Chrome"}), 500
            
        driver = get_driver()
        
        url = "https://gorouter.app/sign-up"
        driver.get(url)
        
        # Chờ Turnstile load
        time.sleep(4)
        
        # Check token lần 1
        token = driver.run_js("return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''")
        
        # Nếu đang ở Interactive mode (profile mới tinh), thử click vào iframe để trigger
        if len(token) == 0:
            print("Token chưa có, có thể đang ở Interactive mode. Thử click iframe...")
            iframe = driver.ele('@name=cf-turnstile-iframe') or driver.ele('css:iframe[src*="turnstile"]')
            if iframe:
                try:
                    # Giả lập chuột di chuyển và click (Human click)
                    driver.actions.move_to(iframe).click()
                    time.sleep(5) # Chờ Turnstile solve sau khi click
                    token = driver.run_js("return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''")
                except Exception as e:
                    print(f"Click iframe failed: {e}")

        page_title = driver.title
        
        return jsonify({
            "pageTitle": page_title,
            "tokenLength": len(token),
            "tokenSnippet": token[:20] + "..." if len(token) > 20 else token,
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Khởi động Chrome ngay khi server start
    spawn_chrome()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
