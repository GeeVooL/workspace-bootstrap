"""Offline protocol validation and atomic publication regressions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import yaml

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='workstation-review-regressions-'))
ansible = shutil.which('ansible-playbook')
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))
pin = '3FEF9748469ADBE15DA7CA80AC2D62742012EA22'
other = '1' * 40
onepassword = yaml.safe_load((repo / 'roles/applications/tasks/onepassword.yml').read_text())
assertion = next(task for task in next(t['block'] for t in onepassword if t.get('name') == 'Install the signed ARM64 archive') if task['name'] == 'Require the published 1Password signing fingerprint')
for label, status, expected in [
    ('primary', f'[GNUPG:] VALIDSIG {pin} 2026-10-15 1792022400 0 4 0 1 10 00 {pin}', 0),
    ('subkey', f'[GNUPG:] VALIDSIG {other} 2026-10-15 1792022400 0 4 0 1 10 00 {pin}', 0),
    ('uid-injection', f'[GNUPG:] GOODSIG {other} {pin} <attacker@example.invalid>\n[GNUPG:] VALIDSIG {other} 2026-10-15 1792022400 0 4 0 1 10 00 {other}', 2),
]:
    play = root / (label + '.yml')
    play.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False, vars=dict(application=dict(signing_fingerprint=pin), application_onepassword_signature=dict(stdout_lines=status.splitlines())), tasks=[assertion])]))
    result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(play)], env=env, capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr

helper = repo / 'roles/applications/files/publish-directory.py'
for collision in ['none', 'directory', 'dangling', 'file']:
    case = root / collision
    source, target = case / 'staged', case / 'target'
    source.mkdir(parents=True)
    (source / 'payload').write_text('new')
    if collision == 'directory': target.mkdir(); (target / 'user').write_text('preserve')
    if collision == 'dangling': target.symlink_to(case / 'missing')
    if collision == 'file': target.write_text('preserve')
    result = subprocess.run([sys.executable, str(helper), str(source), str(target)], capture_output=True)
    assert (result.returncode == 0) == (collision == 'none'), result.stderr
    if collision == 'none': assert (target / 'payload').read_text() == 'new' and not source.exists()
    else:
        assert (source / 'payload').read_text() == 'new'
        assert not (target / 'staged').exists()
        if collision == 'directory': assert (target / 'user').read_text() == 'preserve'
        if collision == 'dangling': assert target.is_symlink()
        if collision == 'file': assert target.read_text() == 'preserve'
print('Signature field binding and atomic publication passed on', sys.platform, root)

# Exercise real Zed routing and owned interrupted installation with the catalog intact.
zed = next(a for a in yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']['editors']['linux']['apps'] if a['id'] == 'zed')
installer = root / 'zed.sh'
installer.write_text('''#!/bin/sh
set -eu
mkdir -p "$HOME/.local/zed.app/bin"
[ ! -e "$HOME/fail" ] || exit 1
printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/zed.app/bin/zed"
chmod +x "$HOME/.local/zed.app/bin/zed"
''')
zed['url'] = installer.as_uri()
play = root / 'zed.yml'
play.write_text('- hosts: localhost\n  gather_facts: false\n  roles: [applications]\n')
env['ANSIBLE_ROLES_PATH'] = str(repo / 'roles')

def deploy(label, home, app=zed, expected=0, catalog=None, **extra):
    variables = dict(ansible_python_interpreter='auto_silent', ansible_facts=dict(system='Linux', architecture='x86_64', user_uid=os.getuid(), env=dict(HOME=str(home), PATH='/usr/bin:/bin')), applications_home=str(home), applications_setup_categories=[], applications_enabled_categories=['fixture'], applications_catalog=catalog or {'fixture': {'linux': {'apps': [app]}}}, **extra)
    result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(play), '-e', json.dumps(variables)], cwd=repo, env=env, capture_output=True, text=True)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    return result.stdout

home = root / 'zed-recovery'
home.mkdir()
(home / 'fail').touch()
deploy('zed-failure', home, expected=2)
assert (home / '.local/.workstation-zed-installing').exists()
(home / 'fail').unlink()
deploy('zed-retry', home)
assert not (home / '.local/.workstation-zed-installing').exists()
assert 'changed=0' in deploy('zed-repeat', home)
for collision in ['directory', 'desktop', 'symlink']:
    home = root / ('zed-unmarked-' + collision)
    path = home / {'directory': '.local/zed.app', 'desktop': '.local/share/applications/dev.zed.Zed.desktop', 'symlink': '.local/bin/zed'}[collision]
    path.parent.mkdir(parents=True)
    if collision == 'directory': path.mkdir()
    elif collision == 'desktop': path.write_text('[Desktop Entry]\nExec=missing\n')
    else: path.symlink_to(home / 'missing')
    deploy('zed-unmarked-' + collision, home, expected=2)
    assert path.is_symlink() if collision == 'symlink' else path.exists()
    assert not (home / '.local/.workstation-zed-installing').exists()
for label, app, catalog in [
    ('unknown-installer', dict(zed, installer='scriptt'), None),
    ('wrong-platform', dict(zed, installer='dmg'), None),
    ('malformed-platform', zed, {'fixture': {'linux': [zed]}}),
    ('malformed-collection', zed, {'fixture': {'linux': {'apps': 'not a list'}}}),
]:
    deploy(label, root / label, app=app, catalog=catalog, expected=2)
print('Zed recovery, unmarked preservation and catalog validation passed on', sys.platform, root)
