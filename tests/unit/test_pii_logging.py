import io
import logging

from apps.api.logging_config import PIIFilter
from mcp_servers.common import mask_pii


def test_ipv4_and_ports_are_not_masked_as_phone_numbers_but_phones_are():
    assert mask_pii("172.18.0.1:60702") == "172.18.0.1:60702"
    assert "[phone]" in mask_pii("call +92 300 1234567 now") and "[email]" in mask_pii("mail bob@example.com")


def test_filter_works_with_uvicorn_style_args_and_redacts_tokens():
    buf = io.StringIO(); h = logging.StreamHandler(buf); h.addFilter(PIIFilter())
    log = logging.getLogger("t"); log.handlers = [h]; log.propagate = False; log.setLevel(logging.INFO)
    log.info('%s - "%s %s HTTP/%s" %d', "172.18.0.1:60702", "GET", "/api/x?email=a@b.co", "1.1", 200)      # uvicorn access-log shape
    log.info("auth header was Bearer abc123.def and key gsk_SECRET123")
    out = buf.getvalue()
    assert "172.18.0.1:60702" in out and "a@b.co" not in out and "200" in out
    assert "abc123" not in out and "gsk_SECRET123" not in out
