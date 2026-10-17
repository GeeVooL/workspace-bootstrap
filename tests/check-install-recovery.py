"""Recover missing archive launchers offline, without downloading or installing apps."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='workstation-install-recovery-'))
ansible = shutil.which('ansible-playbook')
assert ansible
play = root / 'play.yml'
play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
           ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_ROLES_PATH=str(repo / 'roles'))


def run(label, values, check=False):
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(play),
                             '-e', json.dumps(values)] + (['--check'] if check else []),
                            cwd=repo, env=env, text=True, capture_output=True)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    print(label, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for ownership in ['managed', 'unmarked', 'symlink', 'marker-symlink']:
    home = root / ownership
    payload = home / 'payload'
    (payload / 'bin').mkdir(parents=True)
    executable = payload / 'bin/jadx'
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    if ownership != 'unmarked':
        marker = payload / '.workstation-bootstrap.json'
        if ownership == 'marker-symlink':
            target = home / 'marker'
            target.write_text('{}')
            marker.symlink_to(target)
        else:
            marker.write_text('{}')
    destination = payload
    if ownership == 'symlink':
        destination = home / 'linked-payload'
        destination.symlink_to(payload, target_is_directory=True)
    app = dict(name='JADX', installer='upstream_archive', commands=[],
               paths=[str(destination / 'bin/jadx')], destination=str(destination),
               launchers=[dict(name='jadx', path='bin/jadx'), dict(name='jadx-gui', path='bin/jadx')])
    # No metadata URLs: this must never attempt to download or replace the payload.
    values = dict(ansible_python_interpreter=sys.executable,
                  ansible_facts=dict(system='Linux', architecture='aarch64', user_uid=os.getuid(),
                                     env=dict(HOME=str(home), PATH='/usr/bin:/bin')),
                  applications_home=str(home), applications_enabled_categories=['fixture'],
                  applications_setup_categories=[], applications_catalog={'fixture': {'linux': {'apps': [app]}}})
    bins = home / '.local/bin'
    launcher = bins / 'jadx'
    run(ownership + '-check', values, check=True)
    assert not bins.exists()
    run(ownership + '-apply', values)
    assert 'changed=0' in run(ownership + '-repeat', values)
    assert 'changed=0' in run(ownership + '-installed-check', values, check=True)
    assert executable.read_text() == '#!/bin/sh\nprintf "%s\\n" "$@"\n'
    if ownership == 'managed':
        result = subprocess.run([str(launcher), 'one argument', '--flag'], capture_output=True, text=True, check=True)
        assert result.stdout.splitlines() == ['one argument', '--flag']
        # Repair one missing launcher while preserving another dangling symlink.
        launcher.unlink()
        launcher.symlink_to(home / 'user-managed-command')
        (bins / 'jadx-gui').unlink()
        run('managed-partial-check', values, check=True)
        assert not (bins / 'jadx-gui').exists()
        run('managed-partial-repair', values)
        assert launcher.is_symlink() and not launcher.exists()
        assert (bins / 'jadx-gui').is_file()
        assert 'changed=0' in run('managed-partial-repeat', values)
    else:
        assert not bins.exists()
print(f'Archive launcher recovery passed on {sys.platform}; Linux facts simulated. Logs: {root}')
