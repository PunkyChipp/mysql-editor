"""Authenticated browser/Worker/origin/real-MySQL pilot on a disposable runtime.

Start remote_api with a disposable config on 8791 and the test edge adapter on
8700; this script does not contact or configure Cloudflare or a home computer.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def code(page,text):
    page.locator('.cm-content').click();page.keyboard.press('Control+a');page.keyboard.insert_text(text)


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
        page.goto('http://127.0.0.1:8700/mysql-editor')
        assert page.url=='http://127.0.0.1:8700/mysql-editor/'
        expect(page.locator('#remote-login')).to_be_visible(timeout=15000)
        page.screenshot(path='/workspace/scratch/remote-login.png')
        page.locator('#remote-user').fill('owner');page.locator('#remote-password').fill('incorrect-password')
        page.locator('#remote-login button').click();expect(page.locator('#remote-error')).to_contain_text('incorrect')
        page.locator('#remote-password').fill('remote-e2e-test-password');page.locator('#remote-login button').click()
        expect(page.locator('#connection-dot')).to_have_class('live-dot online',timeout=20000)
        expect(page.locator('.connection-dialog')).not_to_be_visible()
        assert page.url=='http://127.0.0.1:8700/mysql-editor/'
        print('PASS: full editor at the exact project path; login authenticates through the real Worker/origin chain',flush=True)
        code(page,'CREATE TABLE IF NOT EXISTS remote_browser (id INT PRIMARY KEY, note VARCHAR(100));\nINSERT INTO remote_browser VALUES (1,\'Browser → Worker → MySQL\') ON DUPLICATE KEY UPDATE note=VALUES(note);\nSELECT * FROM remote_browser;')
        page.keyboard.press('Control+Shift+Enter')
        expect(page.locator('#result-tabs .result-tab')).to_have_count(3,timeout=20000)
        page.locator('[data-result="2"]').click();expect(page.locator('.data-table')).to_contain_text('Browser → Worker → MySQL')
        page.screenshot(path='/workspace/scratch/remote-sql-working.png')
        print('PASS: real MySQL script and result sets execute through same-origin authenticated API requests',flush=True)
        page.locator('[data-view="files"]').click();page.locator('[data-python]').click();page.locator('#run').click()
        expect(page.locator('#save-form')).to_be_visible();page.locator('#file-name').fill('remote-browser.py');page.locator('#save-form button[type=submit]').click()
        expect(page.locator('.output')).to_contain_text('Connected to schoolwork',timeout=20000)
        print('PASS: Python file save and Python/MySQL execution through the authenticated remote connection',flush=True)
        page.locator('#appearance').click();expect(page.locator('.theme-card')).to_have_count(20)
        page.locator('[data-theme-choice="mocha"]').click();page.get_by_role('button',name='Looks good',exact=False).click()
        expect(page.locator('#draft-status')).to_have_text('Drafts saved to workspace',timeout=10000)
        page.reload();expect(page.locator('#connection-dot')).to_have_class('live-dot online',timeout=15000)
        expect(page.locator('body')).to_have_attribute('data-theme','mocha')
        expect(page.locator('.doc-tab[aria-selected=true]')).to_contain_text('remote-browser.py')
        print('PASS: cookie session, theme and coursework restore without another login or URL change',flush=True)
        assert all(url.startswith('http://127.0.0.1:8700/') for url in requests),requests
        assert not errors,errors
        page.get_by_role('button',name='Sign out',exact=True).click();expect(page.locator('#remote-login')).to_be_visible(timeout=15000)
        print('PASS: sign-out revokes the session; browser makes no external API or Codespaces requests',flush=True)
        page.set_viewport_size({'width':834,'height':1194});page.screenshot(path='/workspace/scratch/remote-tablet-login.png')
        page.goto('http://127.0.0.1:8700/mysql-editor/setup/');page.locator('#check').click()
        expect(page.locator('#results')).to_contain_text('Same-domain API gateway reached',timeout=15000)
        expect(page.locator('#results')).to_contain_text('Home PC reached')
        print('PASS: owner/school connection check tests the actual same-domain route',flush=True)
        context.close();browser.close()


if __name__=='__main__':main()
