"""Validate provider-independent CLI discovery and recorded Homebrew installs."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']

with tempfile.TemporaryDirectory(prefix='workstation-discovery-') as directory:
    root = Path(directory)
    home = root / 'home'
    cargo, fzf, local, bins = [home / p for p in ['custom-cargo/bin', '.fzf/bin', '.local/bin', 'brew/bin']]
    for path in [cargo, fzf, local, bins]:
        path.mkdir(parents=True)
    search_path = os.pathsep.join(map(str, [cargo, fzf, local, bins]))

    def binary(path, version='4.9.0', rc=0):
        path.write_text(f'#!/bin/sh\necho "{path.name} {version}"\nexit {rc}\n')
        path.chmod(0o755)

    def discover(**extra):
        spec = dict(id='fish', commands=['fish'], search_path=search_path, minimum_version='4.0.0')
        spec.update(extra)
        result = subprocess.run([sys.executable, str(repo / 'roles/executable_discovery/files/discover.py'), json.dumps(spec)],
                                check=True, text=True, capture_output=True)
        return json.loads(result.stdout)

    assert discover()['status'] == 'missing'
    (cargo / 'fish').symlink_to(cargo / 'missing')
    assert discover()['status'] == 'broken'
    (cargo / 'fish').unlink()
    binary(cargo / 'fish')
    (bins / 'fish').symlink_to(cargo / 'fish')
    assert discover()['candidates'] == [str(cargo / 'fish')]
    (bins / 'fish').unlink()
    binary(bins / 'fish', '4.8.0')
    assert discover()['candidates'] == [str(cargo / 'fish'), str(bins / 'fish')]
    assert discover(override=str(bins / 'fish'))['status'] == 'conflict'
    assert discover(override=str(bins / 'fish'), search_path=str(bins))['status'] == 'ready'
    assert discover(override=str(bins / 'absent/fish'))['status'] == 'broken'
    binary(cargo / 'fish', '3.7.0')
    assert discover()['status'] == 'incompatible', 'Do not silently select another installation'
    binary(cargo / 'fish', rc=1)
    assert discover()['status'] == 'broken'
    binary(cargo / 'fish')
    (bins / 'fish').unlink()
    (local / 'fdfind').symlink_to(cargo / 'fish')
    assert discover(commands=['fd', 'fdfind'], minimum_version='')['path'] == str(local / 'fdfind')
    (local / 'fdfind').unlink()
    print('Discovery: aliases, duplicates, symlinks, overrides, broken probes, and version requirements passed', flush=True)

    # Exercise real catalog entries and the real application/Homebrew roles offline.
    apps = [copy.deepcopy(a) for a in catalog['utilities']['macos']['apps'] if a.get('cli') and a['id'] != 'mise']
    for app in apps:
        destination = fzf if app['id'] == 'fzf' else cargo
        version = {'fish': '4.9.0', 'fzf': '0.66.0', 'fd': '10.0.0', 'bat': '0.26.0'}.get(app['id'], '2.0.0')
        binary(destination / app['commands'][0], version)
    brew = bins / 'brew'
    brew.write_text('#!' + sys.executable + '\n' + '''import json, pathlib, sys
root = pathlib.Path(sys.argv[0]).parent
args = sys.argv[1:]
with (root / 'calls').open('a') as log: log.write(json.dumps(args) + '\\n')
if args[0] == 'list':
    if '--formula' in args and (root / 'receipt').exists(): print('fish')
else:
    assert args == ['install', '--formula', 'fish'], args
    (root / 'receipt').touch()
    fish = root / 'fish'
    fish.write_text('#!/bin/sh\\necho "fish 4.9.0"\\n')
    fish.chmod(0o755)
''')
    brew.chmod(0o755)
    play = root / 'play.yml'
    play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
    values = dict(ansible_python_interpreter=sys.executable,
                  ansible_facts=dict(system='Darwin', architecture='arm64', distribution_version='26.0',
                                     user_uid=os.getuid(), env=dict(HOME=str(home), CARGO_HOME=str(cargo.parent), PATH=str(bins))),
                  applications_catalog={'utilities': {'macos': {'apps': apps}}},
                  applications_setup_categories=[],
                  homebrew_search_path=str(bins))
    env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))

    def run(*flags, expected=0):
        result = subprocess.run([ansible, str(play), '-e', json.dumps(values), *flags],
                                cwd=repo, env=env, text=True, capture_output=True)
        assert result.returncode == expected, result.stdout + result.stderr
        return result.stdout

    assert 'changed=0' in run('--check')
    assert 'changed=0' in run()
    values['ansible_facts']['architecture'] = 'x86_64'
    intel_output = run('--check')
    assert 'changed=0' in intel_output
    assert intel_output.index('item=/usr/local/bin') < intel_output.index('item=/opt/homebrew/bin')
    values['ansible_facts']['architecture'] = 'arm64'
    assert not (bins / 'calls').exists(), 'Working CLI tools must not invoke Homebrew'
    # Isolate missing-tool scenarios from binaries on the test host.
    values['applications_search_path'] = search_path
    values['applications_catalog']['utilities']['macos']['apps'] = [apps[0]]
    assert apps[0]['id'] == 'fish'
    binary(cargo / 'fish', '3.7.0')
    run('--check', expected=2)
    assert not (bins / 'calls').exists()
    (cargo / 'fish').unlink()
    assert 'changed=1' in run('--check')
    assert not (bins / 'receipt').exists()
    run()
    assert 'changed=0' in run()
    assert sum(json.loads(line)[0] == 'install' for line in (bins / 'calls').read_text().splitlines()) == 1
    (bins / 'fish').unlink()
    assert 'records fish as installed' in run('--check', expected=2)
    print('Catalog: external installations reused, old Fish preserved, missing Fish installed once, broken receipt reported', flush=True)
    print('Host: ' + sys.platform + '; Homebrew and macOS facts simulated')
