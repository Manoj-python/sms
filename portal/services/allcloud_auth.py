"""AllCloud `amx` HMAC authentication + resilient async LMS caller.

Two auth models are supported, selected per-call by whether a
`static_auth_header` is passed in:

- **UAT (dynamic, unverified)**: every call carries a freshly generated
  header `amx {appid}:{signature}:{nonce}:{timestamp}:{usertoken}`, built by
  POSTing to AllCloud's enterprise token service
  (https://prod-auth-ace.allcloud.app/enterprise-generatetoken) with headers
  appid / secrettoken / usertoken / url (EXACT target URL incl. query
  string) / X-API-Key. POST bodies participate in signing and MUST be
  minified JSON (`minify()`) — the identical minified string is sent in the
  actual call, or the signature breaks.
- **Prod (static, confirmed live)**: a single long-lived pre-issued
  `amx ...` string per host is sent as-is, no signing step — this is the
  model actually confirmed working for SMSquare (see config.py's
  `*_auth_header` properties). No minification needed; the body goes out as
  ordinary JSON.
"""

import asyncio
import json
import logging
import re
import time
from urllib.parse import urlsplit

import httpx

from portal.config import Settings, get_settings

logger = logging.getLogger("allcloud")


def minify(body: dict) -> str:
    """The one true serialization for POST bodies (token gen AND the call)."""
    return json.dumps(body, separators=(",", ":"))


class LMSError(Exception):
    """LMS call failed after retries (or returned a non-2xx we don't retry)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LMSUnavailable(LMSError):
    """Circuit breaker is open — LMS considered down; fail fast."""


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; half-opens after `cooldown`s."""

    def __init__(self, threshold: int = 5, cooldown: float = 30.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.cooldown:
            return True  # half-open: let one probe through
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._opened_at = time.monotonic()


_PII_QUERY_RE = re.compile(r"(Contact(Number)?|Mobile)=\d+", re.IGNORECASE)


def sanitize_endpoint(url: str) -> str:
    """Path + PII-stripped query, safe for lms_api_log (no mobile numbers)."""
    parts = urlsplit(url)
    query = _PII_QUERY_RE.sub(lambda m: m.group(0).split("=")[0] + "=***", parts.query)
    return parts.path + (("?" + query) if query else "")


class AllCloudAuth:
    """Generates the `amx` Authorization header via the enterprise token API
    and fires the actual LMS call with timeout, retry and circuit breaker."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.breaker = CircuitBreaker()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.lms_timeout_seconds)
        )
    async def warmup(self) -> None:
        """Pre-open HTTPS connection to AllCloud to avoid TLS handshake delay on first request."""
        try:
            # Use a lightweight HEAD request to the lookup base URL.
            # This opens the TCP/TLS connection without fetching heavy data.
            await self._client.head(self.settings.lookup_base_url)
            logger.info("LMS connection pool warmed successfully")
        except Exception as e:
            # Non-fatal: if warmup fails, the first user request will just be slightly slower.
            logger.warning("LMS warmup failed (harmless): %s", e)


    async def aclose(self) -> None:
        await self._client.aclose()

    # --- token generation -------------------------------------------------

    async def generate_auth_header(
        self, method: str, url: str, minified_body: str | None = None
    ) -> str:
        s = self.settings
        headers = {
            "appid": s.allcloud_appid,
            "secrettoken": s.allcloud_secret,
            "usertoken": s.allcloud_usertoken,
            "url": url,  # exact target URL including query string
            "X-API-Key": s.allcloud_apikey,
            "method": method.upper(),
        }
        kwargs: dict = {"headers": headers}
        if minified_body is not None:
            # POST APIs: the minified body is part of the signature input.
            headers["Content-Type"] = "application/json"
            kwargs["content"] = minified_body.encode("utf-8")

        resp = await self._client.post(s.allcloud_auth_url, **kwargs)
        resp.raise_for_status()
        return self._parse_token_response(resp, s)

    @staticmethod
    def _parse_token_response(resp: httpx.Response, s: Settings) -> str:
        """Token API schema is undocumented — parse tolerantly."""
        text = resp.text.strip().strip('"')
        if text.lower().startswith("amx "):
            return text  # service returned the ready-made header
        try:
            data = resp.json()
        except ValueError:
            data = None
        if isinstance(data, dict):
            # unwrap common envelopes
            for wrap in ("data", "Data", "result", "Result"):
                if isinstance(data.get(wrap), dict):
                    data = data[wrap]
                    break
            lower = {k.lower(): v for k, v in data.items()}

            def pick(*names):
                for n in names:
                    if n in lower and lower[n] not in (None, ""):
                        return str(lower[n])
                return None

            token = pick("token", "authorization", "authtoken", "hmactoken")
            if token and token.lower().startswith("amx "):
                return token
            sig = pick("signature", "sign", "hash") or token
            nonce = pick("nonce")
            ts = pick("timestamp", "time", "ts")
            if sig and nonce and ts:
                return (
                    f"amx {s.allcloud_appid}:{sig}:{nonce}:{ts}:{s.allcloud_usertoken}"
                )
        # last resort: 3 colon-separated fields (sig:nonce:ts)
        if text.count(":") == 2:
            return f"amx {s.allcloud_appid}:{text}:{s.allcloud_usertoken}"
        raise LMSError(f"Unrecognized token response shape: {text[:120]}")

    # --- resilient caller ---------------------------------------------------

    async def call_lms(
        self,
        method: str,
        url: str,
        body: dict | None = None,
        log_sink=None,
        static_auth_header: str | None = None,
    ) -> dict | list:
        """Generate token -> fire call. 10s timeout, up to 2 retries with
        backoff on transport errors / 5xx, circuit breaker on repeated failure.
        `log_sink(entry: dict)` receives a PII-free record for lms_api_log.

        `static_auth_header`: when given (prod), skip the per-call
        enterprise-generatetoken signing flow entirely and send this
        pre-issued `amx ...` string as-is — the confirmed-live model for
        SMSquare. The body is then sent as ordinary JSON (no minification;
        minification only matters for reproducing a signature)."""
        if not self.breaker.allow():
            self._log(log_sink, method, url, None, 0, False, "circuit_open")
            raise LMSUnavailable("LMS circuit breaker open")

        minified = minify(body) if (body is not None and not static_auth_header) else None
        last_err: Exception | None = None

        for attempt in range(self.settings.lms_max_retries + 1):
            start = time.monotonic()
            status: int | None = None
            try:
                auth = static_auth_header or await self.generate_auth_header(
                    method, url, minified
                )
                headers = {"Authorization": auth, "Accept": "application/json"}
                if static_auth_header and body is not None:
                    headers["Content-Type"] = "application/json"
                    resp = await self._client.request(
                        method, url, headers=headers, json=body
                    )
                elif minified is not None:
                    headers["Content-Type"] = "application/json"
                    resp = await self._client.request(
                        method, url, headers=headers, content=minified.encode("utf-8")
                    )
                else:
                    resp = await self._client.request(method, url, headers=headers)
                status = resp.status_code
                latency = int((time.monotonic() - start) * 1000)

                if 200 <= status < 300:
                    self.breaker.record_success()
                    self._log(log_sink, method, url, status, latency, True, "")
                    try:
                        return resp.json()
                    except ValueError:
                        return {"raw": resp.text}

                self._log(log_sink, method, url, status, latency, False, f"http_{status}")
                if status >= 500 and attempt < self.settings.lms_max_retries:
                    last_err = LMSError(f"LMS HTTP {status}", status)
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                self.breaker.record_failure()
                raise LMSError(f"LMS HTTP {status}", status)

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                latency = int((time.monotonic() - start) * 1000)
                self._log(log_sink, method, url, status, latency, False, type(exc).__name__)
                last_err = exc
                if attempt < self.settings.lms_max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue

        self.breaker.record_failure()
        raise LMSError(f"LMS unreachable after retries: {last_err}")

    @staticmethod
    def _log(sink, method, url, status, latency_ms, ok, error) -> None:
        entry = {
            "method": method.upper(),
            "endpoint": sanitize_endpoint(url),
            "status_code": status,
            "latency_ms": latency_ms,
            "ok": ok,
            "error": error,
        }
        logger.info("lms %(method)s %(endpoint)s -> %(status_code)s %(latency_ms)sms", entry)
        if sink:
            try:
                sink(entry)
            except Exception:  # logging must never break the call path
                logger.exception("lms_api_log sink failed")
