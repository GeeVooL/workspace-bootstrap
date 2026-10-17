"""Validate standalone mise preservation and official-installer routing offline."""
import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

import yaml

repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']

with tempfile.TemporaryDirectory(prefix='workstation-mise-') as directory:
    root = Path(directory)
    play = root / 'play.yml'
    play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
    installer = root / 'install.sh'
    installer.write_text('\n'.join([
        '#!/bin/sh', 'set -eu',
        'printf "%s\\n" "$MISE_INSTALL_PATH" >> ' + shlex.quote(str(root / 'installer-calls')),
        "printf '%s\\n' '#!/bin/sh' 'echo mise 2026.10.0' > \"$MISE_INSTALL_PATH\"",
        'chmod +x "$MISE_INSTALL_PATH"',
        'test ! -e ' + shlex.quote(str(root / 'fail-installer')),
    ]) + '\n')
    env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
               ANSIBLE_REMOTE_TEMP=str(root / 'remote'))
    for system, platform in [('Darwin', 'macos'), ('Linux', 'linux')]:
        app = copy.deepcopy(next(a for a in catalog['utilities'][platform]['apps'] if a['id'] == 'mise'))
        assert app['installer'] == 'mise' and app['url'] == 'https://mise.run'
        app['url'] = installer.as_uri()
        home = root / platform
        local = home / '.local/bin'
        local.mkdir(parents=True)
        bins = home / 'bin'
        bins.mkdir()
        mise = local / 'mise'
        values = {
            'ansible_python_interpreter': sys.executable,
            'ansible_facts': {'system': system, 'architecture': 'arm64' if system == 'Darwin' else 'aarch64',
                              'distribution_version': '26.0', 'user_uid': os.getuid(),
                              'env': {'HOME': str(home), 'PATH': str(bins)}},
            'applications_catalog': {'utilities': {platform: {'apps': [app]}}},
            'applications_setup_categories': [], 'applications_search_path': str(bins),
        }

        def run(*flags, expected=0):
            result = subprocess.run([ansible, str(play), '-e', json.dumps(values), *flags],
                                    cwd=repo, env=env, text=True, capture_output=True)
            assert result.returncode == expected, result.stdout + result.stderr
            return result.stdout

        mise.write_text('#!/bin/sh\necho "mise 2026.10.0"\n')
        mise.chmod(0o755)
        before = mise.read_bytes()
        for flags in [('--check', '--diff'), ()]:
            assert 'changed=0' in run(*flags)
        assert mise.read_bytes() == before
        # A working command found only on PATH also bypasses the installer.
        mise.rename(bins / 'mise')
        assert 'changed=0' in run('--check')
        (bins / 'mise').unlink()
        calls = (root / 'installer-calls').read_text() if (root / 'installer-calls').exists() else ''
        assert 'changed=1' in run('--check')
        assert not mise.exists()
        assert ((root / 'installer-calls').read_text() if (root / 'installer-calls').exists() else '') == calls
        # Failure after producing a staged binary must not publish it or poison retries.
        (root / 'fail-installer').touch()
        run(expected=2)
        assert not mise.exists()
        (root / 'fail-installer').unlink()
        run()
        assert mise.is_file() and os.access(mise, os.X_OK)
        assert 'changed=0' in run()
        assert 'changed=0' in run('--check')
        assert not (home / '.profile').exists() and not (home / '.config/fish/config.fish').exists()
        for path in (root / 'installer-calls').read_text().splitlines():
            assert not Path(path).exists(), 'Staged payload was not cleaned up'
        print(system + ': preservation, check mode, failed-install recovery, and repeat apply passed', flush=True)
    print('Host: ' + sys.platform + '; macOS/Linux facts and upstream installer simulated')
