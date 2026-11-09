"""Build Pages assets with the actual GitHub repository identity."""
import argparse
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def build(repository,output):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]+',repository) or repository.split('/')[1] in {'.','..'}:
        raise ValueError('Use OWNER/REPOSITORY form')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    template=(ROOT/'site/index.html').read_text()
    assert template.count('/*__REPOSITORY__*/')==1
    (output/'index.html').write_text(template.replace('/*__REPOSITORY__*/',json.dumps(repository)))
    (output/'.nojekyll').write_text('')
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--output',type=Path,default=ROOT/'dist');a=p.parse_args()
    try: result=build(a.repository,a.output)
    except ValueError as e: p.error(str(e))
    print('Pages assets ready in',result)
