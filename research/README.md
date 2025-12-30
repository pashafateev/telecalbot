# Phase 0: Cal.com API Research

This directory contains the research script to validate Cal.com API behavior before implementation.

## Purpose

The `calcom_api_validator.py` script tests critical unknowns about the Cal.com API:

1. **Event Type ID Discovery** - Find the ID for the "step" event type
2. **Availability Endpoint** - Verify slot fetching works correctly
3. **Placeholder Email** - Test if Cal.com accepts emails like `telegram-user-123@telecalbot.local`
4. **Rate Limits** - Check for rate limit headers and constraints
5. **Meeting Method Field** - Identify how to specify Telegram as meeting method

## Running the Research Script

1. **Install dependencies**:
   ```bash
   pip install -r research/requirements.txt
   ```

2. **Ensure .env is configured**:
   - `CALCOM_API_KEY` - Your Cal.com API key
   - `CALCOM_EVENT_SLUG` - Event slug (default: "step")
   - `CAL_API_VERSION` - API version (default: "2024-08-13")

3. **Run the script**:
   ```bash
   python research/calcom_api_validator.py
   ```

## Output

The script will:
- Print a detailed summary of findings to stdout
- Save results to `research/api_research_results.json`
- Create a test booking (if placeholder email test runs)

**IMPORTANT**: If a test booking is created, check your Google Calendar to verify it appears!

## What to Do After

1. Review the printed summary
2. Check `api_research_results.json` for raw data
3. Update `.env` with the discovered `CALCOM_EVENT_TYPE_ID`
4. Make implementation decisions based on findings:
   - If placeholder email works → Email collection is OPTIONAL
   - If placeholder email fails → Email collection is REQUIRED
   - Use documented rate limits or fallback to 60 req/min

## Expected Results

### Success Case
```
✅ Event Type ID found
✅ Availability endpoint working
✅ Placeholder email accepted (or rejected with clear decision)
✅ Rate limits documented (or use conservative ceiling)
```

### Critical Failure
```
❌ Event Type ID not found
```
This is a blocker - verify the event slug exists in your Cal.com account.

## Next Steps

Once research is complete:
- Update `.env` with `CALCOM_EVENT_TYPE_ID`
- Document email handling decision
- Proceed to Phase 1 (Project Foundation)
