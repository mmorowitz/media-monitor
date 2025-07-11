import praw
import logging
from datetime import datetime, timezone
from .base_client import BaseMediaClient

class RedditClient(BaseMediaClient):
    def __init__(self, config):
        """
        Initialize with a config dictionary, e.g.:
        {
            "client_id": "...",
            "client_secret": "...",
            "user_agent": "...",
            "subreddits": ["python", "learnprogramming"]  # Simple format
        }
        OR categorized format:
        {
            "client_id": "...",
            "client_secret": "...",
            "user_agent": "...",
            "categories": {
                "news": ["worldnews", "politics"],
                "tech": ["python", "learnprogramming"]
            }
        }
        """
        super().__init__(config)
        self.reddit = praw.Reddit(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            user_agent=config["user_agent"]
        )
        self.subreddits = self.items

    def _get_items_from_config(self, config):
        """Extract subreddits list from config for simple format."""
        return config.get("subreddits", [])

    def _fetch_items_for_source(self, subreddit, since_datetime):
        """Fetch posts from a specific subreddit."""
        posts = []
        try:
            for submission in self.reddit.subreddit(subreddit).new(limit=100):
                created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                if created_utc > since_datetime:
                    reddit_url = f"https://reddit.com{submission.permalink}"

                    # Determine post type and URLs
                    if submission.is_self:
                        # Self post - discussion only happens on Reddit
                        post_type = "self"
                        external_url = None
                        primary_url = reddit_url
                    else:
                        # Link post - has external content
                        post_type = "link"
                        external_url = submission.url
                        primary_url = submission.url

                    post_data = {
                        "id": submission.id,
                        "title": submission.title,
                        "url": primary_url,  # Maintains backward compatibility
                        "reddit_url": reddit_url,
                        "external_url": external_url,
                        "post_type": post_type,
                        "created_utc": created_utc,
                        "permalink": reddit_url,  # Backward compatibility
                        "subreddit": subreddit,
                        "score": submission.score
                    }
                    posts.append(post_data)
        except praw.exceptions.PRAWException as e:
            logging.error(f"Reddit API error for subreddit '{subreddit}': {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching from subreddit '{subreddit}': {e}")

        return posts