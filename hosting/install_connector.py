"""Install an official portable cloudflared release, checking GitHub's SHA-256."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import tarfile
import urllib.request


def install(directory,progress=lambda message:None,transport=urllib.request.urlopen):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    target=directory/('cloudflared.exe' if os.name=='nt' else 'cloudflared')
    if target.exists():return target
    arm=platform.machine().lower() in {'arm64','aarch64'}
    if os.name=='nt':asset='cloudflared-windows-amd64.exe'
    elif platform.system()=='Darwin':asset='cloudflared-darwin-'+('arm64' if arm else 'amd64')+'.tgz'
    else:asset='cloudflared-linux-'+('arm64' if arm else 'amd64')
    progress('Downloading the official tunnel connector…')
    req=urllib.request.Request('https://api.github.com/repos/cloudflare/cloudflared/releases/latest',headers={'User-Agent':'StudyDeskHome/1.0'})
    with transport(req,timeout=30) as response:release=json.load(response)
    info=next((a for a in release['assets'] if a['name']==asset),None)
    digest=info.get('digest','') if info else ''
    if not digest.startswith('sha256:'):
        raise RuntimeError('The official release did not supply a SHA-256 checksum. Install cloudflared from its official website and retry; no unverified file was executed.')
    url=info['browser_download_url']
    if not url.startswith('https://github.com/cloudflare/cloudflared/releases/download/'):
        raise RuntimeError('The connector download did not use the official release location.')
    temporary=target.with_suffix('.download');hasher=hashlib.sha256();size=0
    try:
        with transport(urllib.request.Request(url,headers={'User-Agent':'StudyDeskHome/1.0'}),timeout=120) as response,temporary.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>200*1024*1024:raise RuntimeError('Connector download exceeded its size limit.')
                hasher.update(chunk);output.write(chunk)
        if not hmac.compare_digest(hasher.hexdigest(),digest.split(':',1)[1]):
            raise RuntimeError('Connector checksum did not match. It has not been installed.')
        if asset.endswith('.tgz'):
            with tarfile.open(temporary) as archive:
                member=next((m for m in archive.getmembers() if m.name.rstrip('/').split('/')[-1]=='cloudflared' and m.isfile()),None)
                if not member or member.size>200*1024*1024:raise RuntimeError('The connector archive was unexpected.')
                with archive.extractfile(member) as stream:target.write_bytes(stream.read())
        else:temporary.replace(target)
        target.chmod(0o700)
        progress('Tunnel connector checksum verified.')
        return target
    finally:temporary.unlink(missing_ok=True)
