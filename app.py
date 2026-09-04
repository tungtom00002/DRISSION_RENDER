import os
import subprocess
import time
import atexit
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== CẤU HÌNH CHROME TRÊN RENDER (LINUX) ======
CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'  # Profile sẽ sống dai suốt vòng đời của instance
_chrome_proc = None

def start_chrome_bat_style():
    """
    BẢN DỊCH CỦA FILE .BAT SANG LINUX:
    Khởi động Chrome như 1 process ĐỘC LẬP, có profile riêng,
    KHÔNG phải do DrissionPage spawn ra -> Tránh bị detect automation.
    """
    global _chrome_proc
    # Nếu Chrome đang chạy rồi thì dùng lại (để giữ cookies/history -> tăng trust)
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        return  
    
    print("🚀 Spawning Chrome as an independent process (BAT style)...")
    _chrome_proc = subprocess.Popen([
        CHROME_PATH,
        f'--remote-debugging-port={DEBUG_PORT}',
        f'--user-data-dir={PROFILE_DIR}',
        '--no-first-run',
        '--headless=new',
        '--no-default-browser-check',
        '--no-sandbox',
        '--window-size=1920,1080',
    ])
    time.sleep(3)  # Chờ Chrome khởi động xong
    print("✅ Chrome is running and listening on port", DEBUG_PORT)

def cleanup():
    """Đảm bảo tắt Chrome khi server bị tắt"""
    global _chrome_proc
    if _chrome_proc:
        _chrome_proc.terminate()

atexit.register(cleanup)

def get_driver():
    """Attach vào Chrome đã mở sẵn (giống hệt logic set_local_port ở local)"""
    start_chrome_bat_style()
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
        
        # Locator chuẩn: Chờ input ẩn có value (token) xuất hiện
        locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
        solved, token = False, ''
        start = time.time()
        
        print(f"⏳ Đang chờ Turnstile solve cho {url}...")
        while time.time() - start < 45:
            ele = page.ele(locator, timeout=2)
            if ele:
                token = ele.attr('value') or ''
                if token:
                    solved = True
                    print(f"✅ SOLVED sau {int(time.time() - start)}s!")
                    break
            time.sleep(1)
            
        if not solved:
            print("❌ Không có token sau 45s")
            
        return jsonify({
            'url': url,
            'pageTitle': page.title,
            'widgetLoaded': solved,
            'turnstileSolved': solved,
            'tokenLength': len(token),
            'tokenPreview': (token[:60] + '...') if token else None,
            'checkedAt': datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        return jsonify({'error': str(e)}), 500
    # ⚠️ TUYỆT ĐỐI KHÔNG GỌI page.quit() -> Giữ browser sống để tích lũy trust!

@app.route('/')
def index():
    return 'Chrome-as-BAT mode (subprocess). GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
