# Initialize Starship for interactive Fish sessions.
if status is-interactive
    if command -q starship
        starship init fish | source
    end
end
