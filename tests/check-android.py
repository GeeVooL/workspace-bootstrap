"""Offline Android catalog checks; Homebrew and platform facts are fixtures."""
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
assert ansible, 'Install Ansible and make ansible-playbook available on PATH.'
root = Path(tempfile.mkdtemp(prefix='workstation-android-'))
brew = root / 'brew'
brew.write_text('#!' + sys.executable + '\n' + r'''import json, pathlib, sys
root = pathlib.Path(__file__).parent
args = sys.argv[1:]
with (root / 'calls').open('a') as log:
    log.write(json.dumps(args) + '\n')
state = root / 'packages.json'
data = json.loads(state.read_text()) if state.exists() else {'formula': [], 'cask': []}
kind = 'formula' if '--formula' in args else 'cask'
if args[0] == 'list':
    print('\n'.join(data[kind]))
elif args[0] == 'install':
    packages = [p.rsplit('/', 1)[-1] for p in args[2:]] if kind == 'cask' else args[2:]
    data[kind] = sorted(set(data[kind] + packages))
    state.write_text(json.dumps(data))
else:
    raise AssertionError(args)
''')
brew.chmod(0o755)
play = root / 'play.yml'
play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
values = {
    'ansible_python_interpreter': sys.executable,
    'ansible_facts': {'system': 'Darwin', 'architecture': 'arm64',
                     'distribution_version': '26.0', 'user_uid': os.getuid(),
                     'env': {'HOME': str(root / 'home'), 'PATH': str(root)}},
    'applications_catalog': catalog,
    'applications_enabled_categories': ['android_development'],
    'macos_homebrew_executable': str(brew),
    'homebrew_search_path': str(root),
    'applications_macos_dirs': [str(root / 'Applications')],
    'applications_macos_install_dir': str(root / 'Applications'),
}
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
           ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def run(name, extra=None, check=False, playbook=None, syntax=False):
    result = subprocess.run(
        [ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(playbook or play),
         '-e', json.dumps(dict(values, **(extra or {})))]
        + (['--check'] if check else []) + (['--syntax-check'] if syntax else []),
        cwd=repo, env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for entry in ['site.yml', 'applications.yml', 'terminal.yml', 'shell-paths.yml']:
    run(entry + '-syntax', playbook=repo / entry, syntax=True)
state = root / 'packages.json'
base = {'formula': ['jadx', 'scrcpy'],
        'cask': ['android-commandlinetools', 'android-platform-tools', 'temurin']}
run('workplace-preview', {'workplace_only': True}, check=True)
assert not state.exists()
run('workplace-apply', {'workplace_only': True})
assert json.loads(state.read_text()) == base
assert 'changed=0' in run('workplace-repeat', {'workplace_only': True})
assert 'oh-my-android' not in (root / 'calls').read_text()
state.unlink()
run('preview', check=True)
assert not state.exists()
run('apply')
assert json.loads(state.read_text()) == dict(base, cask=sorted(base['cask'] + ['oh-my-android']))
assert 'changed=0' in run('repeat')
assert 'changed=0' in run('installed-preview', check=True)
calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
assert calls.count(['install', '--cask', 'ateymoori/tap/oh-my-android']) == 1
state.write_text(json.dumps(base))
for name, facts in [
    ('intel', dict(values['ansible_facts'], architecture='x86_64')),
    ('older-macos', dict(values['ansible_facts'], distribution_version='15.7')),
]:
    output = run(name, {'ansible_facts': facts})
    assert 'changed=0' in output and 'skipping installation' in output
    assert json.loads(state.read_text()) == base
bundle = root / 'Applications/Oh My Android.app'
bundle.mkdir(parents=True)
assert 'changed=0' in run('existing-bundle')
assert json.loads(state.read_text()) == base
before = (root / 'calls').read_bytes()
for name, extra in [
    ('excluded', {'applications_excluded_categories': ['android_development']}),
]:
    assert 'changed=0' in run(name, extra)
    assert (root / 'calls').read_bytes() == before
print(f'Android checks passed on {sys.platform}; installers and platform facts simulated. Logs: {root}')
