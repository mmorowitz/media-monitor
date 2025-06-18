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
        self.reddit = praw.Reddit(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            user_agent=config["user_agent"]
        )
        
        # Support both simple and categorized formats
        if "categories" in config:
            self.categories = config["categories"]
            self.subreddits = []
            for category_subreddits in self.categories.values():
                self.subreddits.extend(category_subreddits)
        else:
            self.categories = None
            self.subreddits = config.get("subreddits", [])

    def get_new_items_since(self, since_datetime):
        """
        Retrieve new posts from configured subreddits since the given datetime.
        Returns a list of dicts with post info, including category if categorized.
        """
        new_posts = []
        
        # Create a mapping from subreddit to category if using categories
        subreddit_to_category = {}
        if self.categories:
            for category, subreddit_list in self.categories.items():
                for subreddit in subreddit_list:
                    subreddit_to_category[subreddit] = category
        
        for subreddit in self.subreddits:
            for submission in self.reddit.subreddit(subreddit).new(limit=100):
                created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                if created_utc > since_datetime:
                    post_data = {
                        "id": submission.id,
                        "title": submission.title,
                        "url": submission.url,
                        "created_utc": created_utc,
                        "permalink": f"https://reddit.com{submission.permalink}",
                        "subreddit": subreddit
                    }
                    
                    # Add category if using categorized format
                    if self.categories:
                        post_data["category"] = subreddit_to_category.get(subreddit, "uncategorized")
                    
                    new_posts.append(post_data)
        return new_posts