from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from src.reddit_client import RedditClient


class TestRedditClient:
    def setup_method(self):
        self.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "user_agent": "test_user_agent",
            "subreddits": ["python", "learnprogramming"],
        }
        self.categorized_config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "user_agent": "test_user_agent",
            "categories": {
                "tech": ["python", "programming"],
                "learning": ["learnprogramming"],
            },
        }

    @patch("src.reddit_client.praw.Reddit")
    def test_init_simple_config(self, mock_reddit):
        mock_reddit_instance = Mock()
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)

        assert client.subreddits == ["python", "learnprogramming"]
        assert client.items == ["python", "learnprogramming"]
        assert client.categories is None
        mock_reddit.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret",
            user_agent="test_user_agent",
        )

    @patch("src.reddit_client.praw.Reddit")
    def test_init_categorized_config(self, mock_reddit):
        mock_reddit_instance = Mock()
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.categorized_config)

        assert set(client.subreddits) == {"python", "programming", "learnprogramming"}
        assert set(client.items) == {"python", "programming", "learnprogramming"}
        assert client.categories == {
            "tech": ["python", "programming"],
            "learning": ["learnprogramming"],
        }
        mock_reddit.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret",
            user_agent="test_user_agent",
        )

    def test_get_items_from_config(self):
        # Test with simple config
        items = RedditClient._get_items_from_config(None, self.config)
        assert items == ["python", "learnprogramming"]

        # Test with missing subreddits key
        config_no_subreddits = {
            "client_id": "test",
            "client_secret": "test",
            "user_agent": "test",
        }
        items = RedditClient._get_items_from_config(None, config_no_subreddits)
        assert items == []

    @patch("src.reddit_client.praw.Reddit")
    def test_fetch_items_for_source_success(self, mock_reddit):
        # Create mock submissions - mix of link and self posts
        mock_submission1 = Mock()
        mock_submission1.id = "post1"
        mock_submission1.title = "Test Post 1"
        mock_submission1.url = "https://example.com/1"
        mock_submission1.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission1.permalink = "/r/python/comments/post1/test_post_1/"
        mock_submission1.score = 42
        mock_submission1.is_self = False  # Link post

        mock_submission2 = Mock()
        mock_submission2.id = "post2"
        mock_submission2.title = "Test Post 2"
        mock_submission2.url = "https://reddit.com/r/python/comments/post2/test_post_2/"
        mock_submission2.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).timestamp()
        mock_submission2.permalink = "/r/python/comments/post2/test_post_2/"
        mock_submission2.score = 15
        mock_submission2.is_self = True  # Self post

        # Mock the Reddit API chain
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = [mock_submission1, mock_submission2]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        posts = client._fetch_items_for_source("python", since_datetime)

        assert len(posts) == 2

        # Check first post (link post)
        post1 = posts[0]
        assert post1["id"] == "post1"
        assert post1["title"] == "Test Post 1"
        assert (
            post1["url"] == "https://example.com/1"
        )  # Primary URL is external for link posts
        assert (
            post1["reddit_url"]
            == "https://reddit.com/r/python/comments/post1/test_post_1/"
        )
        assert post1["external_url"] == "https://example.com/1"
        assert post1["post_type"] == "link"
        assert (
            post1["permalink"]
            == "https://reddit.com/r/python/comments/post1/test_post_1/"
        )
        assert post1["subreddit"] == "python"
        assert post1["score"] == 42
        assert isinstance(post1["created_utc"], datetime)

        # Check second post (self post)
        post2 = posts[1]
        assert post2["id"] == "post2"
        assert post2["title"] == "Test Post 2"
        assert (
            post2["url"] == "https://reddit.com/r/python/comments/post2/test_post_2/"
        )  # Primary URL is Reddit for self posts
        assert (
            post2["reddit_url"]
            == "https://reddit.com/r/python/comments/post2/test_post_2/"
        )
        assert post2["external_url"] is None
        assert post2["post_type"] == "self"
        assert post2["score"] == 15

        # Verify API calls
        mock_reddit_instance.subreddit.assert_called_with("python")
        mock_subreddit.new.assert_called_with(limit=100)

    @patch("src.reddit_client.praw.Reddit")
    def test_post_type_detection(self, mock_reddit):
        """Test that post type detection works correctly for link vs self posts."""
        # Link post
        mock_link_post = Mock()
        mock_link_post.id = "link1"
        mock_link_post.title = "External Link"
        mock_link_post.url = "https://example.com/article"
        mock_link_post.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_link_post.permalink = "/r/test/comments/link1/"
        mock_link_post.score = 10
        mock_link_post.is_self = False

        # Self post
        mock_self_post = Mock()
        mock_self_post.id = "self1"
        mock_self_post.title = "Discussion Post"
        mock_self_post.url = "https://reddit.com/r/test/comments/self1/"
        mock_self_post.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_self_post.permalink = "/r/test/comments/self1/"
        mock_self_post.score = 5
        mock_self_post.is_self = True

        # Mock Reddit API
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = [mock_link_post, mock_self_post]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=2)
        posts = client._fetch_items_for_source("test", since_datetime)

        assert len(posts) == 2

        # Find posts by ID
        link_post = next(p for p in posts if p["id"] == "link1")
        self_post = next(p for p in posts if p["id"] == "self1")

        # Verify link post structure
        assert link_post["post_type"] == "link"
        assert link_post["external_url"] == "https://example.com/article"
        assert link_post["reddit_url"] == "https://reddit.com/r/test/comments/link1/"
        assert (
            link_post["url"] == "https://example.com/article"
        )  # Primary URL is external

        # Verify self post structure
        assert self_post["post_type"] == "self"
        assert self_post["external_url"] is None
        assert self_post["reddit_url"] == "https://reddit.com/r/test/comments/self1/"
        assert (
            self_post["url"] == "https://reddit.com/r/test/comments/self1/"
        )  # Primary URL is Reddit

    @patch("src.reddit_client.praw.Reddit")
    def test_fetch_items_for_source_filters_old_posts(self, mock_reddit):
        # Create mock submissions - one new, one old
        now = datetime.now(timezone.utc)

        mock_submission_new = Mock()
        mock_submission_new.id = "new_post"
        mock_submission_new.title = "New Post"
        mock_submission_new.url = "https://example.com/new"
        mock_submission_new.created_utc = (
            now - timedelta(hours=1)
        ).timestamp()  # Recent
        mock_submission_new.permalink = "/r/python/comments/new_post/"
        mock_submission_new.score = 25

        mock_submission_old = Mock()
        mock_submission_old.id = "old_post"
        mock_submission_old.title = "Old Post"
        mock_submission_old.url = "https://example.com/old"
        mock_submission_old.created_utc = (
            now - timedelta(hours=5)
        ).timestamp()  # Too old
        mock_submission_old.permalink = "/r/python/comments/old_post/"
        mock_submission_old.score = 10

        # Mock the Reddit API chain
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = [mock_submission_new, mock_submission_old]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = now - timedelta(hours=3)  # Only want posts from last 3 hours

        posts = client._fetch_items_for_source("python", since_datetime)

        # Should only get the new post
        assert len(posts) == 1
        assert posts[0]["id"] == "new_post"
        assert posts[0]["title"] == "New Post"

    @patch("src.reddit_client.praw.Reddit")
    @patch("src.reddit_client.logging")
    def test_fetch_items_for_source_reddit_exception(self, mock_logging, mock_reddit):
        # Mock Reddit exception
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.side_effect = Exception("Reddit API error")
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("python", since_datetime)

        # Should return empty list on error
        assert posts == []

        # Should log the error
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        assert "Unexpected error fetching from subreddit 'python'" in error_call

    @patch("src.reddit_client.praw.Reddit")
    @patch("src.reddit_client.logging")
    def test_fetch_items_for_source_praw_exception(self, mock_logging, mock_reddit):
        import praw.exceptions

        # Mock PRAW-specific exception
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.side_effect = praw.exceptions.PRAWException("API rate limit")
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("python", since_datetime)

        # Should return empty list on error
        assert posts == []

        # Should log the Reddit API error specifically
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        assert "Reddit API error for subreddit 'python'" in error_call

    @patch("src.reddit_client.praw.Reddit")
    def test_get_new_items_since_simple_config(self, mock_reddit):
        # Mock Reddit API responses for multiple subreddits
        mock_submission1 = Mock()
        mock_submission1.id = "python_post"
        mock_submission1.title = "Python Post"
        mock_submission1.url = "https://example.com/python"
        mock_submission1.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission1.permalink = "/r/python/comments/python_post/"
        mock_submission1.score = 30

        mock_submission2 = Mock()
        mock_submission2.id = "learning_post"
        mock_submission2.title = "Learning Post"
        mock_submission2.url = "https://example.com/learning"
        mock_submission2.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).timestamp()
        mock_submission2.permalink = "/r/learnprogramming/comments/learning_post/"
        mock_submission2.score = 20

        # Mock different responses for different subreddits
        def subreddit_side_effect(name):
            mock_subreddit = Mock()
            if name == "python":
                mock_subreddit.new.return_value = [mock_submission1]
            elif name == "learnprogramming":
                mock_subreddit.new.return_value = [mock_submission2]
            return mock_subreddit

        mock_reddit_instance = Mock()
        mock_reddit_instance.subreddit.side_effect = subreddit_side_effect
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        all_posts = client.get_new_items_since(since_datetime)

        assert len(all_posts) == 2

        # Check posts don't have category (simple config)
        for post in all_posts:
            assert "category" not in post

        # Check posts are from different subreddits
        subreddits = {post["subreddit"] for post in all_posts}
        assert subreddits == {"python", "learnprogramming"}

    @patch("src.reddit_client.praw.Reddit")
    def test_get_new_items_since_categorized_config(self, mock_reddit):
        # Mock Reddit API responses
        mock_submission1 = Mock()
        mock_submission1.id = "python_post"
        mock_submission1.title = "Python Post"
        mock_submission1.url = "https://example.com/python"
        mock_submission1.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission1.permalink = "/r/python/comments/python_post/"
        mock_submission1.score = 40

        mock_submission2 = Mock()
        mock_submission2.id = "learning_post"
        mock_submission2.title = "Learning Post"
        mock_submission2.url = "https://example.com/learning"
        mock_submission2.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).timestamp()
        mock_submission2.permalink = "/r/learnprogramming/comments/learning_post/"
        mock_submission2.score = 35

        # Mock different responses for different subreddits
        def subreddit_side_effect(name):
            mock_subreddit = Mock()
            if name == "python":
                mock_subreddit.new.return_value = [mock_submission1]
            elif name == "programming":
                mock_subreddit.new.return_value = []
            elif name == "learnprogramming":
                mock_subreddit.new.return_value = [mock_submission2]
            return mock_subreddit

        mock_reddit_instance = Mock()
        mock_reddit_instance.subreddit.side_effect = subreddit_side_effect
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.categorized_config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        all_posts = client.get_new_items_since(since_datetime)

        assert len(all_posts) == 2

        # Check posts have categories
        categories = {post["category"] for post in all_posts}
        assert categories == {"tech", "learning"}

        # Check specific category assignments
        python_post = next(post for post in all_posts if post["subreddit"] == "python")
        assert python_post["category"] == "tech"

        learning_post = next(
            post for post in all_posts if post["subreddit"] == "learnprogramming"
        )
        assert learning_post["category"] == "learning"

    @patch("src.reddit_client.praw.Reddit")
    def test_get_new_items_since_empty_results(self, mock_reddit):
        # Mock empty responses from all subreddits
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = []
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        all_posts = client.get_new_items_since(since_datetime)

        assert all_posts == []

    @patch("src.reddit_client.praw.Reddit")
    def test_pre_fetch_optimization_hook(self, mock_reddit):
        """Test that the pre-fetch optimization hook is called."""
        mock_reddit_instance = Mock()
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)

        # Mock the optimization method to verify it's called
        client._pre_fetch_optimization = Mock()

        # Mock empty subreddit responses to focus on the optimization call
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = []
        mock_reddit_instance.subreddit.return_value = mock_subreddit

        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)
        client.get_new_items_since(since_datetime)

        # Verify the optimization hook was called with the subreddit list
        client._pre_fetch_optimization.assert_called_once_with(
            ["python", "learnprogramming"]
        )

    @patch("src.reddit_client.praw.Reddit")
    def test_karma_filter_no_filters_configured(self, mock_reddit):
        """Test that posts are not filtered when no karma filters are configured."""
        mock_submission1 = Mock()
        mock_submission1.id = "post1"
        mock_submission1.title = "Low Karma Post"
        mock_submission1.url = "https://example.com/1"
        mock_submission1.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission1.permalink = "/r/python/comments/post1/"
        mock_submission1.score = 5
        mock_submission1.is_self = False

        mock_submission2 = Mock()
        mock_submission2.id = "post2"
        mock_submission2.title = "High Karma Post"
        mock_submission2.url = "https://example.com/2"
        mock_submission2.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission2.permalink = "/r/python/comments/post2/"
        mock_submission2.score = 100
        mock_submission2.is_self = False

        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = [mock_submission1, mock_submission2]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=2)
        posts = client._fetch_items_for_source("python", since_datetime)

        # Both posts should be included (no filter)
        assert len(posts) == 2
        assert posts[0]["score"] == 5
        assert posts[1]["score"] == 100

    @patch("src.reddit_client.praw.Reddit")
    def test_karma_filter_with_threshold(self, mock_reddit):
        """Test that posts below karma threshold are filtered out."""
        config_with_karma = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "user_agent": "test_user_agent",
            "subreddits": ["chicago"],
            "karma_filters": {"chicago": 50},
        }

        mock_submission1 = Mock()
        mock_submission1.id = "post1"
        mock_submission1.title = "Low Karma Post"
        mock_submission1.url = "https://example.com/1"
        mock_submission1.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission1.permalink = "/r/chicago/comments/post1/"
        mock_submission1.score = 30  # Below threshold
        mock_submission1.is_self = False

        mock_submission2 = Mock()
        mock_submission2.id = "post2"
        mock_submission2.title = "High Karma Post"
        mock_submission2.url = "https://example.com/2"
        mock_submission2.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission2.permalink = "/r/chicago/comments/post2/"
        mock_submission2.score = 75  # Above threshold
        mock_submission2.is_self = False

        mock_submission3 = Mock()
        mock_submission3.id = "post3"
        mock_submission3.title = "Exact Threshold Post"
        mock_submission3.url = "https://example.com/3"
        mock_submission3.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_submission3.permalink = "/r/chicago/comments/post3/"
        mock_submission3.score = 50  # Exactly at threshold
        mock_submission3.is_self = False

        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_subreddit.new.return_value = [
            mock_submission1,
            mock_submission2,
            mock_submission3,
        ]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(config_with_karma)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=2)
        posts = client._fetch_items_for_source("chicago", since_datetime)

        # Only posts with score >= 50 should be included
        assert len(posts) == 2
        assert all(post["score"] >= 50 for post in posts)
        assert posts[0]["id"] == "post2"
        assert posts[0]["score"] == 75
        assert posts[1]["id"] == "post3"
        assert posts[1]["score"] == 50

    @patch("src.reddit_client.praw.Reddit")
    def test_karma_filter_different_thresholds_per_subreddit(self, mock_reddit):
        """Test that different subreddits can have different karma thresholds."""
        config_with_karma = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "user_agent": "test_user_agent",
            "subreddits": ["chicago", "python"],
            "karma_filters": {"chicago": 100, "python": 25},
        }

        # Chicago posts
        mock_chicago_low = Mock()
        mock_chicago_low.id = "chicago1"
        mock_chicago_low.title = "Chicago Low"
        mock_chicago_low.url = "https://example.com/chicago1"
        mock_chicago_low.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_chicago_low.permalink = "/r/chicago/comments/chicago1/"
        mock_chicago_low.score = 75  # Below chicago threshold (100)
        mock_chicago_low.is_self = False

        mock_chicago_high = Mock()
        mock_chicago_high.id = "chicago2"
        mock_chicago_high.title = "Chicago High"
        mock_chicago_high.url = "https://example.com/chicago2"
        mock_chicago_high.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_chicago_high.permalink = "/r/chicago/comments/chicago2/"
        mock_chicago_high.score = 150  # Above chicago threshold
        mock_chicago_high.is_self = False

        # Python posts
        mock_python_low = Mock()
        mock_python_low.id = "python1"
        mock_python_low.title = "Python Low"
        mock_python_low.url = "https://example.com/python1"
        mock_python_low.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_python_low.permalink = "/r/python/comments/python1/"
        mock_python_low.score = 30  # Above python threshold (25)
        mock_python_low.is_self = False

        def subreddit_side_effect(name):
            mock_subreddit = Mock()
            if name == "chicago":
                mock_subreddit.new.return_value = [mock_chicago_low, mock_chicago_high]
            elif name == "python":
                mock_subreddit.new.return_value = [mock_python_low]
            return mock_subreddit

        mock_reddit_instance = Mock()
        mock_reddit_instance.subreddit.side_effect = subreddit_side_effect
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(config_with_karma)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=2)

        # Test chicago - should only get high karma post
        chicago_posts = client._fetch_items_for_source("chicago", since_datetime)
        assert len(chicago_posts) == 1
        assert chicago_posts[0]["id"] == "chicago2"
        assert chicago_posts[0]["score"] == 150

        # Test python - should get the post with 30 karma (above 25 threshold)
        python_posts = client._fetch_items_for_source("python", since_datetime)
        assert len(python_posts) == 1
        assert python_posts[0]["id"] == "python1"
        assert python_posts[0]["score"] == 30

    @patch("src.reddit_client.praw.Reddit")
    def test_karma_filter_with_categorized_config(self, mock_reddit):
        """Test that karma filters work with categorized subreddit configuration."""
        config_with_karma = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "user_agent": "test_user_agent",
            "categories": {"news": ["worldnews", "chicago"], "tech": ["python"]},
            "karma_filters": {"worldnews": 200, "chicago": 50},
        }

        mock_worldnews_post = Mock()
        mock_worldnews_post.id = "worldnews1"
        mock_worldnews_post.title = "World News"
        mock_worldnews_post.url = "https://example.com/worldnews1"
        mock_worldnews_post.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_worldnews_post.permalink = "/r/worldnews/comments/worldnews1/"
        mock_worldnews_post.score = 250  # Above threshold
        mock_worldnews_post.is_self = False

        mock_chicago_post = Mock()
        mock_chicago_post.id = "chicago1"
        mock_chicago_post.title = "Chicago News"
        mock_chicago_post.url = "https://example.com/chicago1"
        mock_chicago_post.created_utc = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        mock_chicago_post.permalink = "/r/chicago/comments/chicago1/"
        mock_chicago_post.score = 30  # Below threshold
        mock_chicago_post.is_self = False

        def subreddit_side_effect(name):
            mock_subreddit = Mock()
            if name == "worldnews":
                mock_subreddit.new.return_value = [mock_worldnews_post]
            elif name == "chicago":
                mock_subreddit.new.return_value = [mock_chicago_post]
            elif name == "python":
                mock_subreddit.new.return_value = []
            return mock_subreddit

        mock_reddit_instance = Mock()
        mock_reddit_instance.subreddit.side_effect = subreddit_side_effect
        mock_reddit.return_value = mock_reddit_instance

        client = RedditClient(config_with_karma)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=2)

        all_posts = client.get_new_items_since(since_datetime)

        # Should only get worldnews post (chicago filtered out by karma)
        assert len(all_posts) == 1
        assert all_posts[0]["id"] == "worldnews1"
        assert all_posts[0]["category"] == "news"
        assert all_posts[0]["score"] == 250
