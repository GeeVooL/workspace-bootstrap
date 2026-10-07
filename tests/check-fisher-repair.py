"""Exercise Fisher repair offline in a temporary configuration directory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='fisher-repair-'))
fish = shutil.which('fish')
ansible = shutil.which('ansible-playbook')
assert fish and ansible
config = root / 'config' / 'fish'
config.mkdir(parents=True)
env = dict(os.environ, XDG_CONFIG_HOME=str(config.parent),
           ANSIBLE_REMOTE_TEMP=str(root / 'remote'))
required = repo / 'roles/terminal/files/fisher/fish_plugins'
installer = repo / 'roles/terminal/files/fisher/install.fish'
plugins = required.read_text().splitlines()
# Deliberately restore only the manifest, using the upstream owner's casing.
# Fisher normalizes metadata but preserves existing manifest capitalization.
(config / 'fish_plugins').write_text(
    required.read_text().replace('patrickf1/', 'PatrickF1/') + 'example/extra\n')
subprocess.run([fish, '-c', '''
    set -U _fisher_plugins example/extra
    set -U _fisher_example_2F_extra_files $argv[1]
''', str(config / 'extra.fish')], env=env, check=True)
(config / 'extra.fish').write_text('# Keep this additional plugin\n')
bootstrap = root / 'fisher.fish'
bootstrap.write_text('''function fisher
    test "$argv[1]" = install; or return 1
    for plugin in $argv[2..-1]
        echo $plugin >> $__fish_config_dir/repairs.log
        # Model a download failure that Fisher reports without a failing status.
        test -e $__fish_config_dir/fail-download; and continue
        set key (string escape --style=var $plugin)
        command mkdir -p $__fish_config_dir/functions $__fish_config_dir/completions
        set files $__fish_config_dir/functions/$key.fish $__fish_config_dir/completions/$key.fish
        for file in $files
            printf '# Installed fixture\\n' > $file
        end
        set -U _fisher_{$key}_files $files
        contains -- $plugin $_fisher_plugins; or set -Ua _fisher_plugins $plugin
    end
    printf '%s\\n' $_fisher_plugins | string replace 'patrickf1/' 'PatrickF1/' > $__fish_config_dir/fish_plugins
end
''')
variables = {
    'ansible_python_interpreter': sys.executable,
    'terminal_config_root': str(config.parent),
    'shell_home': str(root / 'home'), 'shell_zdotdir': str(root / 'zsh'),
    'ghostty_config_path': str(root / 'ghostty/config'),
    'fisher_bootstrap_url': bootstrap.as_uri(),
}


def deploy(name, *flags, expected=0):
    result = subprocess.run([ansible, 'terminal.yml', '-e', json.dumps(variables), *flags],
                            cwd=repo, env=env, text=True, capture_output=True)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, result.stdout + result.stderr
    print(name, result.stdout.split('PLAY RECAP')[-1].strip(), flush=True)
    return result.stdout


def pending():
    return subprocess.check_output([fish, str(installer), 'check', '-',
                                    str(required)], env=env, text=True).splitlines()


assert pending() == plugins
manifest_before = (config / 'fish_plugins').read_bytes()
deploy('manifest-only-check', '--check')
assert not (config / 'repairs.log').exists()
assert (config / 'fish_plugins').read_bytes() == manifest_before
deploy('manifest-only-repair')
assert pending() == []
assert (config / 'repairs.log').read_text().splitlines() == plugins
assert 'PatrickF1/fzf.fish' in (config / 'fish_plugins').read_text()
healthy_manifest = (config / 'fish_plugins').read_bytes()
healthy_repairs = (config / 'repairs.log').read_bytes()
assert 'changed=0' in deploy('repeat')
assert (config / 'fish_plugins').read_bytes() == healthy_manifest
assert (config / 'repairs.log').read_bytes() == healthy_repairs
# Removing a secondary tracked file must trigger repair too.
tracked = list((config / 'completions').glob('*fzf*'))[0]
tracked.unlink()
assert pending() == ['patrickf1/fzf.fish']
before = (config / 'repairs.log').read_bytes()
deploy('missing-file-check', '--check')
assert not tracked.exists()
assert (config / 'repairs.log').read_bytes() == before
deploy('missing-file-repair')
assert tracked.exists() and pending() == []
assert (config / 'repairs.log').read_text().splitlines() == plugins + ['patrickf1/fzf.fish']
assert 'changed=0' in deploy('repaired-repeat')
assert 'changed=0' in deploy('repaired-check', '--check')
assert (config / 'extra.fish').read_text() == '# Keep this additional plugin\n'
assert 'example/extra' in (config / 'fish_plugins').read_text()
# A nominally successful Fisher call must not hide an incomplete repair.
tracked.unlink()
(config / 'fail-download').touch()
deploy('failed-repair', expected=2)
assert pending() == ['patrickf1/fzf.fish']
print('Fisher repair checks passed on', sys.platform, '; logs:', root)
