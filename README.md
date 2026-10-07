# Workstation Bootstrap

Ansible playbooks for setting up a development workstation on macOS and Linux.

The project installs terminal utilities on macOS and configures a Fish-based
terminal environment on macOS and Linux. The longer-term scope includes editors,
development runtimes, and OS-specific settings for a fresh machine.

## Current setup

| Component | Configuration |
| --- | --- |
| Fish | Git abbreviations covering status, diffs, commits, branches, history, and synchronization |
| Starship | Prompt initialization; existing styling is preserved |
| Fisher | Installs required Fish plugins while preserving additional plugins |
| fzf.fish | File, Git, history, process, and variable pickers with previews |
| zoxide | Directory tracking and `z` / `zi` shortcuts |
| mise | Interactive Fish activation when installed on `PATH` or in `~/.local/bin` |
| Ghostty | Launches Fish; optional |

`terminal.yml` runs locally as the current user. It sets up executable paths and
checks for installed tools before installing Fish integrations. `macos.yml` installs Homebrew and utilities
and configures shared executable paths. Fish integrations remain in `terminal.yml`.

## macOS package installation

`macos.yml` installs Homebrew when missing, then installs mise, Fish, Git,
Starship, fzf, zoxide, bat, fd, ripgrep, tree, and jq. It leaves installed versions
in place and does not remove other packages. Casks are opt-in.

Ansible Core and its Python runtime must already be available to run the playbook;
it cannot install its own prerequisites. For example, with Python available,
install Ansible into a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ansible-core
source .venv/bin/activate
ansible-playbook -i localhost, macos.yml --check --diff
ansible-playbook -i localhost, macos.yml
```

Run as your normal account. On a fresh Mac, Homebrew's installer may need
administrator privileges: run `sudo -v` immediately before applying to cache
authorization. Do not run Ansible itself with sudo. Bootstrap downloads and runs
the [official Homebrew installer](https://docs.brew.sh/Installation) in
noninteractive mode and removes the temporary script afterward. If administrator
access or developer tools are required but unavailable, resolve the installer
error and rerun; install Apple's Command Line Tools with `xcode-select --install`
when needed.

Discovery prefers the architecture's standard Homebrew path (`/opt/homebrew/bin`
on Apple Silicon, `/usr/local/bin` on Intel), then searches `PATH` and both standard
locations. New installations use the architecture's standard prefix. Run from a
native terminal on Apple Silicon, rather than under Rosetta. Check mode reads
installed package lists; when Homebrew is absent, it reports bootstrap and all
requested packages without downloading or executing the installer.

| Variable | Default | Purpose |
| --- | --- | --- |
| `macos_homebrew_executable` | Detected `brew`, or architecture's standard path | Use an existing Homebrew executable at an absolute path |
| `macos_homebrew_formulae` | Package list above | Replace the list of formulae to install; use canonical names, qualified for third-party taps |
| `macos_homebrew_casks` | `[]` | Optional casks to install |

For example, include Ghostty:

```sh
ansible-playbook -i localhost, macos.yml -e '{"macos_homebrew_casks": ["ghostty"]}'
```

The package playbook also runs `shell-paths.yml`, making the installed utilities
available in new Fish, Bash, and Zsh sessions. It leaves the login shell unchanged
and does not install language runtimes through mise. Run `terminal.yml` for Fish
prompt, navigation, and fzf integrations.
`terminal.yml` also activates mise automatically in interactive Fish when it is
installed. No additional manual activation line is needed.

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

On macOS, use `macos.yml` above, or install the terminal prerequisites manually
with Homebrew:

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
macos.yml
terminal.yml
shell-paths.yml
templates/
  shell-paths.fish.j2
  shell-paths.sh.j2
  shell-path-hook.sh.j2
files/
  fish/
    git-abbreviations.fish
    mise.fish
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

## Shared CLI paths

Both playbooks run `shell-paths.yml`; it can also be run independently on macOS or
Linux after installing utilities through the platform's package manager:

```sh
ansible-playbook -i localhost, shell-paths.yml
```

It adds `~/.local/bin` and the detected Homebrew prefix's `bin` and `sbin`
directories to PATH. Without Homebrew, it uses standard platform locations
(`/opt/homebrew/bin` and `/usr/local/bin` on macOS; `/home/linuxbrew/.linuxbrew/bin`
and `/usr/local/bin` on Linux). Nonexistent directories are ignored. Additional
installation directories can be supplied using `shell_extra_bin_paths`.
Existing PATH entries are retained without adding duplicates.

Fish loads `00-workstation-path.fish` before its tool integrations. Bash and Zsh
source `workstation-bootstrap/path.sh` under `terminal_config_root` through managed
blocks in `.bashrc`, the first existing Bash login file (`.bash_profile`,
`.bash_login`, then `.profile`; otherwise a new `.profile`), `.zshrc`, and
`.zprofile`. Zsh honors an exported `ZDOTDIR`; set `shell_zdotdir` explicitly if
it is assigned only inside `.zshenv`. Blocks are inserted before existing content;
subsequent user configuration can override PATH. Changed files are backed up.
Noninteractive scripts inherit PATH from their parent shell; this does not edit
system-wide profiles or force initialization for every script.

This makes executables such as `git`, `fzf`, `zoxide`, `bat`, `fd`, `rg`, `tree`,
and `jq` available across shells. Fish retains the existing prompt and navigation
integrations; Bash and Zsh receive PATH setup only. On Linux, package installation
is still external to these playbooks, and distribution-specific names such as
`batcat` or `fdfind` are not renamed.

## Managed files

The playbook manages these files under `$XDG_CONFIG_HOME/fish/conf.d`, falling back
to `~/.config/fish/conf.d`:

- `00-workstation-path.fish` (generated PATH setup)
- `git-abbreviations.fish`
- `mise.fish`
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
| `terminal_search_path` | Managed executable directories followed by current `PATH` | Tool discovery and task execution path |
| `shell_home` | Current user's home | Home for Bash startup files and `.local/bin`; override for temporary validation |
| `shell_zdotdir` | Exported `ZDOTDIR` or `shell_home` | Directory for Zsh startup files |
| `shell_extra_bin_paths` | `[]` | Additional absolute executable directories for all three shells |

Example using an existing Linux Ghostty configuration:

```sh
ansible-playbook -i localhost, terminal.yml \
  -e 'ghostty_config_path=/home/username/.config/ghostty/config'
```

For isolated validation, override `shell_home` and `shell_zdotdir` as well as
`terminal_config_root` and `ghostty_config_path` so all startup files stay under
temporary directories.

The optional mise snippet also checks `~/.local/bin/mise`; activation makes mise
and its selected tools available in interactive Fish sessions and updates tools
when changing directories. `terminal.yml` does not install mise, and the snippet
does nothing when it is absent; `macos.yml` installs it by default.

## Development

Check playbook syntax:

```sh
ansible-playbook -i localhost, terminal.yml --syntax-check
ansible-playbook -i localhost, macos.yml --syntax-check
ansible-playbook -i localhost, shell-paths.yml --syntax-check
```

Fish snippets are syntax-checked before installation. The current playbook has
been validated on macOS with Ansible Core 2.15.13 and Fish 4.9.3, including a fresh
check-mode run without configuration writes, migration in a temporary directory,
persistent Fisher metadata, fzf bindings, preservation of an additional plugin,
and a second apply with zero changes. Ghostty settings and the legacy fzf backup
were also checked. Linux execution has not yet been validated.

`macos.yml` has been validated on macOS with Ansible Core 2.15.13 using a
temporary Homebrew stand-in: missing-package installation, optional casks,
preservation of unrelated packages, empty package lists, check mode with and
without Homebrew, and a second apply with zero changes. The real Homebrew
installer and real package installation have not been exercised by these tests.

Run the isolated shell startup checks with:

```sh
python3 tests/check-shell-paths.py /path/to/ansible-playbook
```

These checks use temporary startup files and stand-in executables. Validated on
macOS with Fish, Bash, and Zsh, including interactive and Bash/Zsh login shells,
a minimal inherited PATH, directories containing spaces and quotes, backup and
content preservation, and idempotence. This is not Linux execution validation.

## Planned scope

- Linux package installation
- Editor configuration
- Development runtimes and toolchains
- Fonts and terminal themes
- Platform-specific workstation settings
