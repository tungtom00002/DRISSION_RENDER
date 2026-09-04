import os
import time
import subprocess
import requests
from flask import Flask, jsonify, request
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ============ CONFIGURATION ============
CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
os.makedirs(PROFILE_DIR, exist_ok=True)

# Singleton: Cờ đánh dấu Chrome đã được spawn chưa
chrome_spawned = False

def wait_for_chrome(port=9222, timeout=20):
    """Chờ Chromium bind port và sẵn sàng nhận CDP"""
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
    global chrome_spawned
    if chrome_spawned:
        return True

    # 1. Check nếu đã có Chrome chạy sẵn (tránh spawn duplicate)
    try:
        res = requests.get(f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=1)
        if res.status_code == 200:
            print("🔄 Chrome is already running.")
            chrome_spawned = True
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
        # Anti-detect flags
        '--disable-features=IsolateOrigins,site-per-process,BlockInsecurePrivateNetworkRequests',
        '--disable-site-isolation-trials',
        '--disable-web-security',
        '--disable-features=TranslateUI'
    ])

    # 2. ⏳ Wait-loop: Tránh BrowserConnectError
    success = wait_for_chrome(DEBUG_PORT)
    if success:
        chrome_spawned = True
    return success

def get_driver():
    co = ChromiumOptions()
    co.set_local_port(DEBUG_PORT)
    co.auto_port(False)
    return ChromiumPage(co)

# ============ ROUTES ============

@app.route('/')
def home():
    """Health check endpoint cho Render"""
    return jsonify({
        "status": "online",
        "service": "DrissionPage Cloudflare Bypass",
        "chrome_port": DEBUG_PORT,
        "usage": "/test-widget?url=https://example.com"
    })

@app.route('/test-widget')
def test_widget():
    try:
        # 1. Đảm bảo Chrome đã được spawn
        if not spawn_chrome():
            return jsonify({"error": "Failed to start Chrome"}), 500
            
        driver = get_driver()
        
        # 2. Dynamic URL - mặc định là gorouter
        url = request.args.get('url', 'https://gorouter.app/sign-up')
        print(f"🌐 Navigating to: {url}")
        driver.get(url)
        
        # 3. Chờ trang load + Cloudflare JS chạy
        time.sleep(5)
        
        # 4. Thăm dò token
        token = driver.run_js("return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''")
        
        # 5. Nếu chưa có token -> Interactive mode -> Fake click
        if len(token) == 0:
            print("🖱️ Token chưa có, thử click vào Turnstile iframe...")
            iframe = driver.ele('css:iframe[src*="turnstile"]') or driver.ele('@name=cf-turnstile-iframe')
            if iframe:
                try:
                    driver.actions.move_to(iframe).click()
                    time.sleep(6)
                    token = driver.run_js("return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''")
                except Exception as e:
                    print(f"Click iframe failed: {e}")
            else:
                print("⚠️ Không tìm thấy iframe Turnstile")

        return jsonify({
            "pageTitle": driver.title,
            "targetUrl": url,
            "tokenLength": len(token),
            "tokenSnippet": token[:30] + "..." if len(token) > 30 else token,
            "solved": len(token) > 0,
            "timestamp": time.time()
        })
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# ============ APP START ============
if __name__ == '__main__':
    # Spawn Chrome ngay khi server Flask start
    spawn_chrome()
    
    # Render dùng port từ ENV var 'PORT'
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
