# Media Monitor

Media Monitor is a Python application that tracks new posts from specified Reddit subreddits and new videos from specified YouTube channels, then sends a summary email report.

## Features

- Monitors multiple Reddit subreddits for new posts
- Monitors multiple YouTube channels for new videos
- **Optional categorization**: Group subreddits and channels by category for organized email output
- **Professional email templates**: Modern, responsive HTML emails with CSS styling
- **Environment variable support**: Override any configuration value via `MEDIA_MONITOR_*` environment variables
- Sends email notifications with a summary of new items
- Configurable via YAML file
- Uses SQLite for tracking last checked times
- Comprehensive error handling and retry logic

## Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd media-monitor
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application:**
   - Copy the example config and edit it:
     ```bash
     cp config/config.yaml.example config/config.yaml
     ```
   - Fill in your Reddit, YouTube, and SMTP credentials in `config/config.yaml`.

4. **Create required directories:**
   ```bash
   mkdir -p data logs
   ```

## Configuration

Edit `config/config.yaml` to set up your sources and email settings.

### Simple Configuration (Backward Compatible)

```yaml
reddit:
  enabled: true
  subreddits:
    - example_subreddit
  client_id: YOUR_CLIENT_ID
  client_secret: YOUR_CLIENT_SECRET
  user_agent: YOUR_USER_AGENT

youtube:
  enabled: true
  api_key: YOUR_API_KEY
  channels:
    - CHANNEL_ID

smtp:
  enabled: true
  server: smtp.example.com
  port: 465
  username: your@email.com
  password: yourpassword
  from: your@email.com
  to:
    - recipient@example.com
  subject: Media Monitor Report
```

### Categorized Configuration

For better organization, you can group subreddits and channels by category:

```yaml
reddit:
  enabled: true
  categories:
    news:
      - worldnews
      - politics
      - technology
    entertainment:
      - movies
      - gaming
      - music
    programming:
      - python
      - learnprogramming
  client_id: YOUR_CLIENT_ID
  client_secret: YOUR_CLIENT_SECRET
  user_agent: YOUR_USER_AGENT

youtube:
  enabled: true
  categories:
    tech:
      - UC_x5XG1OV2P6uZZ5FSM9Ttw
      - UCXuqSBlHAE6Xw-yeJA0Tunw
    education:
      - UC2C_jShtL725hvbm1arSV9w
      - UCJ0-OtVpF0wOKEqT2Z1HEtA
  api_key: YOUR_API_KEY

smtp:
  enabled: true
  server: smtp.example.com
  port: 465
  username: your@email.com
  password: yourpassword
  from: your@email.com
  to:
    - recipient@example.com
  subject: Media Monitor Report
```

When using categories, the email report will group items by category within each source, making it easier to scan through different types of content.

### Environment Variable Overrides

You can override any configuration value using environment variables with the `MEDIA_MONITOR_` prefix:

```bash
# Override Reddit credentials
export MEDIA_MONITOR_REDDIT_CLIENT_ID="your_reddit_client_id"
export MEDIA_MONITOR_REDDIT_CLIENT_SECRET="your_reddit_secret"

# Override SMTP settings
export MEDIA_MONITOR_SMTP_PASSWORD="your_smtp_password"
export MEDIA_MONITOR_SMTP_TO="email1@example.com,email2@example.com"

# Override service enablement
export MEDIA_MONITOR_YOUTUBE_ENABLED="false"
```

Environment variables support automatic type conversion:
- Booleans: `true`, `1`, `yes`, `on` → `True`; `false`, `0`, `no`, `off` → `False`
- Integers: Automatically converted for port numbers
- Lists: Comma-separated values (for email addresses)

## Usage

Run the main script:

```bash
python main.py
```

- The script will log to `logs/app.log`.
- The SQLite database is stored at `data/media_monitor.db`.

### Running as a Scheduled Task

Media Monitor is designed to run as a scheduled, recurring task using a job scheduler such as `cron` (on Unix/macOS) or Task Scheduler (on Windows). This allows the script to automatically check for new Reddit posts and YouTube videos at regular intervals and send summary emails without manual intervention.

**Example: Running once a day with cron (macOS/Linux):**

1. Open your crontab:
   ```bash
   crontab -e
   ```
2. Add a line like this to run the script every day at midnight:
   ```
   0 0 * * * cd /path/to/media-monitor && /usr/bin/python3 main.py
   ```

Adjust the path to your Python executable and project directory as needed.

## Email Templates

Media Monitor uses Jinja2 templates to generate professional, responsive email reports.

### Template Files

- `templates/email_template.html` - Modern HTML email with CSS styling
- `templates/email_template.txt` - Plain text version for email clients that don't support HTML

### Template Features

- **Responsive Design**: Mobile-friendly layout that works across email clients
- **Modern Styling**: Clean, professional appearance with proper color scheme
- **Category Support**: Automatically groups content by categories when configured
- **Score Display**: Shows Reddit post scores when available
- **Conditional Rendering**: Adapts layout based on content structure

### Customizing Email Templates

You can modify the templates in the `templates/` directory to customize the email appearance:

1. **HTML Template** (`templates/email_template.html`):
   - Modern CSS styling with professional color scheme
   - Responsive design that works on mobile devices
   - Support for categories, scores, and complex grouping

2. **Text Template** (`templates/email_template.txt`):
   - Clean plain text format for email clients that don't support HTML
   - Maintains proper structure and readability

### Template Variables

The templates have access to the following variables:
- `services` - Dictionary of service data (reddit, youtube)
- `has_items` - Boolean indicating if any new items were found
- `timestamp` - Current timestamp for email generation

### Template Example

The generated emails include:
- Clean header with report title
- Organized sections for each service (Reddit, YouTube)
- Category grouping when configured
- Item details with titles, links, and metadata
- Professional footer with timestamp

## File Structure

- `main.py` — Main entry point
- `src/` — Source code for Reddit, YouTube, and database logic
  - `base_client.py` — Abstract base class for media clients
  - `reddit_client.py` — Reddit API integration
  - `youtube_client.py` — YouTube API integration
  - `db.py` — Database operations with context managers
- `templates/` — Jinja2 email templates
  - `email_template.html` — HTML email template
  - `email_template.txt` — Plain text email template
- `config/` — Configuration files
- `data/` — SQLite database
- `logs/` — Log files
- `tests/` — Comprehensive test suite

## License

MIT License

---

*Generated by [GitHub Copilot](https://github.com/features/copilot)*