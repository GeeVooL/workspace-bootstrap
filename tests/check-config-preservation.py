"""Test ownership and Ghostty precedence without touching the user's configuration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from fisher_fixture import seed_plugins

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='workstation-preservation-')).resolve()
ansible = shutil.which('ansible-playbook')
assert ansible
shutil.copytree(repo / 'roles', root / 'roles')
(root / 'ghostty.yml').write_text('''- hosts: workstations
  gather_facts: false
  tasks:
    - ansible.builtin.include_role:
        name: terminal
        tasks_from: ghostty.yml
''')
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def run(label, play, values, check=False):
    result = subprocess.run([ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(play), '-e', json.dumps(dict(values, ansible_python_interpreter=sys.executable))] + (['--check'] if check else []), cwd=repo, env=env, text=True, capture_output=True)
    (root / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    print(label, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


for position in range(4):
    home = root / ('ghostty-' + str(position))
    xdg = home / '.config/ghostty'
    mac = home / 'Library/Application Support/com.mitchellh.ghostty'
    paths = [xdg / 'config.ghostty', xdg / 'config', mac / 'config.ghostty', mac / 'config']
    originals = {}
    for i, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        content = 'font-size = 15\n' + ('command = /custom/shell\n' if i == position else '# command = ignored\n')
        path.write_text(content)
        path.chmod(0o600)
        originals[path] = content
    values = dict(shell_home=str(home), terminal_config_root=str(home / '.config'), fish_executable='/fixture/fish',
                  ansible_facts=dict(system='Darwin', user_dir=str(home), env=dict(HOME=str(home))))
    assert 'changed=0' in run('ghostty-command-' + str(position), root / 'ghostty.yml', values)
    for path, content in originals.items():
        assert path.read_text() == content and path.stat().st_mode & 0o777 == 0o600
# Keep the last existing legacy path, without creating a competing new file.
for system in ['Linux', 'Darwin']:
    home = root / ('legacy-' + system)
    path = home / '.config/ghostty/config'
    path.parent.mkdir(parents=True)
    path.write_text('theme = existing\n')
    values = dict(shell_home=str(home), terminal_config_root=str(home / '.config'), fish_executable='/fixture/fish',
                  ansible_facts=dict(system=system, user_dir=str(home), env=dict(HOME=str(home))))
    run(system + '-preview', root / 'ghostty.yml', values, check=True)
    assert path.read_text() == 'theme = existing\n'
    run(system + '-append', root / 'ghostty.yml', values)
    assert path.read_text() == 'theme = existing\ncommand = /fixture/fish\n'
    assert not (path.parent / 'config.ghostty').exists()
    assert 'changed=0' in run(system + '-repeat', root / 'ghostty.yml', values)
    path.write_text('config-file = other-config\n')
    assert 'changed=0' in run(system + '-includes', root / 'ghostty.yml', values)
    assert path.read_text() == 'config-file = other-config\n'

home = root / 'terminal'
config = home / '.config/fish'
seed_plugins(config)
conf = config / 'conf.d'
conf.mkdir(exist_ok=True)
conf.chmod(0o711)
custom = conf / 'starship.fish'
custom.write_text('# My custom Starship configuration\n')
custom.chmod(0o600)
managed = conf / 'zoxide.fish'
managed.write_text('# Managed by Workstation Bootstrap.\n# Old managed contents\n')
legacy = conf / 'mise.fish'
source = repo / 'roles/terminal/files/fish/mise.fish'
legacy.write_text(source.read_text().split('\n', 1)[1])
symlink_target = home / 'custom-fzf.fish'
symlink_target.write_text('# Private user snippet\n')
(conf / 'fzf-options.fish').symlink_to(symlink_target)
values = dict(shell_home=str(home), shell_zdotdir=str(home / 'zsh'), terminal_config_root=str(home / '.config'), configure_ghostty=False)
run('ownership-preview', repo / 'terminal.yml', values, check=True)
assert managed.read_text().endswith('# Old managed contents\n')
run('ownership-apply', repo / 'terminal.yml', values)
assert custom.read_text() == '# My custom Starship configuration\n' and custom.stat().st_mode & 0o777 == 0o600
assert conf.stat().st_mode & 0o777 == 0o711
assert managed.read_bytes() == (repo / 'roles/terminal/files/fish/zoxide.fish').read_bytes()
assert legacy.read_bytes() == source.read_bytes()
assert (conf / 'fzf-options.fish').is_symlink() and symlink_target.read_text() == '# Private user snippet\n'
assert list(conf.glob('zoxide.fish.*~')) and list(conf.glob('mise.fish.*~'))
assert 'changed=0' in run('ownership-repeat', repo / 'terminal.yml', values)
home = root / 'unmanaged-path'
path_file = home / '.config/workstation-bootstrap/path.sh'
path_file.parent.mkdir(parents=True)
path_file.write_text('# My unrelated script\n')
rc = home / '.bashrc'
rc.write_text('# My startup file\n')
values = dict(shell_home=str(home), shell_zdotdir=str(home), terminal_config_root=str(home / '.config'))
run('unmanaged-path', repo / 'shell-paths.yml', values)
assert path_file.read_text() == '# My unrelated script\n'
assert rc.read_text() == '# My startup file\n'
assert not (home / '.zshrc').exists()
print(f'Configuration preservation passed on {sys.platform}. Logs: {root}')
