"""Small httpx + tenacity helpers for fetching and verifying public source URLs.

The research agents read the web through Claude's server-side web_search / web_fetch tools, so the pipeline itself makes no
direct fetches; these helpers are for source verification (is a cited URL reachable, what does it say) and for services
that need to pull a document by URL. Transient failures (timeouts, connection errors, 429 and 5xx) are retried with
exponential backoff.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

log = structlog.get_logger("services.sources")

USER_AGENT = "AM-Board-Assessment/1.0 (source verification)"
MAX_BYTES = 2_000_000
TIMEOUT = 20.0
BLOCKED_DOMAINS = ("facebook.com", "glassdoor.com", "indeed.com", "instagram.com", "linkedin.com", "medium.com",
                   "quora.com", "reddit.com", "tiktok.com", "twitter.com", "x.com")


class SourceError(RuntimeError):
    """A source could not be fetched; the message is fit to show the user."""


def _transient(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError): return e.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(e, (httpx.TimeoutException, httpx.TransportError))


def is_allowed(url: str) -> bool:
    """http(s) only, and not one of the domains the research prompts exclude."""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https") or not p.hostname: return False
    host = p.hostname.lower()
    return not any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


def _retrying():
    return retry(retry=retry_if_exception(_transient), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8), reraise=True)


def _get(url: str, client: httpx.Client | None, timeout: float) -> httpx.Response:
    def go(c: httpx.Client):
        r = c.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return r
    if client is not None: return _retrying()(go)(client)
    with httpx.Client() as c: return _retrying()(go)(c)


def fetch_text(url: str, *, max_bytes: int = MAX_BYTES, timeout: float = TIMEOUT, client: httpx.Client | None = None) -> str:
    """The page body as text (HTML tags stripped, whitespace collapsed), truncated to max_bytes of source."""
    if not is_allowed(url): raise SourceError(f"The source {url!r} is not an allowed public web address.")
    try:
        r = _get(url, client, timeout)
    except httpx.HTTPStatusError as e:
        raise SourceError(f"The source {url} returned HTTP {e.response.status_code}.") from e
    except httpx.HTTPError as e:
        raise SourceError(f"The source {url} could not be reached ({e.__class__.__name__}).") from e
    text = r.content[:max_bytes].decode(r.encoding or "utf-8", errors="replace")
    if "html" in r.headers.get("content-type", "").lower() or text.lstrip().lower().startswith(("<!doctype", "<html")):
        text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def url_reachable(url: str, *, timeout: float = TIMEOUT, client: httpx.Client | None = None) -> bool:
    """True if the URL answers with a non-error status (used to sanity-check cited sources); never raises."""
    if not is_allowed(url): return False
    try:
        _get(url, client, timeout)
        return True
    except httpx.HTTPError as e:
        log.info("source_unreachable", url=url, error=e.__class__.__name__)
        return False


def quote_in_text(excerpt: str, text: str) -> bool:
    """Whether a short verbatim excerpt appears in a page's text (case and whitespace insensitive)."""
    norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()
    return bool(norm(excerpt)) and norm(excerpt) in norm(text)
