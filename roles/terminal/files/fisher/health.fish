# Print required plugins with missing manifest entries, metadata, or tracked files.
function workstation_pending_plugins --argument-names required_file
    set -l manifest
    if test -f $__fish_config_dir/fish_plugins
        set manifest (string match -rv '^\s*(#|$)' < $__fish_config_dir/fish_plugins)
    end
    for plugin in (string match -rv '^\s*(#|$)' < $required_file)
        set -l files_var _fisher_(string escape --style=var -- $plugin)_files
        if not contains -- $plugin $manifest; or not contains -- $plugin $_fisher_plugins; or not set -q $files_var\[1\]
            echo $plugin
            continue
        end
        for file in $$files_var
            set file (string replace --regex '^~/' "$HOME/" -- $file)
            if not test -e "$file"
                echo $plugin
                break
            end
        end
    end
end
