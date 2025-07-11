from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
import json
import requests

from src.bluesky_client import BlueskyClient


class TestBlueskyClient:
    def setup_method(self):
        self.config = {
            "users": ["alice.bsky.social", "bob.bsky.social"]
        }
        self.categorized_config = {
            "categories": {
                "tech": ["alice.bsky.social", "charlie.bsky.social"],
                "news": ["bob.bsky.social"]
            }
        }

    def test_init_simple_config(self):
        client = BlueskyClient(self.config)

        assert client.users == ["alice.bsky.social", "bob.bsky.social"]
        assert client.items == ["alice.bsky.social", "bob.bsky.social"]
        assert client.categories is None

    def test_init_categorized_config(self):
        client = BlueskyClient(self.categorized_config)

        assert set(client.users) == {"alice.bsky.social", "charlie.bsky.social", "bob.bsky.social"}
        assert set(client.items) == {"alice.bsky.social", "charlie.bsky.social", "bob.bsky.social"}
        assert client.categories == {"tech": ["alice.bsky.social", "charlie.bsky.social"], "news": ["bob.bsky.social"]}

    def test_get_items_from_config(self):
        # Test with simple config
        items = BlueskyClient._get_items_from_config(None, self.config)
        assert items == ["alice.bsky.social", "bob.bsky.social"]

        # Test with missing users key
        config_no_users = {}
        items = BlueskyClient._get_items_from_config(None, config_no_users)
        assert items == []

    @patch('src.bluesky_client.requests.get')
    def test_fetch_items_for_source_success(self, mock_get):
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/abc123",
                    "cid": "bafyrei123",
                    "author": {
                        "did": "did:plc:user123",
                        "handle": "alice.bsky.social",
                        "displayName": "Alice Smith"
                    },
                    "record": {
                        "text": "This is a test post from Alice about technology",
                        "createdAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                    },
                    "indexedAt": "2024-01-15T10:30:05.000Z",
                    "replyCount": 2,
                    "repostCount": 5,
                    "likeCount": 15
                },
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/def456",
                    "cid": "bafyrei456",
                    "author": {
                        "did": "did:plc:user123",
                        "handle": "alice.bsky.social",
                        "displayName": "Alice Smith"
                    },
                    "record": {
                        "text": "Another post from Alice with a longer text that should be truncated for the title but kept in full_text",
                        "createdAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
                    },
                    "indexedAt": "2024-01-15T09:15:02.000Z",
                    "replyCount": 0,
                    "repostCount": 1,
                    "likeCount": 8
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        assert len(posts) == 2

        # Check first post
        post1 = posts[0]
        assert post1["id"] == "abc123"
        assert post1["title"] == "This is a test post from Alice about technology"
        assert post1["url"] == "https://bsky.app/profile/alice.bsky.social/post/abc123"
        assert post1["author"] == "alice.bsky.social"
        assert post1["full_text"] == "This is a test post from Alice about technology"
        assert isinstance(post1["created_utc"], datetime)
        assert post1["reply_count"] == 2
        assert post1["repost_count"] == 5
        assert post1["like_count"] == 15

        # Check second post (with truncated title)
        post2 = posts[1]
        assert post2["id"] == "def456"
        assert post2["title"] == "Another post from Alice with a longer text that should be truncated for the title but kept in full_t..."
        assert post2["full_text"] == "Another post from Alice with a longer text that should be truncated for the title but kept in full_text"
        assert post2["like_count"] == 8

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts" in call_args[0][0]
        assert "from:alice.bsky.social" in call_args[1]["params"]["q"]
        assert call_args[1]["params"]["limit"] == 50

    @patch('src.bluesky_client.requests.get')
    def test_fetch_items_for_source_filters_old_posts(self, mock_get):
        # Mock API response with posts from different times
        now = datetime.now(timezone.utc)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/new123",
                    "cid": "bafyrei123",
                    "author": {
                        "did": "did:plc:user123",
                        "handle": "alice.bsky.social",
                        "displayName": "Alice Smith"
                    },
                    "record": {
                        "text": "New post",
                        "createdAt": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                    },
                    "indexedAt": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                    "replyCount": 0,
                    "repostCount": 0,
                    "likeCount": 5
                },
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/old456",
                    "cid": "bafyrei456",
                    "author": {
                        "did": "did:plc:user123",
                        "handle": "alice.bsky.social",
                        "displayName": "Alice Smith"
                    },
                    "record": {
                        "text": "Old post",
                        "createdAt": (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
                    },
                    "indexedAt": (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                    "replyCount": 0,
                    "repostCount": 0,
                    "likeCount": 2
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = now - timedelta(hours=3)  # Only want posts from last 3 hours

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        # Should only get the new post
        assert len(posts) == 1
        assert posts[0]["id"] == "new123"
        assert posts[0]["title"] == "New post"

    @patch('src.bluesky_client.requests.get')
    def test_fetch_items_for_source_empty_response(self, mock_get):
        # Mock empty API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": []}
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        assert posts == []

    @patch('src.bluesky_client.requests.get')
    @patch('src.bluesky_client.logging')
    def test_fetch_items_for_source_http_error(self, mock_logging, mock_get):
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Bad Request")
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        # Should return empty list on error
        assert posts == []

        # Should log the error
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        assert "HTTP error fetching posts for user 'alice.bsky.social'" in error_call

    @patch('src.bluesky_client.requests.get')
    @patch('src.bluesky_client.logging')
    def test_fetch_items_for_source_request_exception(self, mock_logging, mock_get):
        # Mock requests exception
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        # Should return empty list on error
        assert posts == []

        # Should log the error
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        assert "Request error fetching posts for user 'alice.bsky.social'" in error_call

    @patch('src.bluesky_client.requests.get')
    @patch('src.bluesky_client.logging')
    def test_fetch_items_for_source_json_decode_error(self, mock_logging, mock_get):
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        # Should return empty list on error
        assert posts == []

        # Should log the error
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        assert "JSON decode error fetching posts for user 'alice.bsky.social'" in error_call

    @patch('src.bluesky_client.requests.get')
    def test_fetch_items_for_source_malformed_response(self, mock_get):
        # Mock API response with missing fields
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/abc123",
                    "author": {
                        "handle": "alice.bsky.social"
                    },
                    "record": {
                        "text": "Post with missing fields",
                        "createdAt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
                    }
                    # Missing cid, indexedAt, counts
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        # Should handle missing fields gracefully
        assert len(posts) == 1
        post = posts[0]
        assert post["id"] == "abc123"
        assert post["title"] == "Post with missing fields"
        assert post["reply_count"] == 0  # Default value
        assert post["repost_count"] == 0  # Default value
        assert post["like_count"] == 0  # Default value

    @patch('src.bluesky_client.requests.get')
    def test_get_new_items_since_simple_config(self, mock_get):
        # Mock API responses for multiple users
        def mock_response_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200

            if "from:alice.bsky.social" in kwargs["params"]["q"]:
                mock_response.json.return_value = {
                    "posts": [
                        {
                            "uri": "at://did:plc:alice/app.bsky.feed.post/post1",
                            "cid": "bafyrei1",
                            "author": {"handle": "alice.bsky.social"},
                            "record": {
                                "text": "Alice's post",
                                "createdAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                            },
                            "replyCount": 1, "repostCount": 2, "likeCount": 10
                        }
                    ]
                }
            elif "from:bob.bsky.social" in kwargs["params"]["q"]:
                mock_response.json.return_value = {
                    "posts": [
                        {
                            "uri": "at://did:plc:bob/app.bsky.feed.post/post2",
                            "cid": "bafyrei2",
                            "author": {"handle": "bob.bsky.social"},
                            "record": {
                                "text": "Bob's post",
                                "createdAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
                            },
                            "replyCount": 0, "repostCount": 1, "likeCount": 5
                        }
                    ]
                }
            return mock_response

        mock_get.side_effect = mock_response_side_effect

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        all_posts = client.get_new_items_since(since_datetime)

        assert len(all_posts) == 2

        # Check posts don't have category (simple config)
        for post in all_posts:
            assert "category" not in post

        # Check posts are from different users
        authors = {post["author"] for post in all_posts}
        assert authors == {"alice.bsky.social", "bob.bsky.social"}

    @patch('src.bluesky_client.requests.get')
    def test_get_new_items_since_categorized_config(self, mock_get):
        # Mock API responses for categorized users
        def mock_response_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200

            if "from:alice.bsky.social" in kwargs["params"]["q"]:
                mock_response.json.return_value = {
                    "posts": [
                        {
                            "uri": "at://did:plc:alice/app.bsky.feed.post/tech1",
                            "cid": "bafyrei1",
                            "author": {"handle": "alice.bsky.social"},
                            "record": {
                                "text": "Alice's tech post",
                                "createdAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                            },
                            "replyCount": 1, "repostCount": 2, "likeCount": 10
                        }
                    ]
                }
            elif "from:bob.bsky.social" in kwargs["params"]["q"]:
                mock_response.json.return_value = {
                    "posts": [
                        {
                            "uri": "at://did:plc:bob/app.bsky.feed.post/news1",
                            "cid": "bafyrei2",
                            "author": {"handle": "bob.bsky.social"},
                            "record": {
                                "text": "Bob's news post",
                                "createdAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
                            },
                            "replyCount": 0, "repostCount": 1, "likeCount": 5
                        }
                    ]
                }
            elif "from:charlie.bsky.social" in kwargs["params"]["q"]:
                mock_response.json.return_value = {"posts": []}
            return mock_response

        mock_get.side_effect = mock_response_side_effect

        client = BlueskyClient(self.categorized_config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=3)

        all_posts = client.get_new_items_since(since_datetime)

        assert len(all_posts) == 2

        # Check posts have categories
        categories = {post["category"] for post in all_posts}
        assert categories == {"tech", "news"}

        # Check specific category assignments
        alice_post = next(post for post in all_posts if post["author"] == "alice.bsky.social")
        assert alice_post["category"] == "tech"

        bob_post = next(post for post in all_posts if post["author"] == "bob.bsky.social")
        assert bob_post["category"] == "news"

    @patch('src.bluesky_client.requests.get')
    def test_get_new_items_since_empty_results(self, mock_get):
        # Mock empty responses from all users
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": []}
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        all_posts = client.get_new_items_since(since_datetime)

        assert all_posts == []

    def test_pre_fetch_optimization_hook(self):
        """Test that the pre-fetch optimization hook is called."""
        client = BlueskyClient(self.config)

        # Mock the optimization method to verify it's called
        client._pre_fetch_optimization = Mock()

        # Mock requests to focus on the optimization call
        with patch('src.bluesky_client.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"posts": []}
            mock_get.return_value = mock_response

            since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)
            client.get_new_items_since(since_datetime)

            # Verify the optimization hook was called with the user list
            client._pre_fetch_optimization.assert_called_once_with(["alice.bsky.social", "bob.bsky.social"])

    @patch('src.bluesky_client.requests.get')
    def test_post_url_generation(self, mock_get):
        """Test that post URLs are generated correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/abc123xyz",
                    "cid": "bafyrei123",
                    "author": {"handle": "alice.bsky.social"},
                    "record": {
                        "text": "Test post",
                        "createdAt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
                    },
                    "replyCount": 0, "repostCount": 0, "likeCount": 0
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        assert len(posts) == 1
        assert posts[0]["url"] == "https://bsky.app/profile/alice.bsky.social/post/abc123xyz"

    @patch('src.bluesky_client.requests.get')
    def test_title_truncation(self, mock_get):
        """Test that long post text is truncated for title but preserved in full_text."""
        long_text = "This is a very long post that should be truncated when used as a title because it exceeds the character limit we want to impose for email readability and formatting purposes."

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/long123",
                    "cid": "bafyrei123",
                    "author": {"handle": "alice.bsky.social"},
                    "record": {
                        "text": long_text,
                        "createdAt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
                    },
                    "replyCount": 0, "repostCount": 0, "likeCount": 0
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        assert len(posts) == 1
        assert len(posts[0]["title"]) <= 103  # 100 chars + "..."
        assert posts[0]["title"].endswith("...")
        assert posts[0]["full_text"] == long_text

    @patch('src.bluesky_client.requests.get')
    def test_datetime_parsing(self, mock_get):
        """Test that various datetime formats are parsed correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "uri": "at://did:plc:user123/app.bsky.feed.post/time123",
                    "cid": "bafyrei123",
                    "author": {"handle": "alice.bsky.social"},
                    "record": {
                        "text": "Time test post",
                        "createdAt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
                    },
                    "replyCount": 0, "repostCount": 0, "likeCount": 0
                }
            ]
        }
        mock_get.return_value = mock_response

        client = BlueskyClient(self.config)
        since_datetime = datetime.now(timezone.utc) - timedelta(hours=1)

        posts = client._fetch_items_for_source("alice.bsky.social", since_datetime)

        assert len(posts) == 1
        assert isinstance(posts[0]["created_utc"], datetime)
        assert posts[0]["created_utc"].tzinfo == timezone.utc

