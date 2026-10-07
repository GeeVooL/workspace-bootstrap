# Managed by Workstation Bootstrap.
# Shared picker appearance; Fisher's fzf.fish plugin supplies the bindings.
if status is-interactive
    if command -q fzf
        # Keep the picker compact, with the search field at the top.
        if not set -q FZF_DEFAULT_OPTS
            set -gx FZF_DEFAULT_OPTS '--height=40% --layout=reverse --border'
        end
    end
end
