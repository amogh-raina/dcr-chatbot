"""Remove named authentication values from structured diagnostics, preserving applicant data."""
import re

_SECRET = re.compile(r'(?:^|[#_-])(authorization|api[_-]?key|(?:dcr[_-]?)?auth[_-]?token|token|password|secret)$', re.I)


def redact(value):
    if isinstance(value, dict):
        # Portal exports and the simulation API represent parameters as title/name + value objects.
        sensitive = any(_SECRET.search(str(value.get(key, ''))) for key in ('title', 'name', 'Name', 'Title'))
        return {key: '[REDACTED]' if _SECRET.search(str(key)) or (sensitive and key.lower() == 'value')
                else redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value
