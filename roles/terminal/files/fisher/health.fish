# Match Fisher's repository normalization without changing filesystem path casing.
function workstation_plugin_identity --argument-names plugin
    set plugin (string replace --regex '^~/' "$HOME/" -- $plugin)
    if test -e "$plugin"; or string match -qr '^(\/|\.\.?/)' -- $plugin
        path resolve -- $plugin
    else
        string lower -- $plugin
    end
end

# Print required plugins with missing manifest entries, metadata, or tracked files.
function workstation_pending_plugins --argument-names required_file
    set -l manifest
    if test -f $__fish_config_dir/fish_plugins
        for plugin in (string match -rv '^\s*(#|$)' < $__fish_config_dir/fish_plugins)
            set -a manifest (workstation_plugin_identity $plugin)
        end
    end
    for original in (string match -rv '^\s*(#|$)' < $required_file)
        set -l plugin (workstation_plugin_identity $original)
        set -l files_var _fisher_(string escape --style=var -- $plugin)_files
        if not contains -- $plugin $manifest; or not contains -- $plugin $_fisher_plugins; or not set -q $files_var\[1\]
            echo $original
            continue
        end
        for file in $$files_var
            set file (string replace --regex '^~/' "$HOME/" -- $file)
            if not test -e "$file"
                echo $original
                break
            end
        end
    end
end
