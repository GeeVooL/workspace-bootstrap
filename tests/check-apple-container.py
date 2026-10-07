"""Offline installer checks; never invokes sudo or Apple's real installer."""
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

repo = Path(__file__).resolve().parents[1]
os.chdir(repo)
root = Path(tempfile.mkdtemp(prefix='apple-container-validation-'))
ansible = shutil.which('ansible-playbook')
assert ansible, 'Make ansible-playbook available on PATH.'
(root / 'package.pkg').write_bytes(b'fixture package')

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
release = {
    'tag_name': '1.5.0', 'draft': False, 'prerelease': False,
    'assets': [{'name': 'container-1.5.0-installer-signed.pkg',
                'browser_download_url': base + '/package.pkg',
                'digest': 'sha256:' + hashlib.sha256(b'fixture package').hexdigest()}],
}
(root / 'release.json').write_text(json.dumps(release))
fixture = root / 'fixture'
fixture.write_text('#!' + sys.executable + '\n' + r'''
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parent
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / 'calls').open('a') as log:
    log.write(json.dumps([name, *args]) + '\n')
if name == 'container':
    if args == ['--version']:
        print('container CLI version ' + (root / 'version').read_text())
    elif args == ['list', '--format', 'json']:
        print('[{"id":"busy"}]' if (root / 'busy').exists() else '[]')
    elif args == ['system', 'stop']:
        assert not (root / 'busy').exists()
        (root / 'running').unlink()
    elif args == ['system', 'start', '--enable-kernel-install']:
        (root / 'running').touch()
    else: raise AssertionError(args)
elif name == 'launchctl':
    assert args == ['list']
    if (root / 'running').exists():
        print('123 0 com.apple.container.apiserver')
elif name == 'pkgutil':
    assert args[0] == '--check-signature'
    assert pathlib.Path(args[1]).read_bytes() == b'fixture package'
    if (root / 'bad-signature').exists():
        sys.exit(1)
elif name == 'installer':
    assert args[0] == '-pkg' and args[2:] == ['-target', '/']
    assert pathlib.Path(args[1]).read_bytes() == b'fixture package'
    assert not (root / 'running').exists()
    if (root / 'failed-install').exists(): sys.exit(1)
    (root / 'version').write_text('1.5.0')
    if not (root / 'container').exists():
        (root / 'container').symlink_to(root / 'fixture')
else:
    raise AssertionError(name)
''')
fixture.chmod(0o755)
for name in ['launchctl', 'pkgutil', 'installer']:
    (root / name).symlink_to(fixture)
variables = {
    'ansible_python_interpreter': sys.executable,
    'ansible_become': False,  # Fixture commands run unprivileged, including installer.
    'ansible_facts': {'system': 'Darwin', 'architecture': 'arm64',
                      'distribution_version': '26.0', 'user_uid': 501},
    'applications_catalog': {'development': {'macos': {'apple_container': True}}},
    'apple_container_release_url': base + '/release.json',
    'apple_container_executable': str(root / 'container'),
    'apple_container_installer_executable': str(root / 'installer'),
    'apple_container_pkgutil_executable': str(root / 'pkgutil'),
    'apple_container_launchctl_executable': str(root / 'launchctl'),
}
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))

def run(name, extra=None, check=False, expected=0):
    result = subprocess.run([ansible, 'applications.yml', '-e', json.dumps(dict(variables, **(extra or {}))),
                             *(['--check'] if check else [])], env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip())
    return result.stdout

def calls():
    return [json.loads(line) for line in (root / 'calls').read_text().splitlines()] if (root / 'calls').exists() else []

def installed():
    return sum(c[0] == 'installer' for c in calls())

try:
    assert 'changed=1' in run('missing-check', check=True)
    assert not calls() and not (root / 'container').exists()
    run('fresh-install')
    assert installed() == 1 and (root / 'version').read_text() == '1.5.0'
    assert (root / 'running').exists()
    assert 'changed=0' in run('repeat')
    assert 'changed=0' in run('installed-check', check=True)
    assert installed() == 1
    (root / 'version').write_text('1.4.0')
    assert 'changed=1' in run('upgrade-check', check=True)
    assert (root / 'version').read_text() == '1.4.0'
    (root / 'running').touch()
    (root / 'busy').touch()
    run('running-workload', expected=2)
    assert (root / 'running').exists()
    (root / 'busy').unlink()
    assert installed() == 1
    (root / 'bad-signature').touch()
    run('invalid-signature', expected=2)
    assert installed() == 1
    assert (root / 'running').exists()
    (root / 'bad-signature').unlink()
    (root / 'package.pkg').write_bytes(b'corrupted package')
    run('invalid-checksum', expected=2)
    assert installed() == 1
    (root / 'package.pkg').write_bytes(b'fixture package')
    (root / 'failed-install').touch()
    run('failed-upgrade', expected=2)
    assert (root / 'running').exists()
    (root / 'failed-install').unlink()
    run('upgrade')
    assert installed() == 3
    assert (root / 'running').exists()
    assert 'changed=0' in run('upgrade-repeat')
    (root / 'version').write_text('9.0.0')
    assert 'changed=0' in run('no-downgrade')
    (root / 'version').write_text('1.4.0')
    (root / 'running').unlink()
    run('upgrade-stopped-service')
    assert not (root / 'running').exists()
    (root / 'container').unlink()
    run('fresh-install-without-start', {'apple_container_start_after_install': False})
    assert not (root / 'running').exists()
    before = calls()
    for name, facts in [
        ('intel', {'system': 'Darwin', 'architecture': 'x86_64', 'distribution_version': '26.0', 'user_uid': 501}),
        ('old-macos', {'system': 'Darwin', 'architecture': 'arm64', 'distribution_version': '15.0', 'user_uid': 501}),
        ('linux', {'system': 'Linux', 'user_uid': 501}),
    ]:
        assert 'changed=0' in run(name, {'ansible_facts': facts})
    assert 'changed=0' in run('excluded', {'applications_excluded_categories': ['development']})
    assert calls() == before
    # Successful and failed downloads/installers all clean their temporary directory.
    for call in calls():
        if call[0] in ['installer', 'pkgutil']:
            assert not Path(call[2]).parent.exists()
    print('Offline checks passed; OS facts and installer commands simulated. Logs:', root)
finally:
    server.shutdown()
    server.server_close()
