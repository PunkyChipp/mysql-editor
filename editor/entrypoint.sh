#!/bin/sh
set -eu
# These are defaults for presentation. Network isolation and the immutable
# extension directory provide the actual runtime restriction.
mkdir -p /home/coder/.local/share/code-server/User
python - <<'SETTINGS'
import json
import os
from pathlib import Path
settings = json.loads(Path('/opt/study/settings.json').read_text())
settings['sqltools.connections'] = [{
    'name': 'Schoolwork', 'driver': 'MySQL',
    'server': '127.0.0.1', 'port': 3306,
    'database': 'schoolwork', 'username': 'student',
    'password': os.environ['MYSQL_PASSWORD'],
    'mysqlOptions': {'authProtocol': 'default', 'enableSsl': 'Disabled'},
    'previewLimit': 50
}]
base = Path('/home/coder/.local/share/code-server')
(base / 'Machine').mkdir(exist_ok=True)
for scope in ('User', 'Machine'):
    (base / scope / 'settings.json').write_text(json.dumps(settings, indent=2))
SETTINGS
rm -f /run/editor/editor.sock
exec code-server \
  --auth password \
  --socket /run/editor/editor.sock \
  --socket-mode 0666 \
  --disable-telemetry \
  --disable-update-check \
  --disable-workspace-trust \
  --extensions-dir /opt/study-extensions \
  --user-data-dir /home/coder/.local/share/code-server \
  /home/coder/coursework
