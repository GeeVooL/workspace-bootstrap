"""Test workplace selection with recording installers; no packages are installed."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
ansible = shutil.which('ansible-playbook')
assert ansible, 'Install Ansible and make ansible-playbook available on PATH.'
root = Path(tempfile.mkdtemp(prefix='workstation-workplace-'))
shutil.copytree(repo / 'roles', root / 'roles')
# Keep the actual selection and OS routing; replace installer entry points only.
for platform in ('macos', 'linux'):
    (root / f'roles/applications/tasks/{platform}.yml').write_text('''
- name: Record applications sent to the installer
  ansible.builtin.copy:
    content: "{{ category_apps | to_json }}"
    dest: "{{ record_dir }}/{{ application_category }}.json"
    mode: '0600'
''')
play = root / 'play.yml'
play.write_text('- hosts: workstations\n  gather_facts: false\n  roles: [applications]\n')
entries = [
    {'name': 'approved', 'workplace_permitted': True},
    {'name': 'denied', 'workplace_permitted': False},
    {'name': 'unmarked'},
    {'name': 'string-flag', 'workplace_permitted': 'true'},
]
definition = {kind: copy.deepcopy(entries) + ['legacy']
              for kind in ('formulae', 'casks', 'packages')}
definition['apps'] = copy.deepcopy(entries)
definition['apple_container'] = {'enabled': True, 'workplace_permitted': True}
env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
           ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_HOME=str(root / 'ansible'))


def run(name, system, policy=None, definition_override=None, extra=None, check=False, expected=0):
    record = root / name
    record.mkdir(exist_ok=True)
    platform = 'macos' if system == 'Darwin' else 'linux'
    values = {
        'ansible_python_interpreter': sys.executable,
        'ansible_facts': {'system': system, 'user_uid': os.getuid()},
        'applications_catalog': {'test': {platform: definition_override or definition}},
        'record_dir': str(record),
    }
    if policy is not None:
        values['workplace_only'] = policy
    values.update(extra or {})
    result = subprocess.run(
        [ansible, '-i', str(repo / 'inventories/local/hosts.yml'), str(play),
         '-e', json.dumps(values)] + (['--check'] if check else []),
        cwd=repo, env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return record, result.stdout


for system in ('Darwin', 'Linux'):
    name = system.lower()
    record, _ = run(name + '-check', system, True, check=True)
    assert not (record / 'test.json').exists()
    record, _ = run(name + '-workplace', system, 'true')
    selected = json.loads((record / 'test.json').read_text())
    for kind in ('formulae', 'casks', 'packages'):
        assert selected[kind] == ['approved'], selected
    assert selected['apps'] == [entries[0]]
    assert selected['apple_container'] is True
    assert 'changed=0' in run(name + '-workplace', system, True)[1]
    for policy in (None, 'false'):
        record, _ = run(name + '-personal-' + str(policy), system, policy)
        selected = json.loads((record / 'test.json').read_text())
        for kind in ('formulae', 'casks', 'packages'):
            assert selected[kind] == [entry['name'] for entry in entries] + ['legacy']
        assert selected['apps'] == entries and selected['apple_container'] is True
    for label, container in [('denied', {'workplace_permitted': False}),
                             ('legacy', True), ('disabled', {'enabled': False, 'workplace_permitted': True})]:
        record, _ = run(name + '-container-' + label, system, True,
                        dict(definition, apple_container=container))
        assert json.loads((record / 'test.json').read_text())['apple_container'] is False
    record, _ = run(name + '-excluded', system, True,
                    extra={'applications_excluded_categories': ['test']})
    assert not (record / 'test.json').exists()
    run(name + '-invalid-policy', system, 'tru', expected=2)

print(f'Workplace selection passed on {sys.platform}; installers recorded only. Logs: {root}')
