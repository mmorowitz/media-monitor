from googleapiclient.discovery import build
from datetime import datetime, timezone

class YouTubeClient:
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
        self.api_key = config["api_key"]
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        
        # Support both simple and categorized formats
        if "categories" in config:
            self.categories = config["categories"]
            self.channels = []
            for category_channels in self.categories.values():
                self.channels.extend(category_channels)
        else:
            self.categories = None
            self.channels = config.get("channels", [])

    def get_new_items_since(self, since_datetime):
        """
        Retrieve new videos from configured channels since the given datetime.
        Returns a list of dicts with video info, including category if categorized.
        """
        new_videos = []
        published_after = since_datetime.isoformat("T").replace("+00:00", "Z")
        
        # Create a mapping from channel to category if using categories
        channel_to_category = {}
        if self.categories:
            for category, channel_list in self.categories.items():
                for channel in channel_list:
                    channel_to_category[channel] = category
        
        for channel_id in self.channels:
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
                    
                    # Add category if using categorized format
                    if self.categories:
                        video_data["category"] = channel_to_category.get(channel_id, "uncategorized")
                    
                    new_videos.append(video_data)
        return new_videos