# Managed by Workstation Bootstrap.
# Activate installed mise tools and directory-change hooks in interactive Fish.
if status is-interactive
    if command -q mise
        command mise activate fish | source
    else if test -x "$HOME/.local/bin/mise"
        "$HOME/.local/bin/mise" activate fish | source
    end
end
