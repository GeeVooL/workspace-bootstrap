"""Seed healthy, offline Fisher metadata for tests unrelated to plugin downloads."""
import os
from pathlib import Path
import shutil
import subprocess


def seed_plugins(config):
    config = Path(config)
    config.mkdir(parents=True, exist_ok=True)
    plugins = ['jorgebucaran/fisher', 'patrickf1/fzf.fish']
    (config / 'fish_plugins').write_text('\n'.join(plugins) + '\n')
    subprocess.run([shutil.which('fish'), '-c', '''
        for plugin in $argv
            set file $__fish_config_dir/functions/(string escape --style=var $plugin).fish
            command mkdir -p $__fish_config_dir/functions
            printf '# Offline fixture\n' > $file
            set -U _fisher_(string escape --style=var $plugin)_files $file
        end
        set -U _fisher_plugins $argv
    ''', *plugins], env=dict(os.environ, XDG_CONFIG_HOME=str(config.parent)), check=True)
