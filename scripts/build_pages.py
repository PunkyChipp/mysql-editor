"""Publish the actual editor at the Pages project path, with a same-origin API."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_home_package import build as build_home
def build(repository,output):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]+',repository) or repository.split('/')[1] in {'.','..'}:
        raise ValueError('Use OWNER/REPOSITORY form')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    template=(ROOT/'desk/index.html').read_text()
    template=template.replace('href="/desk/"','href="./"').replace('href="/desk/style.css"','href="./style.css"').replace('src="/desk/assets/app.js"','src="./assets/app.js"')
    inline='<script nonce="__NONCE__">window.STUDY_CONTEXT=/*__CONTEXT__*/;</script>'
    assert template.count(inline)==1
    template=template.replace(inline,'<script src="./config.js"></script>')
    template=template.replace('<a href="/?folder=/home/coder/coursework"','<a hidden href="#"')
    policy="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'"
    template=template.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+policy+'">',1)
    (output/'index.html').write_text(template)
    standalone=(ROOT/'launcher/browser.html').read_text().replace('__ADDRESS__','https://highereconomicsrevision.co.uk/mysql-editor/')
    standalone=standalone.replace('This is a Codespaces preview.', 'This page is embedded in another window.')
    (output/'standalone.html').write_text(standalone)
    config='window.STUDY_CONTEXT='+json.dumps({'mode':'remote','apiBase':'./api/','repository':repository})+';\n'
    config+="if(location.protocol==='http:'&&!['127.0.0.1','localhost'].includes(location.hostname)){window.STUDY_CONTEXT.redirecting=true;location.replace('https://'+location.host+location.pathname+location.search+location.hash);}\n"
    (output/'config.js').write_text(config)
    shutil.copyfile(ROOT/'desk/style.css',output/'style.css')
    (output/'assets').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'desk/assets/app.js',output/'assets/app.js')
    shutil.copyfile(ROOT/'desk/THIRD_PARTY_NOTICES.txt',output/'THIRD_PARTY_NOTICES.txt')
    (output/'setup').mkdir(exist_ok=True)
    (output/'setup/index.html').write_text((ROOT/'hosting/setup.html').read_text())
    (output/'.nojekyll').write_text('')
    build_home(output/'downloads/study-desk-home-windows.zip')
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--output',type=Path,default=ROOT/'dist');a=p.parse_args()
    try: result=build(a.repository,a.output)
    except ValueError as e: p.error(str(e))
    print('Pages assets ready in',result)
