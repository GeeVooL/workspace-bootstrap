import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import sys
import yaml
from fisher_fixture import seed_plugins

assert sys.platform == 'darwin', 'This fixture suite currently requires macOS.'
os.chdir(Path(__file__).resolve().parents[1])
root = Path(tempfile.mkdtemp(prefix='workstation-validation-'))
python = sys.executable
ansible = shutil.which('ansible-playbook')
assert ansible, 'Install Ansible and make ansible-playbook available on PATH.'
brew = root / 'brew'
brew.write_text('#!' + python + '\n' + r'''import json, pathlib, sys
root = pathlib.Path(__file__).parent
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\n')
state = root / 'packages.json'
data = json.loads(state.read_text()) if state.exists() else {'formula': [], 'cask': []}
if args == ['--prefix']:
    print(root)
elif args[0] == 'list':
    kind = 'formula' if '--formula' in args else 'cask'
    print('\n'.join(data[kind]))
elif args[0] == 'install':
    kind = 'formula' if '--formula' in args else 'cask'
    data[kind] = sorted(set(data[kind] + args[2:]))
    state.write_text(json.dumps(data))
    if 'fork' in data['cask']:
        (root / 'installed').write_text('fork')
else:
    raise AssertionError(args)
''')
brew.chmod(0o755)
env = dict(os.environ, ANSIBLE_REMOTE_TEMP=str(root / 'remote'))
catalog = yaml.safe_load(Path('inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
# The signed package installer has its own offline fixture suite.
catalog['development']['macos']['apple_container'] = False
# Ghostty installation has its own offline routing suite.
catalog['utilities']['macos']['apps'] = []

def run(name, playbook, variables=None, *flags, expected=0, inventory=None):
    variables = dict(variables or {}, ansible_python_interpreter=python)
    variables.setdefault('applications_macos_dirs', [str(root / 'Applications')])
    variables.setdefault('applications_macos_install_dir', str(root / 'Applications'))
    variables.setdefault('shell_home', str(root / 'home'))
    variables.setdefault('shell_zdotdir', str(root / 'zsh'))
    variables.setdefault('shell_extra_bin_paths', [str(root)])
    if inventory is None:
        variables.setdefault('applications_enabled_categories', ['development'])
        variables.setdefault('applications_catalog', catalog)
    inventory_args = ['-i', str(inventory)] if inventory else []
    result = subprocess.run([ansible, *inventory_args, playbook,
                             '-e', json.dumps(variables), *flags],
                            env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip())
    return result.stdout

for playbook in ['site.yml', 'applications.yml', 'terminal.yml', 'shell-paths.yml']:
    run(playbook + '-syntax', playbook, None, '--syntax-check')
variables = {'homebrew_search_path': str(root)}
assert 'changed=1' in run('fork-check', 'applications.yml', variables, '--check')
assert not (root / 'installed').exists()
assert 'changed=1' in run('fork-apply', 'applications.yml', variables)
assert (root / 'installed').read_text() == 'fork'
assert 'changed=0' in run('fork-repeat', 'applications.yml', variables)
assert 'changed=0' in run('fork-check-installed', 'applications.yml', variables, '--check')
calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
assert calls.count(['install', '--cask', 'fork']) == 1
run('missing-homebrew', 'applications.yml', {'homebrew_search_path': str(root), 'macos_homebrew_executable': str(root / 'missing-custom-brew')}, '--check', expected=2)
assert 'changed=0' in run('linux-empty-catalog', 'applications.yml', dict(variables, ansible_facts={
    'system': 'Linux', 'user_uid': 501,
    'env': {'HOME': str(root / 'home'), 'PATH': os.environ['PATH']},
}), '--check')

config = root / 'config' / 'fish'
config.mkdir(parents=True)
seed_plugins(config)
ghostty = root / 'ghostty' / 'config.ghostty'
ghostty.parent.mkdir()
original = 'font-size = 14\ntheme = existing\nkeybind = ctrl+a=new_tab\ncommand = /bin/zsh\n'
ghostty.write_text(original)
variables = {'terminal_config_root': str(root / 'config'), 'ghostty_config_path': str(ghostty)}
run('terminal-apply', 'terminal.yml', variables)
assert 'changed=0' in run('terminal-repeat', 'terminal.yml', variables)
assert 'changed=0' in run('terminal-check', 'terminal.yml', variables, '--check')
assert ghostty.read_text() == original
assert not list(ghostty.parent.glob('config.ghostty.*~'))
for source in Path('roles/terminal/files/fish').glob('*.fish'):
    assert source.read_bytes() == (root / 'config' / 'fish' / 'conf.d' / source.name).read_bytes()
# Selection must not invoke Homebrew or deploy unselected components.
before = (root / 'calls.jsonl').read_bytes()
for name, extra in [
    ('excluded', {'applications_excluded_categories': ['development']}),
    ('disabled', {'applications_enabled_categories': []}),
    ('empty-catalog', {'applications_catalog': {}, 'applications_enabled_categories': []}),
]:
    assert 'changed=0' in run(name, 'applications.yml', dict(variables, **extra))
run('unknown-category', 'applications.yml', dict(variables, applications_excluded_categories=['typo']), expected=2)
assert (root / 'calls.jsonl').read_bytes() == before
variables['homebrew_search_path'] = str(root)
assert 'changed=0' in run('site-repeat', 'site.yml', variables)
before = (root / 'calls.jsonl').read_bytes()
assert 'changed=0' in run('terminal-tag', 'site.yml', variables, '--tags', 'terminal')
assert 'changed=0' in run('skip-applications', 'site.yml', variables, '--skip-tags', 'applications')
new_calls = (root / 'calls.jsonl').read_bytes()[len(before):].decode().splitlines()
assert all(json.loads(call) == ['--prefix'] for call in new_calls)
isolated = dict(variables, terminal_config_root=str(root / 'unselected-config'), ghostty_config_path=str(root / 'unselected-ghostty'))
assert 'changed=0' in run('applications-tag', 'site.yml', isolated, '--tags', 'applications')
assert not (root / 'unselected-config').exists()
assert not (root / 'unselected-ghostty').exists()
other_config = root / 'unselected-config' / 'fish'
other_config.mkdir(parents=True)
seed_plugins(other_config)
run('ghostty-disabled', 'terminal.yml', dict(isolated, configure_ghostty=False))
assert not (root / 'unselected-ghostty').exists()

# Inventory group settings select a catalog, and host settings override selection.
profile = root / 'profile'
(profile / 'group_vars').mkdir(parents=True)
(profile / 'host_vars').mkdir()
(profile / 'hosts.yml').write_text(Path('inventories/local/hosts.yml').read_text())
(profile / 'group_vars/workstations.yml').write_text(json.dumps({
    'applications_catalog': {
        'development': {'macos': {'casks': ['fork']}},
        'media': {'macos': {'casks': ['must-not-install']}},
    },
    'applications_excluded_categories': ['media'],
    'homebrew_search_path': str(root),
}))
assert 'changed=0' in run('profile-group-vars', 'applications.yml', inventory=profile / 'hosts.yml')
before = (root / 'calls.jsonl').read_bytes()
(profile / 'host_vars/localhost.yml').write_text(json.dumps({'applications_enabled_categories': []}))
assert 'changed=0' in run('profile-host-vars', 'applications.yml', inventory=profile / 'hosts.yml')
assert (root / 'calls.jsonl').read_bytes() == before
# Exercise both default categories together, including the utilities merged into main.
full = dict(variables, applications_enabled_categories=['utilities', 'development'])
assert 'changed=1' in run('utilities-apply', 'applications.yml', full)
assert 'changed=0' in run('utilities-repeat', 'applications.yml', full)
packages = json.loads((root / 'packages.json').read_text())
assert set(packages['formula']) == {'mise', 'fish', 'git', 'starship', 'fzf', 'zoxide', 'bat', 'fd', 'ripgrep', 'tree', 'jq'}
assert packages['cask'] == ['fork']
print('All checks passed on macOS; Homebrew and Linux OS facts were simulated. Logs:', root)
