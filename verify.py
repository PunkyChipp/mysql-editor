"""Host-side checks for the running stack. Does not print credentials."""
from pathlib import Path
import json
import os
import subprocess
import urllib.request
import urllib.error

os.chdir(Path(__file__).resolve().parent)

def command(*args):
    return subprocess.check_output(args, text=True).strip()

def inside(script):
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'editor', 'python', '-c', script], text=True, capture_output=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())

editor = command('docker', 'compose', 'ps', '-q', 'editor')
assert editor, 'Editor is not running'
config = json.loads(command('docker', 'inspect', editor))[0]
assert config['HostConfig']['NetworkMode'] == 'none'
assert config['HostConfig']['ReadonlyRootfs']
assert 'ALL' in config['HostConfig']['CapDrop']
assert 'no-new-privileges:true' in config['HostConfig']['SecurityOpt']
assert config['Config']['User'] == '1000:1000'
assert not any(m['Destination'] == '/var/run/docker.sock' for m in config['Mounts'])
print('PASS: no external network, read-only installation, unprivileged user, no Docker socket')
inside('''
from pathlib import Path
import socket
for address in [('1.1.1.1', 443), ('8.8.8.8', 53)]:
    try:
        socket.create_connection(address, timeout=2).close()
    except OSError:
        continue
    raise SystemExit('FAIL: external network connection succeeded')
for path in ['/opt/study-extensions/.lock-probe', '/opt/study/.lock-probe', '/usr/bin/.lock-probe']:
    try:
        Path(path).write_text('probe')
    except OSError:
        continue
    raise SystemExit('FAIL: protected path was writable: ' + path)
print('PASS: external TCP blocked; editor and extension installation paths reject writes')
''')
extensions = command('docker', 'compose', 'exec', '-T', 'editor', 'code-server', '--extensions-dir', '/opt/study-extensions', '--list-extensions').splitlines()
expected = {'ms-python.python', 'ms-python.debugpy', 'detachhead.basedpyright', 'mtxr.sqltools', 'mtxr.sqltools-driver-mysql'}
installed = {line.strip().lower() for line in extensions if '.' in line and ' ' not in line}
assert installed == expected, f'Unexpected extension selection: {installed}'
print('PASS: exactly the five approved coding extensions are installed')
inside('''import json, subprocess, tempfile, zipfile
from pathlib import Path
with tempfile.TemporaryDirectory() as temp:
    vsix = Path(temp) / 'lock-probe.vsix'
    manifest = {'name': 'lock-probe', 'publisher': 'study-check', 'version': '1.0.0', 'engines': {'vscode': '^1.90.0'}, 'displayName': 'Harmless lock check'}
    with zipfile.ZipFile(vsix, 'w') as z:
        z.writestr('extension/package.json', json.dumps(manifest))
        z.writestr('extension.vsixmanifest', '<?xml version="1.0"?><PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"><Metadata><Identity Language="en-US" Id="lock-probe" Version="1.0.0" Publisher="study-check"/><DisplayName>Harmless lock check</DisplayName><Description>Lock verification</Description></Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets></PackageManifest>')
    result = subprocess.run(['code-server', '--extensions-dir', '/opt/study-extensions', '--install-extension', str(vsix), '--force'], capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0, 'Extension installation unexpectedly succeeded'
    assert ('/opt/study-extensions/' in output and 'mkdir' in output) or 'EROFS' in output or 'EACCES' in output, 'Installation failed for an unexpected reason: ' + output
    assert not list(Path('/opt/study-extensions').glob('study-check.lock-probe*'))
print('PASS: actual local VSIX extension installation is rejected by filesystem permissions')
''')

inside('''
import os, socket, uuid, debugpy, mysql.connector, subprocess, sys
with mysql.connector.connect(host='127.0.0.1', user='student', password=os.environ['MYSQL_PASSWORD'], database='schoolwork') as db:
    with db.cursor() as c:
        table = 'lock_check_' + uuid.uuid4().hex
        c.execute(f'CREATE TABLE {table} (id INT PRIMARY KEY, note VARCHAR(50))')
        c.execute(f"INSERT INTO {table} VALUES (1, 'Python and SQL work')")
        db.commit()
        c.execute(f'SELECT note FROM {table} WHERE id=1')
        assert c.fetchone()[0] == 'Python and SQL work'
        c.execute(f'DROP TABLE {table}')
print('PASS: Python connects to actual MySQL and creates, writes, reads, and drops a test table')
cli = subprocess.run(['mysql', '--protocol=TCP', '-h127.0.0.1', '-ustudent', 'schoolwork', '-N', '-e', 'SELECT 1'], env={**os.environ, 'MYSQL_PWD': os.environ['MYSQL_PASSWORD']}, capture_output=True, text=True, timeout=10)
assert cli.returncode == 0 and cli.stdout.strip() == '1', 'MySQL command-line connection failed'
print('PASS: MySQL command-line client executes SQL successfully')
address = debugpy.listen(('127.0.0.1', 0))
with socket.create_connection(address, timeout=3) as s:
    message = b'{"seq":1,"type":"request","command":"initialize","arguments":{"adapterID":"python"}}'
    s.sendall(b'Content-Length: ' + str(len(message)).encode() + b'\\r\\n\\r\\n' + message)
    assert b'Content-Length:' in s.recv(8192)
print('PASS: Python debug adapter accepts a debugger protocol connection')
''')
port = '8080'
for line in Path('.env').read_text().splitlines():
    if line.startswith('STUDY_PORT='):
        port = line.partition('=')[2]
with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=10) as response:
    html = response.read().decode()
    assert 'password' in html.lower()
    assert '/login' in response.url
print('PASS: browser gateway requires editor login')
print('All checks passed. These checks cover this editor runtime, not other browser tabs or host administrator changes.')
