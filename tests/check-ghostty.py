"""Offline Ghostty installer routing checks; package managers are fixtures."""
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
root = Path(tempfile.mkdtemp(prefix='workstation-ghostty-'))
shutil.copytree(repo / 'roles', root / 'roles')
tasks = root / 'roles/applications/tasks/snap_or_copr.yml'
tasks.write_text(tasks.read_text().replace('      become: true\n', ''))
play = root / 'play.yml'
play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
fixture = root / 'fixture'
fixture.write_text('#!' + sys.executable + '\n' + r'''import json, os, pathlib, sys
root = pathlib.Path(os.environ['GHOSTTY_FIXTURE'])
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'calls').open('a') as log: log.write(json.dumps([name] + args) + '\n')
state = root / 'installed'
if name == 'snap':
    if (root / 'broken-snap').exists(): sys.exit(2)
    if args == ['list', 'ghostty']: sys.exit(0 if state.exists() else 1)
    assert args == ['install', 'ghostty', '--classic'], args
    if (root / 'failed-install').exists(): sys.exit(1)
    state.touch()
elif name == 'rpm':
    assert args == ['-q', 'ghostty'], args
    sys.exit(0 if state.exists() else 1)
elif name in ('dnf', 'dnf5'):
    assert args == ['install', '-y', 'ghostty'], args
    assert (root / 'repos/workstation-scottames-ghostty.repo').exists()
    state.touch()
elif name == 'brew':
    if args[:2] == ['list', '--formula']: pass
    elif args[:2] == ['list', '--cask']:
        if state.exists(): print('ghostty')
    else:
        assert args == ['install', '--cask', 'ghostty'], args
        state.touch()
else: raise AssertionError((name, args))
''')
fixture.chmod(0o755)
(root / 'fedora-44.repo').write_text('[ghostty-fixture]\nenabled=1\ngpgcheck=1\n')
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
           ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def scenario(name, system='Linux', distribution='Ubuntu', manager='apt', snap=False):
    home = root / name
    bins = home / 'bin'
    bins.mkdir(parents=True)
    for command in ['rpm', 'dnf', 'dnf5', 'brew'] + (['snap'] if snap else []):
        (bins / command).symlink_to(fixture)
    platform = 'macos' if system == 'Darwin' else 'linux'
    app = copy.deepcopy(catalog['utilities'][platform]['apps'][0])
    assert app['id'] == 'ghostty' and app['workplace_permitted'] is True
    if system == 'Linux':
        assert 'scottames/ghostty' in app['copr']['url']
        app['copr']['url'] = root.as_uri() + '/fedora-{release}.repo'
        app['paths'] = []
    values = dict(
        ansible_python_interpreter=sys.executable,
        ansible_facts=dict(system=system, distribution=distribution, pkg_mgr=manager,
                           distribution_major_version='44', architecture='arm64' if system == 'Darwin' else 'aarch64',
                           user_uid=os.getuid(), env=dict(HOME=str(home), PATH=str(bins))),
        applications_catalog={'utilities': {platform: {'apps': [app]}}},
        applications_search_path=str(bins), homebrew_search_path=str(bins),
        applications_macos_dirs=[str(home / 'Applications')],
        applications_macos_install_dir=str(home / 'Applications'),
        applications_copr_repo_dir=str(home / 'repos'))
    return home, values


def run(name, home, values, check=False, expected=0):
    run_env = dict(env, GHOSTTY_FIXTURE=str(home), PATH=str(home / 'bin') + ':' + os.environ['PATH'])
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'),
                             str(play), '-e', json.dumps(values)] + (['--check'] if check else []),
                            cwd=repo, env=run_env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for name, args in [
    ('mac', dict(system='Darwin')),
    ('ubuntu-snap', dict(snap=True)),
    ('fedora-snap', dict(distribution='Fedora', manager='dnf5', snap=True)),
    ('fedora-dnf', dict(distribution='Fedora', manager='dnf')),
    ('fedora-dnf5', dict(distribution='Fedora', manager='dnf5')),
]:
    home, values = scenario(name, **args)
    values['workplace_only'] = True
    run(name + '-check', home, values, check=True)
    assert not (home / 'installed').exists() and not (home / 'repos').exists()
    run(name + '-apply', home, values)
    assert (home / 'installed').exists()
    assert 'changed=0' in run(name + '-repeat', home, values)
    assert 'changed=0' in run(name + '-final-check', home, values, check=True)
    calls = [json.loads(line) for line in (home / 'calls').read_text().splitlines()]
    if args.get('snap'):
        assert calls.count(['snap', 'install', 'ghostty', '--classic']) == 1
        assert all(call[0] == 'snap' for call in calls)
        assert not (home / 'repos').exists()
    elif args.get('system') != 'Darwin':
        assert calls.count([args['manager'], 'install', '-y', 'ghostty']) == 1

home, values = scenario('existing', snap=True)
(home / 'bin/ghostty').write_text('#!/bin/sh\nexit 0\n')
(home / 'bin/ghostty').chmod(0o755)
assert 'changed=0' in run('existing', home, values)
assert not (home / 'calls').exists()
home, values = scenario('no-snap')
assert 'Install and configure Snap first' in run('no-snap', home, values, check=True, expected=2)
assert not (home / 'calls').exists()
for failure in ['broken-snap', 'failed-install']:
    home, values = scenario(failure, distribution='Fedora', manager='dnf5', snap=True)
    (home / failure).touch()
    run(failure, home, values, expected=2)
    assert not (home / 'repos').exists() and not (home / 'installed').exists()
    assert all(json.loads(line)[0] == 'snap' for line in (home / 'calls').read_text().splitlines())
home, values = scenario('excluded', snap=True)
values['applications_excluded_categories'] = ['utilities']
assert 'changed=0' in run('excluded', home, values)
assert not (home / 'calls').exists()
print(f'Ghostty checks passed on {sys.platform}; package managers simulated. Logs: {root}')
