"""PII-masking log filter: emails, phone numbers, card-like numbers and bearer tokens never reach logs/traces (E4).
Works with %-style records (uvicorn's access log passes its fields as `record.args`): arguments are masked one by one and never discarded."""
import logging
import re

from mcp_servers.common import mask_pii

_TOKEN = re.compile(r"(Bearer\s+)[\w.\-]+|(KGAT_|gsk_|sk-)[\w\-]+", re.I)


def _clean(v):
    return _TOKEN.sub(r"\1[redacted]", mask_pii(v)) if isinstance(v, str) else v


class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _clean(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_clean(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _clean(v) for k, v in record.args.items()}
        return True


def setup():
    f = PIIFilter()
    for h in logging.getLogger().handlers + logging.getLogger("uvicorn.access").handlers + logging.getLogger("uvicorn.error").handlers:
        h.addFilter(f)
    logging.getLogger().addFilter(f)
