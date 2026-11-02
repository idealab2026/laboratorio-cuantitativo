"""Scan public files without committing the private identifiers being blocked."""
import html
import json
import os
from urllib.parse import unquote


def configured_terms(env=None):
    env = os.environ if env is None else env
    raw = env.get("IDEALAB_PUBLIC_DENY_TERMS_JSON", "")
    if not raw and env.get("IDEALAB_REQUIRE_PRIVATE_DENY_TERMS") != "true":
        return ()
    try:
        terms = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("Private publication guard is not configured") from None
    if (not isinstance(terms, list) or not 2 <= len(terms) <= 100 or
            any(not isinstance(x, str) or not 4 <= len(x.strip()) <= 160 for x in terms)):
        raise ValueError("Private publication guard is not configured")
    return tuple(x.strip().casefold() for x in terms)


def contains_private_term(text, terms):
    text = str(text)
    for _ in range(3):
        text = html.unescape(unquote(text)).replace("\\/", "/")
        if any(term in text.casefold() for term in terms):
            return True
    return False
