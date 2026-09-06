"""
Posts scheduled LinkedIn updates via LinkedIn's official Posts API.

Reads pending posts from posts.json, publishes any whose scheduled
time has passed and hasn't been posted yet, then updates posts.json
to mark them as posted (so they never post twice).

Requires: LINKEDIN_ACCESS_TOKEN environment variable (set as a
GitHub Actions secret — never hardcode it here).
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN")
POSTS_FILE = "posts.json"
LINKEDIN_VERSION = "202410"  # LinkedIn API version header, update periodically

if not ACCESS_TOKEN:
    print("ERROR: LINKEDIN_ACCESS_TOKEN environment variable not set.")
    sys.exit(1)


def get_person_urn():
    """Fetch the authenticated member's URN via the OpenID Connect userinfo endpoint."""
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        timeout=30,
    )
    resp.raise_for_status()
    sub = resp.json()["sub"]
    return f"urn:li:person:{sub}"


def publish_post(author_urn, text):
    """Publish a single text post to LinkedIn using the Posts API."""
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    body = {
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
    resp = requests.post(
        "https://api.linkedin.com/rest/posts", headers=headers, json=body, timeout=30
    )
    resp.raise_for_status()
    return resp.headers.get("x-restli-id", "unknown")


def main():
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)

    now = datetime.now(timezone.utc)
    author_urn = None
    changed = False

    for post in posts:
        if post.get("posted"):
            continue

        scheduled = datetime.fromisoformat(post["date"])
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)

        if scheduled <= now:
            if author_urn is None:
                author_urn = get_person_urn()
            try:
                post_id = publish_post(author_urn, post["text"])
                post["posted"] = True
                post["published_id"] = post_id
                changed = True
                print(f"Published post scheduled for {post['date']} -> {post_id}")
            except requests.exceptions.HTTPError as e:
                print(f"Failed to publish post scheduled for {post['date']}: {e}")
                print(f"Response body: {e.response.text}")

    if changed:
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
    else:
        print("No posts were due.")


if __name__ == "__main__":
    main()
