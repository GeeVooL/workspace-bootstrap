#!/usr/bin/env python3
"""Install real mise in a disposable Linux home; requires network and Ansible.

Run only in a disposable Linux container with Fish, Bash, Zsh, curl, and PyYAML.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

assert sys.platform == 'linux', 'This integration check requires Linux'
assert os.getuid() != 0, 'Run as a normal user inside the disposable container'
repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
app = next(app for app in catalog['utilities']['linux']['apps'] if app['id'] == 'mise')
with tempfile.TemporaryDirectory(prefix='workstation-real-mise-') as directory:
    root = Path(directory)
    home = root / 'home'
    home.mkdir()
    config = home / '.config'
    play = root / 'play.yml'
    play.write_text('- hosts: workstations\n  gather_facts: true\n  roles: [applications, shell_paths]\n')
    variables = {
        'ansible_python_interpreter': sys.executable,
        'applications_home': str(home), 'shell_home': str(home),
        'terminal_config_root': str(config), 'shell_zdotdir': str(home),
        'applications_catalog': {'utilities': {'linux': {'apps': [app]}}},
        'applications_setup_categories': [],
    }
    env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
               ANSIBLE_REMOTE_TEMP=str(root / 'remote'))

    def run(*flags):
        result = subprocess.run([ansible, str(play), '-e', json.dumps(variables), *flags],
                                cwd=repo, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    binary = home / '.local/bin/mise'
    run('--check', '--diff')
    assert not binary.exists(), 'Check mode installed mise'
    run()
    before = binary.read_bytes()
    version = subprocess.check_output([str(binary), '--version'], text=True).strip()
    assert 'changed=0' in run(), 'Repeat apply changed configuration'
    assert 'changed=0' in run('--check', '--diff'), 'Final check was not clean'
    assert binary.read_bytes() == before, 'Existing installation was replaced'
    clean = dict(HOME=str(home), XDG_CONFIG_HOME=str(config), ZDOTDIR=str(home),
                 PATH='/usr/bin:/bin', TERM='dumb')
    for shell, modes in [('fish', ['-c', '-ic']), ('bash', ['-ic', '-lic']),
                         ('zsh', ['-ic', '-lic'])]:
        for mode in modes:
            result = subprocess.run([shell, mode, 'command -v mise; mise --version'],
                                    env=clean, text=True, capture_output=True)
            assert result.returncode == 0, (shell, mode, result.stderr)
            assert result.stdout.splitlines() == [str(binary), version], (shell, mode, result.stdout)
    print('Real Linux mise installer: ' + version)
    print('PASS: dry-run, installation, preservation, repeat/check zero changes, Fish/Bash/Zsh discovery')
