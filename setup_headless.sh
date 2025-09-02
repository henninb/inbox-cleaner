#!/bin/bash
# Setup script to configure headless environment for inbox-cleaner

echo "🔧 Setting up headless environment for inbox-cleaner..."

# Detect shell and configure accordingly
FISH_CONFIG_DIR="$HOME/.config/fish"
FISH_CONFIG_FILE="$FISH_CONFIG_DIR/config.fish"
BASHRC_FILE="$HOME/.bashrc"
PROFILE_FILE="$HOME/.profile"

# Function to add environment variable to bash-style files
add_headless_var_bash() {
    local file="$1"

    if [ -f "$file" ]; then
        if ! grep -q "export HEADLESS=true" "$file"; then
            echo "" >> "$file"
            echo "# Enable headless mode for inbox-cleaner (bypass keyring)" >> "$file"
            echo "export HEADLESS=true" >> "$file"
            echo "✅ Added HEADLESS=true to $file"
        else
            echo "ℹ️  HEADLESS variable already exists in $file"
        fi
    else
        echo "⚠️  $file not found, skipping"
    fi
}

# Function to add environment variable to fish config
add_headless_var_fish() {
    # Create fish config directory if it doesn't exist
    mkdir -p "$FISH_CONFIG_DIR"

    if [ -f "$FISH_CONFIG_FILE" ]; then
        if ! grep -q "set -gx HEADLESS true" "$FISH_CONFIG_FILE"; then
            echo "" >> "$FISH_CONFIG_FILE"
            echo "# Enable headless mode for inbox-cleaner (bypass keyring)" >> "$FISH_CONFIG_FILE"
            echo "set -gx HEADLESS true" >> "$FISH_CONFIG_FILE"
            echo "✅ Added HEADLESS=true to $FISH_CONFIG_FILE"
        else
            echo "ℹ️  HEADLESS variable already exists in $FISH_CONFIG_FILE"
        fi
    else
        # Create new fish config file
        echo "# Fish shell configuration" > "$FISH_CONFIG_FILE"
        echo "" >> "$FISH_CONFIG_FILE"
        echo "# Enable headless mode for inbox-cleaner (bypass keyring)" >> "$FISH_CONFIG_FILE"
        echo "set -gx HEADLESS true" >> "$FISH_CONFIG_FILE"
        echo "✅ Created $FISH_CONFIG_FILE with HEADLESS=true"
    fi
}

# Configure for fish shell
echo "🐟 Configuring for Fish shell..."
add_headless_var_fish

# Also configure bash files for compatibility
echo "🔄 Adding compatibility for bash/sh..."
add_headless_var_bash "$BASHRC_FILE"
add_headless_var_bash "$PROFILE_FILE"

echo ""
echo "🎉 Headless setup complete!"
echo ""
echo "To apply the changes:"
echo "  🐟 For Fish shell:"
echo "    - Option 1: Run 'source ~/.config/fish/config.fish' (current session)"
echo "    - Option 2: Start new fish terminal session"
echo "  🐚 For Bash/other shells:"
echo "    - Option 1: Run 'source ~/.bashrc' (current session)"
echo "    - Option 2: Log out and log back in"
echo ""
echo "Or run any inbox-cleaner command with manual override:"
echo "  🐟 Fish: set -gx HEADLESS true; python -m inbox_cleaner.cli list-filters"
echo "  🐚 Bash: export HEADLESS=true && python -m inbox_cleaner.cli list-filters"
echo ""
echo "✅ Your inbox-cleaner will now work without keyring prompts in both shells!"