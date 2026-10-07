"""Exercise the Bash wrapper without running Ansible or installing anything."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='bootstrap tests ') as directory:
    root = Path(directory).resolve()
    checkout = root / 'repo with spaces'
    checkout.mkdir()
    shutil.copy2(repo / 'bootstrap', checkout / 'bootstrap')
    bins = root / 'bin'
    bins.mkdir()
    record = root / 'call.json'
    fake = bins / 'ansible-playbook'
    fake.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
Path(os.environ['WRAPPER_RECORD']).write_text(json.dumps(dict(args=sys.argv[1:], cwd=os.getcwd(), config=os.environ.get('ANSIBLE_CONFIG'))))
sys.exit(int(os.environ.get('WRAPPER_EXIT', '0')))
''')
    fake.chmod(0o755)
    uname = bins / 'uname'
    uname.write_text('#!/bin/sh\nprintf "%s\\n" "$WRAPPER_OS"\n')
    uname.chmod(0o755)
    env = dict(os.environ, PATH=str(bins) + ':/usr/bin:/bin', WRAPPER_RECORD=str(record),
               WRAPPER_OS='Darwin', ANSIBLE_CONFIG='/unrelated/config')

    def run(args, expected=0, **overrides):
        if record.exists(): record.unlink()
        result = subprocess.run(['/bin/bash', str(checkout / 'bootstrap')] + args,
                                cwd=root, env=dict(env, **overrides), text=True, capture_output=True)
        assert result.returncode == expected, result.stdout + result.stderr
        return json.loads(record.read_text()) if record.exists() else None

    for platform in ['Darwin', 'Linux']:
        for profile in ['personal', 'workplace']:
            call = run([profile, '--check', '--diff'], WRAPPER_OS=platform)
            assert call['cwd'] == str(checkout)
            assert call['config'] == str(checkout / 'ansible.cfg')
            assert call['args'] == ['site.yml', '--check', '--diff', '--ask-become-pass', '-e',
                                     '{"workplace_only":' + ('true' if profile == 'workplace' else 'false') + '}']
    call = run(['personal', '--apps-only', '--exclude', 'writing', '--exclude', 'apple_development', '--no-ask-become-pass'])
    assert call['args'][0] == 'applications.yml' and '--ask-become-pass' not in call['args']
    assert json.loads(call['args'][2]) == {'applications_excluded_categories': ['writing', 'apple_development']}
    call = run(['workplace', '--terminal-only', '--', '-e', 'shell_home=/tmp/a path', '-e', 'workplace_only=false'])
    assert call['args'][0] == 'terminal.yml' and '--ask-become-pass' not in call['args']
    assert 'shell_home=/tmp/a path' in call['args']
    assert json.loads(call['args'][-1]) == {'workplace_only': True}
    run(['personal'], expected=7, WRAPPER_EXIT='7')
    for args in [[], ['unknown'], ['personal', '--exclude'], ['personal', '--exclude', 'bad"name'],
                 ['personal', '--apps-only', '--terminal-only'], ['personal', '--unknown']]:
        assert run(args, expected=2) is None
    assert run(['personal'], expected=2, WRAPPER_OS='FreeBSD') is None
    assert run(['--help']) is None
    assert run(['workplace', '--help']) is None
    fake.unlink()
    # Keep uname available while making Ansible unavailable, independent of host tools.
    assert run(['personal'], expected=2, PATH=str(bins)) is None
print(f'Bootstrap argument, platform, path, profile, and exit-status checks passed on {sys.platform}.')
