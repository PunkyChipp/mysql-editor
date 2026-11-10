"""Package only the reviewed home runtime sources, never private state."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['START STUDY DESK.cmd','home_setup.py','home_runner.py','home_paths.py','remote_api.py',
       'launch.py','desk_api.py','setup.py','verify.py','compose.yaml','README.md','starter/.vscode/launch.json']
FOLDERS=['desk','editor','gateway','starter','scripts','hosting']


def build(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    files=[ROOT/name for name in FILES]
    for folder in FOLDERS:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not p.is_symlink()
                     and not any(part.startswith('.') or part=='__pycache__' for part in p.relative_to(ROOT).parts))
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            relative=path.relative_to(ROOT)
            assert '.env' not in relative.parts and '.home' not in relative.parts
            info=zipfile.ZipInfo(str(relative).replace('\\','/'),date_time=(2026,11,10,0,0,0))
            info.external_attr=(0o100755 if path.suffix=='.sh' else 0o100644)<<16
            archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
    return output


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();print(build(args.output))
