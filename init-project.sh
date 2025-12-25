#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   ADW Template - Project Initialization${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Get the current directory name
CURRENT_DIR=$(basename "$PWD")
PARENT_DIR=$(dirname "$PWD")

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    echo "This script should be run from the root of a cloned adw-template repository"
    exit 1
fi

# Get project name from argument or prompt
if [ -n "$1" ]; then
    PROJECT_NAME="$1"
    echo -e "${GREEN}Project name:${NC} $PROJECT_NAME"
else
    echo -e "${GREEN}Enter your new project name:${NC}"
    echo "(This will rename the directory and be used for git repository)"
    read -r PROJECT_NAME
fi

if [ -z "$PROJECT_NAME" ]; then
    echo -e "${RED}Error: Project name cannot be empty${NC}"
    echo "Usage: ./init-project.sh <project-name>"
    exit 1
fi

# Validate project name (no spaces, basic chars only)
if [[ ! "$PROJECT_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo -e "${RED}Error: Project name can only contain letters, numbers, hyphens, and underscores${NC}"
    exit 1
fi

# Check if target directory already exists
if [ -d "$PARENT_DIR/$PROJECT_NAME" ] && [ "$CURRENT_DIR" != "$PROJECT_NAME" ]; then
    echo -e "${RED}Error: Directory $PROJECT_NAME already exists in parent directory${NC}"
    exit 1
fi

# Get GitHub username/org (optional)
echo ""
echo -e "${GREEN}Enter your GitHub username or organization (optional):${NC}"
echo "(Press Enter to skip - you can add remote later)"
read -r GITHUB_USER

# Confirm
echo ""
echo -e "${YELLOW}This will:${NC}"
if [ "$CURRENT_DIR" != "$PROJECT_NAME" ]; then
    echo "  1. Rename directory: $CURRENT_DIR → $PROJECT_NAME"
    echo "  2. Remove the current git history"
    echo "  3. Initialize a new git repository"
else
    echo "  1. Remove the current git history"
    echo "  2. Initialize a new git repository"
fi
if [ -n "$GITHUB_USER" ]; then
    echo "  4. Set remote to: https://github.com/$GITHUB_USER/$PROJECT_NAME.git"
else
    echo "  4. Remove the git remote (you can add it later)"
fi
echo "  5. Copy .env.sample to .env"
echo "  6. Create initial commit"
echo "  7. Delete this init script"
echo ""
echo -e "${YELLOW}Continue? (y/n)${NC}"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Aborting."
    exit 0
fi

echo ""
echo -e "${BLUE}Starting initialization...${NC}"
echo ""

# Step 1: Remove git history
echo -e "${GREEN}[1/6]${NC} Removing template git history..."
rm -rf .git
echo "  ✓ Git history removed"

# Step 2: Initialize new git repo
echo -e "${GREEN}[2/6]${NC} Initializing new git repository..."
git init -b main > /dev/null 2>&1
echo "  ✓ New git repository initialized"

# Step 3: Set up .env file
echo -e "${GREEN}[3/6]${NC} Setting up environment file..."
if [ ! -f ".env" ]; then
    cp .env.sample .env
    echo "  ✓ Created .env from .env.sample"
    echo "  ${YELLOW}Remember to edit .env with your API keys!${NC}"
else
    echo "  ⊘ .env already exists, skipping"
fi

# Step 4: Delete init script before committing
echo -e "${GREEN}[4/6]${NC} Cleaning up initialization script..."
rm -- "$0"
echo "  ✓ init-project.sh deleted"

# Step 5: Create initial commit
echo -e "${GREEN}[5/6]${NC} Creating initial commit..."
git add .
git commit -m "Initial commit from adw-template

Project: $PROJECT_NAME
Template: https://github.com/pashafateev/adw-template" > /dev/null 2>&1
echo "  ✓ Initial commit created"

# Step 6: Set up remote (if provided)
echo -e "${GREEN}[6/6]${NC} Configuring git remote..."
if [ -n "$GITHUB_USER" ]; then
    git remote add origin "https://github.com/$GITHUB_USER/$PROJECT_NAME.git"
    echo "  ✓ Remote set to: https://github.com/$GITHUB_USER/$PROJECT_NAME.git"
    NEED_TO_CREATE_REPO=true
else
    echo "  ⊘ Skipped (no GitHub username provided)"
    NEED_TO_CREATE_REPO=false
fi

# Step 7: Rename directory (must be last, as it changes our location)
if [ "$CURRENT_DIR" != "$PROJECT_NAME" ]; then
    echo ""
    echo -e "${GREEN}Renaming directory:${NC} $CURRENT_DIR → $PROJECT_NAME"
    cd "$PARENT_DIR"
    mv "$CURRENT_DIR" "$PROJECT_NAME"
    cd "$PROJECT_NAME"
    echo "  ✓ Directory renamed"
    RENAMED=true
else
    echo ""
    echo -e "${YELLOW}Directory already named $PROJECT_NAME${NC}"
    RENAMED=false
fi

# Final instructions
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Initialization Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$RENAMED" = true ]; then
    echo -e "${YELLOW}Note: Directory has been renamed. Your current shell is still in the old path.${NC}"
    echo -e "${YELLOW}Run this to update your shell:${NC}"
    echo "  cd \"$PARENT_DIR/$PROJECT_NAME\""
    echo ""
fi

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. ${YELLOW}Edit .env${NC} and add your API keys:"
echo "   - ANTHROPIC_API_KEY"
echo "   - GITHUB_REPO_URL (https://github.com/$GITHUB_USER/$PROJECT_NAME)"
echo ""
echo "2. ${YELLOW}Set up your application${NC} in the app/ directory:"
echo "   rm app/README.md"
echo "   # Add your application code"
echo ""
echo "3. ${YELLOW}Customize scripts/start.sh${NC} for your project"
echo ""
if [ "$NEED_TO_CREATE_REPO" = true ]; then
    echo "4. ${YELLOW}Create the repository on GitHub:${NC}"
    echo "   gh repo create $GITHUB_USER/$PROJECT_NAME --public --source=. --remote=origin --push"
    echo "   # or create it manually at https://github.com/new"
    echo ""
else
    echo "4. ${YELLOW}Add a git remote and push:${NC}"
    echo "   git remote add origin <your-repo-url>"
    echo "   git push -u origin main"
    echo ""
fi
echo "5. ${YELLOW}Start building with ADW!${NC}"
echo "   - Create GitHub issues for features/bugs"
echo "   - Run: cd adws && uv run adw_plan_build.py <issue-number>"
echo "   - Or use continuous monitoring: uv run trigger_cron.py"
echo ""
echo -e "${GREEN}Happy coding!${NC}"
echo ""
