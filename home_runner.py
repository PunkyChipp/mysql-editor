"""Persistent home process: private launcher, authenticated API, outbound tunnel."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

from remote_api import RemoteApp, make_server, write_private
from scripts.codespace_boot import ensure_running
from home_paths import DATA

ROOT=Path(__file__).resolve().parent
HOME=DATA
os.environ.setdefault('PYTHONUTF8','1')


def keep_awake(enabled):
    if os.name=='nt':
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000|(0x00000001 if enabled else 0))


def retry_runtime():
    """Retry a failed local boot after Docker/install/network problems recover."""
    try:
        with urllib.request.urlopen('http://127.0.0.1:8787/__study/api/status',timeout=2) as response:
            if json.load(response).get('phase')!='error':return
        with urllib.request.urlopen('http://127.0.0.1:8787/__study/?stay=1',timeout=2) as response:
            html=response.read().decode('utf-8')
        match=re.search(r'window\.STUDY_CONTEXT=(\{.*?\});',html)
        context=json.loads(match[1]) if match else {}
        token=context.get('token')
        if not isinstance(token,str):return
        request=urllib.request.Request('http://127.0.0.1:8787/__study/api/start',data=b'{}',
            headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8787','X-Study-Token':token})
        with urllib.request.urlopen(request,timeout=3) as response:response.read()
    except (OSError,ValueError):pass


def lock_runner():
    HOME.mkdir(exist_ok=True)
    stream=(HOME/'runner.lock').open('a+b')
    if stream.tell()==0:stream.write(b'1');stream.flush()
    stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        stream.close();return None
    return stream


def main():
    lock=lock_runner()
    if lock is None:return
    config_path=HOME/'config.json'
    config=json.loads(config_path.read_text())
    keep_awake(config.get('keepAwake',False))
    server=make_server(config)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    connector=None;log=None;last_config=config_path.stat().st_mtime_ns;last_token=None
    binary=HOME/'bin'/('cloudflared.exe' if os.name=='nt' else 'cloudflared')
    token=HOME/'tunnel-token'
    next_runtime_check=0
    last_retry=-1000000
    try:
        while not (HOME/'disconnect.request').exists():
            stamp=config_path.stat().st_mtime_ns
            if stamp!=last_config:
                config=json.loads(config_path.read_text());server.app=RemoteApp(config);last_config=stamp
                keep_awake(config.get('keepAwake',False))
            if time.monotonic()>=next_runtime_check:
                try:ensure_running()
                except Exception:pass
                if time.monotonic()-last_retry>=60:retry_runtime();last_retry=time.monotonic()
                next_runtime_check=time.monotonic()+15
            stamp=token.stat().st_mtime_ns if token.exists() else None
            if connector and (connector.poll() is not None or stamp!=last_token):
                if connector.poll() is None:connector.terminate();connector.wait(timeout=10)
                connector=None
                if log:log.close();log=None
            if connector is None and binary.is_file() and token.is_file():
                fd=os.open(HOME/'tunnel.log',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
                log=os.fdopen(fd,'a')
                connector=subprocess.Popen([str(binary),'--no-autoupdate','tunnel','--protocol','http2','run','--token-file',str(token)],
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                last_token=stamp
            write_private(HOME/'heartbeat.json',{'updated':time.time(),'api':'running','connector':bool(connector and connector.poll() is None)})
            time.sleep(3)
    finally:
        keep_awake(False)
        server.shutdown();server.server_close()
        if connector and connector.poll() is None:
            connector.terminate()
            try:connector.wait(timeout=10)
            except subprocess.TimeoutExpired:connector.kill();connector.wait()
        if log:log.close()
        (HOME/'heartbeat.json').unlink(missing_ok=True)
        (HOME/'disconnect.request').unlink(missing_ok=True)
        lock.close()


if __name__=='__main__':main()
