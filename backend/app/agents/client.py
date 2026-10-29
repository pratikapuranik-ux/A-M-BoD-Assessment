"""Provider client (Anthropic or Microsoft Foundry), error classes and the tenacity retry wrapper."""
from __future__ import annotations

import threading
import time
from typing import Callable

import structlog
from tenacity import Retrying, retry_if_exception, stop_after_attempt

from . import settings as cfg

try:
    import anthropic
except ImportError:  # research_enabled() reports it
    anthropic = None

log = structlog.get_logger("agents.client")
PROVIDER = cfg.PROVIDER


class ResearchError(RuntimeError):
    """A research step failed; the message is fit to show the user."""


class ResearchRefused(ResearchError):
    """Claude (and the server-side fallback model) declined the request."""


class ResearchInvalid(ResearchError):
    """The model's output still broke the rules after the allowed fix rounds."""

    def __init__(self, msg, problems=()):
        super().__init__(msg); self.problems = list(problems)


_CLIENT, _CLIENT_LOCK = None, threading.Lock()


def research_enabled() -> tuple[bool, str]:
    if anthropic is None:
        return False, "Install the anthropic package on the server (pip install anthropic) to enable live research."
    if cfg.FOUNDRY:
        try: anthropic.AnthropicFoundry()
        except (anthropic.AnthropicError, ValueError, OSError) as e: return False, f"The Microsoft Foundry client could not be configured ({e})."
        return True, "Live research is enabled (Microsoft Foundry)."
    try:
        c = anthropic.Anthropic()
    except anthropic.CredentialsError as e:
        return False, f"The server's Anthropic credentials could not be loaded ({e}). Set ANTHROPIC_API_KEY on the server to enable live research."
    except (anthropic.AnthropicError, ValueError, OSError) as e:
        return False, f"The Anthropic client could not be configured ({e})."
    if c.api_key or c.auth_token or c.credentials:
        return True, "Live research is enabled."
    return False, "Set ANTHROPIC_API_KEY on the server to enable live research."


def get_client():
    """The shared SDK client. Tests replace this function with a scripted fake."""
    global _CLIENT
    if anthropic is None:
        raise ResearchError("The anthropic package is not installed on the server.")
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = anthropic.AnthropicFoundry(max_retries=4) if cfg.FOUNDRY else anthropic.Anthropic(max_retries=4)
    return _CLIENT


def _err(e):
    return getattr(e, "message", None) or str(e)


def is_busy(e) -> bool:
    """A rate limit, overload, server or connection error: worth waiting for."""
    if anthropic is None: return False
    kinds = tuple(getattr(anthropic, n) for n in ("RateLimitError", "OverloadedError", "InternalServerError", "APIConnectionError") if hasattr(anthropic, n))
    if isinstance(e, kinds): return True
    body = getattr(e, "body", None); err = body.get("error") if isinstance(body, dict) else None
    return isinstance(e, anthropic.APIStatusError) and (e.status_code in cfg.BUSY_STATUS or (isinstance(err, dict) and err.get("type") == "overloaded_error"))


def api_error(e, label, model=None) -> ResearchError:
    """Maps an SDK error to a ResearchError with a user-facing message."""
    P, M = cfg.PROVIDER, model or cfg.MODEL
    if isinstance(e, anthropic.AuthenticationError): return ResearchError(f"The server's {P} API key was rejected. Check the key in .env.")
    if isinstance(e, anthropic.PermissionDeniedError): return ResearchError(f"The {P} API key lacks access to {M} or to web search ({_err(e)}).")
    if isinstance(e, anthropic.NotFoundError): return ResearchError(f"The model {M} is not available to this {P} key ({_err(e)}).")
    if isinstance(e, anthropic.RateLimitError): return ResearchError(f"The {P} rate limit was reached; try again in a few minutes.")
    if isinstance(e, anthropic.BadRequestError): return ResearchError(f"The {label} request was rejected: {_err(e)}")
    if is_busy(e) and not isinstance(e, anthropic.APIConnectionError): return ResearchError(f"{P} stayed busy during {label} after {len(cfg.RETRY_WAITS)} retries; try again shortly.")
    if isinstance(e, anthropic.APIStatusError): return ResearchError(f"The {P} API returned an error during {label} ({e.status_code}); try again shortly.")
    if isinstance(e, anthropic.APIConnectionError): return ResearchError(f"Could not reach the {P} API during {label}; check the server's network.")
    return ResearchError(f"The {P} API failed during {label}: {_err(e)}")


def call_with_retry(fn: Callable, label: str, stop: threading.Event | None = None, say: Callable[[str], None] | None = None):
    """Calls fn(); while the service is busy waits cfg.RETRY_WAITS between attempts (tenacity), waking early if `stop` is set.
    The last busy error is re-raised for the caller to map with api_error."""
    waits = tuple(cfg.RETRY_WAITS)

    def wait(rs): return waits[min(rs.attempt_number, len(waits)) - 1]

    def sleep(seconds):
        if stop is not None: stop.wait(seconds)
        else: time.sleep(seconds)

    def before_sleep(rs):
        w = waits[min(rs.attempt_number, len(waits)) - 1]
        log.warning("provider_busy", step=label, provider=cfg.PROVIDER, error=_err(rs.outcome.exception()), retry_in=w)
        if say: say(f"{cfg.PROVIDER} is busy, retrying in {w}s")

    retrying = Retrying(stop=stop_after_attempt(len(waits) + 1), wait=wait, sleep=sleep, before_sleep=before_sleep,
                        retry=retry_if_exception(is_busy), reraise=True)
    return retrying(fn)
