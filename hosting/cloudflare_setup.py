"""Owner-run Cloudflare setup. The API token stays in memory on the home PC."""
import hashlib
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.parse
import urllib.request

from remote_api import write_private

ROOT=Path(__file__).resolve().parents[1]
DOMAIN='highereconomicsrevision.co.uk'
API_PATH='/mysql-editor/api/*'
MARKER='Study Desk managed gateway v1'


class CloudflareError(RuntimeError):pass


class Cloudflare:
    def __init__(self,token,transport=urllib.request.urlopen):
        self.token=token;self.transport=transport
    def request(self,method,path,payload=None,raw=None,content_type=None,missing_ok=False):
        headers={'Authorization':'Bearer '+self.token,'User-Agent':'StudyDeskHome/1.0'}
        if raw is not None:
            data=raw;headers['Content-Type']=content_type
        elif payload is not None:
            data=json.dumps(payload).encode();headers['Content-Type']='application/json'
        else:data=None
        req=urllib.request.Request('https://api.cloudflare.com/client/v4'+path,data=data,headers=headers,method=method)
        try:
            with self.transport(req,timeout=40) as response:
                content=response.read();kind=response.headers.get('Content-Type','')
        except urllib.error.HTTPError as exc:
            if exc.code==404 and missing_ok:return None
            if exc.code in {401,403}:raise CloudflareError('The Cloudflare token needs the account/zone permissions listed in the setup guide.')
            raise CloudflareError('Cloudflare could not complete this step (HTTP '+str(exc.code)+'). Your token was not saved.') from None
        if 'application/json' not in kind:return content.decode(errors='replace')
        result=json.loads(content)
        if not result.get('success',False):
            raise CloudflareError('Cloudflare rejected this step. Check the zone status and token permissions in your dashboard.')
        return result.get('result')

    def upload_worker(self,account,name,origin,origin_key):
        code=(ROOT/'hosting/worker.mjs').read_text(encoding='utf-8')
        existing=self.request('GET',f'/accounts/{account}/workers/scripts/{name}',missing_ok=True)
        if existing is not None and MARKER not in str(existing):
            raise CloudflareError('A different Worker already uses the generated name. It has not been overwritten.')
        metadata={'main_module':'worker.mjs','compatibility_date':'2026-11-01',
                  'bindings':[{'type':'plain_text','name':'ORIGIN_URL','text':origin},
                              {'type':'secret_text','name':'STUDY_ORIGIN_KEY','text':origin_key}]}
        boundary='StudyDesk'+secrets.token_hex(16)
        parts=[]
        for name_part,content,kind,filename in [
                ('metadata',json.dumps(metadata),'application/json',None),
                ('worker.mjs',code,'application/javascript+module','worker.mjs')]:
            disposition=f'Content-Disposition: form-data; name="{name_part}"'+(f'; filename="{filename}"' if filename else '')
            parts.append(f'--{boundary}\r\n{disposition}\r\nContent-Type: {kind}\r\n\r\n{content}\r\n')
        body=(''.join(parts)+f'--{boundary}--\r\n').encode()
        self.request('PUT',f'/accounts/{account}/workers/scripts/{name}',raw=body,content_type='multipart/form-data; boundary='+boundary)


def provision(token,config_path,progress=lambda message:None,client=None):
    config_path=Path(config_path);config=json.loads(config_path.read_text())
    client=client or Cloudflare(token)
    progress('Checking that your existing domain is active on Cloudflare…')
    zones=client.request('GET','/zones?name='+urllib.parse.quote(DOMAIN)+'&per_page=50')
    zone=next((z for z in zones if z['name']==DOMAIN),None)
    if not zone or zone.get('status')!='active':
        raise CloudflareError('First add highereconomicsrevision.co.uk to Cloudflare, import all existing DNS records, and activate its nameservers at your registrar. The existing economics website must keep its GitHub Pages records. No DNS has been changed by this setup.')
    account=zone['account']['id'];zid=zone['id']
    suffix=hashlib.sha256(DOMAIN.encode()).hexdigest()[:8]
    worker_name='study-desk-'+suffix
    origin_host='study-desk-origin.'+DOMAIN
    cf=config.setdefault('cloudflare',{})
    if cf.get('accountId') and cf['accountId']!=account:
        raise CloudflareError('This installation belongs to another Cloudflare account. Reconnect from that account.')
    # Check collisions before changing any existing resources.
    records=client.request('GET',f'/zones/{zid}/dns_records?name={origin_host}&per_page=100')
    routes=client.request('GET',f'/zones/{zid}/workers/routes')
    route=next((r for r in routes if r['pattern']==DOMAIN+API_PATH),None)
    if route and route.get('script') not in {worker_name,None}:
        raise CloudflareError('Another Worker already handles the editor API path. That route has not been changed.')
    if records and not cf.get('tunnelId'):
        raise CloudflareError('The origin hostname already exists. It has not been changed. Use the original installation configuration.')
    roots=client.request('GET',f'/zones/{zid}/dns_records?name={DOMAIN}&per_page=100')
    web_records=[r for r in roots if r['type'] in {'A','AAAA','CNAME'}]
    if not web_records:raise CloudflareError('No existing website DNS record was found. Import the current GitHub Pages DNS records first.')
    progress('Creating the outbound home tunnel…')
    if not cf.get('tunnelId'):
        tunnel=client.request('POST',f'/accounts/{account}/cfd_tunnel',{'name':worker_name,'config_src':'cloudflare'})
        cf.update({'accountId':account,'zoneId':zid,'tunnelId':tunnel['id'],'workerName':worker_name,'originHost':origin_host})
        write_private(config_path,config)
    tid=cf['tunnelId']
    target=tid+'.cfargotunnel.com'
    if records and any(r['type']!='CNAME' or r['content'].rstrip('.')!=target for r in records):
        raise CloudflareError('The origin DNS record points somewhere else. It has not been overwritten.')
    client.request('PUT',f'/accounts/{account}/cfd_tunnel/{tid}/configurations',{'config':{'ingress':[
        {'hostname':origin_host,'service':'http://127.0.0.1:8791'}, {'service':'http_status:404'}]}})
    tunnel_token=client.request('GET',f'/accounts/{account}/cfd_tunnel/{tid}/token')
    if not isinstance(tunnel_token,str) or len(tunnel_token)<30:
        raise CloudflareError('Cloudflare returned an unexpected tunnel credential. No unverified connector was started.')
    write_private(config_path.parent/'tunnel-token',tunnel_token)
    if not records:client.request('POST',f'/zones/{zid}/dns_records',{'type':'CNAME','name':origin_host,'content':target,'proxied':True,'ttl':1})
    elif not records[0].get('proxied'):
        client.request('PATCH',f'/zones/{zid}/dns_records/{records[0]["id"]}',{'proxied':True})
    progress('Installing the same-origin API gateway…')
    client.upload_worker(account,worker_name,'https://'+origin_host,config['originKey'])
    if not route:client.request('POST',f'/zones/{zid}/workers/routes',{'pattern':DOMAIN+API_PATH,'script':worker_name})
    elif route.get('script')!=worker_name:
        client.request('PUT',f'/zones/{zid}/workers/routes/{route["id"]}',{'pattern':DOMAIN+API_PATH,'script':worker_name})
    # Preserve content, TTL and every non-web record. Enable proxying only on
    # the existing website record so the narrow Worker route can be applied.
    for record in web_records:
        if not record.get('proxied'):
            client.request('PATCH',f'/zones/{zid}/dns_records/{record["id"]}',{'proxied':True})
    cf['configured']=True;write_private(config_path,config)
    progress('Website routing is configured. Starting the local tunnel connector…')
    return {'originHost':origin_host,'workerName':worker_name,'website':'https://'+DOMAIN+'/mysql-editor/'}
