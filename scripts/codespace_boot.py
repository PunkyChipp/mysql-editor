"""Start the private web app independently of the Codespaces IDE terminal."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def address(port=8787):
    name=os.environ.get('CODESPACE_NAME','')
    domain=os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')
    if re.fullmatch(r'[A-Za-z0-9-]+',name) and re.fullmatch(r'[A-Za-z0-9.-]+',domain):
        return f'https://{name}-{port}.{domain}'
    return f'http://127.0.0.1:{port}'


def running(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/__study/api/status',timeout=.5) as response:
            data=json.load(response)
            return data.get('phase') in {'idle','working','ready','error'}
    except (OSError,ValueError):
        return False


def ensure_running(root=ROOT,port=8787,timeout=20):
    if running(port):
        return None
    fd=os.open(root/'.study-desk-launcher.log',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,'a') as log:
        process=subprocess.Popen([sys.executable,str(root/'launch.py'),'--no-browser','--port',str(port)],
            cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
            start_new_session=True,close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    # Reap the child if this helper stays alive (e.g. a test process). The daemon
    # waiter never keeps the startup command alive or holds the backend open.
    threading.Thread(target=process.wait,daemon=True).start()
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if running(port):
            return process.pid
        if process.poll() is not None:
            break
        time.sleep(.15)
    raise RuntimeError('Study Desk could not start. See .study-desk-launcher.log in the host workspace.')


def write_note(root=ROOT,port=8787):
    url=address(port)+'/desk/'
    (root/'.study-desk-start.md').write_text(f'''# Open Study Desk in your browser

## [Open Study Desk →]({url})

This link opens your own full-page SQL and Python app. Codespaces provides the
computer behind it. Work in the Study Desk browser tab, outside the IDE preview.

The app shows setup progress, then opens your editor automatically. The first
boot can take several minutes. If your browser blocks the automatic tab, follow
the Open Study Desk link above once. GitHub may ask you to sign in.

Bookmark this private address: {url}

You can close this IDE tab after the app opens. Keep the Codespace running and
port 8787 Private. Stopping the Codespace stops the app; resume it in GitHub
before returning. GitHub inactivity and usage limits still apply.
''')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','attach'])
    args=parser.parse_args()
    ensure_running()
    write_note()
    if args.action=='attach':
        # Emit after attachment: onAutoForward=openBrowser opens a real browser
        # tab, rather than a Simple Browser frame in the Codespaces workbench.
        print('Study Desk web app: http://localhost:8787/desk/',flush=True)
        print('Open in your own browser: '+address()+'/desk/',flush=True)
        print('If a tab was blocked, follow the Open Study Desk link in .study-desk-start.md.',flush=True)
    else:
        print('Study Desk is starting in the background.',flush=True)


if __name__=='__main__':
    main()
