# Workstation Bootstrap

Ansible playbooks for setting up a development workstation on macOS and Linux.

The project currently configures a Fish-based terminal environment. The longer-term
scope includes package installation, editors, development tools, and OS-specific
settings for a fresh machine.

## Current setup

| Component | Configuration |
| --- | --- |
| Fish | Git abbreviations covering status, diffs, commits, branches, history, and synchronization |
| Starship | Prompt initialization; existing styling is preserved |
| Fisher | Installs required Fish plugins while preserving additional plugins |
| fzf.fish | File, Git, history, process, and variable pickers with previews |
| zoxide | Directory tracking and `z` / `zi` shortcuts |
| Ghostty | Launches Fish; optional |

`terminal.yml` runs locally as the current user. It checks for installed tools
before modifying configuration. Package installation is not automated yet.

## Requirements

- macOS or Linux
- Ansible Core
- Fish 4.0+, fzf 0.33+, fd 8.5+, and bat 0.16+ on `PATH`
- Git, Starship, zoxide, curl, and tar on `PATH`
- Internet access to GitHub when installing missing plugins
- Ghostty, when using the Ghostty configuration task

No additional Ansible collections are required. On Linux, some distributions name
`fd` and `bat` executables `fdfind` and `batcat`; provide `fd` and `bat` on `PATH`
before running the playbook.

On macOS with Homebrew:

```sh
brew install ansible fish git starship fzf fd bat zoxide
brew install --cask ghostty
```

On Linux, install the dependencies through the distribution's package manager or
the projects' official installation instructions. Repository availability and
package versions vary by distribution.

## Usage

Run from the repository directory as a normal user, without `sudo`.

Preview the changes:

```sh
ansible-playbook -i localhost, terminal.yml --check --diff
```

Apply the configuration:

```sh
ansible-playbook -i localhost, terminal.yml
```

Reload Ghostty's configuration and open a new tab to start Fish with the updated
settings. Repeated runs only change managed files whose contents or permissions
differ. Check mode runs read-only prerequisite checks.

To configure Fish without touching Ghostty:

```sh
ansible-playbook -i localhost, terminal.yml -e configure_ghostty=false
```

This also applies to headless Linux systems and WSL sessions using another terminal.

## Repository layout

```text
terminal.yml
files/
  fish/
    git-abbreviations.fish
    starship.fish
    fzf-options.fish
    zoxide.fish
  fisher/
    fish_plugins
    install.fish
    legacy-fzf.fish
```

Edit Fish configuration in `files/fish/`. The playbook copies these files to the
Fish configuration directory, validating their syntax before installation.

## Managed files

The playbook manages these files under `$XDG_CONFIG_HOME/fish/conf.d`, falling back
to `~/.config/fish/conf.d`:

- `git-abbreviations.fish`
- `starship.fish`
- `fzf-options.fish`
- `zoxide.fish`

Existing files with those names are replaced when their contents differ. Ansible
creates timestamped backups before content changes. Other Fish files, including
`config.fish`, are preserved. Remove duplicate initialization of these tools from
other configuration files before applying.

When enabled, the Ghostty task adds or updates its `command` setting with the
detected Fish executable path. Fonts, themes, key bindings, and other settings
are preserved. The configuration file is backed up before content changes.
Managed configuration directories use mode `0700`; managed files use `0644`.

Default Ghostty configuration paths:

| Platform | Path |
| --- | --- |
| macOS | `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty` |
| Linux | `$XDG_CONFIG_HOME/ghostty/config.ghostty`, or `~/.config/ghostty/config.ghostty` |

For a legacy `config` filename or a custom location, set `ghostty_config_path`.
Other loaded Ghostty files can override the `command` setting; use the appropriate
configuration file for the existing setup.

The playbook does not change the account's login shell or manage shell history,
zoxide's database, or `starship.toml`. Starship uses its defaults when no separate
prompt configuration exists.

## Fish plugins

The required plugin list lives in `files/fisher/fish_plugins`:

- [Fisher](https://github.com/jorgebucaran/fisher)
- [fzf.fish](https://github.com/PatrickF1/fzf.fish)

Ansible downloads a Fisher bootstrap function from a fixed commit and installs
missing plugins. Plugin versions follow their upstream defaults at first install;
existing installations are not automatically upgraded. Additional Fisher plugins
are preserved. Fisher maintains the installed list in `fish/fish_plugins`, plugin
files in `fish/functions`, `fish/completions`, and `fish/conf.d`, and installation
metadata in Fish's universal variables. These generated files are not committed.
The bootstrap function is cached under `fish/.bootstrap`.

Add a plugin interactively with `fisher install owner/repository`, or add it to the
repository's required list to install it on subsequent playbook runs. Removing a
line from that list does not uninstall it; use `fisher remove owner/repository`.
Run `fisher update` explicitly to update installed plugins.

The previous repository-managed `conf.d/fzf.fish` is backed up and removed only
when its content matches the old snippet exactly. Fisher then installs its own
`conf.d/fzf.fish`. Modified or unrelated files are preserved; a conflicting file
can prevent installation and needs to be reconciled manually. Remove any separate
`fzf --fish | source` initialization or other fzf plugins before using fzf.fish.

Default fzf.fish bindings:

| Binding | Search |
| --- | --- |
| Ctrl+Alt+F | Files and directories, with previews |
| Ctrl+Alt+L | Git history, with commit diffs |
| Ctrl+Alt+S | Git status, with file diffs |
| Ctrl+R | Command history |
| Ctrl+Alt+P | Processes |
| Ctrl+V | Shell variables |

Picker appearance remains in `files/fish/fzf-options.fish`. Plugin installation
runs in noninteractive Fish with `XDG_CONFIG_HOME` set to
`terminal_config_root`, so temporary deployments use isolated Fish configuration
and Fisher metadata. Fish startup files should guard interactive-only commands
with `status is-interactive`. Check mode reports missing plugins without downloading or
installing them. No plugins are downloaded when opening a shell.

## Git shortcuts

Git shortcuts use Fish abbreviations: typing a shortcut and pressing Space or
Enter expands it to the full command. They apply to interactive input rather
than scripts or function bodies. Open a new shell after updating, or reload:

```fish
source ~/.config/fish/conf.d/git-abbreviations.fish
```

| Shortcut | Expansion |
| --- | --- |
| `gd` | `git diff` (unstaged changes) |
| `gds` | `git diff --staged` |
| `gdca` | `git diff --cached` |
| `gdw` | `git diff --word-diff` |
| `gdcw` | `git diff --cached --word-diff` |
| `gst` | `git status` |
| `gcmsg` | `git commit --message` |
| `glog` | `git log --oneline --decorate --graph` |

The configuration includes 111 common Git abbreviations based on Oh My Zsh.
It does not port that plugin's advanced helper functions or every alias.
`gfa` fetches all remotes with tags and pruning, without a fixed parallel-job count.
Run `abbr --show` to inspect the active mappings.

## Configuration variables

Pass overrides with `-e` or an Ansible variables file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `configure_ghostty` | `true` | Enable Ghostty configuration tasks |
| `terminal_config_root` | `$XDG_CONFIG_HOME` or `~/.config` | Root for Fish configuration and the default Linux Ghostty path |
| `ghostty_config_path` | Platform-specific path above | Ghostty file to update |
| `terminal_search_path` | Current `PATH`, Homebrew locations, and `~/.local/bin` | Tool discovery and task execution path |

Example using an existing Linux Ghostty configuration:

```sh
ansible-playbook -i localhost, terminal.yml \
  -e 'ghostty_config_path=/home/username/.config/ghostty/config'
```

The playbook does not persist changes to `PATH`. Dependencies must also be
available in interactive Fish sessions.

## Development

Check playbook syntax:

```sh
ansible-playbook -i localhost, terminal.yml --syntax-check
```

Fish snippets are syntax-checked before installation. The current playbook has
been validated on macOS with Ansible Core 2.15.13 and Fish 4.9.3, including a fresh
check-mode run without configuration writes, migration in a temporary directory,
persistent Fisher metadata, fzf bindings, preservation of an additional plugin,
and a second apply with zero changes. Ghostty settings and the legacy fzf backup
were also checked. Linux execution has not yet been validated.

## Planned scope

- Package installation and dependency bootstrapping
- Editor configuration
- Development runtimes and toolchains
- Fonts and terminal themes
- Platform-specific workstation settings
