# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Media Monitor is a Python application that tracks new posts from Reddit subreddits, new videos from YouTube channels, and new posts from Bluesky users, then sends email notifications with a summary of new content. It's designed to run as a scheduled task (e.g., via cron) to provide regular updates.

## Development Commands

**Setup and Installation:**
```bash
pip install -r requirements.txt
mkdir -p data logs
cp config/config.yaml.example config/config.yaml
```

**Running the Application:**
```bash
python main.py
```

**Running Tests:**
```bash
python -m pytest tests/
```

## Architecture

The application follows a modular client-based architecture:

**Core Components:**
- `main.py` - Entry point that orchestrates the monitoring workflow
- `src/db.py` - SQLite database operations for tracking last check timestamps
- `src/reddit_client.py` - Reddit API client using PRAW library
- `src/youtube_client.py` - YouTube API client using Google API client
- `src/bluesky_client.py` - Bluesky API client using direct HTTP requests

**Data Flow:**
1. Load configuration from `config/config.yaml`
2. Initialize SQLite database in `data/media_monitor.db`
3. For each enabled source (Reddit/YouTube/Bluesky):
   - Retrieve last checked timestamp from database
   - Fetch new items since last check via respective client
   - Update last checked timestamp
4. Compile all new items and send email notification if SMTP is enabled

**Client Pattern:**
All clients (Reddit, YouTube, and Bluesky) implement the same interface:
- `__init__(config)` - Initialize with service-specific configuration
- `get_new_items_since(datetime)` - Return list of new items since given timestamp

**Database Schema:**
- `last_checked` table with columns: `source` (TEXT, PRIMARY KEY), `last_checked` (TIMESTAMP)

**Configuration:**
YAML-based configuration in `config/config.yaml` with sections for `reddit`, `youtube`, `bluesky`, and `smtp`. Each section has an `enabled` flag to control which services are active.

All sources (Reddit, YouTube, and Bluesky) support two configuration formats:
1. **Simple format** (backward compatible): List subreddits/channels/users directly
2. **Categorized format**: Group subreddits/channels/users under named categories for organized email output

When using categories, email output groups items by category within each source section.

**Logging:**
Uses rotating file handler writing to `logs/app.log` with 5MB rotation and 5 backup files.