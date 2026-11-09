#!/usr/bin/env python3
"""Guided, local-only Study Desk launcher. Standard library only."""
from __future__ import annotations
import argparse
import http.client
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse
import webbrowser

ROOT=Path(__file__).resolve().parent
STATE={'phase':'idle','step':0,'message':'Ready to prepare your workspace.','details':[],'error':None}
LOCK=threading.RLock()
JOB=None
TOKEN=secrets.token_urlsafe(32)
COOKIE=''
COOKIE_FINGERPRINT=None
AUTH_LOCK=threading.Lock()
MAX_BODY=20*1024*1024


def values():
    p=ROOT/'.env'
    return dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line) if p.exists() else {}

def redact(text):
    for key,value in values().items():
        if 'PASSWORD' in key and value: text=text.replace(value,'[private]')
    return text[-16000:]

def update(phase,step,message,error=None):
    with LOCK: STATE.update(phase=phase,step=step,message=message,error=error)

def run(command,timeout=120):
    result=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    with LOCK:
        STATE['details'].append(redact(result.stdout))
        STATE['details']=STATE['details'][-12:]
    if result.returncode: raise RuntimeError('The setup command could not finish. Open details for the diagnostic.')
    return result.stdout

def recover_existing_workspace():
    """Reuse this application's credentials when moving from the old package."""
    if (ROOT/'.env').exists(): return
    listing=subprocess.run(['docker','ps','-aq','--filter','label=com.docker.compose.project=locked-study'],capture_output=True,text=True)
    ids=listing.stdout.split()
    if not ids: return
    result=subprocess.run(['docker','inspect',*ids],capture_output=True,text=True)
    if result.returncode: return
    recovered={}
    for item in json.loads(result.stdout):
        labels=item['Config'].get('Labels',{})
        service=labels.get('com.docker.compose.service')
        env=dict(x.split('=',1) for x in item['Config'].get('Env',[]) if '=' in x)
        if service=='editor' and env.get('PASSWORD'): recovered['EDITOR_PASSWORD']=env['PASSWORD']
        if service=='db':
            for key in ('MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD'):
                if env.get(key): recovered[key]=env[key]
        if service=='gateway':
            ports=item.get('NetworkSettings',{}).get('Ports',{}).get('8080/tcp') or []
            if ports: recovered['STUDY_PORT']=ports[0]['HostPort']
    if all(recovered.get(k) for k in ['EDITOR_PASSWORD','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD']):
        fd=os.open(ROOT/'.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as file:
            for key in ['EDITOR_PASSWORD','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','STUDY_PORT']:
                file.write(key+'='+recovered.get(key,'8080')+'\n')

def start_job():
    global JOB
    with LOCK:
        if JOB and JOB.is_alive(): return
        STATE['details']=[]
        JOB=threading.Thread(target=prepare,daemon=True); JOB.start()

def prepare():
    global COOKIE
    try:
        update('working',0,'Checking this computer…')
        if not shutil.which('docker'):
            candidates=[Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Docker/Docker/resources/bin/docker.exe'] if os.name=='nt' else [Path('/Applications/Docker.app/Contents/Resources/bin/docker')]
            for candidate in candidates:
                if candidate.is_file(): os.environ['PATH']=str(candidate.parent)+os.pathsep+os.environ.get('PATH',''); break
        if not shutil.which('docker'):
            raise RuntimeError('Docker is not installed on this host. Install Docker Desktop, open it, then choose Try again. On an iPad, use a Codespace as the host.')
        run(['docker','compose','version'])
        try: run(['docker','info','--format','{{.ServerVersion}}'],timeout=20)
        except Exception:
            if os.name=='nt':
                app=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Docker/Docker/Docker Desktop.exe'
                if app.exists(): subprocess.Popen([str(app)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            elif os.uname().sysname=='Darwin': subprocess.run(['open','-a','Docker'],capture_output=True)
            elif os.environ.get('CODESPACE_NAME'): subprocess.run(['sudo','-n','service','docker','start'],capture_output=True,timeout=30)
            else: raise RuntimeError('Docker is installed but is not running. Start it on this host, then choose Try again.')
            update('working',0,'Waiting for Docker to open…')
            for _ in range(40):
                probe=subprocess.run(['docker','info','--format','{{.ServerVersion}}'],capture_output=True,timeout=5)
                if probe.returncode==0: break
                time.sleep(3)
            else: raise RuntimeError('Docker is still starting. Once it is open, choose Try again.')
        update('working',1,'Preparing your private workspace…')
        recover_existing_workspace()
        run([os.sys.executable,'setup.py'])
        image=subprocess.run(['docker','image','inspect','locked-study-editor:local'],capture_output=True,cwd=ROOT)
        if image.returncode:
            update('working',2,'Installing your coding tools. The first launch takes a few minutes…')
            run(['docker','compose','build','editor'],timeout=1800)
        update('working',3,'Starting Python and MySQL…')
        run(['docker','compose','up','-d','--wait','--wait-timeout','180'],timeout=240)
        update('working',4,'Checking the database and editor…')
        run([os.sys.executable,'verify.py'])
        auth_cookie('localhost:8787')
        update('ready',5,'Your workspace is ready.')
    except Exception as e:
        message=str(e) if isinstance(e,RuntimeError) else 'Setup did not finish. Check the details and try again.'
        with LOCK: STATE['details'].append(redact(str(e)))
        update('error',STATE['step'],message,error=message)

def app_port(): return int(values().get('STUDY_PORT','8080'))

def auth_cookie(host):
    global COOKIE,COOKIE_FINGERPRINT
    with AUTH_LOCK:
        fingerprint=hashlib.sha256(values()['EDITOR_PASSWORD'].encode()).digest()
        if COOKIE and COOKIE_FINGERPRINT==fingerprint: return COOKIE
        from urllib.parse import urlencode
        conn=http.client.HTTPConnection('127.0.0.1',app_port(),timeout=15)
        conn.request('POST','/login',body=urlencode({'password':values()['EDITOR_PASSWORD'],'base':'/','href':'http://'+host+'/login'}),headers={'Content-Type':'application/x-www-form-urlencoded','Host':host})
        response=conn.getresponse(); response.read()
        jar=SimpleCookie()
        for name,value in response.getheaders():
            if name.lower()=='set-cookie': jar.load(value)
        conn.close()
        COOKIE='; '.join(f'{item.key}={item.value}' for item in jar.values())
        if response.status not in (200,302,303) or not COOKIE: raise RuntimeError('The editor is still finishing startup. Return to setup and retry.')
        COOKIE_FINGERPRINT=fingerprint
        return COOKIE

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    rbufsize=0
    def read_body(self,size):
        result=bytearray()
        while len(result)<size:
            part=self.rfile.read(size-len(result))
            if not part: raise ConnectionResetError('Incomplete request')
            result.extend(part)
        return bytes(result)
    def log_message(self,*args): pass
    def valid_host(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        return host in {'127.0.0.1','localhost',self.server.remote_host}
    def send(self,status,body,ctype='application/json'):
        data=body.encode() if isinstance(body,str) else body
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def do_DELETE(self): self.handle_request()
    def do_HEAD(self): self.handle_request()
    def handle_request(self):
        if not self.valid_host(): self.send(403,'{"error":"Unrecognized host"}'); return
        path=urlparse(self.path).path
        if path.startswith('/__study'):
            if path=='/__study/api/status' and self.command=='GET':
                with LOCK: data={**STATE,'codespaces':bool(os.environ.get('CODESPACE_NAME'))}
                self.send(200,json.dumps(data)); return
            if path=='/__study/api/start' and self.command=='POST':
                origin=self.headers.get('Origin','')
                if self.headers.get('X-Study-Token')!=TOKEN or (origin and urlparse(origin).netloc!=self.headers['Host']):
                    self.send(403,'{"error":"Refresh the setup page and try again"}'); return
                length=int(self.headers.get('Content-Length','0'))
                if length>2048: self.send(413,'{}'); return
                self.read_body(length); start_job(); self.send(202,'{"ok":true}'); return
            if path in {'/__study','/__study/'}:
                html=(ROOT/'launcher/index.html').read_text().replace('/*__CONTEXT__*/',json.dumps({'mode':'launcher','token':TOKEN}))
                self.send(200,html,'text/html; charset=utf-8'); return
            self.send(404,'{}'); return
        if STATE['phase']!='ready':
            self.send_response(302); self.send_header('Location','/__study/'); self.send_header('Content-Length','0'); self.end_headers(); return
        try: self.proxy()
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e:
            with LOCK: STATE['details'].append(redact(str(e)))
            update('error',4,'The workspace disconnected. Choose Try again to resume it.')
            self.send(502,'The workspace is reconnecting. <a href="/__study/">Return to setup</a>.','text/html; charset=utf-8')
    def proxy(self):
        host=self.headers['Host']; cookie=auth_cookie(host)
        headers={k:v for k,v in self.headers.items() if k.lower() not in {'connection','transfer-encoding','content-length','cookie','accept-encoding'}}
        headers['Cookie']=cookie
        if self.headers.get('Upgrade','').lower()=='websocket':
            upstream=socket.create_connection(('127.0.0.1',app_port()),timeout=15)
            headers['Connection']='Upgrade'
            request=f'{self.command} {self.path} HTTP/1.1\r\n'+''.join(f'{k}: {v}\r\n' for k,v in headers.items())+'\r\n'
            upstream.sendall(request.encode('latin-1'))
            received=b''
            while b'\r\n\r\n' not in received:
                data=upstream.recv(65536)
                if not data: raise RuntimeError('Editor connection closed')
                received+=data
                if len(received)>131072: raise RuntimeError('Invalid upgrade response')
            self.connection.sendall(received)
            if not received.startswith(b'HTTP/1.1 101'): upstream.close(); self.close_connection=True; return
            upstream.settimeout(None); self.connection.settimeout(None)
            try:
                while True:
                    ready,_,_=select.select([self.connection,upstream],[],[],30)
                    if not ready: continue
                    for source in ready:
                        block=source.recv(65536)
                        if not block: return
                        (upstream if source is self.connection else self.connection).sendall(block)
            finally: upstream.close(); self.close_connection=True
        else:
            size=int(self.headers.get('Content-Length','0'))
            if size>MAX_BODY: self.send(413,'File too large','text/plain'); return
            body=self.read_body(size) if size else None
            conn=http.client.HTTPConnection('127.0.0.1',app_port(),timeout=60)
            conn.request(self.command,self.path,body=body,headers=headers)
            response=conn.getresponse(); data=response.read()
            self.send_response(response.status)
            for key,value in response.getheaders():
                if key.lower() not in {'connection','transfer-encoding','content-length','set-cookie'}: self.send_header(key,value)
            self.send_header('Content-Length',response.getheader('Content-Length','0') if self.command=='HEAD' else str(len(data))); self.end_headers()
            if self.command!='HEAD': self.wfile.write(data)
            conn.close()

def main():
    parser=argparse.ArgumentParser(description='Open the guided Study Desk launcher')
    parser.add_argument('--no-browser',action='store_true'); parser.add_argument('--port',type=int,default=8787)
    parser.add_argument('--no-auto-start',action='store_true')
    args=parser.parse_args()
    name=os.environ.get('CODESPACE_NAME',''); domain=os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')
    remote_host=(name+'-'+str(args.port)+'.'+domain).lower() if name and re.fullmatch(r'[a-zA-Z0-9.-]+',domain) else ''
    address='https://'+remote_host if remote_host else f'http://localhost:{args.port}'
    try:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.daemon_threads=True
    except OSError:
        import urllib.request
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/__study/api/status',timeout=3) as response:
                existing=json.loads(response.read())
                if 'phase' not in existing: raise ValueError()
        except Exception:
            raise SystemExit('This port is already in use. Run with --port followed by another number.')
        print('Study Desk is already open: '+address+'/__study/',flush=True)
        if not args.no_browser and not name: webbrowser.open(address+'/__study/')
        return
    server.remote_host=remote_host
    print('\nOpen Study Desk: '+address+'/__study/\nKeep this launcher running while you work.',flush=True)
    if not args.no_auto_start: start_job()
    if not args.no_browser and not name: threading.Timer(.6,lambda:webbrowser.open(address+'/__study/')).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
