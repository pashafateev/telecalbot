#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Application...${NC}"

# Get the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

# =============================================================================
# CUSTOMIZE THIS SECTION FOR YOUR PROJECT
# =============================================================================

# Check for required environment files
# Uncomment and modify as needed for your project:
# if [ ! -f "$PROJECT_ROOT/app/.env" ]; then
#     echo -e "${RED}Warning: No .env file found${NC}"
#     echo "Please create app/.env with required configuration"
#     exit 1
# fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"

    # Kill all child processes
    jobs -p | xargs -r kill 2>/dev/null

    # Wait for processes to terminate
    wait

    echo -e "${GREEN}Services stopped successfully.${NC}"
    exit 0
}

# Trap EXIT, INT, and TERM signals
trap cleanup EXIT INT TERM

# =============================================================================
# START YOUR APPLICATION
# =============================================================================
# Replace the examples below with commands to start your actual application

echo -e "${YELLOW}⚠️  This is a template start script${NC}"
echo -e "${YELLOW}   Customize this file to start your specific application${NC}"
echo ""
echo -e "${GREEN}Example configurations:${NC}"
echo ""
echo -e "  ${BLUE}Web App (Frontend + Backend):${NC}"
echo "    cd \"\$PROJECT_ROOT/app/server\" && npm start &"
echo "    cd \"\$PROJECT_ROOT/app/client\" && npm run dev &"
echo ""
echo -e "  ${BLUE}FastAPI + React:${NC}"
echo "    cd \"\$PROJECT_ROOT/app/server\" && uv run python server.py &"
echo "    cd \"\$PROJECT_ROOT/app/client\" && npm run dev &"
echo ""
echo -e "  ${BLUE}CLI Application:${NC}"
echo "    cd \"\$PROJECT_ROOT/app\" && python main.py"
echo ""
echo -e "  ${BLUE}Single Backend:${NC}"
echo "    cd \"\$PROJECT_ROOT/app\" && npm start"
echo ""
echo -e "${YELLOW}Uncomment and modify the section below to start your app:${NC}"
echo ""

# =============================================================================
# UNCOMMENT AND CUSTOMIZE FOR YOUR PROJECT
# =============================================================================

# Example: FastAPI + React
# echo -e "${GREEN}Starting backend server...${NC}"
# cd "$PROJECT_ROOT/app/server"
# uv run python server.py &
# BACKEND_PID=$!
# sleep 3
# if ! kill -0 $BACKEND_PID 2>/dev/null; then
#     echo -e "${RED}Backend failed to start!${NC}"
#     exit 1
# fi
#
# echo -e "${GREEN}Starting frontend server...${NC}"
# cd "$PROJECT_ROOT/app/client"
# npm run dev &
# FRONTEND_PID=$!
# sleep 3
# if ! kill -0 $FRONTEND_PID 2>/dev/null; then
#     echo -e "${RED}Frontend failed to start!${NC}"
#     exit 1
# fi
#
# echo -e "${GREEN}✓ Services started successfully!${NC}"
# echo -e "${BLUE}Frontend: http://localhost:5173${NC}"
# echo -e "${BLUE}Backend:  http://localhost:8000${NC}"
# echo ""
# echo "Press Ctrl+C to stop all services..."
#
# # Wait for user to press Ctrl+C
# wait

# For now, just wait
echo -e "${YELLOW}Update this script with your start commands, then run it again.${NC}"
sleep 2
