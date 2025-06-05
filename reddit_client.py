import praw
from datetime import datetime, timezone

class RedditClient:
    def __init__(self, config):
        """
        Initialize with a config dictionary, e.g.:
        {
            "client_id": "...",
            "client_secret": "...",
            "user_agent": "...",
            "subreddits": ["python", "learnprogramming"]
        }
        """
        self.reddit = praw.Reddit(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            user_agent=config["user_agent"]
        )
        self.subreddits = config["subreddits"]

    def get_new_posts_since(self, since_datetime):
        """
        Retrieve new posts from configured subreddits since the given datetime.
        Returns a list of dicts with post info.
        """
        new_posts = []
        for subreddit in self.subreddits:
            for submission in self.reddit.subreddit(subreddit).new(limit=100):
                created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                if created_utc > since_datetime:
                    new_posts.append({
                        "id": submission.id,
                        "title": submission.title,
                        "url": submission.url,
                        "created_utc": created_utc,
                        "permalink": f"https://reddit.com{submission.permalink}",
                        "subreddit": subreddit
                    })
        return new_posts