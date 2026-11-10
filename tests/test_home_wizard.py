import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import home_setup as wizard


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name)
        self.server=wizard.ThreadingHTTPServer(('127.0.0.1',0),wizard.Handler)
        self.patches=[patch.object(wizard,'HOME',self.home),patch.object(wizard,'CONFIG',self.home/'config.json'),
            patch.object(wizard,'PORT',self.server.server_port),patch.object(wizard,'start_runner'),patch.object(wizard,'startup'),
            patch.object(wizard,'runtime_status',return_value={'phase':'idle','step':0,'message':'Not started'})]
        for p in self.patches:p.start()
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def request(self,path,data=None,token=True):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Origin':'http://127.0.0.1:'+str(self.server.server_port)}
        if token:headers['X-Setup-Token']=wizard.TOKEN
        c.request('GET' if data is None else 'POST',path,None if data is None else json.dumps(data),headers)
        r=c.getresponse();status=r.status;body=r.read();c.close();return status,body
    def test_account_secret_is_hashed_and_status_does_not_expose_it(self):
        status,_=self.request('/account',{'username':'owner','password':'a-local-owner-password','autoStart':True,'keepAwake':True})
        self.assertEqual(status,200)
        config=json.loads((self.home/'config.json').read_text())
        self.assertNotIn('a-local-owner-password',json.dumps(config));self.assertTrue(config['keepAwake'])
        status,body=self.request('/status')
        self.assertEqual(status,200)
        self.assertNotIn(config['originKey'].encode(),body)
        self.assertNotIn(config['password']['digest'].encode(),body)
        wizard.start_runner.assert_called_once();wizard.startup.assert_called_once_with(True)
    def test_configuration_mutations_require_local_token_and_review(self):
        self.assertEqual(self.request('/account',{'username':'owner','password':'a-local-owner-password'},token=False)[0],403)
        self.assertFalse((self.home/'config.json').exists())
        self.request('/account',{'username':'owner','password':'a-local-owner-password'})
        self.assertEqual(self.request('/connect',{'token':'a-token-that-will-never-be-used','confirmed':False})[0],400)
    def test_wizard_is_the_local_setup_ui(self):
        status,body=self.request('/')
        self.assertEqual(status,200);self.assertIn(b'LOCAL SETUP',body)
        self.assertIn(b'Create your sign-in',body);self.assertIn(b'Connect your domain',body)


if __name__=='__main__':unittest.main()
