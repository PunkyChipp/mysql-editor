import http.client
import io
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from remote_api import make_server,password_record,RemoteApp
from remote_api import _runtime_probe


class Service:
    def __init__(self):self.calls=[]
    def call(self,data):self.calls.append(data);return {'database':'schoolwork','tables':[],'files':[]}
    def start(self,data):self.calls.append(data);return {'id':'run-1'}
    def status(self,identifier):return {'id':identifier,'state':'done','result':{'results':[]}}
    def cancel(self,identifier):return {'id':identifier,'state':'stopping'}


class RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.record=password_record('a-unique-test-password')
    def setUp(self):
        self.service=Service()
        self.config={'publicOrigin':'https://highereconomicsrevision.co.uk','apiPath':'/mysql-editor/api/',
                     'username':'owner','password':self.record,'originKey':secrets.token_urlsafe(48)}
        self.server=make_server(self.config,port=0,service=self.service,
                               status=lambda:{'phase':'ready','step':5,'message':'Ready'})
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.cookie='';self.csrf=''
    def tearDown(self):self.server.shutdown();self.server.server_close()
    def request(self,action,data=None,headers=None,origin_key=True):
        client=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        supplied={'Origin':self.config['publicOrigin']}
        if origin_key:supplied['X-Study-Origin-Key']=self.config['originKey']
        if self.cookie:supplied['Cookie']=self.cookie
        if self.csrf:supplied['X-Study-CSRF']=self.csrf
        if data is not None:supplied['Content-Type']='application/json'
        supplied.update(headers or {})
        client.request('GET' if data is None else 'POST','/api/'+action,
                       body=None if data is None else json.dumps(data),headers=supplied)
        response=client.getresponse();status=response.status;out=dict(response.getheaders());payload=json.loads(response.read());client.close()
        return status,payload,out
    def login(self):
        status,data,headers=self.request('login',{'username':'owner','password':'a-unique-test-password'})
        self.assertEqual(status,200)
        self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=data['csrf'];return headers
    def test_origin_secret_is_required_even_for_health(self):
        status,_,_=self.request('health',origin_key=False)
        self.assertEqual(status,403)
        self.assertEqual(self.request('health')[0],200)
        self.assertEqual(self.service.calls,[])
    def test_passwords_are_hashed_and_auth_cookie_is_scoped_secure_and_http_only(self):
        self.assertNotIn('a-unique-test-password',json.dumps(self.record))
        headers=self.login();cookie=headers['Set-Cookie']
        for attribute in ['Secure','HttpOnly','SameSite=Strict','Path=/mysql-editor/api/']:
            self.assertIn(attribute,cookie)
        self.assertNotIn('password',json.dumps(self.request('session')[1]))
    def test_unauthenticated_and_forged_requests_never_execute(self):
        self.assertEqual(self.request('call',{'op':'schema'})[0],401)
        self.login();self.csrf='invalid'
        self.assertEqual(self.request('run',{'op':'execute','sql':'SELECT 1'})[0],403)
        self.assertEqual(self.service.calls,[])
    def test_cross_site_and_unknown_operations_are_rejected(self):
        self.login()
        self.assertEqual(self.request('call',{'op':'schema'},headers={'Origin':'https://other.example'})[0],403)
        self.assertEqual(self.request('call',{'op':'kill','connectionId':1})[0],404)
        self.assertEqual(self.service.calls,[])
    def test_authenticated_api_and_logout(self):
        self.login()
        self.assertEqual(self.request('call',{'op':'schema'})[0],200)
        self.assertEqual(self.request('run',{'op':'execute','sql':'SELECT 1'})[1]['id'],'run-1')
        self.assertEqual(self.request('job',{'id':'run-1'})[1]['state'],'done')
        self.assertEqual(self.request('stop',{'id':'run-1'})[0],200)
        self.assertEqual(self.request('logout',{})[0],200)
        self.assertEqual(self.request('call',{'op':'schema'})[0],401)
    def test_expired_session_is_invalid(self):
        self.login();self.server.app.clock=lambda:10**12
        self.assertEqual(self.request('session')[0],401)
    def test_failed_logins_are_rate_limited(self):
        for _ in range(6):self.assertEqual(self.request('login',{'username':'owner','password':'wrong'})[0],401)
        self.assertEqual(self.request('login',{'username':'owner','password':'wrong'})[0],429)
    def test_remote_backend_never_exposes_the_auto_login_editor_proxy(self):
        self.login()
        self.assertEqual(self.request('../desk/')[0],404)
        self.assertEqual(self.request('login',{},headers={'Content-Type':'text/plain'})[0],415)
    def test_not_ready_runtime_does_not_run_sql(self):
        self.login();self.server.app.runtime_status=lambda:{'phase':'working','message':'Starting','step':2}
        self.assertFalse(self.request('health')[1]['ready'])
        self.assertEqual(self.request('run',{'op':'execute','sql':'SELECT 1'})[0],503)
        self.assertEqual(self.service.calls,[])
    def test_runtime_health_rechecks_docker_instead_of_trusting_old_boot_state(self):
        ready=json.dumps({'phase':'ready','step':5,'message':'Ready'}).encode()
        containers=[{'Service':'editor','State':'running','Health':'healthy'},
                    {'Service':'db','State':'running','Health':'healthy'}]
        with patch('remote_api.urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(ready)),patch('remote_api.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(containers))):
            self.assertEqual(_runtime_probe()['phase'],'ready')
            containers[1]['Health']='unhealthy'
        with patch('remote_api.urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(ready)),patch('remote_api.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(containers))):
            self.assertEqual(_runtime_probe()['phase'],'offline')


if __name__=='__main__':unittest.main()
