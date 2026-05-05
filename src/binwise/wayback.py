"""Wayback Machine Save Page Now wrapper."""

from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; binwise-archive/0.1)"
SPN_TIMEOUT = 200


class ArchiveError(Exception):
    """Save Page Now did not yield a snapshot URL."""


def save(url: str) -> str:
    """Trigger Wayback Save Page Now and return the dated snapshot URL.

    Wayback follows GET to /save/<url> with a redirect to the new snapshot
    URL on success. On rate-limit (429) or other transient failure, raises
    ArchiveError with a short, actionable message.
    """
    save_url = f"https://web.archive.org/save/{url}"
    req = Request(save_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=SPN_TIMEOUT) as resp:
            final = resp.url
            if "web.archive.org" in final and "/web/" in final:
                return final
            raise ArchiveError(f"unexpected response URL from SPN: {final}")
    except HTTPError as e:
        if e.code == 429:
            raise ArchiveError("rate limited (HTTP 429) — try again later") from e
        raise ArchiveError(f"HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        raise ArchiveError(f"network error: {e.reason}") from e
    except TimeoutError as e:
        raise ArchiveError("timed out waiting for snapshot") from e


__all__ = ["ArchiveError", "save"]
