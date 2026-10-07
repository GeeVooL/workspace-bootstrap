"""Offline fixtures for official editor installers; never invoke host package managers."""
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
os.chdir(repo)
root = Path(tempfile.mkdtemp(prefix='workstation-editors-'))
ansible = shutil.which('ansible-playbook')
assert ansible
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
# Copy roles before replacing privileged Ansible modules with local fixtures.
# All task routing, detection, downloads, script execution and cleanup stays real.
shutil.copytree(repo / 'roles', root / 'roles')
native = root / 'roles/applications/tasks/native.yml'
s = native.read_text()
assert 'ansible.builtin.apt:' in s and 'ansible.builtin.rpm_key:' in s
s = s.replace('''ansible.builtin.apt:
            deb: "{{ application_package_download.path }}/editor.deb"
            state: present''', '''ansible.builtin.command:
            argv: [fixture-apt, "{{ application_package_download.path }}/editor.deb"]''')
s = s.replace('''ansible.builtin.rpm_key:
            key: "{{ application.signing_key }}"
            state: present''', '''ansible.builtin.command:
            argv: [fixture-key, "{{ application.signing_key }}"]''')
s = s.replace('          become: true\n', '')
native.write_text(s)
snap_tasks = root / 'roles/applications/tasks/snap.yml'
snap_tasks.write_text(snap_tasks.read_text().replace('      become: true\n', ''))
play = root / 'play.yml'
play.write_text('''- hosts: workstations
  gather_facts: false
  roles: [applications]
''')
bin_dir = root / 'bin'
bin_dir.mkdir()
fixture = bin_dir / 'fixture'
fixture.write_text('#!' + sys.executable + '\n' + r'''import json, os, pathlib, shutil, sys
root = pathlib.Path(os.environ['EDITOR_FIXTURE'])
root.mkdir(parents=True, exist_ok=True)
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'calls').open('a') as log: log.write(json.dumps([name] + args) + '\n')
state = root / 'installed'
if name == 'brew':
    if args[:2] == ['list', '--cask']:
        if state.exists(): print(state.read_text())
    elif args[:2] == ['list', '--formula']: pass
    elif args[:2] == ['install', '--cask']: state.write_text(args[2])
    else: raise AssertionError(args)
elif name in ['dpkg-query', 'rpm']:
    if not state.exists(): sys.exit(1)
    print('install ok installed' if name == 'dpkg-query' else 'code-1.0')
elif name in ['fixture-apt', 'dnf', 'dnf5', 'yum', 'zypper']:
    package = pathlib.Path(args[-1])
    assert package.exists() and package.suffix == ('.deb' if name == 'fixture-apt' else '.rpm')
    state.touch()
elif name == 'snap':
    if (root / 'broken-snap').exists(): sys.exit(2)
    if args == ['list', 'typora']: sys.exit(0 if state.exists() else 1)
    assert args == ['install', 'typora'], args
    if (root / 'failed-install').exists(): sys.exit(1)
    state.touch()
elif name == 'fixture-key':
    assert args == ['https://packages.microsoft.com/keys/microsoft.asc']
elif name == 'ditto':
    shutil.copytree(args[0], args[1])
elif name == 'hdiutil':
    if args[0] == 'attach':
        mount = pathlib.Path(args[args.index('-mountpoint') + 1])
        app = mount / 'Visual Studio Code.app'
        app.mkdir(parents=True)
        (app / 'fixture').write_text('official DMG fixture')
    elif args[0] == 'detach':
        import shutil
        shutil.rmtree(args[1])
    else: raise AssertionError(args)
else: raise AssertionError(name)
''')
fixture.chmod(0o755)
for command in ['brew', 'dpkg-query', 'rpm', 'fixture-apt', 'fixture-key', 'dnf', 'dnf5', 'yum', 'zypper', 'hdiutil', 'ditto']:
    (bin_dir / command).symlink_to(fixture)
script = root / 'zed-install.sh'
script.write_text('''#!/bin/sh
set -eu
[ "$ZED_CHANNEL" = stable ]
[ "$ZED_VERSION" = latest ]
mkdir -p "$HOME/.local/zed.app/bin" "$HOME/.local/bin"
printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/zed.app/bin/zed"
chmod +x "$HOME/.local/zed.app/bin/zed"
ln -s "$HOME/.local/zed.app/bin/zed" "$HOME/.local/bin/zed"
''')
download = root / 'package'
download.write_text('official download fixture')
for platform, apps in catalog['editors'].items():
    for app in apps['apps']:
        if app['installer'] == 'dmg':
            assert app['url'].endswith('/darwin-universal-dmg/stable')
            app['url'] = download.as_uri()
        elif app['installer'] == 'script':
            assert app['url'] == 'https://zed.dev/install.sh'
            app['url'] = script.as_uri()
        elif app['installer'] == 'native':
            for fmt, arches in app['urls'].items():
                for arch, url in arches.items():
                    assert f'linux-{fmt}-' in url
                    assert ('arm64' if arch == 'aarch64' else 'x64') in url
                    arches[arch] = download.as_uri()
        if platform == 'linux': app['paths'] = ['{{ applications_home }}/.local/zed.app/bin/zed'] if app['id'] == 'zed' else []

typora = catalog['writing']['linux']['apps'][0]
assert typora['workplace_permitted'] is False
for arch, url in typora['urls']['deb'].items():
    assert url.startswith('https://downloads.typora.io/linux/typora_')
    assert url.endswith(('_arm64.deb' if arch == 'aarch64' else '_amd64.deb'))
    typora['urls']['deb'][arch] = download.as_uri()
typora['paths'] = []

env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'], ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))

def variables(system, name, family='Debian', manager='apt', arch='x86_64'):
    home = root / name
    return dict(applications_catalog=copy.deepcopy(catalog), applications_enabled_categories=['editors'],
                ansible_facts=dict(system=system, architecture=arch, os_family=family, pkg_mgr=manager, user_uid=os.getuid(), env=dict(HOME=str(home), PATH=str(bin_dir))),
                applications_home=str(home), applications_search_path=str(home / '.local/bin'),
                applications_macos_dirs=[str(home / 'Applications')], applications_macos_install_dir=str(home / 'Applications'),
                homebrew_search_path=str(bin_dir), ansible_python_interpreter=sys.executable)

def run(name, v, check=False, expected=0):
    run_env = dict(env, EDITOR_FIXTURE=v['applications_home'] + '/state')
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(play), '-e', json.dumps(v)] + (['--check'] if check else []), env=run_env, capture_output=True, text=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout

for entry in ['terminal.yml', 'site.yml', 'applications.yml', 'shell-paths.yml']:
    subprocess.run([ansible, entry, '--syntax-check'], env=env, check=True)
v = variables('Darwin', 'mac')
assert 'changed=2' in run('mac-check', v, True)
assert not (root / 'mac/Applications').exists()
run('mac-install', v)
assert (root / 'mac/Applications/Visual Studio Code.app/fixture').exists()
assert 'changed=0' in run('mac-repeat', v)
calls = (root / 'mac/state/calls').read_text()
assert 'visual-studio-code' not in calls
assert '["brew", "install", "--cask", "zed"]' in calls
assert '"detach"' in calls
(root / 'mac/Applications/Zed.app').mkdir()
before = (root / 'mac/state/calls').read_text()
assert 'changed=0' in run('mac-existing-bundles', v)
assert (root / 'mac/state/calls').read_text() == before

for family, manager, arch in [('Debian', 'apt', 'x86_64'), ('Debian', 'apt', 'aarch64'), ('RedHat', 'dnf', 'x86_64'), ('RedHat', 'dnf5', 'aarch64'), ('Suse', 'zypper', 'x86_64')]:
    name = manager + '-' + arch
    v = variables('Linux', name, family, manager, arch)
    assert 'changed=2' in run(name + '-check', v, True)
    assert not (root / name / '.local').exists()
    run(name + '-install', v)
    assert (root / name / '.local/bin/zed').is_symlink()
    assert (root / name / 'state/installed').exists()
    assert 'changed=0' in run(name + '-repeat', v)
    assert 'changed=0' in run(name + '-check-installed', v, True)
    calls = (root / name / 'state/calls').read_text()
    assert ('fixture-apt' in calls) == (family == 'Debian')
    assert ('fixture-key' in calls) == (family != 'Debian')

v = variables('Linux', 'external')
commands = root / 'external/.local/bin'
commands.mkdir(parents=True)
for command in ['code', 'zeditor']:
    (commands / command).write_text('#!/bin/sh\nexit 0\n')
    (commands / command).chmod(0o755)
assert 'changed=0' in run('external-commands', v)
assert not (root / 'external/state').exists()
v = variables('Linux', 'excluded')
v['applications_excluded_categories'] = ['editors']
assert 'changed=0' in run('excluded', v)
v['applications_excluded_categories'] = []
v['ansible_facts']['os_family'] = 'Archlinux'
run('unsupported-distro', v, True, expected=2)
for category, cask, bundle in [('writing', 'typora', 'Typora.app'),
                               ('security', 'little-snitch', 'Little Snitch.app')]:
    v = variables('Darwin', cask)
    v['applications_enabled_categories'] = [category]
    v['applications_catalog'][category]['macos']['apps'] = [app for app in v['applications_catalog'][category]['macos']['apps'] if app['cask'] == cask]
    assert catalog[category]['macos']['apps'][0]['workplace_permitted'] is False
    assert 'changed=0' in run(cask + '-workplace', dict(v, workplace_only=True))
    assert not (root / cask / 'state').exists()
    assert 'changed=1' in run(cask + '-check', v, True)
    assert not (root / cask / 'state/installed').exists()
    run(cask + '-install', v)
    assert (root / cask / 'state/installed').read_text() == cask
    assert 'changed=0' in run(cask + '-repeat', v)
    (root / cask / 'Applications' / bundle).mkdir(parents=True)
    before = (root / cask / 'state/calls').read_text()
    assert 'changed=0' in run(cask + '-existing-bundle', v)
    assert (root / cask / 'state/calls').read_text() == before

for arch in ['x86_64', 'aarch64']:
    name = 'typora-' + arch
    v = variables('Linux', name, arch=arch)
    v['applications_enabled_categories'] = ['writing']
    assert 'changed=0' in run(name + '-workplace', dict(v, workplace_only=True))
    assert not (root / name / 'state').exists()
    assert 'changed=1' in run(name + '-check', v, True)
    assert not (root / name / 'state/installed').exists()
    run(name + '-install', v)
    assert (root / name / 'state/installed').exists()
    assert 'changed=0' in run(name + '-repeat', v)
    calls = (root / name / 'state/calls').read_text()
    assert 'fixture-apt' in calls and 'fixture-key' not in calls

v = variables('Linux', 'typora-rpm', 'RedHat', 'dnf')
v['applications_enabled_categories'] = ['writing']
for check in [True, False]:
    output = run('typora-rpm-' + str(check), v, check)
    assert 'Skipping Typora: no native installer' in output and 'changed=0' in output
assert not (root / 'typora-rpm/state').exists()
for family in ['RedHat', 'Archlinux']:
    name = 'typora-snap-' + family
    v = variables('Linux', name, family, 'dnf' if family == 'RedHat' else 'pacman')
    v['applications_enabled_categories'] = ['writing']
    snap = Path(v['applications_search_path']) / 'snap'
    snap.parent.mkdir(parents=True)
    snap.symlink_to(fixture)
    assert 'changed=0' in run(name + '-workplace', dict(v, workplace_only=True))
    assert not (root / name / 'state').exists()
    assert 'changed=1' in run(name + '-check', v, True)
    assert not (root / name / 'state/installed').exists()
    run(name + '-apply', v)
    assert (root / name / 'state/installed').exists()
    assert 'changed=0' in run(name + '-repeat', v)
    calls = [json.loads(line) for line in (root / name / 'state/calls').read_text().splitlines()]
    assert calls.count(['snap', 'install', 'typora']) == 1
    assert all(call[0] == 'snap' for call in calls)
for failure in ['broken-snap', 'failed-install']:
    v = variables('Linux', failure, 'RedHat', 'dnf')
    v['applications_enabled_categories'] = ['writing']
    snap = Path(v['applications_search_path']) / 'snap'
    snap.parent.mkdir(parents=True)
    snap.symlink_to(fixture)
    state = root / failure / 'state'
    state.mkdir()
    (state / failure).touch()
    run(failure, v, expected=2)
    assert not (state / 'installed').exists()
assert all(app['id'] != 'little-snitch' for app in catalog['security']['linux']['apps'])
print(f'Passed on {sys.platform}; disk mounts and native package managers simulated. Logs: {root}')
