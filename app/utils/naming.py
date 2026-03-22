from __future__ import annotations

import re
import secrets
import string
from datetime import datetime

SAFE_PREFIX_PATTERN = re.compile(r"[^a-zA-Z0-9_]+")


def random_name_with_timestamp(prefix: str, random_length: int = 6) -> str:
    """
    Generate random name using a prefix and datetime suffix.
    Format: <prefix>_<random>_<YYYYMMDDHHMMSS>
    """
    clean_prefix = SAFE_PREFIX_PATTERN.sub("_", prefix.strip()).strip("_") or "file"
    random_part = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(random_length))
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{clean_prefix}_{random_part}_{timestamp}"
