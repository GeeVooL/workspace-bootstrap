"""Offline Snap setup and ordering checks. Services/package managers are fixtures."""
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
root = Path(tempfile.mkdtemp(prefix='workstation-snap-setup-')).resolve()
shutil.copytree(repo / 'roles', root / 'roles')


def adapt(tasks):
    for task in tasks:
        task.pop('become', None)
        task.pop('async', None)
        task.pop('poll', None)
        for module, action in [('ansible.builtin.package', 'package'), ('ansible.builtin.systemd', 'service')]:
            if module in task:
                args = task.pop(module)
                task['ansible.builtin.command'] = {'argv': ['fixture-setup', action, json.dumps(args), '{{ ansible_check_mode }}']}
                register = task['register']
                task['changed_when'] = "'changed' in " + register + '.stdout'
                task['check_mode'] = False
        for key in ['block', 'always']:
            if key in task: adapt(task[key])


for name in ['snapd.yml', 'snap.yml', 'snap_or_copr.yml']:
    path = root / 'roles/applications/tasks' / name
    tasks = yaml.safe_load(path.read_text())
    adapt(tasks)
    path.write_text(yaml.safe_dump(tasks, sort_keys=False))
(root / 'play.yml').write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
profile = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())
fixture = root / 'fixture'
fixture.write_text('#!' + sys.executable + '\n' + r'''import json, os, pathlib, sys
home = pathlib.Path(os.environ['SNAP_FIXTURE'])
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with (home / 'calls').open('a') as f: f.write(json.dumps([name] + args) + '\n')
if name == 'fixture-setup':
    action, spec, check = args[0], json.loads(args[1]), args[2].lower() == 'true'
    if action == 'package':
        assert spec == {'name': 'snapd', 'state': 'present'}
        marker = home / 'package'
        if not marker.exists():
            print('changed')
            if not check:
                marker.touch()
                (home / 'bin/snap').symlink_to(sys.argv[0])
    else:
        assert (home / 'package').exists()
        assert spec['state'] == 'started'
        if spec['name'] == 'snapd.socket': assert spec['enabled'] is True
        marker = home / spec['name']
        if not marker.exists():
            print('changed')
            if not check: marker.touch()
elif name == 'snap':
    assert (home / 'snapd.socket').exists() and (home / 'snapd.service').exists()
    if args == ['wait', 'system', 'seed.loaded']:
        if (home / 'seed-failure').exists(): sys.exit(1)
        (home / 'seeded').touch()
    elif args[0] == 'list': sys.exit(0 if (home / ('installed-' + args[1])).exists() else 1)
    else:
        assert args in [['install', 'ghostty', '--classic'], ['install', 'typora'], ['install', 'snapd']], args
        assert (home / 'seeded').exists()
        if (home / 'fedora').exists(): assert (home / 'snap').is_symlink()
        (home / ('installed-' + args[1])).touch()
else: raise AssertionError((name, args))
''')
fixture.chmod(0o755)
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def scenario(name, distro='Fedora', system='Linux', policy=True):
    home = root / name
    bins = home / 'bin'
    bins.mkdir(parents=True)
    (bins / 'fixture-setup').symlink_to(fixture)
    if distro == 'Fedora': (home / 'fedora').touch()
    catalog = {key: copy.deepcopy(profile['applications_catalog'][key]) for key in ['package_managers', 'utilities', 'writing']}
    # Only Linux application paths; no fixture may invoke host Homebrew.
    catalog['utilities'].pop('macos')
    catalog['writing'].pop('macos')
    catalog['utilities']['linux']['apps'][0]['paths'] = []
    catalog['writing']['linux']['apps'][0]['paths'] = []
    values = dict(ansible_python_interpreter=sys.executable,
        ansible_facts=dict(system=system, distribution=distro, os_family='RedHat' if distro == 'Fedora' else 'Debian',
            pkg_mgr='dnf5' if distro == 'Fedora' else 'apt', service_mgr='systemd', architecture='aarch64',
            user_uid=1000, env=dict(HOME=str(home), PATH=str(bins))),
        applications_catalog=catalog, applications_setup_categories=profile['applications_setup_categories'],
        applications_enabled_categories=['writing', 'utilities', 'package_managers'] if distro == 'Fedora' else ['utilities', 'package_managers'],
        applications_search_path=str(bins), applications_snap_mount_path=str(home / 'snap'),
        applications_snap_mount_source=str(home / 'snap-source'), workplace_only=policy)
    return home, values


def run(label, home, values, check=False, expected=0):
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(root / 'play.yml'), '-e', json.dumps(values)] + (['--check'] if check else []), cwd=repo,
                            env=dict(env, SNAP_FIXTURE=str(home), PATH=str(home / 'bin') + ':' + os.environ['PATH']), text=True, capture_output=True)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(label, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for distro in ['Ubuntu', 'Debian', 'Fedora']:
    home, values = scenario(distro, distro, policy=distro != 'Fedora')
    output = run(distro + '-check', home, values, check=True)
    assert 'after the planned Snap setup' in output
    assert not (home / 'package').exists() and not (home / 'snap').is_symlink()
    run(distro + '-apply', home, values)
    assert (home / 'installed-ghostty').exists()
    assert (home / 'installed-typora').exists() == (distro == 'Fedora')
    assert (home / 'installed-snapd').exists() == (distro == 'Debian')
    assert 'changed=0' in run(distro + '-repeat', home, values)
    assert 'changed=0' in run(distro + '-final-check', home, values, check=True)
    # An installed CLI must not prevent repairing disabled services.
    (home / 'snapd.socket').unlink()
    run(distro + '-repair-check', home, values, check=True)
    assert not (home / 'snapd.socket').exists()
    run(distro + '-repair', home, values)
    assert (home / 'snapd.socket').exists()

for name in ['excluded', 'denied', 'mac', 'unsupported', 'no-systemd', 'collision', 'seed-failure']:
    home, values = scenario(name, system='Darwin' if name == 'mac' else 'Linux')
    values['applications_enabled_categories'] = ['package_managers']
    expected = 0
    if name == 'excluded': values['applications_excluded_categories'] = ['package_managers']
    if name == 'denied': values['applications_catalog']['package_managers']['linux']['apps'][0]['workplace_permitted'] = False
    if name == 'unsupported':
        values['ansible_facts']['distribution'] = 'Archlinux'
        expected = 2
    if name == 'no-systemd':
        values['ansible_facts']['service_mgr'] = 'sysvinit'
        expected = 2
    if name == 'collision':
        (home / 'snap').write_text('preserve me')
        expected = 2
    if name == 'seed-failure':
        (home / 'seed-failure').touch()
        expected = 2
    output = run(name, home, values, expected=expected)
    if name in ['excluded', 'denied', 'mac', 'unsupported', 'no-systemd']:
        assert not (home / 'calls').exists()
    if name == 'collision': assert (home / 'snap').read_text() == 'preserve me'
print(f'Snap setup fixtures passed on {sys.platform}; package managers and systemd simulated. Logs: {root}')
