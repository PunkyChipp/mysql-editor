"""Lifecycle checks with a tiny disposable HTTP service, without Docker."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('codespace_boot',ROOT/'scripts/codespace_boot.py')
boot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class LifecycleTests(unittest.TestCase):
    def test_background_service_survives_startup_function_and_reattach_reuses_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'launch.py').write_text('''import argparse,json
from http.server import BaseHTTPRequestHandler,HTTPServer
p=argparse.ArgumentParser();p.add_argument('--port',type=int);a,_=p.parse_known_args()
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=json.dumps({'phase':'working'}).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
''')
            with socket.socket() as s:
                s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            pid=boot.ensure_running(root=root,port=port,timeout=5)
            try:
                self.assertTrue(boot.running(port))
                self.assertEqual(os.getsid(pid),pid)
                self.assertIsNone(boot.ensure_running(root=root,port=port,timeout=5))
            finally:
                os.kill(pid,signal.SIGTERM)
                for _ in range(30):
                    try: os.kill(pid,0)
                    except ProcessLookupError: break
                    time.sleep(.02)

    def test_start_note_contains_the_actual_private_web_app_link(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{
                'CODESPACE_NAME':'my-school-space','GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}):
            root=Path(folder);boot.write_note(root)
            note=(root/'.study-desk-start.md').read_text()
            self.assertIn('https://my-school-space-8787.app.github.dev/desk/',note)
            self.assertIn('close this IDE tab',note)

    def test_configuration_opens_the_browser_and_does_not_tie_backend_to_attach_terminal(self):
        config=json.loads((ROOT/'.devcontainer/devcontainer.json').read_text())
        self.assertEqual(config['portsAttributes']['8787']['onAutoForward'],'openBrowser')
        self.assertEqual(config['waitFor'],'postStartCommand')
        self.assertEqual(config['postStartCommand'],'python3 scripts/codespace_boot.py start')
        self.assertEqual(config['postAttachCommand'],'python3 scripts/codespace_boot.py attach')


if __name__=='__main__': unittest.main()
