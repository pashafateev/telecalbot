"""Version management for ADW system."""

from datetime import datetime

# Version follows semantic versioning: MAJOR.MINOR.PATCH
VERSION = "1.0.0"

def get_version_info() -> dict:
    """Get version metadata for health checks and monitoring.

    Returns:
        Dictionary containing version string and timestamp.
    """
    return {
        "version": VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
