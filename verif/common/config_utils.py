# verif/common/config_utils.py

from pyuvm import ConfigDB


def _cfg(component, key, default=None):
    """ConfigDB.get() wrapper with optional default.

    ConfigDB.get() signature is (requestor, inst_name, field_name) — no
    default arg. This wrapper normalises call sites that need a fallback.
    """
    try:
        return ConfigDB().get(component, "", key)
    except Exception:
        return default
