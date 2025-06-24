from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.youtube_client import YouTubeClient


class TestYouTubeClient:
    def setup_method(self):
        self.config = {
            "api_key": "test_api_key",
            "channels": ["UC123", "UC456"]
        }
        self.categorized_config = {
            "api_key": "test_api_key",
            "categories": {
                "tech": ["UC123"],
                "education": ["UC456"]
            }
        }

    @patch('src.youtube_client.build')
    def test_init_simple_config(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        client = YouTubeClient(self.config)
        
        assert client.api_key == "test_api_key"
        assert client.channels == ["UC123", "UC456"]
        assert client.channel_names_cache == {}
        mock_build.assert_called_once_with("youtube", "v3", developerKey="test_api_key")

    @patch('src.youtube_client.build')
    def test_init_categorized_config(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        client = YouTubeClient(self.categorized_config)
        
        assert client.api_key == "test_api_key"
        assert set(client.channels) == {"UC123", "UC456"}
        assert client.categories == {"tech": ["UC123"], "education": ["UC456"]}

    @patch('src.youtube_client.build')
    def test_get_channel_name_cache_hit(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        client = YouTubeClient(self.config)
        client.channel_names_cache["UC123"] = "TechChannel"
        
        result = client._get_channel_name("UC123")
        
        assert result == "TechChannel"
        # Should not make API call when cache hit
        mock_youtube.channels.assert_not_called()

    @patch('src.youtube_client.build')
    def test_get_channel_name_api_success(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock API response
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "TechChannel"
                    }
                }
            ]
        }
        
        client = YouTubeClient(self.config)
        result = client._get_channel_name("UC123")
        
        assert result == "TechChannel"
        assert client.channel_names_cache["UC123"] == "TechChannel"
        mock_youtube.channels.return_value.list.assert_called_once_with(
            part="snippet",
            id="UC123"
        )

    @patch('src.youtube_client.build')
    def test_get_channel_name_api_failure(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock API failure
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.side_effect = Exception("API Error")
        
        client = YouTubeClient(self.config)
        result = client._get_channel_name("UC123")
        
        # Should fallback to channel ID
        assert result == "UC123"
        assert client.channel_names_cache["UC123"] == "UC123"

    @patch('src.youtube_client.build')
    def test_get_channel_name_no_items(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock API response with no items
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.return_value = {"items": []}
        
        client = YouTubeClient(self.config)
        result = client._get_channel_name("UC123")
        
        # Should fallback to channel ID
        assert result == "UC123"
        assert client.channel_names_cache["UC123"] == "UC123"

    @patch('src.youtube_client.build')
    def test_fetch_items_for_source_with_channel_names(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock channel name lookup
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "TechChannel"
                    }
                }
            ]
        }
        
        # Mock search API response
        search_request = Mock()
        mock_youtube.search.return_value.list.return_value = search_request
        search_request.execute.return_value = {
            "items": [
                {
                    "id": {"videoId": "video123"},
                    "snippet": {
                        "title": "Test Video",
                        "publishedAt": "2024-01-02T12:00:00Z"
                    }
                }
            ]
        }
        
        client = YouTubeClient(self.config)
        since_datetime = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        result = client._fetch_items_for_source("UC123", since_datetime)
        
        assert len(result) == 1
        video = result[0]
        assert video["id"] == "video123"
        assert video["title"] == "Test Video"
        assert video["url"] == "https://www.youtube.com/watch?v=video123"
        assert video["channel_id"] == "TechChannel"  # Should use channel name, not ID
        assert isinstance(video["published_at"], datetime)
        
        # Verify channel name was fetched
        mock_youtube.channels.return_value.list.assert_called_once_with(
            part="snippet",
            id="UC123"
        )

    @patch('src.youtube_client.build')
    def test_fetch_items_filters_by_datetime(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock channel name lookup
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [{"snippet": {"title": "TechChannel"}}]
        }
        
        # Mock search API response with videos before and after the since_datetime
        search_request = Mock()
        mock_youtube.search.return_value.list.return_value = search_request
        search_request.execute.return_value = {
            "items": [
                {
                    "id": {"videoId": "old_video"},
                    "snippet": {
                        "title": "Old Video",
                        "publishedAt": "2024-01-01T10:00:00Z"  # Before since_datetime
                    }
                },
                {
                    "id": {"videoId": "new_video"},
                    "snippet": {
                        "title": "New Video",
                        "publishedAt": "2024-01-02T12:00:00Z"  # After since_datetime
                    }
                }
            ]
        }
        
        client = YouTubeClient(self.config)
        since_datetime = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        result = client._fetch_items_for_source("UC123", since_datetime)
        
        # Should only return the video after since_datetime
        assert len(result) == 1
        assert result[0]["id"] == "new_video"
        assert result[0]["title"] == "New Video"

    @patch('src.youtube_client.build')
    def test_get_new_items_since_with_categories(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock channel name lookup for both channels
        def mock_channel_response(**kwargs):
            channel_id = kwargs.get('id')
            if channel_id == "UC123":
                return Mock(execute=lambda: {"items": [{"snippet": {"title": "TechChannel"}}]})
            elif channel_id == "UC456":
                return Mock(execute=lambda: {"items": [{"snippet": {"title": "EduChannel"}}]})
            return Mock(execute=lambda: {"items": []})
        
        mock_youtube.channels.return_value.list.side_effect = mock_channel_response
        
        # Mock search API responses
        def mock_search_response(**kwargs):
            channelId = kwargs.get('channelId')
            if channelId == "UC123":
                return Mock(execute=lambda: {
                    "items": [{
                        "id": {"videoId": "tech_video"},
                        "snippet": {
                            "title": "Tech Video",
                            "publishedAt": "2024-01-02T12:00:00Z"
                        }
                    }]
                })
            elif channelId == "UC456":
                return Mock(execute=lambda: {
                    "items": [{
                        "id": {"videoId": "edu_video"},
                        "snippet": {
                            "title": "Education Video",
                            "publishedAt": "2024-01-02T12:00:00Z"
                        }
                    }]
                })
            return Mock(execute=lambda: {"items": []})
        
        mock_youtube.search.return_value.list.side_effect = mock_search_response
        
        client = YouTubeClient(self.categorized_config)
        since_datetime = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        result = client.get_new_items_since(since_datetime)
        
        assert len(result) == 2
        
        # Find items by ID
        tech_item = next(item for item in result if item["id"] == "tech_video")
        edu_item = next(item for item in result if item["id"] == "edu_video")
        
        # Verify categories are assigned
        assert tech_item["category"] == "tech"
        assert edu_item["category"] == "education"
        
        # Verify channel names are used
        assert tech_item["channel_id"] == "TechChannel"
        assert edu_item["channel_id"] == "EduChannel"

    @patch('src.youtube_client.build')
    def test_channel_name_caching_across_calls(self, mock_build):
        mock_youtube = Mock()
        mock_build.return_value = mock_youtube
        
        # Mock channel name lookup - should only be called once due to caching
        mock_request = Mock()
        mock_youtube.channels.return_value.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [{"snippet": {"title": "TechChannel"}}]
        }
        
        client = YouTubeClient(self.config)
        
        # Call _get_channel_name multiple times
        name1 = client._get_channel_name("UC123")
        name2 = client._get_channel_name("UC123")
        name3 = client._get_channel_name("UC123")
        
        assert name1 == "TechChannel"
        assert name2 == "TechChannel"
        assert name3 == "TechChannel"
        
        # API should only be called once due to caching
        mock_youtube.channels.return_value.list.assert_called_once()