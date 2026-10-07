# Workstation Bootstrap

Ansible configuration for development workstations on macOS and Linux. The current
setup installs VS Code and Zed on macOS and Linux, Fork and Apple container on
supported Macs, and configures Fish, Starship, fzf, zoxide, and optional
Ghostty integration. The `utilities` application category installs terminal prerequisites on macOS.
Linux prerequisites are still installed separately.

## Structure

This repository follows Ansible's [sample setup](https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html):
top-level orchestration playbooks, reusable roles, and an inventory containing
machine-profile variables. Platform-specific implementation is inside roles.

```text
ansible.cfg
site.yml                         # full setup: applications, then terminal
applications.yml                 # application installation only
terminal.yml                     # shell paths and terminal configuration
macos.yml                        # macOS applications and shell paths
shell-paths.yml                  # shell paths only
inventories/local/
  hosts.yml                      # localhost in the workstations group
  group_vars/workstations.yml    # application catalog and profile settings
  host_vars/                     # optional per-machine overrides
roles/
  apple_container/               # latest signed upstream macOS installer
  applications/
    defaults/main.yml
    tasks/
      main.yml
      category.yml
      macos.yml
      linux.yml
  terminal/
    defaults/main.yml
    tasks/main.yml
    files/fish/                  # managed Fish snippets
    files/fisher/                # plugin manifest, installer, legacy migration
tests/validate.py                # macOS integration checks with temporary fixtures
```

Roles contain related tasks, defaults, and files. Add `templates/` when a component
needs generated configuration, and `handlers/` when changes require a follow-up
such as a service restart. Add other components as roles and invoke them from
function-focused playbooks imported by `site.yml`. No unused role directories or
custom module scaffolding are required.

## Requirements

- Ansible Core (validated with 2.15.13); no external collections are required
- A normal user account on macOS or Linux
- macOS Homebrew prerequisites (including Command Line Tools); Homebrew is bootstrapped when absent
- Fish 4+, Git, Starship, fzf 0.33+, zoxide, fd 8.5+, bat 0.16+, curl, and tar for terminal configuration
- Ghostty if configuring its Fish launch command

On macOS, install terminal prerequisites with:

```sh
brew install ansible fish git starship fzf zoxide fd bat
brew install --cask ghostty
```

On Linux, use the distribution's package manager or the tools' official installers.
Linux editors use official installers and native packages as described below. Native package
installation is also implemented, but package names must be supplied for the target distribution.
Linux package tasks use privilege escalation; pass `--ask-become-pass` if needed.
The Homebrew role preserves main’s noninteractive bootstrap behavior. Linux
repositories, Flatpak, and Snap are not managed yet.

To bootstrap without an existing Homebrew installation, install Ansible into a
Python virtual environment first:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ansible-core
source .venv/bin/activate
ansible-playbook macos.yml --check --diff
ansible-playbook macos.yml --ask-become-pass
```

Run from a native terminal on Apple Silicon. Homebrew bootstraps into the standard
architecture-specific prefix. Its official noninteractive installer may require
cached administrator authorization (`sudo -v`) and Apple's Command Line Tools
(`xcode-select --install`); do not run Ansible itself with sudo. The temporary
installer is removed afterward. Check mode reports missing Homebrew and packages
without downloading or running the installer.

`homebrew_search_path` controls discovery, and `macos_homebrew_executable` can select
an existing custom executable. Put package lists in the application catalog;
the former `macos_homebrew_formulae` and `macos_homebrew_casks` variables are now
internal inputs passed to the Homebrew role for each category.

## Usage

Run from the repository root as your normal user. `ansible.cfg` selects the local
inventory and roles directory. Preview, then apply:

```sh
ansible-playbook site.yml --check --diff
ansible-playbook site.yml --ask-become-pass
```

Run a component or exclude it:

```sh
ansible-playbook terminal.yml
ansible-playbook applications.yml --ask-become-pass
ansible-playbook site.yml --tags terminal
ansible-playbook site.yml --skip-tags applications
ansible-playbook site.yml -e configure_ghostty=false
```

`terminal.yml` now calls the terminal role; `applications.yml` replaces
`macos/fork.yml`. Fish source files moved from `files/fish/` to
`roles/terminal/files/fish/`. Use the configured inventory instead of `-i localhost,`
for execution: plays target the `workstations` group.

Reload Ghostty configuration and open a new tab after applying terminal changes.
The account login shell is unchanged. Check mode runs read-only prerequisite checks;
it does not install applications. Homebrew tasks install only missing packages, with automatic updates and upgrades disabled. Fork licensing is separate.

## Application categories and machine profiles

The local inventory's `group_vars/workstations.yml` defines the application catalog.
All catalog categories are enabled by default. Currently `utilities` contains mise, fish, git, starship, fzf, zoxide, bat, fd,
ripgrep, tree, and jq on macOS; `development` contains Fork and Apple container,
and `editors` contains VS Code and Zed on both platforms. Apple container is skipped
on Intel Macs and macOS versions below 26. Linux utilities remain unmanaged.
Excluding a category skips installation;
it does not uninstall existing applications.

Exclude a category for one run, or select an explicit subset:

```sh
ansible-playbook site.yml -e '{"applications_excluded_categories": ["development"]}'
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["development"]}'
ansible-playbook site.yml -e '{"applications_enabled_categories": []}'
```

For persistent choices, put the same variables in inventory group or host vars.
Category selection uses variables; the runnable tags are `applications` and
`terminal`, and `shell_paths`. `--tags development` is not a category selector. Unknown category
names fail validation rather than silently skipping work.

Add categories such as `browsers` or `media` as catalog entries:

```yaml
applications_catalog:
  development:
    macos:
      casks: [fork]
      formulae: []
      apple_container: true
    linux:
      packages: []
  browsers:
    macos:
      casks: []
      formulae: []
    linux:
      packages: []
```

Fill the lists with the packages you want; empty or omitted platform entries do
nothing and require no package manager. Fork has no official Linux release.
Catalog overrides replace the dictionary, so supply the complete desired catalog.

### Editors

The `editors` category is enabled by default. Install only editors with:

```sh
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["editors"]}'
```

On macOS, Zed uses the `zed` Homebrew cask. VS Code uses Microsoft's official
Universal `.dmg`: the role mounts it read-only, copies `Visual Studio Code.app`
into `/Applications`, then unmounts and removes the download. The destination can
be overridden with `applications_macos_install_dir`; the account must have write
access there. VS Code's command palette can install the `code` command in PATH.
See [Microsoft's macOS instructions](https://code.visualstudio.com/docs/setup/mac).

On Linux, Zed is installed by downloading and running the
[official install script](https://zed.dev/docs/linux) as the current user, with the
stable channel selected. The script installs into `~/.local/zed.app` and creates
the command and desktop launcher. Run `shell-paths.yml` if `~/.local/bin` is not
on PATH. Zed requires curl or wget, tar, and compatible runtime libraries and
Vulkan graphics; these prerequisites are not installed by this role.

Linux VS Code uses Microsoft's official architecture-specific `.deb` on
Debian/Ubuntu, or `.rpm` on Fedora/RHEL and openSUSE/SLE. Ansible installs the local
`.deb` with apt; RPM packages use the detected dnf, dnf5, yum, or zypper command
after importing Microsoft's signing key. Package installation uses privilege
escalation; pass `--ask-become-pass` if needed. Unsupported distribution families
fail clearly rather than falling back to a tarball. Both Linux installers support
x86_64 and aarch64. See [Microsoft's Linux instructions](https://code.visualstudio.com/docs/setup/linux).

Before installing, the role checks CLI commands and known installation locations,
including `/Applications`, `~/Applications`, the official Zed Linux install path,
and standard user/system Flatpak locations. VS Code also checks the Linux native
package database. Homebrew's inventory prevents reinstalling an existing Zed cask.
Detected editors are left untouched: no reinstall, upgrade, or settings changes.
For custom locations, extend `applications_search_path`, `applications_macos_dirs`,
or the catalog application's `paths` list. Check mode reports missing editors
without downloading or running installers. Temporary downloads are removed afterward.

The catalog's platform `apps` entries select `homebrew`, `dmg`, `script`, or
`native` installation. Existing `casks`, `formulae`, and Linux `packages` lists
continue to work unchanged. `applications_home`, `applications_bin_dir`,
`applications_search_path`, `applications_macos_dirs`, and
`applications_macos_install_dir` can be overridden for custom locations or fixtures.
Subsequent updates are left to the user, editor, or native package manager.

For another machine profile, copy `inventories/local/` to a named inventory and
adjust its group/host variables, then run `ansible-playbook -i inventories/PROFILE/hosts.yml site.yml`.
Keep `ansible_connection: local` when applying on that machine. The playbooks target
the `workstations` group, and roles detect the OS through gathered facts. Merely
naming a group `macos` does not detect the operating system.

Use `host_vars/HOSTNAME.yml` for host-specific overrides. Keep private settings
outside the repository and load them with `-e @/path/to/settings.yml`. Role defaults
provide fallback settings; inventory variables customize a profile; `-e` overrides
both. See [Ansible inventory documentation](https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_inventory.html).

### Apple container

The development category selects the `apple_container` role using
`macos.apple_container: true`. It installs the latest stable release from
[apple/container](https://github.com/apple/container) on Apple silicon with macOS
26 or later. Each run queries GitHub's latest-release API and compares it with
`/usr/local/bin/container --version`. Older installations are upgraded; current
or newer versions are left untouched. Unlike the Homebrew package tasks, this
component tracks upstream updates. GitHub access is needed even in check mode.

The role downloads the signed `.pkg`, checks its GitHub SHA-256 digest and macOS
package signature, and invokes `/usr/sbin/installer -pkg ... -target /` with
task-level `become: true`. Run Ansible as your normal account:

```sh
ansible-playbook applications.yml --ask-become-pass
```

`--ask-become-pass` (`-K`) prompts for your sudo password. Ansible uses it only for
tasks requesting privilege escalation; the password is not saved in this repository.
Do not run the whole playbook with sudo. Check mode previews the change without
downloading the package or requesting administrator access, so omit `-K` for previews.

Before an upgrade, stop a running service with `container system stop`; the role
fails with instructions instead of interrupting workloads. Temporary installer files
are removed after success or failure. The role does not start services, download a
Linux kernel, or create containers. After installation, run `container system start`
as your normal user when ready. Avoid managing the same installation through Homebrew.

Role defaults include `apple_container_release_url`, `apple_container_executable`,
`apple_container_installer_executable`, `apple_container_pkgutil_executable`, and
`apple_container_launchctl_executable`. Their defaults use GitHub and Apple's standard
paths; overrides support trusted mirrors and isolated fixture validation.

## Shared CLI paths

`terminal.yml` and `macos.yml` invoke the shell-path role; `shell-paths.yml` can also be run independently on macOS or
Linux after installing utilities through the platform's package manager:

```sh
ansible-playbook shell-paths.yml
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
integrations; Bash and Zsh receive PATH setup only. On Linux, terminal dependency installation
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

The required plugin list lives in `roles/terminal/files/fisher/fish_plugins`:

- [Fisher](https://github.com/jorgebucaran/fisher)
- [fzf.fish](https://github.com/PatrickF1/fzf.fish)

Ansible downloads a Fisher bootstrap function from the `4.4.8` release tag and installs
missing plugins. It checks required manifest entries, Fisher's universal metadata,
and every file recorded for each required plugin. Manifest matching ignores
capitalization, preserving Fisher's existing plugin spelling. Incomplete required plugins are
reinstalled; healthy plugins are left untouched. Installation and repair fetch the
plugin's configured upstream reference, so a repair can also update that plugin.
Additional Fisher plugins
are preserved. Fisher maintains the installed list in `fish/fish_plugins`, plugin
files in `fish/functions`, `fish/completions`, and `fish/conf.d`, and installation
metadata in Fish's universal variables. These generated files are not committed.
The bootstrap function is cached under `fish/.bootstrap`.
Set `fisher_bootstrap_url` to use a trusted bootstrap mirror (the default is the
version-tagged upstream function). Missing metadata with surviving, untracked files can
produce Fisher's file-conflict error; these files are not deleted automatically.

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

Picker appearance remains in `roles/terminal/files/fish/fzf-options.fish`. Plugin installation
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
ansible-playbook terminal.yml \
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

Syntax-check all entry points:

```sh
ansible-playbook site.yml --syntax-check
ansible-playbook applications.yml --syntax-check
ansible-playbook terminal.yml --syntax-check
ansible-playbook macos.yml --syntax-check
ansible-playbook shell-paths.yml --syntax-check
ansible-inventory --graph
ansible-playbook site.yml --list-tags
```

Validate configuration using `terminal_config_root` and `ghostty_config_path`
plus `shell_home` and `shell_zdotdir` overrides pointing into a temporary directory. Verify the files, preservation of
unrelated Ghostty settings, backups, and zero changes on a second apply. Package
behavior must be tested with temporary fixtures unless live installation is
explicitly requested. Check both component tags and category exclusions.

On macOS with the requirements installed, run `python3 tests/validate.py` using
the Python environment that provides Ansible. The suite uses a temporary Homebrew
executable and temporary configuration paths, checks inventory overrides, category
exclusions, tags, check mode, backups, and repeat-run idempotence. It leaves logs in
the temporary directory printed at completion.

Validated on macOS with Ansible Core 2.15.13 and Fish on the local Mac.
Linux routing with an empty catalog is checked using simulated facts; native Linux
package installation and real Homebrew downloads have not been tested.

## Planned scope

- Linux dependency installation and package-manager configuration
- Additional application categories for macOS and Linux
- Editor configuration
- Development runtimes and toolchains
- Fonts, themes, and operating-system settings

Run `python3 tests/check-shell-paths.py /path/to/ansible-playbook` to validate
Fish, Bash, and Zsh startup behavior with temporary homes. The integration suite
seeds healthy Fisher metadata and placeholder files to avoid downloads; it does not exercise real
plugin downloads or Homebrew bootstrapping. On a fresh machine, check mode can
report missing terminal tools that the preceding application play would install.

Run `python3 tests/check-apple-container.py` with Ansible on PATH for offline Apple
container installer checks. A temporary HTTP server supplies release metadata and
packages; fake installer/signature/service commands run without sudo. These cover
install, upgrade, idempotence, check mode, platform/category skips, running-service
protection, checksum/signature failures, and cleanup. The general validation suite
disables Apple container because it is covered by this dedicated suite. Actual Apple
package installation, sudo escalation, and Linux execution are not exercised.

Run `python3 tests/check-fisher-repair.py` for offline repair regression checks.
These use a local bootstrap fixture to verify manifest-only recovery, missing-file
repair, failure detection, preservation of extra plugins, check mode, and idempotence.

Run `python3 tests/check-editors.py` in the Ansible Python environment for offline
editor checks. It validates official installer routing, both Linux architecture
selections, existing commands and bundles, package database detection, category
exclusion, check mode, and zero changes on repeat. The suite runs copied roles
with local download fixtures, simulated disk mounts and package managers, and
substitutes privileged apt/key modules in that copy. Actual Linux package
installation, GUI launches, and upstream downloads are not tested by this suite.
