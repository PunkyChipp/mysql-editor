"""Real workspace UI pilot. Start the launcher against a disposable MySQL runtime.

Requires Playwright/Chromium and DESK_BROWSER_URL (default localhost:8787).
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('DESK_BROWSER_URL','http://127.0.0.1:8787')
SHOTS=Path(os.environ.get('DESK_SCREENSHOTS','/workspace/scratch'))


def set_code(page, code):
    editor=page.locator('.cm-content')
    editor.click();page.keyboard.press('Control+a');page.keyboard.insert_text(code)


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/desk/')
        expect(page.locator('#connection-dot')).to_have_class('live-dot online',timeout=20000)
        expect(page.locator('.doc-tab')).to_have_count(1)
        token=page.evaluate('window.STUDY_CONTEXT.token')
        def api(action,data,expected=200):
            response=page.request.post(BASE+'/__study/desk/'+action,data=data,headers={'X-Study-Token':token})
            assert response.status==expected,(response.status,response.text())
            return response.json()
        api('call',{'op':'state','value':None})
        # A SQL script is run using the actual toolbar and the real MySQL worker.
        set_code(page,"CREATE TABLE IF NOT EXISTS students (id INT PRIMARY KEY, name VARCHAR(100), subject VARCHAR(100), score INT);\nINSERT INTO students VALUES (1,'Alex','Computing',92),(2,'Sam','Mathematics',85),(3,'Jordan','Computing',78),(4,'Taylor','Physics',96),(5,'Riley','Mathematics',88) ON DUPLICATE KEY UPDATE name=VALUES(name);\nSELECT * FROM students ORDER BY score DESC;")
        page.keyboard.press('Control+Shift+Enter')
        expect(page.locator('#result-tabs .result-tab')).to_have_count(3,timeout=15000)
        page.locator('[data-result="2"]').click()
        expect(page.locator('.data-table')).to_contain_text('Taylor')
        expect(page.locator('#result-footer')).to_contain_text('5 rows')
        print('PASS: run entire script; switch between real MySQL result sets',flush=True)
        page.screenshot(path=str(SHOTS/'desk-default-dark.png'))
    
        set_code(page,"SELECT 'first statement' AS message;\nSELECT 'second statement' AS message;")
        page.locator('#run').click()
        expect(page.locator('.data-table')).to_contain_text('second statement',timeout=15000)
        expect(page.locator('#result-tabs')).to_be_hidden()
        print('PASS: Run query chooses the statement at the cursor',flush=True)
    
        set_code(page,"SELECT 1 AS selected_value;\nSELECT 2 AS other_value;")
        page.keyboard.press('Control+Home');page.keyboard.press('Control+Shift+End')
        page.locator('#run').click()
        expect(page.locator('#result-tabs .result-tab')).to_have_count(2,timeout=15000)
        print('PASS: selected SQL runs and returns multiple result sets',flush=True)
    
        page.locator('[data-table="students"]').click()
        expect(page.locator('#result-title')).to_have_text('students',timeout=10000)
        expect(page.locator('#result-content')).to_contain_text('Alex')
        page.locator('td[data-row="0"][data-column="1"]').dblclick()
        expect(page.locator('#modal')).to_be_visible()
        page.locator('#cell-value').fill('Alex Updated')
        page.get_by_role('button',name='Save change',exact=True).click()
        expect(page.locator('#result-content')).to_contain_text('Alex Updated',timeout=10000)
        page.locator('#table-search').fill('Mathematics');page.locator('#table-search').press('Enter')
        expect(page.locator('#result-count')).to_have_text('2',timeout=10000)
        page.locator('#structure-view').click()
        expect(page.locator('#result-content')).to_contain_text('varchar(100)')
        page.locator('#data-view').click()
        expect(page.locator('#result-title')).to_have_text('students')
        print('PASS: table browser, direct row edit, server search and structure view',flush=True)
    
        page.locator('#table-search').fill('');page.locator('#table-search').press('Enter')
        expect(page.locator('#result-count')).to_have_text('5',timeout=10000)
        with page.expect_download() as download:
            page.locator('#export').click()
        exported=download.value
        assert exported.suggested_filename=='students.csv'
        assert 'Alex Updated' in Path(exported.path()).read_text()
        print('PASS: CSV export contains the displayed database rows',flush=True)
    
        page.locator('#appearance').click()
        expect(page.locator('.theme-card')).to_have_count(20)
        names=[]
        for card in page.locator('.theme-card').all(): names.append(card.get_attribute('data-theme-choice'))
        for name in names:
            page.locator(f'[data-theme-choice="{name}"]').click()
            expect(page.locator('body')).to_have_attribute('data-theme',name)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('[data-theme-choice="mocha"]').click()
        page.screenshot(path=str(SHOTS/'desk-appearance.png'))
        page.get_by_role('button',name='Looks good',exact=False).click()
        page.screenshot(path=str(SHOTS/'desk-mocha.png'))
        print('PASS: all 20 appearance presets apply; rounded layout selected',flush=True)
    
        page.locator('[data-view="files"]').click();page.locator('[data-python]').click()
        page.locator('#run').click()
        expect(page.locator('#save-form')).to_be_visible()
        page.locator('#file-name').fill('ui-python-check.py')
        page.locator('#save-form button[type="submit"]').click()
        expect(page.locator('.output')).to_contain_text('Connected to schoolwork',timeout=20000)
        print('PASS: Python file save and actual Python/MySQL integration from the UI',flush=True)
    
        # Theme, open documents and Python output code survive a browser reload.
        expect(page.locator('#draft-status')).to_have_text('Drafts saved to workspace',timeout=10000)
        page.reload();expect(page.locator('#connection-dot')).to_have_class('live-dot online',timeout=20000)
        expect(page.locator('body')).to_have_attribute('data-theme','mocha')
        expect(page.locator('.doc-tab[aria-selected="true"]')).to_contain_text('ui-python-check.py')
        print('PASS: saved appearance and documents restore from workspace storage',flush=True)
    
        # Request forgery must not reach the database worker.
        response=page.request.post(BASE+'/__study/desk/run',data={'op':'execute','sql':'SELECT 1'})
        assert response.status==403
        print('PASS: API rejects mutation requests without its private token',flush=True)
        assert not errors,errors
    
        for name,width,height in [('tablet',834,1194),('phone',390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            page.locator('#appearance').click();page.locator('[data-theme-choice="matcha"]').click()
            page.get_by_role('button',name='Looks good',exact=False).click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(SHOTS/('desk-'+name+'.png')))
            print('PASS:',name,'responsive layout',flush=True)
        context.close();browser.close()


if __name__=="__main__":
    main()
