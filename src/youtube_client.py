import logging
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
    
    def _pre_fetch_optimization(self, channel_ids):
        """Batch fetch channel names for all channels at once."""
        self._batch_fetch_channel_names(channel_ids)
    
    def _batch_fetch_channel_names(self, channel_ids):
        """Fetch channel names for multiple channel IDs in a single API call."""
        if not channel_ids:
            return
        
        # Filter out already cached channel IDs
        uncached_ids = [cid for cid in channel_ids if cid not in self.channel_names_cache]
        if not uncached_ids:
            return
        
        try:
            # YouTube API supports up to 50 channel IDs per request
            batch_size = 50
            for i in range(0, len(uncached_ids), batch_size):
                batch_ids = uncached_ids[i:i + batch_size]
                ids_param = ",".join(batch_ids)
                
                request = self.youtube.channels().list(
                    part="snippet",
                    id=ids_param
                )
                response = request.execute()
                
                # Cache the results
                for item in response.get("items", []):
                    channel_id = item["id"]
                    channel_name = item["snippet"]["title"]
                    self.channel_names_cache[channel_id] = channel_name
                
                # For any channels that weren't returned, use the ID as fallback
                returned_ids = {item["id"] for item in response.get("items", [])}
                for channel_id in batch_ids:
                    if channel_id not in returned_ids:
                        self.channel_names_cache[channel_id] = channel_id
                        
        except Exception as e:
            logging.warning(f"Failed to batch fetch channel names: {e}")
            # Fallback: cache all requested IDs as themselves
            for channel_id in uncached_ids:
                if channel_id not in self.channel_names_cache:
                    self.channel_names_cache[channel_id] = channel_id
    
    def _get_channel_name(self, channel_id):
        """Get channel name from ID, using cache to avoid repeated API calls."""
        if channel_id in self.channel_names_cache:
            return self.channel_names_cache[channel_id]
        
        # If not in cache, batch fetch (this is now a fallback for single requests)
        self._batch_fetch_channel_names([channel_id])
        return self.channel_names_cache.get(channel_id, channel_id)
    
    def _fetch_items_for_source(self, channel_id, since_datetime):
        """Fetch videos from a specific channel."""
        videos = []
        try:
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
                        "channel_id": channel_id,
                        "channel_name": channel_name
                    }
                    videos.append(video_data)
        except Exception as e:
            logging.error(f"YouTube API error for channel '{channel_id}': {e}")
        
        return videos