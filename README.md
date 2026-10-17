# Workstation Bootstrap

Ansible configuration for development workstations on macOS and Linux. The current
setup installs VS Code, Zed, Typora, 1Password, and fonts on macOS and supported Linux distributions,
Fork, Little Snitch, and Apple container on supported Macs, and configures Fish, Starship, fzf, zoxide, and optional
Ghostty integration. The `utilities` application category installs terminal prerequisites on macOS.
Linux CLI prerequisites are still installed separately; Ghostty, Snap setup, Flatpak, and Flathub are managed.
Xcode and Apple Command Line Tools are available on macOS. Android device/development
tools are available on macOS and Linux, using official upstream downloads on Linux.

## Structure

This repository follows Ansible's [sample setup](https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html):
top-level orchestration playbooks, reusable roles, and an inventory containing
machine-profile variables. Platform-specific implementation is inside roles.

```text
ansible.cfg
site.yml                         # full setup: applications, then terminal
applications.yml                 # application installation only
terminal.yml                     # shell paths and terminal configuration
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
  managed_config/               # ownership checks and backed-up managed-file updates
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
- Fish 4+, Git, Starship, fzf 0.33+, zoxide, fd/fdfind 8.5+, bat/batcat 0.16+, curl, and tar for terminal configuration
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
Flatpak and its per-user Flathub remote are managed in the `desktop` category. The `package_managers` category sets up Snap before apps; Ghostty can otherwise use existing Snap or a Fedora COPR repository.

To bootstrap without an existing Homebrew installation, install Ansible into a
Python virtual environment first:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ansible-core
source .venv/bin/activate
ansible-playbook applications.yml --check --diff
ansible-playbook applications.yml --ask-become-pass
ansible-playbook shell-paths.yml --check --diff
ansible-playbook shell-paths.yml
```

Run from a native terminal on Apple Silicon. Homebrew bootstraps into the standard
architecture-specific prefix. Its official noninteractive installer may require
administrator authorization through the macOS password dialog and Apple's Command Line Tools
(`xcode-select --install`); do not run Ansible itself with sudo. The temporary
installer is removed afterward. Check mode reports missing Homebrew and packages
without downloading or running the installer.

`homebrew_search_path` controls discovery, and `macos_homebrew_executable` can select
an existing custom executable. Put package lists in the application catalog;
the former `macos_homebrew_formulae` and `macos_homebrew_casks` variables are now
internal inputs passed to the Homebrew role for each category.

## Usage

The `bootstrap` wrapper provides personal and workplace profiles on both macOS and
Linux. Run as your normal user with Ansible available on PATH:

```sh
./bootstrap personal --check --diff  # preview a personal Mac or Linux laptop
./bootstrap personal                 # apply
./bootstrap workplace --check --diff # preview a workplace laptop
./bootstrap workplace                # apply only workplace-permitted apps
```

The default runs `site.yml` (applications, then terminal configuration). Personal
mode explicitly sets `workplace_only=false`; workplace mode sets it to `true`.
The selected profile overrides inventory values and forwarded extra variables.
Platform detection and application installation remain in Ansible.

```sh
./bootstrap personal --apps-only
./bootstrap workplace --terminal-only
./bootstrap personal --exclude apple_development --exclude security
./bootstrap workplace --no-ask-become-pass # configured credentials/passwordless sudo
./bootstrap personal -- --limit localhost
./bootstrap --help
```

Application runs prompt for the privilege-escalation password, including previews;
terminal-only runs do not prompt by default. Repeat `--exclude` for multiple
categories; explicit exclusions replace inventory exclusions. Extra Ansible options
follow `--`. The wrapper runs from the repository root and selects its `ansible.cfg`,
even when invoked by absolute path elsewhere; paths in forwarded options are relative
to that root. It does not install Ansible or terminal prerequisites. On a fresh
machine, a full preview can report missing tools that an application apply would install.
Linux terminal prerequisites still need separate installation, as described above.

Direct Ansible commands remain supported. Run these from the repository root;
`ansible.cfg` selects the local inventory and roles directory. Preview, then apply:

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
All catalog categories are enabled by default. `package_managers` sets up Snap on supported Linux systems.
Currently `utilities` contains mise, fish, git, starship, fzf, zoxide, bat, fd,
ripgrep, tree, and jq on macOS; `development` contains Fork and Apple container,
and `editors` contains VS Code and Zed on both platforms. `writing` contains Typora
on both platforms; `security` contains 1Password on both platforms and Little Snitch on macOS.
`fonts` contains JetBrains Mono and JetBrains Mono Nerd Font on both platforms.
`desktop` enables Flatpak and Flathub on Linux. `apple_development` contains Xcode
and Apple Command Line Tools on macOS. `android_development` installs Android Platform
Tools, Android Command-line Tools, Temurin Java, scrcpy, JADX, and Oh My Android
on macOS. On Linux it installs Android Studio, Android Studio for Platform, SDK tools,
JADX, scrcpy, and Temurin from upstream. Oh My Android requires Apple Silicon and
macOS 26+. Apple container is skipped
on Intel Macs and macOS versions below 26. `utilities` also installs Ghostty on
macOS and supported Linux setups. Linux CLI utilities remain unmanaged.
Excluding a category skips installation;
it does not uninstall existing applications. `applications_setup_categories` lists categories
that run first when selected; the inventory sets it to `[package_managers]`.
Explicit category subsets must include `package_managers` if Snap setup is needed.
Other categories retain their requested order.

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

### Workplace selection

Install only apps explicitly approved in the catalog with:

```sh
ansible-playbook site.yml -e workplace_only=true
ansible-playbook applications.yml -e workplace_only=true --check --diff
```

`workplace_only` defaults to `false`, which includes all selected apps. Set it in
`host_vars/localhost.yml` for a work machine, or override it on the command line.
Workplace mode includes only entries with the YAML boolean `workplace_permitted: true`;
false, missing, string, or numeric approval values are skipped before discovery,
downloads, and installation.
Category selections and exclusions still apply. This filters application installation;
it does not uninstall existing apps or change terminal configuration and Fisher plugins.

The current catalog marks all apps except Fork, Typora, Little Snitch, 1Password, Xcode,
Apple Command Line Tools, and Oh My Android as permitted, according to this
repository's workplace policy. These labels record approval, not a licensing determination.
New apps require explicit approval to be included in workplace mode.

For `formulae`, `casks`, and Linux `packages`, use entries such as
`{name: git, workplace_permitted: true}`. Existing plain package strings still
work in normal mode, but are unapproved in workplace mode. For entries under
`apps`, add `workplace_permitted: true` beside `name` and `installer`.
Apple Container uses `{enabled: true, workplace_permitted: true}`; the legacy
`apple_container: true` form remains supported only in normal mode.

### Extending the catalog

Add categories such as `browsers` or `media` as catalog entries:

```yaml
applications_catalog:
  development:
    macos:
      casks:
        - {name: fork, workplace_permitted: false}
      formulae: []
      apple_container: {enabled: true, workplace_permitted: true}
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
`apps` entries may set `architectures` to skip unsupported CPUs with an explanatory
message. macOS entries may also set `minimum_macos_version`. Homebrew casks may use fully
qualified `owner/tap/token` names; installed cask tokens are recognized on reruns.

### Snap setup

`package_managers` contains Snap (`workplace_permitted: true`) on Linux. It runs
before other selected categories, including when the caller lists them in a different
order. The default personal and workplace profiles both include it:

```sh
./bootstrap workplace --apps-only --check
./bootstrap workplace --apps-only
# Skip setup and use existing package managers instead:
./bootstrap personal --exclude package_managers
# Set up only Snap:
./bootstrap workplace --apps-only -- -e '{"applications_enabled_categories":["package_managers"]}'
```

Setup supports Debian, Ubuntu, and conventional Fedora with systemd. It installs
the distribution's `snapd` package, enables and starts `snapd.socket`, starts the
daemon, and waits up to three minutes for initial seeding. Debian also installs
the `snapd` snap, following [Snap's Debian instructions](https://snapcraft.io/docs/tutorials/install-the-daemon/debian/).
Fedora gets the `/snap` symlink needed for classic snaps, following
[Snap's Fedora instructions](https://snapcraft.io/docs/tutorials/install-the-daemon/fedora/).
An unrelated file, directory, or symlink at `/snap` is preserved and reported as an
error. These paths are checked before installation. Service startup and the Debian
`snapd` snap apply to new or interrupted bootstrap-owned setup. A persistent marker
at `/var/lib/workstation-bootstrap/snapd-installing` is written before installing
the package and removed only after setup succeeds. A retry resumes unfinished
package installation, service startup, seeding, and Debian snap installation.
`applications_snap_setup_marker` overrides the marker path for isolated validation.
Existing installations without this marker retain their service enablement/running
state; rerunning does not reinstall snaps or start an intentionally stopped daemon.
Unrelated files and symlinks at the marker path are preserved and reported as errors.

This does not configure extra distribution repositories or bypass distro policies
that disable Snap. Other distributions, non-systemd hosts, and OSTree systems need
manual setup and exclusion of `package_managers`. Package and service errors stop
the run. A new login or reboot may be needed for desktop session paths to update;
Ansible uses explicit search paths for same-run installations.

With default setup enabled, Fedora uses Snap for Ghostty and Typora. Ghostty's COPR
fallback remains available when setup is excluded and Snap is absent. Approving the
Snap package manager does not approve every app available from the Snap Store.

### Ghostty installation

Ghostty is part of `utilities` and is workplace-permitted. Existing installations
are detected first and left in place. macOS uses the `ghostty` Homebrew cask.
Linux uses the following order:

1. If `snap` is installed, install `ghostty --classic` through Snap, including on Fedora.
2. Without Snap, Fedora with `dnf` or `dnf5` uses the `scottames/ghostty` COPR
   documented by [Ghostty](https://ghostty.org/docs/install/binary). The role
   downloads its repository configuration and installs the native package.
3. Other Linux systems without Snap fail with instructions to configure Snap or
   install Ghostty manually. Snap setup is handled separately by `package_managers`.

Snap service or installation failures are reported; they do not trigger COPR
fallback. Fedora Atomic/rpm-ostree installation is not supported by this fallback.
Package installation uses privilege escalation; pass `--ask-become-pass` if needed.
Check mode previews installation without downloading repository files or installing
packages. Installed packages are not upgraded by these tasks.

`configure_ghostty` controls terminal configuration only; it does not control app
installation. Use application-category selection to control installation.

### 1Password, fonts, Flatpak, and Apple developer tools

These categories are enabled by default; select a subset with, for example:

```sh
ansible-playbook applications.yml --ask-become-pass -e '{"applications_enabled_categories": ["security", "fonts", "desktop"]}'
```

- **1Password** (`security`, not workplace permitted): Homebrew cask on macOS.
  Linux x86-64 uses official Debian or RPM packages; Linux ARM64 uses the official
  archive, verifies its detached signature against the published signing fingerprint
  in an isolated keyring, then runs the vendor integration script under `/opt/1Password`.
  The role supplies the standard desktop-menu directory required by the vendor script.
  An incomplete-install marker permits retries of its own failed installations,
  even when the application command is already discoverable. An existing unmarked
  installation directory is preserved.
  See [1Password's Linux installation instructions](https://support.1password.com/install-linux/).
- **Fonts** (`fonts`, workplace permitted): JetBrains Mono and JetBrains Mono Nerd Font
  use Homebrew casks on macOS. Linux extracts upstream archives into
  `~/.local/share/fonts/<family>` and refreshes fontconfig. Override
  `applications_fonts_dir` to change the destination. Existing fonts are preserved;
  this does not select a font or alter Ghostty configuration. The plain font uses
  [JetBrains Mono 2.304](https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304);
  the patched family uses the latest [Nerd Fonts release](https://github.com/ryanoasis/nerd-fonts/releases/latest).
- **Flatpak + Flathub** (`desktop`, Linux only, workplace permitted): installs the
  distribution's `flatpak` package, adds the official Flathub remote for the current
  user, and preserves existing remotes, including disabled ones. This does not
  automatically approve or install apps from Flathub.
- **Xcode + Command Line Tools** (`apple_development`, macOS only, not workplace
  permitted): checks the selected developer directory for a compiler. If missing,
  requests [Apple's interactive installer](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools)
  and stops with instructions to complete it and rerun. Both standalone Command Line
  Tools and Xcode's default toolchain compiler layout satisfy this check. Xcode is
  installed through Homebrew's `mas` CLI using App Store ID `497799835`; sign into
  the App Store and obtain Xcode with your Apple
  Account first, as required by [mas](https://github.com/mas-cli/mas). First-launch
  setup and license acceptance remain interactive. The selected developer directory
  is not changed.

Homebrew itself requires Command Line Tools. On a fresh Mac, run only
`apple_development` first, complete Apple's installer if prompted, and rerun before
running the full catalog. Workplace filtering skips the explicit Apple tools entries;
it does not remove Homebrew's prerequisites or tools already installed.

### Android devices and emulators (macOS)

The `android_development` category is enabled in personal and workplace modes.
All Android tools and their installation prerequisites are workplace-permitted
except Oh My Android, which is included only in personal mode. It installs:

- [Android Platform Tools](https://formulae.brew.sh/cask/android-platform-tools):
  `adb` for USB/Wi-Fi debugging, logs, APK installation, file transfer, and shell
  access; `fastboot` for supported devices in bootloader mode.
- [scrcpy](https://github.com/Genymobile/scrcpy): screen mirroring and control of
  physical devices from the Mac.
- [Android Command-line Tools](https://formulae.brew.sh/cask/android-commandlinetools):
  `sdkmanager`, `avdmanager`, and other SDK utilities, without Android Studio.
- `temurin`: the Java runtime/JDK required by Android Command-line Tools, as
  recommended by the Homebrew cask. Its macOS package installer may request an
  administrator password.
- [JADX](https://formulae.brew.sh/formula/jadx): APK/resources inspection and Java
  decompilation. The `jadx` formula includes both `jadx` and `jadx-gui`; launch the
  graphical interface with `jadx-gui`. Homebrew also installs its OpenJDK dependency.
- [Oh My Android](https://github.com/ateymoori/oh-my-android): a native GUI for
  physical-device and emulator testing, installed from the author's
  `ateymoori/tap/oh-my-android` cask. Requires Apple Silicon and macOS 26 or later;
  unsupported Macs skip this app while installing the other Android tools.
  Existing app bundles are preserved. The app uses the command-line SDK above;
  emulator packages still need separate installation. MCP integration is optional
  and is not configured by this playbook.

Install only this category:

```sh
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["android_development"]}' --check --diff
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["android_development"]}'
```

Homebrew exposes `adb`, `fastboot`, `scrcpy`, `sdkmanager`, and `avdmanager` in its `bin` directory; run
`shell-paths.yml` if Homebrew is not already on your shell's PATH. See below for Linux.

For a physical device, enable Developer options and USB debugging, connect a
data-capable USB cable, unlock the device, and accept its RSA authorization prompt.
[macOS needs no additional USB driver](https://developer.android.com/studio/run/device).
Then use:

```sh
adb devices -l
adb -d shell
adb -d logcat
adb -d install /path/to/app.apk
scrcpy
```

`unauthorized` means the device still needs authorization. With several devices,
use `adb -s SERIAL ...` or `scrcpy -s SERIAL`. For wireless debugging on Android 11+,
enable Wireless debugging, select pairing by code, and run `adb pair IP:PAIRING_PORT`.
Enter the displayed code, then use `adb connect IP:DEBUGGING_PORT` if needed;
the pairing and debugging ports can differ. Both devices must be on the same network.
Bootloader access varies by vendor; installing these tools does not unlock or flash
a device.

The cask's default SDK root is `$(brew --prefix)/share/android-commandlinetools`.
Use [sdkmanager](https://developer.android.com/tools/sdkmanager) to inspect available
packages and review licenses:

```sh
sdkmanager --list
sdkmanager --licenses
# Optional emulator binaries:
sdkmanager --install "emulator"
```

Install the SDK Platform and Build-Tools versions required by your project using
the quoted package IDs from `sdkmanager --list`. For emulators, also install a
compatible system-image package (ARM64 on Apple Silicon, x86_64 on Intel), then
create a device with `avdmanager create avd --name dev-phone --package "SYSTEM_IMAGE_ID"`,
replacing `SYSTEM_IMAGE_ID` with that exact package ID. Launch it with
`"$(brew --prefix)/share/android-commandlinetools/emulator/emulator" -avd dev-phone`.
Google now documents `android sdk` as the successor to `sdkmanager`; the cask still
includes `sdkmanager` and `avdmanager` for these commands.

SDK licenses, additional SDK downloads, and virtual-device creation remain manual;
this playbook does not provision an emulator. NDK and CMake are only needed for
projects with native code. Homebrew owns the standalone Platform Tools; installing
`platform-tools` with `sdkmanager` creates a separate copy. Update each through its
owning manager and check `command -v adb` if versions differ. No `ANDROID_HOME` or
`JAVA_HOME` is overwritten. An existing `JAVA_HOME` must point to a compatible JDK;
project build JDK requirements may differ from those of the SDK utilities. Use
`--sdk_root=PATH` to select another SDK root, and `shell_extra_bin_paths` if you want
its `emulator` directory on PATH.

### Android tools on Linux

The same `android_development` category installs the following from their official
upstream sources, without Android packages from Ubuntu/Fedora repositories,
community PPAs/COPRs, Snap, or Flatpak:

| Component | Source |
| --- | --- |
| Android Studio | Current stable Linux archive and SHA-256 from [Google's download page](https://developer.android.com/studio) |
| Android Studio for Platform (ASfP) | [Google's stable `asfp-current-linux.deb`](https://developer.android.com/studio/platform/install) |
| ADB and fastboot | Current stable Platform Tools from Google's SDK repository metadata |
| SDK command-line tools | Current Linux archive and SHA-256 from Google's download page |
| JADX, including `jadx-gui` | Latest stable release of [skylot/jadx](https://github.com/skylot/jadx/releases) |
| scrcpy | Latest stable Linux static build from [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md) |
| Temurin JDK 25 LTS | Current Eclipse Adoptium release from its official API |

New installations resolve current upstream versions at apply time. Existing
installations are preserved, not automatically upgraded. Google publishes SHA-1
for Platform Tools; other archive downloads verify published SHA-256 digests.
ASfP's persistent `.deb` is downloaded over Google's HTTPS endpoint, which does
not publish a companion checksum. No downloads or metadata requests occur in
check mode. The distro package manager installs only archive prerequisites
(`tar`, `unzip`, and `xz`/`xz-utils`); it supplies no Android application binaries.

Install with:

```sh
ansible-playbook applications.yml --ask-become-pass -e '{"applications_enabled_categories": ["android_development"]}'
ansible-playbook shell-paths.yml
```

Archives are installed for the current user under
`~/.local/share/workstation-bootstrap/android` (`applications_android_dir`). Launchers
in `~/.local/bin` include `android-studio`, `asfp`, `adb`, `fastboot`, `sdkmanager`,
`avdmanager`, `jadx`, `jadx-gui`, and `scrcpy`. The dedicated Java runtime is selected
only inside the SDK/JADX launchers, leaving the shell's `JAVA_HOME` unchanged;
`applications_android_java_home` changes its destination. Existing destination
files, directories, and launcher symlinks are preserved. Existing bootstrap-owned
archives regain missing launchers on reruns without downloading the payload again.
An incomplete payload destination fails with instructions instead of overwriting user data. Ordinary desktop Linux
runtime libraries and glibc 2.31+ are required for the IDEs.

**Fedora ASfP:** the installer extracts the IDE payload from Google's `.deb` and
places it in the user installation directory. It does not run Debian maintainer
scripts, convert packages, or modify a package database. Google's post-install
script normally moves the same payload from `/tmp` into `/opt`; the extracted
IDE includes its own Java runtime. This portable extraction route also works on
Debian/Ubuntu, but differs from Google's documented `apt install ./asfp-current-linux.deb`
method. Launch with `asfp`. GUI operation on a real Fedora workstation has not been
validated; the installation path is covered by archive fixtures. The IDEs can create
desktop-menu entries through **Tools > Create Desktop Entry** after first launch.

Google's Linux IDEs and the selected upstream scrcpy binary require **x86-64**.
On ARM64, this category installs Temurin and JADX and reports the unsupported tools
as skipped; it does not substitute community ARM builds. Oh My Android is macOS-only.

The SDK root is `~/.local/share/workstation-bootstrap/android/sdk`. Select this
location in Android Studio to share the installed tools, then use the setup wizard
or SDK Manager for project-specific platforms, build tools, emulator binaries, and
system images. SDK licenses and AVD creation remain interactive. ASfP installation
does not download AOSP, configure its build dependencies, or create Cuttlefish VMs.

For USB access, Linux additionally needs suitable udev rules and user permissions;
see [Google's device setup instructions](https://developer.android.com/studio/run/device).
This category does not change group membership, USB rules, or KVM permissions.
Wireless debugging with `adb pair` and `adb connect` avoids USB permission setup.
If an existing `~/.local/bin` launcher was preserved, use the executables under the
installation directory or reconcile that launcher to select the new upstream tools.

### Typora and Little Snitch

Typora (`writing`) and Little Snitch (`security`) are enabled in normal mode and
excluded by `workplace_only=true`. Both use Homebrew casks on macOS:
[Typora](https://formulae.brew.sh/cask/typora) and
[Little Snitch](https://formulae.brew.sh/cask/little-snitch).
Existing application bundles are preserved. Little Snitch's first-run setup,
system-extension approval, and licensing remain manual.

On Linux, Typora uses the official 1.14.9 `.deb` downloads linked by its
[download page](https://typora.io/) for x86_64 and aarch64. Debian/Ubuntu are
preferred. On Fedora and other Linux distributions without a configured native
package, an existing Snap installation is used with `snap install typora` (without
classic confinement). If Snap is absent, Ansible prints a skip message and continues;
there is no need to exclude `writing`. Include `package_managers` to set up Snap first.
Snap service and installation errors fail the run instead of being treated as skips.
The [Snap version's sandbox limitations](https://support.typora.io/Snap/#limitations-for-the-snap-version)
affect filesystem access and external export/image-upload commands.

For Wayland, Typora documents the optional launch flags
`--enable-features=UseOzonePlatform --ozone-platform=wayland`. These are not added
automatically because the playbook does not manage Typora launchers.
The native package manager installs dependencies. This does not add Typora's
APT repository or update an existing installation; change the catalog URLs for
future fresh-install versions. Little Snitch has no Linux catalog entry.

```sh
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["writing", "security"]}'
```

### Editors

The `editors` category is enabled by default. Install only editors with:

```sh
ansible-playbook applications.yml -e '{"applications_enabled_categories": ["editors"]}'
```

On macOS, Zed uses the `zed` Homebrew cask. VS Code uses Microsoft's official
Universal `.dmg`: the role mounts it read-only, copies `Visual Studio Code.app`
into staging inside `/Applications`, validates its metadata and executable, and
publishes the complete bundle without replacing an existing destination. Failed
copies are cleaned up so retries can install again. It then unmounts and removes
the download. Override the destination with `applications_macos_install_dir`; the account must have write
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
Healthy detected editors are left untouched. A bootstrap-owned pending Zed
installation resumes vendor integration before clearing its recovery marker.
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

Use `host_vars/HOSTNAME.yml` for host-specific overrides. For the local inventory,
copy the commented example once, then uncomment the settings you need:

```sh
cp -n inventories/local/host_vars/localhost.yml.example inventories/local/host_vars/localhost.yml
```

Ansible loads `localhost.yml` automatically; Git ignores it. The `.example` file
is only a template and is not loaded by Ansible. Keep secrets outside the repository
and load them with `-e @/path/to/settings.yml`. Role defaults
provide fallback settings; inventory variables customize a profile; `-e` overrides
both. See [Ansible inventory documentation](https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_inventory.html).

### Apple container

The development category selects the `apple_container` role using
`macos.apple_container: {enabled: true, workplace_permitted: true}`. It installs the latest stable release from
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

The role uses Apple's documented signed-package installation method for both
installation and upgrades. After verifying the download, it checks for active
containers and refuses to interrupt them. For an idle running service, it runs
`container system stop`, installs the package, and restores the service with
`container system start --enable-kernel-install`, even after an installer failure.
A previously stopped service stays stopped during an upgrade. Current/newer
versions do not cause service changes unless a bootstrap-owned pending startup
needs recovery; downgrades are never automatic.

Fresh installs start the service by default, including downloading the default
Linux kernel if needed. Set `apple_container_start_after_install=false` to leave
it stopped. No workload containers are created. Temporary installers are removed
after success or failure. Avoid managing the same installation through Homebrew.

Role defaults include `apple_container_release_url`, `apple_container_executable`,
`apple_container_installer_executable`, `apple_container_pkgutil_executable`, and
`apple_container_launchctl_executable`. Their defaults use GitHub and Apple's standard
paths; overrides support trusted mirrors and isolated fixture validation.

## Shared CLI paths

`terminal.yml` invokes the shell-path role; `shell-paths.yml` can also be run independently on macOS or
Linux after installing utilities through the platform's package manager:

```sh
ansible-playbook shell-paths.yml
```

It adds `~/.local/bin` to PATH. On macOS, it also adds the detected Homebrew
prefix's `bin` and `sbin` directories, falling back to `/opt/homebrew/bin` and
`/usr/local/bin` when Homebrew is absent. Linux adds `/usr/local/bin` and does
not discover or manage Homebrew. Nonexistent directories are ignored. Additional
installation directories can be supplied using `shell_extra_bin_paths`.
Existing PATH entries are retained without adding duplicates.

Fish loads `00-workstation-path.fish` before its tool integrations. Bash and Zsh
source `workstation-bootstrap/path.sh` under `terminal_config_root` through managed
blocks in `.bashrc`, the first existing Bash login file (`.bash_profile`,
`.bash_login`, then `.profile`; otherwise a new `.profile`), `.zshrc`, and
`.zprofile`. Zsh honors an exported `ZDOTDIR`; set `shell_zdotdir` explicitly if
it is assigned only inside `.zshenv`. Missing targets and dangling links are skipped
during Bash selection. Unreadable files, directories, and traversal errors block
Bash's fallback to later profiles; these paths and symlinks are preserved, and
later login files are left untouched.
Blocks are inserted before existing content; subsequent user configuration can
override PATH. Changed files are backed up.
Noninteractive scripts inherit PATH from their parent shell; this does not edit
system-wide profiles or force initialization for every script.

This makes executables such as `git`, `fzf`, `zoxide`, `bat`, `fd`, `rg`, `tree`,
and `jq` available across shells. Fish retains the existing prompt and navigation
integrations; Bash and Zsh receive PATH setup only. On Linux, terminal dependency installation
is still external to these playbooks, and distribution-specific names such as
`batcat` and `fdfind` are accepted by prerequisite checks. Fish supplies `bat`
and `fd` aliases when the standard names are absent, preserving existing commands,
aliases, and functions. No executable symlinks are created.

## Managed files

The playbook manages these files under `$XDG_CONFIG_HOME/fish/conf.d`, falling back
to `~/.config/fish/conf.d`:

- `00-workstation-path.fish` (generated PATH setup)
- `tool-aliases.fish` (Fish aliases for Debian/Ubuntu executable names)
- `git-abbreviations.fish`
- `mise.fish`
- `starship.fish`
- `fzf-options.fish`
- `zoxide.fish`

Files beginning with `# Managed by Workstation Bootstrap.` receive updates with
timestamped backups. Exact copies of the previous repository snippets are adopted
and marked on the next run. Other existing contents and symlinks at those filenames
are preserved and reported, so a filename collision does not overwrite user settings.
The same ownership rule applies to the generated Fish and POSIX PATH files.
Bash/Zsh startup edits replace only this repository's marked block and back up the
file, preserving surrounding content. Symlinked and nonregular startup files are
left untouched. Ghostty launch configuration is left untouched if any discovered
configuration path is a symlink or nonregular file. Existing directory modes are not changed.
Other Fish files, including `config.fish`, remain untouched. Fisher continues to
manage and repair the required plugin code using its tracked-file metadata.

When enabled, the Ghostty task checks all documented locations in load order:

1. `$XDG_CONFIG_HOME/ghostty/config`
2. `$XDG_CONFIG_HOME/ghostty/config.ghostty`
3. On macOS, `~/Library/Application Support/com.mitchellh.ghostty/config`
4. On macOS, `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`

`XDG_CONFIG_HOME` defaults to `~/.config`; `terminal_config_root` overrides it for
this deployment. If any loaded file defines `command` or `initial-command`, nothing
is added. Files using `config-file` includes are also left alone because an included
file may define the launch command. Otherwise the Fish command is appended to the
last existing file only if it starts with `# Managed by Workstation Bootstrap.`,
with a backup. Unmarked files are preserved, including files containing only fonts
or themes; add the desired launch command yourself for those files. If no file
exists, the platform's `config.ghostty` is created with the managed marker
(macOS-specific directory on macOS, XDG directory on Linux). Fonts,
themes, key bindings, and existing file permissions are preserved.

`ghostty_config_path` explicitly selects a single custom file instead of discovery;
this is also useful for isolated tests. `ghostty_config_paths` can supply a custom
list in load order. Managed snippet files use mode `0644`; existing unmarked files
retain their contents and permissions.

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
| `ghostty_config_path` | Unset (discover all documented paths) | Optional single-file override |
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
does nothing when it is absent; `applications.yml` installs it by default on macOS.

## Development

Syntax-check all entry points:

```sh
ansible-playbook site.yml --syntax-check
ansible-playbook applications.yml --syntax-check
ansible-playbook terminal.yml --syntax-check
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
Linux routing fixtures use simulated facts. Real Homebrew downloads and host GUI
installation are not exercised.

## Planned scope

- Linux dependency installation and package-manager configuration
- Additional application categories for macOS and Linux
- Editor configuration
- Development runtimes and toolchains
- Additional fonts, themes, and operating-system settings

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
It also covers Typora and Little Snitch installation routes and workplace exclusions.

Run `python3 tests/check-ghostty.py` for offline Ghostty routing checks. Fake Snap,
DNF, RPM, and Homebrew commands verify source selection, existing installations,
check mode, failures without fallback, exclusions, and repeat-run idempotence.
Fedora facts are simulated; this suite does not exercise a real Snap daemon or COPR installation.

Run `python3 tests/check-workplace.py` for workplace-selection regression checks.
It replaces installer entry points with recording fixtures and tests approval
labels, legacy entries, category exclusions, check mode, invalid flag values,
and repeat-run idempotence. It installs no applications.

Run `python3 tests/check-platform-apps.py` for offline fonts, Flatpak/Flathub,
1Password, and Apple developer tool checks. It checks workplace filtering, check
mode, archive extraction, disabled remote repair, signature rejection, interactive
CLT handling, and zero changes on repeat. Package managers, signature verification,
and Apple services are simulated; no production apps are installed.
This suite has passed on macOS (Ansible Core 2.15.13) and Debian ARM64 in an
Apple Container (Ansible Core 2.19.11). ARM archive extraction is tested on Linux;
App Store, Homebrew, Flatpak, and native package installation remain fixture-based.

Run `python3 tests/check-bootstrap.py` for wrapper argument, platform, profile,
path handling, and exit-status checks using a recording Ansible fixture.

Run `python3 tests/check-snap-setup.py` for offline Snap setup tests covering
category ordering, workplace filtering, check mode, existing-service preservation, mount-path
preservation, setup-marker ownership, failure recovery, and repeat-run idempotence.
Package managers, Snap, and systemd are simulated; these checks do not validate
real daemon startup or snap mounts.

Run `python3 tests/check-tool-names.py` for alternate executable detection,
version checks, alias argument forwarding, and preservation of existing commands
and Fish functions. These checks use isolated executable fixtures.

Run `python3 tests/check-config-preservation.py` to verify managed-file adoption,
backed-up updates, unmarked files and symlinks, directory/file permissions, Ghostty
load order, legacy filenames, included configuration, and repeat-run idempotence.
Ghostty checks cover unmarked-file preservation, marked-file backups, and creation
of marked configurations. Editor checks also cover failed and invalid DMG copies,
retry installation, and preservation of destinations appearing during publication.

### Cross-platform audit (2026-10-08)

All ten portable regression suites passed on macOS, Ubuntu 26.04 ARM64, and Fedora
44 ARM64; the macOS integration suite also passed. Fresh Apple Containers ran real
installations of VS Code, Zed, JetBrains fonts, Flatpak/Flathub, and 1Password on
both Linux distributions, Typora on Ubuntu, and Ghostty via COPR on Fedora.
The combined application/terminal playbook installed real Fisher plugins and shell
configuration in the containers. Repeat applications and final check-mode runs
reported zero changes for the tested selections.

These minimal images do not boot systemd. Snap's real preflight correctly refused
them without changes; Snap package/service behavior was tested with fixtures.
Ubuntu's real run excluded `package_managers` and `utilities` (Ghostty needs Snap);
Fedora excluded `package_managers`, used COPR for Ghostty, and skipped Typora because
Snap was absent. GUI launches, macOS package installation, App Store operations,
and live Apple Container upgrades were not exercised. Package-manager dependencies
and vendor post-install hooks remain upstream behavior, beyond repository-managed
configuration. The local Mac was used only for isolated fixtures and container hosting.

Run `python3 tests/check-android.py` for offline macOS Android package selection,
platform guards, existing bundle preservation, fully qualified cask names, and
repeat-run checks. Run `python3 tests/check-android-linux.py` on Linux with Ansible,
GNU tar, gzip, xz, and unzip for upstream archive/checksum, ASfP payload extraction,
launcher argument handling, preservation, check mode, and repeat-run tests. These
use local fixture payloads; they do not launch the real Android GUIs.

The Android suites passed on macOS and Fedora 44 ARM64 in a temporary Apple
Container. Linux x86-64 routing used simulated facts and tiny fixture executables;
real upstream metadata resolution and the ASfP Debian control/payload layout were
checked separately. Real x86-64 GUI launches, USB devices, and KVM were not tested.

Run `python3 tests/check-install-recovery.py` for offline archive launcher recovery
checks, including check mode, argument forwarding, symlink and unmarked-payload
preservation, and repeat-run idempotence. `tests/check-platform-apps.py` also tests
ARM64 1Password recovery after its command becomes discoverable. On macOS that
fixture substitutes native tar for Ansible's GNU tar extraction backend.

### Installer recovery and preservation

Fresh Homebrew bootstrap requires Apple Silicon; existing Intel Homebrew installations
remain usable. Casks that require administrator access use a macOS password dialog
through a temporary `SUDO_ASKPASS` helper, because Ansible workers do not have a
controlling terminal. The password is not stored. For unattended installations set
`homebrew_sudo_askpass` to an existing trusted executable or configure passwordless
sudo. Ansible's `-K` password is not forwarded to Homebrew.

Apple Container records pending startup in `apple_container_recovery_marker` and
retries it even when the newest binary is already installed. Zed records interrupted
vendor installation in `applications_zed_marker`; an incomplete unmarked installation
is preserved and requires manual repair. Zed presence checks use executable payloads,
not desktop files or empty application directories. Font installation preserves each
existing destination, including dangling symlinks. Archive publication uses atomic
no-replace rename on macOS and Linux, failing if a destination appears concurrently.
Linux systems must provide libc `renameat2` support for archive publication.

Catalog platform definitions and collection types, installer/platform combinations,
and setup category references are validated before their corresponding work begins.
Native RPM installation explicitly enables local-package signature verification.
Fisher repair isolates the required repair request from unrelated manifest entries,
restores those entries on failure, and preserves local-path casing.

Run `python3 tests/check-review-regressions.py` in the Ansible Python environment
for offline signature-status field binding, atomic publication collisions, Zed
interrupted-install recovery, unmarked Zed preservation, and malformed catalog
checks. Signature verification uses synthetic GnuPG status records, not live keys.
