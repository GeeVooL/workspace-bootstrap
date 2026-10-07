# Run in noninteractive Fish so Fisher's universal metadata persists.
# Arguments: check|apply, bootstrap function path (unused for check), required list.
source (path dirname (status filename))/health.fish; or exit 1
set -l bootstrap $argv[2]
set -l missing (workstation_pending_plugins $argv[3])
if test "$argv[1]" = check
    if set -q missing[1]
        printf '%s\n' $missing
    end
    exit 0
end
test "$argv[1]" = apply; or exit 1

source $bootstrap; or exit 1
# fzf.fish supports noninteractive installation through its CI guard.
set -gx CI true
if set -q missing[1]
    # Fisher reinstalls registered plugins and installs unregistered ones.
    # Pass only damaged/missing required plugins, never update unrelated plugins.
    fisher install $missing
end
# Fisher can report a download/conflict error without returning a failure status.
set -l remaining (workstation_pending_plugins $argv[3])
if set -q remaining[1]
    printf 'Fisher plugins still incomplete: %s\n' $remaining >&2
    exit 1
end
