import os
import subprocess
import time
import shutil
import urllib.request
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== CẤU HÌNH ======
CHROME_PATH = '/usr/bin/chromium'   # Debian/Ubuntu: /usr/bin/chromium
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
_chrome_proc = None

def _wait_for_chrome(timeout=30):
    """Chờ Chrome mở port xong mới cho kết nối"""
    for i in range(timeout):
        try:
            urllib.request.urlopen(
                f'http://127.0.0.1:{DEBUG_PORT}/json/version',
                timeout=1
            )
            print(f'✅ Chrome sẵn sàng sau {i+1}s')
            return True
        except Exception:
            time.sleep(1)
    return False

def start_chrome():
    global _chrome_proc

    # Nếu Chrome đang chạy rồi thì bỏ qua
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        try:
            urllib.request.urlopen(
                f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=1
            )
            return  # vẫn sống, dùng lại
        except Exception:
            pass  # chết rồi, spawn lại

    # Dọn profile cũ (tránh xung đột lock file)
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
        time.sleep(1)

    # Kill chrome zombie (nếu có)
    os.system('pkill -f "remote-debugging-port" 2>/dev/null || true')
    time.sleep(1)

    print('🚀 Đang spawn Chrome...')
    _chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            f'--remote-debugging-port={DEBUG_PORT}',
            '--remote-debugging-address=127.0.0.1',   # 👈 FIX IPv6 issue
            f'--user-data-dir={PROFILE_DIR}',
            '--headless=new',
            '--no-first-run',
            '--no-default-browser-check',
            '--no-sandbox',                            # 👈 BẮT BUỘC trên Docker
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_chrome(30):
        raise Exception('❌ Chrome không start được sau 30s. Kiểm tra log.')

def get_driver():
    start_chrome()
    co = ChromiumOptions()
    co.set_local_port(DEBUG_PORT)
    return ChromiumPage(co)

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    try:
        page = get_driver()
        page.get(url)
        # ... logic xử lý tiếp theo
        return jsonify({'pageTitle': page.title})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
