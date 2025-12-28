#!/bin/bash
# Quick helper to apply ADW fixes to the template repo

TEMPLATE_PATH="$HOME/Documents/Programming/templates/adw-template"
CURRENT_PROJECT=$(basename "$PWD")

echo "🔧 ADW Template Updater"
echo "Template: $TEMPLATE_PATH"
echo "Current project: $CURRENT_PROJECT"
echo ""

# Check if template exists
if [ ! -d "$TEMPLATE_PATH" ]; then
    echo "❌ Template not found at $TEMPLATE_PATH"
    exit 1
fi

# Function to copy a file to template
copy_to_template() {
    local file=$1
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi

    echo "📋 Copying $file to template..."
    cp "$file" "$TEMPLATE_PATH/$file"
    echo "✅ Copied"
}

# Show menu
echo "What would you like to do?"
echo ""
echo "1) Copy adws/adw_plan_build.py to template"
echo "2) Copy all adws/*.py files to template"
echo "3) Open template directory in new terminal"
echo "4) Show git status of template"
echo "5) Custom file path"
echo ""
read -p "Choice [1-5]: " choice

case $choice in
    1)
        copy_to_template "adws/adw_plan_build.py"
        ;;
    2)
        echo "📋 Copying all adws/*.py files..."
        for file in adws/*.py; do
            if [ -f "$file" ]; then
                cp "$file" "$TEMPLATE_PATH/$file"
                echo "  ✅ $file"
            fi
        done
        ;;
    3)
        echo "📂 Opening template directory..."
        osascript -e "tell application \"Terminal\" to do script \"cd $TEMPLATE_PATH && pwd && ls -la\""
        ;;
    4)
        echo "📊 Template git status:"
        cd "$TEMPLATE_PATH" && git status
        ;;
    5)
        read -p "Enter file path (relative to project root): " custom_file
        copy_to_template "$custom_file"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Ask about committing
if [ $choice -eq 1 ] || [ $choice -eq 2 ] || [ $choice -eq 5 ]; then
    echo ""
    read -p "📝 Commit to template? [y/N]: " do_commit
    if [ "$do_commit" = "y" ] || [ "$do_commit" = "Y" ]; then
        read -p "Commit message: " commit_msg

        cd "$TEMPLATE_PATH"
        git add -A
        git commit -m "$commit_msg"

        read -p "🚀 Push to GitHub? [y/N]: " do_push
        if [ "$do_push" = "y" ] || [ "$do_push" = "Y" ]; then
            git push origin main
            echo "✅ Pushed to template repo"
        fi
    fi
fi

echo ""
echo "✨ Done!"
