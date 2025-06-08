from googleapiclient.discovery import build
from datetime import datetime, timezone

class YouTubeClient:
    def __init__(self, config):
        """
        Initialize with a config dictionary, e.g.:
        {
            "api_key": "...",
            "channels": ["UC_x5XG1OV2P6uZZ5FSM9Ttw", ...]
        }
        """
        self.api_key = config["api_key"]
        self.channels = config["channels"]
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

    def get_new_videos_since(self, since_datetime):
        """
        Retrieve new videos from configured channels since the given datetime.
        Returns a list of dicts with video info.
        """
        new_videos = []
        published_after = since_datetime.isoformat("T").replace("+00:00", "Z")
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
                    new_videos.append({
                        "id": item["id"]["videoId"],
                        "title": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                        "published_at": video_datetime,
                        "channel_id": channel_id
                    })
        return new_videos