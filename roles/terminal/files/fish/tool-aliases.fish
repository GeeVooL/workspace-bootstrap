# Managed by Workstation Bootstrap.
# Debian and Ubuntu use different executable names for these tools.
if status is-interactive
    if not type -q bat; and command -q batcat
        alias bat batcat
    end
    if not type -q fd; and command -q fdfind
        alias fd fdfind
    end
end
