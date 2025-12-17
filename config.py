import os
from typing import Optional

BOT_TOKEN = ""
ADMIN_IDS = ""


def get_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default

    value_lower = value.lower().strip()
    if value_lower in ('true', 'yes', '1', 'on', 'y'):
        return True
    elif value_lower in ('false', 'no', '0', 'off', 'n'):
        return False

    return default


DEBUG: bool = get_bool(os.getenv('DEBUG'), False)