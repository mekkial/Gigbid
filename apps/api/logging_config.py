"""PII-masking log filter: emails, phone numbers, card-like numbers and bearer tokens never reach logs/traces (E4)."""
import logging
import re

from mcp_servers.common import mask_pii

_TOKEN = re.compile(r"(Bearer\s+)[\w.\-]+|(KGAT_|gsk_|sk-)[\w\-]+", re.I)


class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _TOKEN.sub(r"\1[redacted]", mask_pii(str(record.getMessage())))
        record.args = ()
        return True


def setup():
    f = PIIFilter()
    for h in logging.getLogger().handlers + logging.getLogger("uvicorn.access").handlers + logging.getLogger("uvicorn.error").handlers:
        h.addFilter(f)
    logging.getLogger().addFilter(f)
