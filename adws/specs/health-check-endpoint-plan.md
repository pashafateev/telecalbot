# Feature: Health Check Endpoint

## Feature Description
Create a simple, lightweight health check endpoint that returns the bot's operational status, version information, and timestamp. This endpoint will provide a quick way to verify that the ADW system is running correctly without executing the comprehensive health check script. The endpoint should be optimized for monitoring systems and load balancers that need rapid health status responses.

## User Story
As a system administrator or monitoring service
I want to quickly check if the ADW bot is healthy and get its version information
So that I can monitor system availability, track deployments, and ensure the service is responding correctly without waiting for comprehensive health checks

## Problem Statement
The current ADW system has a `/health` endpoint in `trigger_webhook.py` that runs the comprehensive `health_check.py` script, which performs extensive checks (environment variables, git repository, GitHub CLI, Claude Code CLI). This comprehensive check:
- Takes significant time to execute (up to 30 seconds with timeout)
- May fail due to external dependencies being temporarily unavailable
- Is too heavy for frequent monitoring pings from load balancers or uptime services
- Doesn't provide quick version information for deployment tracking

There's a need for a lightweight health check that simply confirms the service is running and provides basic metadata without deep system validation.

## Solution Statement
Implement a new lightweight health check endpoint at `/health` (or `/health/quick`) in the webhook server that:
- Returns immediately (< 100ms response time)
- Provides HTTP 200 status when the service is running
- Includes version number from a version file or environment variable
- Includes timestamp of the current check
- Returns a simple JSON response format
- Can be called frequently by monitoring systems without performance impact

The existing comprehensive health check will remain available at a different endpoint (e.g., `/health/full`) for deep system validation.

## Relevant Files
Use these files to implement the feature:

- **trigger_webhook.py** (lines 125-199) - Contains the existing `/health` endpoint that runs the comprehensive health check script. This needs to be refactored to support both quick and full health checks.
  - Current implementation runs the `health_check.py` script via subprocess
  - Takes up to 30 seconds with timeout
  - Returns detailed health check results

- **health_check.py** (entire file) - The comprehensive health check script that validates all system components. This will be moved to a `/health/full` endpoint.
  - Checks environment variables, git repository, GitHub CLI, Claude Code CLI
  - Used for deep system validation

- **data_types.py** (lines 1-144) - Contains Pydantic models for type safety. We'll add new models for health check responses.
  - Already has `CheckResult` and `HealthCheckResult` in health_check.py
  - Need to add lightweight `QuickHealthResponse` model

- **utils.py** (lines 1-79) - Contains utility functions. We may add version retrieval function here.
  - Has ADW ID generation and logging utilities
  - Good place for version management utilities

### New Files

- **version.py** - New file to store and retrieve version information
  - Will contain `VERSION` constant
  - Function to get version metadata (version, build date, etc.)

- **pyproject.toml** or **setup.py** - Python project configuration file to manage version
  - Define project version in standard Python packaging format
  - Will be the single source of truth for version number

## Implementation Plan

### Phase 1: Foundation
1. Create version management infrastructure
   - Add `version.py` file with version constant
   - Consider using semantic versioning (e.g., "1.0.0")
   - Add function to retrieve version metadata including build timestamp

2. Add Pydantic models for health check responses
   - Create `QuickHealthResponse` model in `data_types.py` for lightweight checks
   - Include fields: status, version, timestamp, service_name
   - Ensure JSON serialization is properly configured

### Phase 2: Core Implementation
1. Refactor the existing `/health` endpoint in `trigger_webhook.py`
   - Rename current `/health` to `/health/full` to run comprehensive checks
   - Keep all existing functionality for deep validation

2. Implement new lightweight `/health` endpoint
   - Create simple endpoint that returns immediately
   - Include version information from `version.py`
   - Include current timestamp in ISO format
   - Return HTTP 200 with JSON response
   - Add minimal error handling

### Phase 3: Integration
1. Update documentation to reflect both endpoints
   - Document `/health` as quick health check
   - Document `/health/full` as comprehensive health check
   - Add usage examples in README.md

2. Test both endpoints work correctly
   - Verify quick endpoint responds in < 100ms
   - Verify full endpoint still works with comprehensive checks
   - Test JSON response format matches specification

## Step by Step Tasks

### Step 1: Create Version Management Module
- Create `version.py` file with VERSION constant set to "1.0.0"
- Add `get_version_info()` function that returns version metadata (version string, timestamp)
- Write docstrings explaining version management approach

### Step 2: Add Health Response Models
- Add `QuickHealthResponse` Pydantic model to `data_types.py`
- Include fields: status (str), version (str), timestamp (str), service (str)
- Add JSON configuration for proper serialization

### Step 3: Implement Lightweight Health Endpoint
- Rename existing `/health` endpoint to `/health/full` in `trigger_webhook.py`
- Create new `/health` endpoint that returns quick health status
- Import version information from `version.py`
- Generate current timestamp in ISO 8601 format
- Return `QuickHealthResponse` model as JSON with HTTP 200

### Step 4: Add Error Handling
- Wrap health endpoint in try-except to catch any unexpected errors
- Return HTTP 503 (Service Unavailable) if there's an internal error
- Log errors appropriately without exposing sensitive information

### Step 5: Update Server Startup Logging
- Update the startup print statements in `trigger_webhook.py` to include version
- Print both `/health` (quick) and `/health/full` (comprehensive) endpoints on startup

### Step 6: Write Unit Tests
- Create test file `test_health_endpoint.py` in appropriate test directory
- Test quick health endpoint returns 200 and correct JSON structure
- Test version information is included correctly
- Test timestamp is in valid ISO 8601 format
- Test comprehensive health endpoint still works

### Step 7: Integration Testing
- Start the webhook server locally
- Make GET request to `/health` and verify response time < 100ms
- Make GET request to `/health/full` and verify comprehensive check runs
- Verify both return proper JSON responses

### Step 8: Update Documentation
- Update README.md to document both health check endpoints
- Add examples of calling each endpoint with curl
- Explain when to use quick vs comprehensive health checks

### Step 9: Run Validation Commands
- Execute all validation commands to ensure feature works with zero regressions
- Fix any issues discovered during validation
- Verify all tests pass

## Testing Strategy

### Unit Tests
- **test_version_module**: Test `version.py` functions return correct data types and format
- **test_quick_health_response_model**: Test Pydantic model validation and JSON serialization
- **test_health_endpoint**: Test `/health` endpoint returns 200 with correct JSON structure
- **test_health_endpoint_fields**: Verify all required fields are present (status, version, timestamp, service)
- **test_health_endpoint_performance**: Verify response time is under 100ms
- **test_health_full_endpoint**: Test `/health/full` endpoint still runs comprehensive checks

### Integration Tests
- **test_webhook_server_startup**: Test server starts and both endpoints are available
- **test_health_endpoint_real_request**: Make actual HTTP request to `/health` and validate response
- **test_version_consistency**: Verify version matches across different parts of the system

### Edge Cases
- **Missing version file**: Test graceful handling if version.py is somehow missing (return "unknown")
- **Timestamp format**: Verify timestamp is always in valid ISO 8601 format
- **Concurrent requests**: Test multiple simultaneous health check requests don't cause issues
- **Invalid routes**: Test that similar routes like `/healths` or `/health/` return appropriate errors

## Acceptance Criteria
- [ ] New `/health` endpoint returns HTTP 200 when bot is healthy
- [ ] Response includes version number in semantic versioning format (e.g., "1.0.0")
- [ ] Response includes ISO 8601 formatted timestamp of the current check
- [ ] Response is in simple JSON format with keys: status, version, timestamp, service
- [ ] Response time is under 100ms (lightweight check)
- [ ] Existing comprehensive health check is preserved at `/health/full`
- [ ] Both endpoints are documented in README.md
- [ ] Unit tests pass with 100% success rate
- [ ] Integration tests verify real HTTP requests work correctly
- [ ] Server startup logs show both endpoint URLs
- [ ] Version number is manageable from a single source of truth

## Validation Commands
Execute every command to validate the feature works correctly with zero regressions.

```bash
# Start the webhook server in the background
cd /Users/pasha/Documents/Programming/projects/active/telecalbot/adws && uv run trigger_webhook.py &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Test quick health endpoint
curl -s http://localhost:8001/health | jq .

# Verify quick health endpoint returns 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health

# Test comprehensive health endpoint
curl -s http://localhost:8001/health/full | jq .

# Verify response time is fast (< 100ms)
time curl -s http://localhost:8001/health

# Kill the background server
kill $SERVER_PID
```

Additional validation:
- `cd /Users/pasha/Documents/Programming/projects/active/telecalbot/adws && uv run pytest tests/` - Run all tests if test directory exists
- Verify version number is displayed correctly in health response
- Verify timestamp is in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.microseconds)
- Verify all fields are present in JSON response: status, version, timestamp, service
- Verify server startup logs show both `/health` and `/health/full` endpoints

## Notes

### Version Management Strategy
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Consider using `importlib.metadata` to read version from `pyproject.toml` if available
- Fallback to hardcoded version in `version.py` if metadata not available
- Version should be bumped manually for each release

### Performance Considerations
- Quick health check should have no I/O operations
- No subprocess calls, no file reads (except one-time version import)
- Response should be near-instantaneous (< 10ms typical, < 100ms maximum)

### Monitoring Integration
- Quick health endpoint can be polled every 10-30 seconds by monitoring systems
- Comprehensive health endpoint should be called less frequently (every 5-10 minutes)
- Consider adding `/metrics` endpoint in future for Prometheus integration

### Future Enhancements
- Add `/health/ready` endpoint for Kubernetes readiness probes
- Add `/health/live` endpoint for Kubernetes liveness probes
- Include uptime duration in health response
- Add build/commit hash to version information
- Consider adding rate limiting to health endpoints if needed

### Alternative Endpoint Paths Considered
- Option 1: `/health` (quick) and `/health/full` (comprehensive) - **CHOSEN**
- Option 2: `/ping` (quick) and `/health` (comprehensive)
- Option 3: `/status` (quick) and `/health` (comprehensive)
- Reasoning: Using `/health` as the base path is most standard for health checks
