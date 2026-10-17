"""Exercise upstream Android installs in temporary homes with tiny local archives."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import yaml

repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible
root = Path(tempfile.mkdtemp(prefix='workstation-android-linux-'))
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
apps = copy.deepcopy(catalog['android_development']['linux']['apps'])
fixture_script = '#!/bin/sh\nprintf "%s\\n" "$JAVA_HOME" "$ADB" "$@"\n'
for app in apps:
    app_root = app['archive_root'].replace('*', 'fixture')
    base = '' if app_root == '.' else app.get('archive_parent', '') + '/' + app_root + '/'
    base = base.lstrip('/')
    files = {base + exe: fixture_script.encode() for exe in app['executables']}
    archive = root / (app['id'] + '.' + app['archive_format'])
    if app['archive_format'] == 'zip':
        with zipfile.ZipFile(archive, 'w') as z:
            for name, content in files.items():
                z.writestr(name, content)
    else:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            for name, content in files.items():
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode = len(content), 0o755
                tar.addfile(entry, io.BytesIO(content))
        payload = stream.getvalue()
        if app['archive_format'] == 'deb':
            header = ('data.tar.gz/'.ljust(16) + '0'.ljust(12) + '0'.ljust(6)
                      + '0'.ljust(6) + '100644'.ljust(8) + str(len(payload)).ljust(10) + '`\n').encode()
            payload = b'!<arch>\n' + header + payload + (b'\n' if len(payload) % 2 else b'')
        archive.write_bytes(payload)
    metadata = root / (app['id'] + '.json')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata.write_text(json.dumps({'draft': False, 'prerelease': False, 'assets': [
        {'name': archive.name, 'browser_download_url': archive.as_uri(), 'digest': 'sha256:' + checksum}]}))
    app.update(metadata_kind='github', metadata_url=metadata.as_uri(), asset_pattern=archive.name.replace('.', r'\.'))
    # Isolate discovery from any pre-existing /opt installations.
    app['commands'] = []
    app['paths'] = [path for path in app['paths'] if not path.startswith('/opt/')]
play = root / 'play.yml'
play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))


def values(home, system='Linux', arch='x86_64'):
    return dict(ansible_python_interpreter=sys.executable,
                ansible_facts={'system': system, 'architecture': arch, 'user_uid': os.getuid(),
                               'env': {'HOME': str(home), 'PATH': '/usr/bin:/bin'},
                               'distribution': 'Fedora', 'os_family': 'RedHat'},
                applications_setup_categories=[], applications_catalog={'android_development': {'linux': {'apps': apps}}},
                applications_enabled_categories=['android_development'],
                applications_home=str(home), applications_search_path=str(home / 'bin'))


def run(name, options, check=False, expected=0):
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(play),
                             '-e', json.dumps(options)] + (['--check'] if check else []),
                            cwd=repo, env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


home = root / 'home'
opts = dict(values(home), workplace_only=True)
run('preview', opts, check=True)
assert not home.exists()
run('apply', opts)
assert 'changed=0' in run('repeat', opts)
assert 'changed=0' in run('installed-preview', opts, check=True)
android = home / '.local/share/workstation-bootstrap/android'
for command in ['android-studio', 'asfp', 'adb', 'fastboot', 'sdkmanager', 'avdmanager', 'jadx', 'jadx-gui', 'scrcpy']:
    launcher = home / '.local/bin' / command
    result = subprocess.run([str(launcher), 'an argument', '--flag'], text=True, capture_output=True, check=True)
    assert result.stdout.splitlines()[-2:] == ['an argument', '--flag']
    if command in ['sdkmanager', 'avdmanager', 'jadx', 'jadx-gui']:
        assert result.stdout.splitlines()[0] == str(android / 'java')
    if command == 'scrcpy':
        assert result.stdout.splitlines()[1] == str(android / 'sdk/platform-tools/adb')
assert not list(home.rglob('.workstation-download-*'))
for name, extra in [('excluded', {'applications_excluded_categories': ['android_development']})]:
    fresh = root / name
    assert 'changed=0' in run(name, dict(values(fresh), **extra))
    assert not fresh.exists()
arm = root / 'arm'
run('arm-preview', values(arm, arch='aarch64'), check=True)
run('arm-apply', values(arm, arch='aarch64'))
assert sorted(p.name for p in (arm / '.local/share/workstation-bootstrap/android').iterdir()) == ['jadx', 'java']
assert 'changed=0' in run('arm-repeat', values(arm, arch='aarch64'))
# Existing unmarked destinations are refused before extraction, even if incomplete.
existing = root / 'existing'
existing_java = existing / '.local/share/workstation-bootstrap/android/java'
existing_java.mkdir(parents=True)
(existing_java / 'keep').write_text('user data')
run('preserve-directory', values(existing), expected=2)
assert (existing_java / 'keep').read_text() == 'user data'
# Wrong upstream digest must fail and clean staging without publishing an install.
bad = copy.deepcopy(opts)
bad['applications_home'] = str(root / 'bad')
bad_apps = copy.deepcopy(apps[:1])
metadata = json.loads((root / 'android-java.json').read_text())
metadata['assets'][0]['digest'] = 'sha256:' + '0' * 64
(root / 'bad.json').write_text(json.dumps(metadata))
bad_apps[0]['metadata_url'] = (root / 'bad.json').as_uri()
bad['applications_catalog'] = {'android_development': {'linux': {'apps': bad_apps}}}
run('checksum-rejection', bad, expected=2)
assert not (root / 'bad/.local/share/workstation-bootstrap/android/java').exists()
assert not list((root / 'bad').rglob('.workstation-download-*'))
# Existing launchers (including symlinks) are preserved.
collision = root / 'collision'
(collision / '.local/bin').mkdir(parents=True)
(collision / 'original').write_text('user launcher')
(collision / '.local/bin/jadx').symlink_to(collision / 'original')
collision_apps = [copy.deepcopy(apps[5])]
collision_opts = values(collision)
collision_opts['applications_catalog'] = {'android_development': {'linux': {'apps': collision_apps}}}
run('preserve-launcher', collision_opts)
assert (collision / '.local/bin/jadx').is_symlink()
assert (collision / 'original').read_text() == 'user launcher'
print(f'Linux Android archive checks passed on {sys.platform}; Linux facts and payloads simulated. Logs: {root}')
