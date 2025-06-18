from googleapiclient.discovery import build
from datetime import datetime, timezone
from .base_client import BaseMediaClient

class YouTubeClient(BaseMediaClient):
    def __init__(self, config):
        """
        Initialize with a config dictionary, e.g.:
        {
            "api_key": "...",
            "channels": ["UC_x5XG1OV2P6uZZ5FSM9Ttw", ...]  # Simple format
        }
        OR categorized format:
        {
            "api_key": "...",
            "categories": {
                "tech": ["UC_x5XG1OV2P6uZZ5FSM9Ttw", ...],
                "education": ["UC2C_jShtL725hvbm1arSV9w", ...]
            }
        }
        """
        super().__init__(config)
        self.api_key = config["api_key"]
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        self.channels = self.items

    def _get_items_from_config(self, config):
        """Extract channels list from config for simple format."""
        return config.get("channels", [])
    
    def _fetch_items_for_source(self, channel_id, since_datetime):
        """Fetch videos from a specific channel."""
        videos = []
        published_after = since_datetime.isoformat("T").replace("+00:00", "Z")
        
        request = self.youtube.search().list(
            part="snippet",
            channelId=channel_id,
            publishedAfter=published_after,
            maxResults=50,
            order="date",
            type="video"
        )
        response = request.execute()
        for item in response.get("items", []):
            video_published = item["snippet"]["publishedAt"]
            video_datetime = datetime.fromisoformat(video_published.replace("Z", "+00:00"))
            if video_datetime > since_datetime:
                video_data = {
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    "published_at": video_datetime,
                    "channel_id": channel_id
                }
                videos.append(video_data)
        return videos