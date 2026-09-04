import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, Response
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

def create_options():
    co = ChromiumOptions()
    co.set_browser_path('/usr/bin/chromium')
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--window-size=1920,1080')
    co.set_user_agent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    return co

def wait_for_turnstile(page, max_wait=30):
    start = time.time()
    locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
    while time.time() - start < max_wait:
        try:
            token_input = page.ele(locator, timeout=2)
            if token_input:
                return True, token_input.attr('value')
        except Exception:
            pass
        time.sleep(2)
    return False, ''

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())
        page.get(url)

        solved, token = wait_for_turnstile(page)
        title = page.title
        chrome_version = page.run_cdp('Browser.getVersion')['product']

        return jsonify({
            'url': url,
            'pageTitle': title,
            'chromeVersion': chrome_version,
            'widgetLoaded': solved,
            'turnstileSolved': solved,
            'tokenLength': len(token),
            'tokenPreview': (token[:60] + '...') if token else None,
            'checkedAt': datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if page:
            page.quit()

@app.route('/debug')
def debug_html():
    """Dump toàn bộ HTML sau khi chờ 15 giây để xem trang render ra gì."""
    url = request.args.get('url')
    wait = int(request.args.get('wait', 15))  # thời gian chờ, mặc định 15s
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())
        page.get(url)
        time.sleep(wait)
        html = page.html
        title = page.title
        return Response(
            f"<!-- TITLE: {title} -->\n<!-- WAITED: {wait}s -->\n"
            f"<!-- LENGTH: {len(html)} chars -->\n"
            f"<!-- Ctrl+F 'turnstile' or 'cf-' để tìm widget -->\n\n" + html,
            mimetype='text/html; charset=utf-8'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if page:
            page.quit()

@app.route('/debug-iframes')
def debug_iframes():
    """Liệt kê tất cả iframe có trong trang."""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())
        page.get(url)
        time.sleep(10)
        iframes = page.eles('tag:iframe')
        result = []
        for i, iframe in enumerate(iframes):
            result.append({
                'index': i,
                'src': iframe.attr('src'),
                'id': iframe.attr('id'),
                'name': iframe.attr('name'),
                'class': iframe.attr('class'),
            })
        return jsonify({
            'url': url,
            'pageTitle': page.title,
            'iframeCount': len(result),
            'iframes': result,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if page:
            page.quit()

@app.route('/')
def index():
    return '''
    <h3>🥷 DrissionPage Debug Endpoints</h3>
    <ul>
      <li><code>/test-widget?url=...</code> - Test Turnstile (logic chính)</li>
      <li><code>/debug?url=...&wait=15</code> - Dump toàn bộ HTML</li>
      <li><code>/debug-iframes?url=...</code> - Liệt kê tất cả iframe</li>
    </ul>
    '''
    
@app.route('/debug-deep')
def debug_deep():
    url = request.args.get('url')
    wait = int(request.args.get('wait', 20))
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())

        # Hook console + error TRƯỚC khi trang chạy
        page.add_init_js("""
            window.__dbg = {console: [], errors: []};
            ['log','warn','error','info'].forEach(lv => {
                const orig = console[lv] ? console[lv].bind(console) : null;
                console[lv] = function(...args){
                    try {
                        window.__dbg.console.push(lv + ': ' + args.map(a =>
                            (typeof a === 'object' ? JSON.stringify(a) : String(a))
                        ).join(' '));
                    } catch(e){}
                    if (orig) orig(...args);
                };
            });
            window.addEventListener('error', e => window.__dbg.errors.push(e.message));
        """)

        page.get(url)
        time.sleep(wait)

        info = page.run_js("""
            const out = {};
            out.turnstileLoaded = typeof window.turnstile;
            out.widgetContainers = document.querySelectorAll('.cf-turnstile, [data-sitekey], [id*="turnstile"]').length;
            out.hiddenInputs = document.querySelectorAll('input[name="cf-turnstile-response"]').length;
            out.iframes = Array.from(document.querySelectorAll('iframe')).map(f => f.src || '(no src)');
            out.cloudflareResources = performance.getEntriesByType('resource')
                .filter(r => r.name.includes('cloudflare'))
                .map(r => ({
                    file: r.name.split('?')[0].split('/').slice(-2).join('/'),
                    httpStatus: r.responseStatus || 0,
                    sizeKB: Math.round(r.transferSize / 1024),
                    durationMs: Math.round(r.duration)
                }));
            out.consoleLogs = (window.__dbg || {}).console || [];
            out.jsErrors = (window.__dbg || {}).errors || [];
            return out;
        """)

        info['pageTitle'] = page.title
        info['url'] = url
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if page:
            page.quit()
            
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
