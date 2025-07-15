import requests
import logging
from datetime import datetime
from .base_client import BaseMediaClient
import json


class BlueskyClient(BaseMediaClient):
    def __init__(self, config):
        """
        Initialize with a config dictionary, e.g.:
        {
            "users": ["alice.bsky.social", "bob.bsky.social"]  # Simple format
        }
        OR categorized format:
        {
            "categories": {
                "tech": ["alice.bsky.social", "charlie.bsky.social"],
                "news": ["bob.bsky.social"]
            }
        }
        """
        super().__init__(config)
        self.base_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
        self.users = self.items

    def _get_items_from_config(self, config):
        """Extract users list from config for simple format."""
        return config.get("users", [])

    def _fetch_items_for_source(self, username, since_datetime):
        """Fetch posts from a specific Bluesky user."""
        posts = []
        try:
            # Format the since_datetime for the API
            since_iso = since_datetime.isoformat().replace("+00:00", "Z")

            # Prepare API request parameters
            params = {
                "actor": username,
                "limit": 50
            }

            # Make API request
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Process each post from the feed
            for feed_item in data.get("feed", []):
                post = feed_item.get("post", {})
                try:
                    # Extract post ID from URI
                    post_id = post["uri"].split("/")[-1]

                    # Parse creation time
                    created_at_str = post["record"]["createdAt"]
                    # Handle both .000Z and .123Z formats
                    if created_at_str.endswith("Z"):
                        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    else:
                        created_at = datetime.fromisoformat(created_at_str)

                    # Filter posts by time (API filtering might not be perfect)
                    # Debug: print dates for troubleshooting
                    # print(f"Post created: {created_at}, Since: {since_datetime}, Include: {created_at > since_datetime}")
                    if created_at > since_datetime:
                        # Get post text
                        full_text = post["record"]["text"]

                        # Create title (truncate if too long)
                        title = full_text
                        if len(title) > 100:
                            title = title[:100] + "..."

                        # Build post data
                        post_data = {
                            "id": post_id,
                            "title": title,
                            "url": f"https://bsky.app/profile/{username}/post/{post_id}",
                            "author": username,
                            "full_text": full_text,
                            "created_utc": created_at,
                            "reply_count": post.get("replyCount", 0),
                            "repost_count": post.get("repostCount", 0),
                            "like_count": post.get("likeCount", 0)
                        }
                        posts.append(post_data)
                except (KeyError, ValueError, IndexError) as e:
                    # Handle malformed posts gracefully
                    logging.warning(f"Skipping malformed post for user '{username}': {e}")
                    continue

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error fetching posts for user '{username}': {e}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error fetching posts for user '{username}': {e}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching posts for user '{username}': {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching posts for user '{username}': {e}")

        return posts