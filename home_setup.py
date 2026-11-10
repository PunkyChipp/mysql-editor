"""Windows-friendly local setup wizard; account secrets never leave this PC
except over HTTPS to Cloudflare when explicitly configuring the owner account.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import urllib.request
from urllib.parse import urlparse
import webbrowser

from remote_api import password_record,write_private,runtime_status
from hosting.cloudflare_setup import provision
from hosting.install_connector import install
from home_paths import DATA

ROOT=Path(__file__).resolve().parent
HOME=DATA;CONFIG=HOME/'config.json';PORT=8890
TOKEN=secrets.token_urlsafe(32);LOCK=threading.RLock();JOB=None
STATE={'phase':'idle','message':'Set up your account, then connect your website.','error':None}
URL='https://highereconomicsrevision.co.uk/mysql-editor/'


def read_config():
    try:return json.loads(CONFIG.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def update(message):
    with LOCK:STATE.update(message=message,error=None)


def start_runner():
    HOME.mkdir(exist_ok=True)
    (HOME/'disconnect.request').unlink(missing_ok=True)
    fd=os.open(HOME/'home.log',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,'a') as log:
        process=subprocess.Popen([sys.executable,str(ROOT/'home_runner.py')],cwd=ROOT,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
            start_new_session=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    threading.Thread(target=process.wait,daemon=True).start()


def startup(enabled):
    if os.name!='nt':return
    directory=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup'
    directory.mkdir(parents=True,exist_ok=True);path=directory/'Study Desk.cmd'
    if enabled:
        # Windows path characters such as percent must not become batch variables.
        def quoted(value):return str(value).replace('%','%%')
        executable=Path(sys.executable).with_name('pythonw.exe')
        if not executable.exists():executable=Path(sys.executable)
        path.write_text('@echo off\nchcp 65001 >nul\nset PYTHONUTF8=1\nstart "" "'+quoted(executable)+'" "'+quoted(ROOT/'home_runner.py')+'"\n',encoding='utf-8')
    else:path.unlink(missing_ok=True)


def save_account(data):
    username=str(data.get('username','')).strip()
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}',username):raise ValueError('Use letters, numbers, dots, underscores or @ in your username.')
    existing=read_config()
    password=data.get('password','')
    if not password and not existing:raise ValueError('Choose your workspace password.')
    record=password_record(password) if password else existing['password']
    existing.update({'version':1,'publicOrigin':'https://highereconomicsrevision.co.uk','apiPath':'/mysql-editor/api/',
        'username':username,'password':record,'originKey':existing.get('originKey') or secrets.token_urlsafe(48),
        'autoStart':bool(data.get('autoStart')),'keepAwake':bool(data.get('keepAwake'))})
    write_private(CONFIG,existing);startup(bool(data.get('autoStart')));start_runner()


def configure(token):
    with LOCK:STATE.update(phase='working',error=None,message='Checking your domain…')
    try:
        provision(token,CONFIG,progress=update)
        install(HOME/'bin',progress=update)
        start_runner()
        with LOCK:STATE.update(phase='done',message='Routing is configured. The connection test below checks when it is live.',error=None)
    except Exception as exc:
        with LOCK:STATE.update(phase='error',error=str(exc),message='Setup needs your attention.')
    finally:token=None


def public_check():
    try:
        with urllib.request.urlopen(URL+'api/health',timeout=12) as response:
            if 'application/json' not in response.headers.get('Content-Type',''):raise ValueError()
            result=json.load(response)
        return {'website':True,'route':result.get('route')=='connected','home':result.get('home')=='online','ready':bool(result.get('ready'))}
    except Exception:return {'website':False,'route':False,'home':False,'ready':False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,value,kind='application/json'):
        body=value.encode() if isinstance(value,str) else json.dumps(value).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        self.end_headers();self.wfile.write(body)
    def valid_host(self):return self.headers.get('Host') in {'127.0.0.1:'+str(PORT),'localhost:'+str(PORT)}
    def do_GET(self):
        if not self.valid_host():self.send(403,{'error':'Open setup on this PC.'});return
        if self.path=='/':
            html=(ROOT/'hosting/home.html').read_text(encoding='utf-8').replace('/*__TOKEN__*/',json.dumps(TOKEN))
            self.send(200,html,'text/html; charset=utf-8');return
        if self.path=='/status':
            cfg=read_config()
            try:heartbeat=json.loads((HOME/'heartbeat.json').read_text());running=time.time()-heartbeat['updated']<20
            except Exception:heartbeat={};running=False
            with LOCK:state=dict(STATE)
            self.send(200,{**state,'configured':bool(cfg),'username':cfg.get('username','owner'),
                'domainConfigured':cfg.get('cloudflare',{}).get('configured',False),'running':running,
                'connector':heartbeat.get('connector',False),'dockerInstalled':bool(shutil.which('docker')),
                'autoStart':cfg.get('autoStart',True),'keepAwake':cfg.get('keepAwake',True),
                'runtime':runtime_status()});return
        self.send(404,{'error':'Not found.'})
    def do_POST(self):
        global JOB
        if not self.valid_host() or self.headers.get('X-Setup-Token')!=TOKEN or self.headers.get('Origin') not in {'http://127.0.0.1:'+str(PORT),'http://localhost:'+str(PORT)}:
            self.send(403,{'error':'Refresh the local setup window.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 1<=length<=10000:raise ValueError('Setup request was too large or incomplete.')
            data=json.loads(self.rfile.read(length))
            if self.path=='/check':self.send(200,public_check());return
            if self.path=='/disconnect':(HOME/'disconnect.request').touch();self.send(200,{'ok':True});return
            with LOCK:
                if JOB and JOB.is_alive():raise ValueError('Website setup is still in progress. Wait for it to finish.')
                if self.path=='/account':save_account(data);self.send(200,{'ok':True});return
                if self.path=='/start':
                    if not CONFIG.exists():raise ValueError('Save your workspace account first.')
                    start_runner();self.send(200,{'ok':True});return
                if self.path=='/connect':
                    if not CONFIG.exists():raise ValueError('Save your workspace account first.')
                    if not data.get('confirmed'):raise ValueError('Review and confirm the exact DNS/API changes first.')
                    token=data.get('token','').strip()
                    if not 20<=len(token)<=2048:raise ValueError('Enter your Cloudflare API token in this local window.')
                    JOB=threading.Thread(target=configure,args=(token,),daemon=True);JOB.start();self.send(202,{'ok':True});return
            self.send(404,{'error':'Unknown setup action.'})
        except (ValueError,TypeError,KeyError) as exc:self.send(400,{'error':str(exc)})
        except Exception:self.send(500,{'error':'Setup could not finish this step. Check the local configuration and try again.'})


def main():
    HOME.mkdir(exist_ok=True)
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(PORT)+'/status',timeout=2) as response:
                data=json.load(response)
                if 'configured' not in data:raise ValueError()
        except Exception:raise SystemExit('Local setup port 8890 is already in use by another application.')
        webbrowser.open('http://127.0.0.1:'+str(PORT)+'/');return
    server.daemon_threads=True
    webbrowser.open('http://127.0.0.1:'+str(PORT)+'/')
    print('Study Desk setup is open on this PC. Keep this window open while configuring the website.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
