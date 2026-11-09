"""Boot handoff checks. Run with Python + Playwright and installed Chromium."""
import importlib.util
from pathlib import Path
import threading
import unittest
import sys

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('launcher', ROOT / 'launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class TestHandler(launcher.Handler):
    def handle_request(self):
        if self.path=='/desk/':
            self.send(200, '<h1>Study editor</h1>', 'text/html')
        else:
            super().handle_request()
    def proxy(self):
        self.send(200, '<h1>Study editor</h1>', 'text/html')


class BootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = launcher.ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
        cls.server.remote_host = ''
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path='/usr/bin/chromium', args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        launcher.STATE.update(phase='working', step=2, message='Installing tools',
                              details=[], error=None)
        self.context = self.browser.new_context(viewport={'width':834,'height':1194}, has_touch=True)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.context.close()

    def test_waits_for_checks_then_opens_editor_without_click(self):
        self.page.goto(self.base)
        expect(self.page.locator('#message')).to_have_text('Installing tools')
        expect(self.page.locator('#open-editor')).to_be_hidden()
        launcher.update('working', 4, 'Checking MySQL')
        expect(self.page.locator('#message')).to_have_text('Checking MySQL')
        self.assertIn('/__study/', self.page.url)
        launcher.update('ready', 5, 'Ready')
        expect(self.page.get_by_role('heading', name='Study editor')).to_be_visible()
        self.assertEqual(self.page.url, self.base + '/desk/')

    def test_setup_error_stays_visible_and_retry_resumes_automatic_handoff(self):
        launcher.update('error', 2, 'Download failed', error='Download failed')
        self.page.goto(self.base)
        expect(self.page.locator('#start')).to_have_text('Try again')
        expect(self.page.locator('#message')).to_have_text('Download failed')
        launcher.start_job = lambda: launcher.update('ready', 5, 'Ready')
        try:
            self.page.locator('#start').click()
            expect(self.page.get_by_role('heading', name='Study editor')).to_be_visible()
        finally:
            del launcher.start_job
            # Restore the module's real implementation for later tests.
            launcher.start_job = original_start_job

    def test_ready_session_also_opens_inside_preview_frame(self):
        launcher.update('ready', 5, 'Ready')
        self.page.set_content('<iframe title="Workspace"></iframe>')
        self.page.locator('iframe').evaluate('(frame, url) => frame.src = url', self.base)
        expect(self.page.frame_locator('iframe').get_by_role('heading', name='Study editor')).to_be_visible()

    def test_diagnostic_view_can_remain_open_when_ready(self):
        launcher.update('ready', 5, 'Ready')
        self.page.goto(self.base + '/__study/?stay=1')
        expect(self.page.locator('#open-editor')).to_be_visible()
        self.assertIn('stay=1', self.page.url)

    def test_denied_browser_storage_gets_working_temporary_preferences(self):
        self.page.goto(self.base + '/__study/?stay=1')
        self.page.evaluate('''() => {
            for (const name of ['localStorage', 'sessionStorage']) {
                Object.defineProperty(window, name, {configurable:true,
                    get() { throw new DOMException('Blocked', 'SecurityError'); }});
            }
        }''')
        self.page.add_script_tag(path=str(ROOT / 'editor/browser-storage.js'))
        self.assertTrue(self.page.evaluate('''() => {
            for (const name of ['localStorage', 'sessionStorage']) {
                const store = window[name];
                store.setItem('test', 42);
                if (store.getItem('test') !== '42' || store.length !== 1) return false;
                store.profile = 'student';
                if (store.getItem('profile') !== 'student') return false;
                if (!Object.keys(store).includes('test')) return false;
                store.removeItem('test');
                if (store.getItem('test') !== null) return false;
                delete store.missing;
                store.clear();
                if (store.length !== 0) return false;
            }
            return true;
        }'''))

    def test_available_browser_storage_is_preserved(self):
        self.page.goto(self.base + '/__study/?stay=1')
        self.page.evaluate("localStorage.setItem('saved-preference', 'kept')")
        self.page.add_script_tag(path=str(ROOT / 'editor/browser-storage.js'))
        self.page.reload()
        self.assertEqual(self.page.evaluate("localStorage.getItem('saved-preference')"), 'kept')


original_start_job = launcher.start_job
if __name__ == '__main__':
    unittest.main()
