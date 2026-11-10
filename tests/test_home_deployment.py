import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hosting.cloudflare_setup import provision,CloudflareError,DOMAIN
from hosting.install_connector import install
from scripts.build_pages import build
from home_runner import retry_runtime


class FakeCloudflare:
    def __init__(self,active=True,conflict=False):self.calls=[];self.active=active;self.conflict=conflict
    def request(self,method,path,payload=None,**kwargs):
        self.calls.append((method,path,payload))
        if path.startswith('/zones?'):return [{'name':DOMAIN,'id':'zone','account':{'id':'account'},'status':'active' if self.active else 'pending'}]
        if '/dns_records?name=study-desk-origin.' in path:return []
        if '/dns_records?name='+DOMAIN in path:return [{'id':'root-a','type':'A','content':'185.199.108.153','proxied':False}]
        if path.endswith('/workers/routes') and method=='GET':return [{'id':'other','pattern':DOMAIN+'/mysql-editor/api/*','script':'unrelated'}] if self.conflict else []
        if path.endswith('/cfd_tunnel') and method=='POST':return {'id':'tunnel-id'}
        if path.endswith('/token'):return 'test-tunnel-credential-that-is-long-enough'
        return {}
    def upload_worker(self,*args):self.calls.append(('UPLOAD',args,None))


class DeploymentTests(unittest.TestCase):
    def config(self,folder):
        path=Path(folder)/'config.json';path.write_text(json.dumps({'originKey':'test-origin-key-very-long-and-private'}));return path
    def test_inactive_zone_and_conflicting_route_do_not_modify_dns_or_workers(self):
        for fake in [FakeCloudflare(active=False),FakeCloudflare(conflict=True)]:
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(CloudflareError):provision('private-api-token',self.config(folder),client=fake)
                self.assertTrue(all(method=='GET' for method,_,_ in fake.calls))
    def test_provisioning_only_adds_editor_origin_and_route_and_preserves_website_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            fake=FakeCloudflare();path=self.config(folder);provision('private-api-token',path,client=fake)
            changes=[x for x in fake.calls if x[0]!='GET']
            for method,url,payload in changes:
                if method=='PATCH' and '/dns_records/' in url:self.assertEqual(payload,{'proxied':True})
                if method=='POST' and url.endswith('/workers/routes'):self.assertEqual(payload['pattern'],DOMAIN+'/mysql-editor/api/*')
                if method=='POST' and url.endswith('/dns_records'):self.assertEqual(payload['name'],'study-desk-origin.'+DOMAIN)
            self.assertTrue(json.loads(path.read_text())['cloudflare']['configured'])
            self.assertNotIn('private-api-token',path.read_text())
            self.assertEqual((Path(folder)/'tunnel-token').read_text(),'test-tunnel-credential-that-is-long-enough')
    def test_pages_build_is_the_editor_with_relative_assets_and_no_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            output=build('PunkyChipp/mysql-editor',Path(folder)/'site')
            html=(output/'index.html').read_text()
            self.assertIn('id="editor"',html);self.assertIn('src="./assets/app.js"',html)
            self.assertNotIn('codespaces.new',html);self.assertNotIn('/*__CONTEXT__*/',html)
            self.assertNotIn('/__study/desk/',(output/'config.js').read_text())
            config=(output/'config.js').read_text()
            self.assertIn('"mode": "remote"',config);self.assertNotIn('originKey',config);self.assertNotIn('token',config)
            package=output/'downloads/study-desk-home-windows.zip'
            with zipfile.ZipFile(package) as archive:
                names=archive.namelist()
                self.assertIn('START STUDY DESK.cmd',names);self.assertIn('home_setup.py',names)
                self.assertFalse(any('.env' in Path(n).parts or '.home' in Path(n).parts or 'node_modules' in Path(n).parts for n in names))
    def test_connector_checksum_failure_never_installs_download(self):
        binary=b'not-a-real-connector'
        metadata={'assets':[{'name':'cloudflared-linux-amd64','digest':'sha256:'+'0'*64,
            'browser_download_url':'https://github.com/cloudflare/cloudflared/releases/download/test/cloudflared-linux-amd64'}]}
        def transport(request,**kwargs):return io.BytesIO(json.dumps(metadata).encode() if request.full_url.endswith('/latest') else binary)
        with tempfile.TemporaryDirectory() as folder,patch('hosting.install_connector.platform.machine',return_value='x86_64'),patch('hosting.install_connector.platform.system',return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError,'checksum'):
                install(folder,transport=transport)
            self.assertFalse((Path(folder)/'cloudflared').exists())
            self.assertFalse((Path(folder)/'cloudflared.download').exists())
    def test_failed_local_boot_is_retried_through_its_existing_token_check(self):
        replies=[json.dumps({'phase':'error'}).encode(),
                 b'<script>window.STUDY_CONTEXT={"mode":"launcher","token":"local-test-token"};</script>',b'{}']
        requests=[]
        def transport(request,**kwargs):
            requests.append(request);return io.BytesIO(replies.pop(0))
        with patch('home_runner.urllib.request.urlopen',side_effect=transport):retry_runtime()
        request=requests[-1]
        self.assertEqual(request.get_method(),'POST')
        self.assertEqual(request.get_header('X-study-token'),'local-test-token')
        self.assertEqual(request.get_header('Origin'),'http://127.0.0.1:8787')


if __name__=='__main__':unittest.main()
