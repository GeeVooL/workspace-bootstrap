# Repository guidance

## Purpose and structure

Workstation Bootstrap provides Ansible configuration for development machines on
macOS and Linux. The current scope is the terminal and shell; package installation,
editors, and development toolchains are planned. Read README.md for current behavior.

- Keep playbooks focused on orchestration. Store static configuration in `files/`
  and use separate templates when values need substitution.
- Fish snippets live in `files/fish/` and are deployed by `terminal.yml`.
- Use Fish abbreviations for Git shortcuts. Preserve Oh My Zsh meanings where
  supported, especially `gd` for unstaged diffs and `gds` for staged diffs.
- Keep documentation factual and repository-focused. Update it when managed files,
  requirements, configuration variables, or supported behavior change.

## Configuration changes

- Support macOS and Linux; detect executable paths and make platform differences
  explicit. Do not hardcode a particular user's home directory.
- Keep Ansible tasks idempotent and compatible with check mode. Prefer built-in
  modules and preserve backups when replacing existing configuration contents.
- Preserve unrelated settings, especially Ghostty fonts, themes, and key bindings.
  Keep Ghostty configuration optional and leave the account login shell unchanged
  unless the requested task explicitly includes changing it.
- Repository edits do not imply deployment to the current machine. Validate in a
  temporary configuration directory unless applying live changes was requested.
- Do not commit credentials, machine history, runtime caches, or generated backups.

## Validation

- Run `ansible-playbook -i localhost, terminal.yml --syntax-check` after playbook edits.
- Run `fish --no-execute` on each changed Fish snippet.
- For changes to deployment behavior, test against temporary paths using
  `terminal_config_root` and `ghostty_config_path` overrides. Check the resulting
  files and confirm a second apply reports zero changes.
- Use focused behavior checks for Git shortcut changes; verify staged versus
  unstaged diffs and argument handling when relevant.
- Report which platforms were actually tested. Do not infer Linux validation from
  a successful macOS run.
