"""Check alternate executable discovery and Fish aliases without host changes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='workstation-tool-names-'))
fish = shutil.which('fish')
ansible = shutil.which('ansible-playbook')
assert fish and ansible
bin_dir = root / 'bin'
bin_dir.mkdir()
for name in ['fish', 'git', 'starship', 'fzf', 'zoxide', 'fdfind', 'batcat', 'curl', 'tar']:
    path = bin_dir / name
    path.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ' 99.0.0"\n')
    path.chmod(0o755)
# Exercise the actual prerequisite tasks with only alternate names on PATH.
tasks = yaml.safe_load((repo / 'roles/terminal/tasks/main.yml').read_text())[0]['block']
end = next(i for i, task in enumerate(tasks) if task['name'] == 'Create Fish configuration directory')
play = root / 'play.yml'
play.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False,
    environment={'PATH': str(bin_dir)}, tasks=tasks[:end])]))
values = dict(ansible_facts=dict(system='Linux', user_uid=1000),
              ansible_python_interpreter=shutil.which('python'))
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'), ANSIBLE_REMOTE_TEMP=str(root / 'remote'))
for mode in [[], ['--check', '--diff']]:
    result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(play), '-e', json.dumps(values), *mode], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert str(bin_dir / 'batcat') in result.stdout and str(bin_dir / 'fdfind') in result.stdout
    print(result.stdout.split('PLAY RECAP')[-1].strip())
snippet = repo / 'roles/terminal/files/fish/tool-aliases.fish'
def run_fish(script):
    result = subprocess.run([fish, '--no-config', '-i', '-c', script], env=dict(env, PATH=str(bin_dir), TERM='xterm', XDG_CONFIG_HOME=str(root / 'config')), text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()
source = 'source ' + str(snippet) + '; '
assert run_fish(source + 'bat; fd') == 'batcat 99.0.0\nfdfind 99.0.0'
assert run_fish('function bat; echo custom-bat; end; function fd; echo custom-fd; end; ' + source + 'bat; fd') == 'custom-bat\ncustom-fd'
# Aliases must forward arguments, including paths containing spaces.
for alternate, standard in [('batcat', 'bat'), ('fdfind', 'fd')]:
    (bin_dir / alternate).write_text('#!/bin/sh\nprintf "<%s>\\n" "$@"\n')
    assert run_fish(source + standard + ' --help "two words"') == '<--help>\n<two words>'
for name in ['bat', 'fd']:
    path = bin_dir / name
    path.write_text('#!/bin/sh\necho standard-' + name + '\n')
    path.chmod(0o755)
assert run_fish(source + 'bat; fd') == 'standard-bat\nstandard-fd'
print('Alternate executable checks and Fish alias preservation passed.')
