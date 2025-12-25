#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping Application Services...${NC}"

# Kill any running start.sh processes
echo -e "${GREEN}Killing start.sh processes...${NC}"
pkill -f "start.sh" 2>/dev/null

# Kill ADW webhook server
echo -e "${GREEN}Killing ADW webhook server...${NC}"
pkill -f "trigger_webhook.py" 2>/dev/null

# =============================================================================
# CUSTOMIZE PORTS FOR YOUR PROJECT
# =============================================================================
# Add or modify the ports based on your application
# Common ports:
#   3000    - Node.js/Express/React
#   5173    - Vite
#   8000    - FastAPI/Django
#   8001    - ADW webhook server
#   8080    - Alternative HTTP
#   5432    - PostgreSQL
#   6379    - Redis
#   27017   - MongoDB

echo -e "${GREEN}Killing processes on common development ports...${NC}"
# Modify this list based on your application's ports
lsof -ti:3000,5173,8000,8001,8080 | xargs kill -9 2>/dev/null

# =============================================================================
# ADD CUSTOM CLEANUP FOR YOUR PROJECT
# =============================================================================
# If your application requires additional cleanup, add it here
# Examples:
#   - Killing specific process names: pkill -f "your-process-name"
#   - Removing temporary files: rm -rf /tmp/your-app-*
#   - Stopping Docker containers: docker-compose down

echo -e "${GREEN}✓ Services stopped successfully!${NC}"
