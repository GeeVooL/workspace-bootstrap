# Learn visited directories and enable z / zi shortcuts.
if status is-interactive
    if command -q zoxide
        zoxide init fish | source
    end
end
