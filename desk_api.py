"""Private workspace API. User SQL/Python executes only inside the editor container."""
from __future__ import annotations
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
WORKER = (ROOT / 'desk/worker.py').read_text()


class DeskError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class DeskService:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def container(self):
        result = subprocess.run(['docker', 'compose', 'ps', '-q', 'editor'], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        identifier = result.stdout.strip()
        if result.returncode or not identifier:
            raise DeskError('The coding runtime is asleep. Return to setup to restart it.', 503)
        return identifier

    def command(self, container, seconds=35):
        return ['docker', 'exec', '-i', container, 'timeout', '--signal=TERM', '--kill-after=2',
                str(seconds), '/opt/python/bin/python', '-I', '-c', WORKER]

    def call(self, request):
        result = subprocess.run(self.command(self.container(), 15), cwd=ROOT,
            input=json.dumps(request), text=True, capture_output=True, timeout=20)
        if result.returncode:
            raise DeskError('That operation did not finish. Check the connection and try again.', 503)
        try:
            payload = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise DeskError('The runtime returned an incomplete response. Try again.', 503)
        if payload.get('error'):
            raise DeskError(payload['error'])
        return payload

    def start(self, request):
        if request.get('op') not in {'execute', 'python'}:
            raise DeskError('Choose SQL or Python to run.')
        if request['op'] == 'execute' and (not isinstance(request.get('sql'), str) or not request['sql'].strip()):
            raise DeskError('Write or select a SQL statement first.')
        with self.lock:
            if any(j['state'] == 'running' for j in self.jobs.values()):
                raise DeskError('A run is already in progress. Stop it or wait for it to finish.', 409)
            identifier = secrets.token_hex(12)
            self.jobs = dict(list(self.jobs.items())[-19:])
            self.jobs[identifier] = {'id': identifier, 'state': 'running', 'kind': request['op'],
                                     'started': time.time(), 'cancelled': False}
            threading.Thread(target=self.run, args=(identifier, request), daemon=True).start()
        return {'id': identifier, 'state': 'running'}

    def run(self, identifier, request):
        job = self.jobs[identifier]
        process = None
        try:
            container = self.container()
            with self.lock:
                job['container'] = container
            process = subprocess.Popen(self.command(container), cwd=ROOT, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            # An inner timeout bounds execution even if the host CLI disconnects.
            watchdog = threading.Timer(42, process.kill)
            watchdog.start()
            try:
                process.stdin.write(json.dumps(request))
                process.stdin.close()
                process.stdin = None
                first = process.stdout.readline()
                try:
                    control = json.loads(first)
                except ValueError:
                    raise DeskError('The runtime could not start this run.')
                if 'pid' in control:
                    with self.lock:
                        job['pid'] = int(control['pid'])
                        job['connectionId'] = control.get('connectionId')
                        cancelled = job['cancelled']
                    if cancelled:
                        self.interrupt(job)
                    output = process.stdout.read(8 * 1024 * 1024)
                    process.wait(timeout=40)
                    if process.returncode:
                        raise DeskError('The run reached its 35-second limit or the runtime stopped. '
                                        'Earlier auto-committed SQL changes may remain.')
                    payload = json.loads(output)
                else:
                    payload = control
                with self.lock:
                    job['result'] = payload
                    job['state'] = 'error' if payload.get('error') else 'done'
            finally:
                watchdog.cancel()
        except Exception as exc:
            with self.lock:
                job['state'] = 'error'
                job['result'] = {'error': str(exc) if isinstance(exc, DeskError)
                                 else 'This run did not complete. Check the connection and try again.'}
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait()
            if process and process.stdout:
                process.stdout.close()
            with self.lock:
                if job['cancelled']:
                    job['state'] = 'cancelled'
                    job['result'] = {'error': 'Run stopped. Earlier auto-committed SQL changes may remain.'}

    def interrupt(self, job):
        if job.get('connectionId'):
            try:
                subprocess.run(self.command(job['container'], 5), input=json.dumps({
                    'op': 'kill', 'connectionId': job['connectionId']}),
                    capture_output=True, text=True, timeout=8)
            except Exception:
                pass
        if job.get('pid'):
            subprocess.run(['docker', 'exec', job['container'], 'kill', '-TERM', str(job['pid'])],
                           capture_output=True, timeout=8)

    def cancel(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if not job:
                raise DeskError('That run is no longer available.', 404)
            if job['state'] != 'running':
                return self.status(identifier)
            job['cancelled'] = True
        self.interrupt(job)
        return {'id': identifier, 'state': 'stopping'}

    def status(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if not job:
                raise DeskError('That run is no longer available. It may have finished before a restart.', 404)
            return {k: v for k, v in job.items() if k in {'id', 'state', 'kind', 'started', 'result'}}


SERVICE = DeskService()
