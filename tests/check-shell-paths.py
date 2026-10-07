#!/usr/bin/env python3
"""Validate shell PATH deployment in a temporary home; install no packages.

Usage: python3 tests/check-shell-paths.py /path/to/ansible-playbook
Requires Fish, Bash, and Zsh on the test host.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
ANSIBLE = sys.argv[1] if len(sys.argv) > 1 else shutil.which('ansible-playbook')
assert ANSIBLE, 'Provide an ansible-playbook executable'
SHELLS = {name: shutil.which(name) for name in ('fish', 'bash', 'zsh')}
assert all(SHELLS.values()), 'Fish, Bash, and Zsh must be installed'

with tempfile.TemporaryDirectory(prefix='workstation-shells-') as directory:
    root = Path(directory)
    home, config, zdotdir = root/'home', root/'config', root/'zsh'
    bins = root/"tools with spaces and 'quotes'"/'bin'
    for path in (home, config, zdotdir, bins):
        path.mkdir(parents=True, exist_ok=True)
    tools = ['git', 'starship', 'fzf', 'zoxide', 'bat', 'fd', 'rg', 'tree', 'jq']
    for tool in tools:
        executable = bins/tool
        executable.write_text('#!/bin/sh\nexit 0\n')
        executable.chmod(0o755)
    originals = {
        home/'.bashrc': '# Existing Bash settings\nreturn\n',
        home/'.bash_login': '# Existing login settings\n',
        home/'.profile': '# Lower-priority profile must stay untouched\n',
        zdotdir/'.zshrc': '# Existing Zsh settings\n',
        zdotdir/'.zprofile': '# Existing Zsh login settings\n',
    }
    for path, content in originals.items():
        path.write_text(content)
    import json
    variables = {
        'shell_home': str(home), 'terminal_config_root': str(config),
        'shell_zdotdir': str(zdotdir), 'shell_extra_bin_paths': [str(bins)],
    }
    env = dict(os.environ, ANSIBLE_HOME=str(root/'ansible'),
               ANSIBLE_LOCAL_TEMP=str(root/'local'), ANSIBLE_REMOTE_TEMP=str(root/'remote'))

    def deploy(*flags):
        result = subprocess.run(
            [ANSIBLE, '-i', 'localhost,', 'shell-paths.yml', '-e', json.dumps(variables), *flags],
            cwd=REPO, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    deploy('--check', '--diff')
    assert not (config/'fish').exists(), 'Check mode wrote configuration'
    for path, content in originals.items():
        assert path.read_text() == content
    deploy()
    assert 'changed=0' in deploy(), 'Second application was not idempotent'
    for path, content in originals.items():
        assert path.read_text().endswith(content), path
    assert not (home/'.bash_profile').exists(), 'Existing login file was shadowed'
    assert (home/'.profile').read_text() == originals[home/'.profile']
    assert list(home.glob('.bashrc.*~')), 'Changed startup file was not backed up'
    snippet = config/'fish'/'conf.d'/'00-workstation-path.fish'
    subprocess.run([SHELLS['fish'], '--no-execute', str(snippet)], check=True)
    for shell in ('bash', 'zsh'):
        subprocess.run([SHELLS[shell], '-n', str(config/'workstation-bootstrap'/'path.sh')], check=True)

    clean = {'HOME': str(home), 'XDG_CONFIG_HOME': str(config),
             'XDG_DATA_HOME': str(root/'data'), 'XDG_CACHE_HOME': str(root/'cache'),
             'ZDOTDIR': str(zdotdir), 'PATH': '/usr/bin:/bin', 'TERM': 'dumb'}
    for shell, modes in [('fish', ['-ic']), ('bash', ['-ic', '-lic']), ('zsh', ['-ic', '-lic'])]:
        for mode in modes:
            commands = '; '.join('command -v ' + tool for tool in tools)
            result = subprocess.run([SHELLS[shell], mode, commands], env=clean, text=True, capture_output=True)
            assert result.returncode == 0, (shell, mode, result.stderr)
            assert result.stdout.splitlines() == [str(bins/tool) for tool in tools], (shell, mode, result.stdout)
            # Sourcing twice must not accumulate PATH entries.
            source = snippet if shell == 'fish' else config/'workstation-bootstrap'/'path.sh'
            command = 'source ' + shlex.quote(str(source))
            print_path = 'string join : $PATH' if shell == 'fish' else 'printf "%s\\n" "$PATH"'
            result = subprocess.run([SHELLS[shell], mode, command+'; '+command+'; '+print_path],
                                    env=clean, text=True, capture_output=True, check=True)
            assert result.stdout.strip().split(':').count(str(bins)) == 1, (shell, mode, result.stdout)
            print(f'{shell} {mode}: all utilities discoverable; no duplicate PATH entries')
    print('Check mode, preservation, backups, syntax, and idempotence passed on ' + sys.platform)
