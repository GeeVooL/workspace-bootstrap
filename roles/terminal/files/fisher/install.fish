# Run in noninteractive Fish so Fisher's universal metadata persists.
# Arguments: apply, bootstrap function path, required plugin list.
set -l bootstrap $argv[2]
set -l required (string match -rv '^\s*(#|$)' < $argv[3])
set -l missing
for plugin in $required
    if not contains -- $plugin $_fisher_plugins
        set -a missing $plugin
    end
end

source $bootstrap; or exit 1
# fzf.fish supports noninteractive installation through its CI guard.
set -gx CI true
if set -q missing[1]
    fisher install $missing
end
# Fisher can report a download/conflict error without returning a failure status.
for plugin in $required
    contains -- $plugin $_fisher_plugins; or exit 1
end
test -f $__fish_config_dir/functions/fisher.fish; or exit 1
test -f $__fish_config_dir/functions/fzf_configure_bindings.fish; or exit 1
