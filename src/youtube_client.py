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
        self.channel_names_cache = {}

    def _get_items_from_config(self, config):
        """Extract channels list from config for simple format."""
        return config.get("channels", [])
    
    def _get_channel_name(self, channel_id):
        """Get channel name from ID, using cache to avoid repeated API calls."""
        if channel_id in self.channel_names_cache:
            return self.channel_names_cache[channel_id]
        
        try:
            request = self.youtube.channels().list(
                part="snippet",
                id=channel_id
            )
            response = request.execute()
            
            if response.get("items"):
                channel_name = response["items"][0]["snippet"]["title"]
                self.channel_names_cache[channel_id] = channel_name
                return channel_name
        except Exception:
            pass
        
        # Fallback to channel ID if name fetch fails
        self.channel_names_cache[channel_id] = channel_id
        return channel_id
    
    def _fetch_items_for_source(self, channel_id, since_datetime):
        """Fetch videos from a specific channel."""
        videos = []
        published_after = since_datetime.isoformat("T").replace("+00:00", "Z")
        
        # Get channel name for friendly display
        channel_name = self._get_channel_name(channel_id)
        
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
                    "channel_id": channel_name
                }
                videos.append(video_data)
        return videos