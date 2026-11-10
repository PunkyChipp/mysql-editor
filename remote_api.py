"""Authenticated home origin. Only the edge Worker may reach its JSON API.

This server never exposes the launcher's automatic code-server sign-in proxy.
It binds to loopback; cloudflared connects locally using an outbound tunnel.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from urllib.parse import urlparse
import urllib.request

from desk_api import DeskError, SERVICE
from home_paths import DATA

ROOT=Path(__file__).resolve().parent
COOKIE='__Secure-study_desk'
ITERATIONS=600000
SESSION_SECONDS=8*60*60
MAX_BODY=1200000
HEALTH_LOCK=threading.RLock()
HEALTH_CACHE={'at':0,'value':None}


def password_record(password):
    if not isinstance(password,str) or not 12<=len(password)<=256:
        raise ValueError('Choose a password between 12 and 256 characters.')
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    return {'salt':salt,'digest':digest,'iterations':ITERATIONS}


def check_password(password,record):
    if not isinstance(password,str) or len(password)>256:
        password=''
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(record['salt']),record['iterations']).hex()
    return hmac.compare_digest(digest,record['digest'])


def write_private(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write(json.dumps(value,indent=2) if not isinstance(value,str) else value)
    temporary.replace(path)


def _runtime_probe():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8787/__study/api/status',timeout=2) as response:
            result=json.load(response)
        state={k:result.get(k) for k in ('phase','step','message')}
        if state['phase']=='ready':
            check=subprocess.run(['docker','compose','ps','--format','json'],cwd=ROOT,capture_output=True,text=True,timeout=4)
            text=check.stdout.strip()
            rows=json.loads(text) if text.startswith('[') else [json.loads(line) for line in text.splitlines() if line]
            services={row.get('Service'):row for row in rows}
            if check.returncode or any(services.get(name,{}).get('State')!='running' or services.get(name,{}).get('Health')!='healthy' for name in ['editor','db']):
                state={'phase':'offline','step':3,'message':'The coding runtime is not healthy. Keep Docker Desktop running; the home launcher will retry.'}
        return state
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {'phase':'offline','step':0,'message':'The home runtime is not running yet.'}


def runtime_status():
    with HEALTH_LOCK:
        if HEALTH_CACHE['value'] is not None and time.monotonic()-HEALTH_CACHE['at']<1:
            return dict(HEALTH_CACHE['value'])
        state=_runtime_probe()
        HEALTH_CACHE.update(at=time.monotonic(),value=state)
        return dict(state)


class RemoteApp:
    def __init__(self,config,service=SERVICE,status=runtime_status,clock=time.time):
        self.config=config;self.service=service;self.runtime_status=status;self.clock=clock
        parsed=urlparse(config['publicOrigin'])
        self.secure=parsed.scheme=='https'
        if (not self.secure and not (parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost'})) or parsed.path not in {'','/'}:
            raise ValueError('The public origin must use HTTPS (loopback HTTP is only for local tests).')
        if len(config['originKey'])<32:
            raise ValueError('The origin key must have at least 32 characters.')
        self.cookie=COOKIE if self.secure else 'study_desk_local_test'
        self.sessions={};self.failures=defaultdict(deque);self.lock=threading.RLock()
        self.login_slots=threading.BoundedSemaphore(3)

    def session(self,cookie):
        jar=SimpleCookie()
        try: jar.load(cookie)
        except Exception: return None
        value=jar.get(self.cookie)
        if not value:return None
        key=hashlib.sha256(value.value.encode()).hexdigest()
        with self.lock:
            session=self.sessions.get(key)
            if not session or session['expires']<=self.clock():
                self.sessions.pop(key,None);return None
            return key,session

    def login(self,username,password,client):
        now=self.clock();bucket=hashlib.sha256((client+'|'+str(username)[:80]).encode()).hexdigest()
        with self.lock:
            # Bound accounting memory as well as attempts for one client/name.
            if len(self.failures)>5000:
                self.failures=defaultdict(deque,{'global':self.failures['global']})
            for key,limit in [(bucket,6),('global',40)]:
                queue=self.failures[key]
                while queue and queue[0]<now-900:queue.popleft()
                if len(queue)>=limit:raise DeskError('Too many sign-in attempts. Wait 15 minutes and try again.',429)
                queue.append(now)
        if not self.login_slots.acquire(blocking=False):raise DeskError('Sign-in is busy. Try again shortly.',429)
        try:
            valid=check_password(password,self.config['password'])
            valid=hmac.compare_digest(str(username).encode(),self.config['username'].encode()) and valid
        finally:self.login_slots.release()
        if not valid:raise DeskError('The username or password is incorrect.',401)
        token=secrets.token_urlsafe(32);key=hashlib.sha256(token.encode()).hexdigest()
        session={'username':self.config['username'],'csrf':secrets.token_urlsafe(32),'expires':now+SESSION_SECONDS}
        with self.lock:
            self.failures.pop(bucket,None)
            self.sessions={k:v for k,v in self.sessions.items() if v['expires']>now}
            if len(self.sessions)>=100:self.sessions.pop(next(iter(self.sessions)))
            self.sessions[key]=session
        return token,session

    def cookie_header(self,token,max_age=SESSION_SECONDS):
        return f'{self.cookie}={token}; Path={self.config["apiPath"]}; HttpOnly; SameSite=Strict; Max-Age={max_age}'+('; Secure' if self.secure else '')


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.settimeout(20)
    def log_message(self,*args):pass
    def send_json(self,status,payload,cookie=None):
        body=json.dumps(payload,default=str).encode()
        self.send_response(status)
        for key,value in {'Content-Type':'application/json; charset=utf-8','Content-Length':str(len(body)),
                'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}.items():
            self.send_header(key,value)
        if cookie:self.send_header('Set-Cookie',cookie)
        if status==429:self.send_header('Retry-After','900')
        if status>=400:self.send_header('Connection','close');self.close_connection=True
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.handle_api()
    def do_POST(self):self.handle_api()
    def do_OPTIONS(self):self.send_json(405,{'error':'This API uses same-origin HTTPS requests only.'})
    def handle_api(self):
        app=self.server.app
        key=self.headers.get('X-Study-Origin-Key','')
        if not hmac.compare_digest(key.encode(),app.config['originKey'].encode()):
            self.send_json(403,{'error':'Access denied.'});return
        path=urlparse(self.path).path
        action=path.removeprefix('/api/')
        methods={'health':'GET','session':'GET','login':'POST','logout':'POST','call':'POST','run':'POST','job':'POST','stop':'POST'}
        if not path.startswith('/api/') or action not in methods:self.send_json(404,{'error':'Not found.'});return
        if self.command!=methods[action]:self.send_json(405,{'error':'Method not allowed.'});return
        try:
            if self.command=='POST':
                if self.headers.get('Origin')!=app.config['publicOrigin'] or self.headers.get('Sec-Fetch-Site','same-origin')=='cross-site':
                    raise DeskError('Open the editor on its own website and try again.',403)
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise DeskError('Send JSON.',415)
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=MAX_BODY:raise DeskError('Request too large or incomplete.',413)
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise DeskError('Send a JSON object.')
            else:data={}
            if action=='health':
                state=app.runtime_status()
                self.send_json(200,{'route':'connected','home':'online','ready':state['phase']=='ready','runtime':state});return
            if action=='login':
                token,session=app.login(data.get('username',''),data.get('password',''),self.headers.get('X-Study-Client-IP','unknown'))
                self.send_json(200,{'username':session['username'],'csrf':session['csrf']},app.cookie_header(token));return
            session=app.session(self.headers.get('Cookie',''))
            if not session:raise DeskError('Sign in to your workspace.',401)
            sid,current=session
            if action=='session':
                self.send_json(200,{'username':current['username'],'csrf':current['csrf']});return
            if not hmac.compare_digest(self.headers.get('X-Study-CSRF','').encode(),current['csrf'].encode()):
                raise DeskError('Refresh the editor and sign in again.',403)
            if action=='logout':
                with app.lock:app.sessions.pop(sid,None)
                self.send_json(200,{'signedOut':True},app.cookie_header('',0));return
            state=app.runtime_status()
            if state['phase']!='ready':raise DeskError('The home runtime is starting. Wait for setup to finish.',503)
            if action=='run':result=app.service.start(data)
            elif action=='job':result=app.service.status(data.get('id'))
            elif action=='stop':result=app.service.cancel(data.get('id'))
            elif action=='call' and data.get('op') in {'bootstrap','schema','table','update','files','read','save','state'}:
                result=app.service.call(data)
            else:raise DeskError('Unknown workspace operation.',404)
            self.send_json(200,result)
        except DeskError as exc:self.send_json(exc.status,{'error':str(exc)})
        except (ValueError,TypeError,KeyError):self.send_json(400,{'error':'The request was incomplete.'})
        except Exception:self.send_json(503,{'error':'The home runtime could not complete this request. Try again.'})


def make_server(config,port=8791,service=SERVICE,status=runtime_status):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True;server.app=RemoteApp(config,service,status)
    return server


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=DATA/'config.json');parser.add_argument('--port',type=int,default=8791)
    args=parser.parse_args();config=json.loads(args.config.read_text())
    server=make_server(config,args.port)
    print('Study Desk authenticated origin is running on loopback.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
