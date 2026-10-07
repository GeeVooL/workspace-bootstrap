"""Offline fonts, Flatpak, 1Password, and Apple developer tools checks.

Package managers, signature verification, and Apple services are fixtures. Real
archive extraction and role control flow run against temporary directories.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
import yaml

repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible
root = Path(tempfile.mkdtemp(prefix='workstation-platform-apps-'))
shutil.copytree(repo / 'roles', root / 'roles')


def adapt(tasks):
    for task in tasks:
        task.pop('become', None)
        if 'ansible.builtin.package' in task:
            package = task.pop('ansible.builtin.package')['name']
            task['ansible.builtin.command'] = {'argv': ['fixture-package', json.dumps(package), '{{ ansible_check_mode }}']}
            task.update(register='fixture_package', changed_when="'changed' in fixture_package.stdout", check_mode=False)
        for module, command, argument in [('ansible.builtin.apt', 'fixture-apt', 'deb'),
                                          ('ansible.builtin.rpm_key', 'fixture-key', 'key')]:
            if module in task:
                value = task.pop(module)[argument]
                task['ansible.builtin.command'] = {'argv': [command, value]}
        for key in ['block', 'always', 'rescue']:
            if key in task:
                adapt(task[key])


for path in (root / 'roles/applications/tasks').glob('*.yml'):
    tasks = yaml.safe_load(path.read_text())
    adapt(tasks)
    path.write_text(yaml.safe_dump(tasks, sort_keys=False))
(root / 'play.yml').write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
catalog = yaml.safe_load((repo / 'inventories/local/group_vars/workstations.yml').read_text())['applications_catalog']
fixture = root / 'fixture'
fixture.write_text('#!' + sys.executable + '\n' + r'''import json, os, pathlib, sys
home = pathlib.Path(os.environ['APP_FIXTURE'])
name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with (home / 'calls').open('a') as f: f.write(json.dumps([name] + args) + '\n')
if name == 'fixture-package':
    packages = json.loads(args[0]); packages = packages if isinstance(packages, list) else [packages]
    for package in packages:
        marker = home / ('package-' + package)
        if not marker.exists():
            print('changed')
            if args[1].lower() == 'false':
                marker.touch()
                if package == 'flatpak': (home / 'bin/flatpak').symlink_to(sys.argv[0])
elif name == 'flatpak':
    remote = home / 'remote'
    if args[0] == 'remotes':
        assert '--user' in args and '--show-disabled' in args
        print('unrelated\tuser')
        if remote.exists(): print('flathub\t' + remote.read_text())
    elif args[0] in ['remote-add', 'remote-modify']:
        assert '--user' in args and 'flathub' in args
        remote.write_text('user')
    else: raise AssertionError(args)
elif name == 'fc-cache': assert args[0] == '-f'
elif name == 'gpg':
    if '--verify' in args:
        if (home / 'bad-signature').exists(): sys.exit(1)
        print('[GNUPG:] VALIDSIG ' + ('BADKEY' if (home / 'bad-key').exists() else '3FEF9748469ADBE15DA7CA80AC2D62742012EA22'))
elif name in ['dpkg-query', 'rpm']:
    if not (home / 'native-installed').exists(): sys.exit(1)
    if name == 'dpkg-query': print('install ok installed', end='')
elif name in ['fixture-apt', 'dnf']:
    assert pathlib.Path(args[-1]).is_file()
    (home / 'native-installed').touch()
elif name == 'fixture-key': assert '1password' in args[0]
elif name == 'brew':
    state = home / ('brew-' + ('formula' if '--formula' in args else 'cask'))
    if args[0] == 'list': print(state.read_text() if state.exists() else '')
    else:
        assert args[0] == 'install'
        state.write_text('\n'.join(args[2:]))
elif name == 'mas':
    assert args == ['install', '497799835']
    (home / 'Applications/Xcode.app').mkdir(parents=True)
elif name == 'xcode-select':
    if args == ['-p']:
        if not (home / 'Developer/usr/bin/clang').exists(): sys.exit(2)
        print(home / 'Developer')
    else:
        assert args == ['--install']
        (home / 'clt-request').touch()
else: raise AssertionError((name, args))
''')
fixture.chmod(0o755)
for font in ['JetBrainsMono-Regular.ttf', 'JetBrainsMonoNerdFont-Regular.ttf']:
    with zipfile.ZipFile(root / (font + '.zip'), 'w') as archive:
        archive.writestr('fonts/' + font, b'font fixture')
source = root / 'vendor'
source.mkdir()
script = source / 'after-install.sh'
script.write_text('#!/bin/sh\nset -eu\nprintf "#!/bin/sh\\n" > "$APP_FIXTURE/bin/1password"\nchmod +x "$APP_FIXTURE/bin/1password"\n')
script.chmod(0o755)
with tarfile.open(root / '1password.tar.gz', 'w:gz') as archive:
    archive.add(source, arcname='1password')
for name in ['1password.tar.gz.sig', '1password.asc', '1password.deb', '1password.rpm']:
    (root / name).write_text('fixture')
base_env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def scenario(name, category, system='Linux', arch='aarch64', family='Debian', apps=None):
    home = root / name
    bins = home / 'bin'
    bins.mkdir(parents=True)
    for command in ['fixture-package', 'fc-cache', 'gpg', 'rpm', 'dpkg-query', 'fixture-apt', 'fixture-key', 'dnf', 'brew', 'mas', 'xcode-select']:
        (bins / command).symlink_to(fixture)
    platform = 'macos' if system == 'Darwin' else 'linux'
    selected = copy.deepcopy(catalog[category][platform])
    if apps is not None: selected['apps'] = [app for app in selected['apps'] if app['id'] in apps]
    for app in selected.get('apps', []):
        if app['installer'] == 'font_archive':
            app['url'] = (root / (Path(app['paths'][0]).name + '.zip')).as_uri()
        if app['id'] == '1password' and system == 'Linux':
            app['paths'] = []
            app['archive_url'] = (root / '1password.tar.gz').as_uri()
            app['signing_key'] = (root / '1password.asc').as_uri()
            app['urls'] = {fmt: {'x86_64': (root / ('1password.' + fmt)).as_uri()} for fmt in ['deb', 'rpm']}
    values = dict(ansible_python_interpreter=sys.executable,
                  ansible_facts=dict(system=system, architecture='arm64' if system == 'Darwin' else arch,
                                     os_family=family, pkg_mgr='apt' if family == 'Debian' else 'dnf',
                                     user_uid=501, env=dict(HOME=str(home), PATH=str(bins))),
                  applications_catalog={category: {platform: selected}},
                  applications_search_path=str(bins), homebrew_search_path=str(bins),
                  applications_fonts_dir=str(home / 'fonts'), applications_onepassword_dir=str(home / 'opt/1Password'),
                  applications_xcode_select=str(bins / 'xcode-select'),
                  applications_macos_dirs=[str(home / 'Applications')], applications_macos_install_dir=str(home / 'Applications'))
    return home, values


def run(label, home, values, check=False, expected=0):
    env = dict(base_env, APP_FIXTURE=str(home), PATH=str(home / 'bin') + ':' + os.environ['PATH'])
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(root / 'play.yml'), '-e', json.dumps(values)] + (['--check'] if check else []), cwd=repo, env=env, text=True, capture_output=True)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(label, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for name, category, kwargs in [
    ('fonts-linux', 'fonts', {}), ('fonts-mac', 'fonts', {'system': 'Darwin'}),
    ('flatpak', 'desktop', {}), ('password-arm', 'security', {'apps': ['1password']}),
    ('password-deb', 'security', {'apps': ['1password'], 'arch': 'x86_64'}),
    ('password-rpm', 'security', {'apps': ['1password'], 'arch': 'x86_64', 'family': 'RedHat'}),
    ('password-mac', 'security', {'apps': ['1password'], 'system': 'Darwin'}),
    ('apple', 'apple_development', {'system': 'Darwin'}),
]:
    if name == 'password-arm' and sys.platform != 'linux':
        print('ARM archive extraction is exercised on Linux (Ansible requires GNU tar).', flush=True)
        continue
    home, values = scenario(name, category, **kwargs)
    permitted = category in ['fonts', 'desktop']
    if not permitted:
        assert 'changed=0' in run(name + '-workplace', home, dict(values, workplace_only=True))
        assert not (home / 'calls').exists()
    else: values['workplace_only'] = True
    run(name + '-check', home, values, check=True)
    assert not list(home.glob('package-*')) and not (home / 'remote').exists() and not (home / 'opt').exists()
    if name == 'apple':
        assert not (home / 'clt-request').exists()
        run('clt-request', home, values, expected=2)
        assert (home / 'clt-request').exists() and not (home / 'Applications/Xcode.app').exists()
        compiler = home / 'Developer/usr/bin/clang'
        compiler.parent.mkdir(parents=True)
        compiler.touch()
    run(name + '-apply', home, values)
    assert 'changed=0' in run(name + '-repeat', home, values)
    assert 'changed=0' in run(name + '-final-check', home, values, check=True)
    if name == 'fonts-linux':
        assert len(list((home / 'fonts').rglob('*.ttf'))) == 2
    if name == 'flatpak':
        (home / 'remote').write_text('disabled')
        run('flatpak-disabled-check', home, values, check=True)
        assert (home / 'remote').read_text() == 'disabled'
        run('flatpak-enable', home, values)
        assert (home / 'remote').read_text() == 'user'
        assert 'changed=0' in run('flatpak-enabled-repeat', home, values)
for failure in ['bad-key', 'bad-signature']:
    home, values = scenario(failure, 'security', apps=['1password'])
    (home / failure).touch()
    run(failure, home, values, expected=2)
    assert not (home / 'opt').exists() and not (home / 'bin/1password').exists()
print(f'Platform app checks passed on {sys.platform}; external installers simulated. Logs: {root}')
