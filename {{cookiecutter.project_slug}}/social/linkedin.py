"""
Daily Scout — LinkedIn Social Distribution Module
Posts curated content to LinkedIn personal profile via Posts API.

Auth: OAuth 2.0 (Share on LinkedIn product)
Scopes: w_member_social, openid
Token: stored in LINKEDIN_ACCESS_TOKEN env var (GitHub Secret)
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger("daily-scout.linkedin")

# ── Config ───────────────────────────────────────────────────────────
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN")  # format: "urn:li:person:XXXXXX"
LINKEDIN_API_VERSION = "202503"  # LinkedIn monthly API version

POSTS_API_URL = "https://api.linkedin.com/rest/posts"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def get_author_urn() -> str | None:
    """
    Resolve author URN from token if LINKEDIN_PERSON_URN is not set.
    Uses the OpenID Connect userinfo endpoint.
    """
    if LINKEDIN_PERSON_URN:
        urn = LINKEDIN_PERSON_URN
        # Normalize: ensure it has the urn:li:person: prefix
        if not urn.startswith("urn:li:person:"):
            urn = f"urn:li:person:{urn}"
        return urn

    if not LINKEDIN_ACCESS_TOKEN:
        logger.error("No LINKEDIN_ACCESS_TOKEN configured")
        return None

    try:
        resp = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            sub = data.get("sub")
            if sub:
                urn = f"urn:li:person:{sub}"
                logger.info(f"Resolved author URN: {urn}")
                return urn
        logger.error(f"Failed to resolve URN: HTTP {resp.status_code} — {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Error resolving author URN: {e}")
        return None


def post_text(text: str, dry_run: bool = False) -> dict:
    """
    Publish a text-only post to LinkedIn personal profile.

    Args:
        text: The post content (max ~3000 chars for good rendering)
        dry_run: If True, validates everything but doesn't POST

    Returns:
        dict with keys: success (bool), post_id (str|None), error (str|None), dry_run (bool)
    """
    result = {"success": False, "post_id": None, "error": None, "dry_run": dry_run}

    # ── Validate ──
    if not LINKEDIN_ACCESS_TOKEN:
        result["error"] = "LINKEDIN_ACCESS_TOKEN not configured"
        logger.error(result["error"])
        return result

    author_urn = get_author_urn()
    if not author_urn:
        result["error"] = "Could not resolve LinkedIn author URN"
        logger.error(result["error"])
        return result

    if not text or not text.strip():
        result["error"] = "Post text is empty"
        logger.error(result["error"])
        return result

    # LinkedIn soft limit: ~3000 chars render well, hard limit ~2500-3000 for text posts
    if len(text) > 3000:
        logger.warning(f"Post text is {len(text)} chars — may be truncated by LinkedIn")

    # ── Build payload ──
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
    }

    logger.info(f"LinkedIn post prepared: {len(text)} chars, author={author_urn}")
    logger.info(f"Preview (first 200 chars): {text[:200]}...")

    # ── Dry run: stop here ──
    if dry_run:
        result["success"] = True
        result["dry_run"] = True
        logger.info("DRY_RUN — post NOT sent to LinkedIn API")
        return result

    # ── POST to LinkedIn ──
    try:
        resp = requests.post(
            POSTS_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            # LinkedIn returns the post URN in x-restli-id header
            post_id = resp.headers.get("x-restli-id", "unknown")
            result["success"] = True
            result["post_id"] = post_id
            logger.info(f"LinkedIn: posted successfully! ID={post_id}")
        elif resp.status_code == 401:
            result["error"] = "LinkedIn: 401 Unauthorized — token expired or invalid"
            logger.error(result["error"])
        elif resp.status_code == 403:
            result["error"] = "LinkedIn: 403 Forbidden — missing w_member_social scope"
            logger.error(result["error"])
        elif resp.status_code == 422:
            result["error"] = f"LinkedIn: 422 Unprocessable — {resp.text[:300]}"
            logger.error(result["error"])
        elif resp.status_code == 429:
            result["error"] = "LinkedIn: 429 Rate limited — try again later"
            logger.error(result["error"])
        else:
            result["error"] = f"LinkedIn: HTTP {resp.status_code} — {resp.text[:300]}"
            logger.error(result["error"])

    except requests.Timeout:
        result["error"] = "LinkedIn: request timed out"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = f"LinkedIn: connection error — {e}"
        logger.error(result["error"])

    return result


def post_with_article(text: str, article_url: str, article_title: str = "",
                      article_description: str = "", dry_run: bool = False) -> dict:
    """
    Publish a text post with an article link attachment (renders as link preview).
    Great for driving traffic back to the newsletter LP or specific articles.

    Args:
        text: The post content
        article_url: URL to attach (will render as link preview card)
        article_title: Optional title for the article card
        article_description: Optional description for the article card
        dry_run: If True, validates but doesn't POST
    """
    result = {"success": False, "post_id": None, "error": None, "dry_run": dry_run}

    if not LINKEDIN_ACCESS_TOKEN:
        result["error"] = "LINKEDIN_ACCESS_TOKEN not configured"
        logger.error(result["error"])
        return result

    author_urn = get_author_urn()
    if not author_urn:
        result["error"] = "Could not resolve LinkedIn author URN"
        logger.error(result["error"])
        return result

    # ── Build payload with article ──
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "article": {
                "source": article_url,
                "title": article_title or article_url,
                "description": article_description or "",
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
    }

    logger.info(f"LinkedIn article post: {len(text)} chars + article={article_url}")

    if dry_run:
        result["success"] = True
        result["dry_run"] = True
        logger.info("DRY_RUN — article post NOT sent to LinkedIn API")
        return result

    try:
        resp = requests.post(
            POSTS_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            post_id = resp.headers.get("x-restli-id", "unknown")
            result["success"] = True
            result["post_id"] = post_id
            logger.info(f"LinkedIn: article posted! ID={post_id}")
        else:
            result["error"] = f"LinkedIn: HTTP {resp.status_code} — {resp.text[:300]}"
            logger.error(result["error"])

    except Exception as e:
        result["error"] = f"LinkedIn: error — {e}"
        logger.error(result["error"])

    return result
