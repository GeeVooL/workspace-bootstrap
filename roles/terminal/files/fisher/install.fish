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
    # Hide the manifest during targeted repair: Fisher expands explicit installs
    # to every manifest entry when its universal registry has been lost.
    set -l manifest $__fish_config_dir/fish_plugins
    if test -L $manifest; or test -e $manifest; and not test -f $manifest
        echo 'Preserving nonregular Fisher manifest; repair it manually.' >&2
        exit 1
    end
    set -g workstation_manifest_backup (command mktemp "$manifest.workstation-XXXXXX"); or exit 1
    if test -f $manifest
        command cp -p $manifest $workstation_manifest_backup; or exit 1
    end
    function workstation_restore_manifest --on-event fish_exit
        if set -q workstation_manifest_backup; and test -f $workstation_manifest_backup
            command mv -f $workstation_manifest_backup $__fish_config_dir/fish_plugins
        end
    end
    printf '' >$manifest; or exit 1
    fisher install $missing
    # Restore exact original entries, including unrelated plugins and comments,
    # even when Fisher reports a conflict with a successful exit status.
    command mv -f $workstation_manifest_backup $manifest; or exit 1
    set -e workstation_manifest_backup
    set -l recorded
    for plugin in (string match -rv '^\s*(#|$)' <$manifest)
        set -a recorded (workstation_plugin_identity $plugin)
    end
    for plugin in $missing
        set -l identity (workstation_plugin_identity $plugin)
        if contains -- $identity $_fisher_plugins; and not contains -- $identity $recorded
            printf '\n%s\n' $plugin >>$manifest
            set -a recorded $identity
        end
    end
end
# Fisher can report a download/conflict error without returning a failure status.
set -l remaining (workstation_pending_plugins $argv[3])
if set -q remaining[1]
    printf 'Fisher plugins still incomplete: %s\n' $remaining >&2
    exit 1
end
