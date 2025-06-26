import logging
from logging.handlers import RotatingFileHandler
import yaml
import time
import os
from datetime import datetime, timedelta, timezone
from src.db import init_db, get_last_checked, update_last_checked
from src.reddit_client import RedditClient
from src.youtube_client import YouTubeClient
import smtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape

log_handler = RotatingFileHandler(
    'logs/app.log', maxBytes=5*1024*1024, backupCount=5  # 5 MB per file, keep 5 backups
)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))

logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO
)

def _apply_env_overrides(config):
    """Apply environment variable overrides to configuration.
    
    Environment variables should be in the format:
    MEDIA_MONITOR_<SERVICE>_<FIELD> = value
    
    Examples:
    - MEDIA_MONITOR_REDDIT_CLIENT_ID overrides reddit.client_id
    - MEDIA_MONITOR_SMTP_PASSWORD overrides smtp.password
    - MEDIA_MONITOR_YOUTUBE_API_KEY overrides youtube.api_key
    """
    env_prefix = "MEDIA_MONITOR_"
    
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(env_prefix):
            continue
        
        # Parse the environment variable name
        config_path = env_key[len(env_prefix):].lower().split('_')
        if len(config_path) < 2:
            continue
        
        service = config_path[0]
        field = '_'.join(config_path[1:])
        
        # Apply the override
        if service not in config:
            config[service] = {}
        
        # Convert certain values to appropriate types
        if field == 'enabled':
            env_value = env_value.lower() in ('true', '1', 'yes', 'on')
        elif field == 'port':
            try:
                env_value = int(env_value)
            except ValueError:
                logging.warning(f"Invalid port value in {env_key}: {env_value}")
                continue
        elif field == 'to' and service == 'smtp':
            # Split comma-separated email addresses
            env_value = [email.strip() for email in env_value.split(',')]
        
        config[service][field] = env_value
        logging.info(f"Applied environment override: {service}.{field}")

def load_config(filename='config/config.yaml'):
    try:
        with open(filename, 'r') as file:
            config = yaml.safe_load(file)
            _apply_env_overrides(config)
            validate_config(config)
            return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {filename}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Invalid YAML in configuration file: {e}")
        raise

def validate_config(config):
    """Validate configuration structure and required fields."""
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")
    
    # Validate Reddit configuration if enabled
    reddit_config = config.get('reddit', {})
    if reddit_config.get('enabled', False):
        required_reddit_fields = ['client_id', 'client_secret', 'user_agent']
        for field in required_reddit_fields:
            if not reddit_config.get(field):
                raise ValueError(f"Reddit configuration missing required field: {field}")
        
        # Validate Reddit has either subreddits or categories
        if not reddit_config.get('subreddits') and not reddit_config.get('categories'):
            raise ValueError("Reddit configuration must specify either 'subreddits' or 'categories'")
    
    # Validate YouTube configuration if enabled
    youtube_config = config.get('youtube', {})
    if youtube_config.get('enabled', False):
        if not youtube_config.get('api_key'):
            raise ValueError("YouTube configuration missing required field: api_key")
        
        # Validate YouTube has either channels or categories
        if not youtube_config.get('channels') and not youtube_config.get('categories'):
            raise ValueError("YouTube configuration must specify either 'channels' or 'categories'")
    
    # Validate SMTP configuration if enabled
    smtp_config = config.get('smtp', {})
    if smtp_config.get('enabled', False):
        required_smtp_fields = ['server', 'port', 'username', 'password', 'from', 'to']
        for field in required_smtp_fields:
            if not smtp_config.get(field):
                raise ValueError(f"SMTP configuration missing required field: {field}")
        
        # Validate port is a number
        try:
            int(smtp_config['port'])
        except (ValueError, TypeError):
            raise ValueError("SMTP port must be a valid integer")
        
        # Validate 'to' is a list
        if not isinstance(smtp_config['to'], list):
            raise ValueError("SMTP 'to' field must be a list of email addresses")
    
    logging.info("Configuration validation passed")

def process_source(source_name, client_class, config):
    items = []
    if config.get(source_name, {}).get("enabled"):
        try:
            logging.info(f"{source_name.capitalize()} integration is enabled.")
            client = client_class(config[source_name])
            last_checked = get_last_checked(source_name)
            if last_checked:
                last_checked = datetime.fromisoformat(last_checked)
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=timezone.utc)
            else:
                last_checked = datetime.now(timezone.utc) - timedelta(hours=72)
                logging.info(f"No previous check found, using last 72 hours as initial window for {source_name}.")
            logging.info(f"Last checked time for {source_name.capitalize()}: {last_checked}")

            new_items = client.get_new_items_since(last_checked)
            item_type = f"{source_name.capitalize()} items"

            logging.info(f"Found {len(new_items)} new {item_type} since last checked.")
            for item in new_items:
                logging.debug(f"New {source_name} item: {item['title']} (ID: {item['id']})")

            update_last_checked(source_name, datetime.now(timezone.utc))
            logging.info(f"Updated last checked time for {source_name.capitalize()} in the database.")
            items = new_items
        except Exception as e:
            logging.error(f"Error processing {source_name}: {e}")
            return []
    return items

def load_smtp_settings(config):
    smtp_cfg = config.get("smtp", {})
    if not smtp_cfg.get("enabled", False):
        logging.info("SMTP is not enabled in config.")
        return None
    return smtp_cfg

def group_items_by_category_and_source(items):
    """
    Group items by category (optional) and then by source (subreddit/channel).
    Returns a nested dict structure.
    """
    if not items:
        return {}
    
    # First group by category if categories exist
    has_categories = any(item.get('category') for item in items)
    
    if has_categories:
        # Group by category first
        categorized = {}
        for item in items:
            category = item.get('category', 'uncategorized')
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(item)
        
        # Then group each category by source
        result = {}
        for category, category_items in categorized.items():
            result[category] = group_by_source(category_items)
        return result
    else:
        # No categories, just group by source
        return {'uncategorized': group_by_source(items)}

def group_by_source(items):
    """Group items by their source (subreddit or channel_id)."""
    grouped = {}
    for item in items:
        source = item.get('subreddit') or item.get('channel_name', 'unknown')
        if source not in grouped:
            grouped[source] = []
        grouped[source].append(item)
    return grouped

def _setup_jinja_environment():
    """Set up Jinja2 environment with custom filters."""
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    # Add custom filter for grouping items
    env.filters['group_by_category_and_source'] = group_items_by_category_and_source
    
    return env

def format_email_content(all_items):
    """Format email content using Jinja2 templates.
    
    Returns:
        tuple: (plain_text_body, html_body)
    """
    # Set up Jinja2 environment
    env = _setup_jinja_environment()
    
    # Prepare template context
    has_items = any(items for items in all_items.values())
    
    context = {
        'services': all_items,
        'has_items': has_items,
        'timestamp': datetime.now(timezone.utc)
    }
    
    # Render templates
    try:
        text_template = env.get_template('email_template.txt')
        html_template = env.get_template('email_template.html')
        
        plain_text = text_template.render(context)
        html_content = html_template.render(context)
        
        return plain_text, html_content
        
    except Exception as e:
        logging.error(f"Error rendering email templates: {e}")
        # Fallback to simple content
        if has_items:
            fallback_text = f"New items found from {len(all_items)} services. Check the application logs for details."
            fallback_html = f"<p>{fallback_text}</p>"
        else:
            fallback_text = "No new items found from any source."
            fallback_html = f"<p>{fallback_text}</p>"
        
        return fallback_text, fallback_html

def send_email(smtp_cfg, all_items):
    """Send email notification with formatted content using Jinja2 templates."""
    msg = EmailMessage()
    msg["Subject"] = "Media Monitor Report"
    msg["From"] = smtp_cfg["from"]
    msg["To"] = ", ".join(smtp_cfg["to"])

    # Generate email content using templates
    plain_text, html_content = format_email_content(all_items)
    
    # Set message content
    msg.set_content(plain_text)
    msg.add_alternative(html_content, subtype='html')

    # Send email with retry logic
    _send_email_with_retry(smtp_cfg, msg)

def _send_email_with_retry(smtp_cfg, msg, max_retries=3, base_delay=1.0):
    """Send email with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            with smtplib.SMTP_SSL(smtp_cfg["server"], smtp_cfg["port"]) as server:
                server.login(smtp_cfg["username"], smtp_cfg["password"])
                server.send_message(msg)
            logging.info("Email sent successfully.")
            return True
        
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP Authentication failed: {e}")
            # Don't retry authentication failures
            return False
        
        except smtplib.SMTPRecipientsRefused as e:
            logging.error(f"SMTP Recipients refused: {e}")
            # Don't retry recipient errors
            return False
        
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPException) as e:
            attempt_num = attempt + 1
            if attempt_num < max_retries:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"SMTP error on attempt {attempt_num}/{max_retries}: {e}. Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                logging.error(f"Failed to send email after {max_retries} attempts: {e}")
                return False
        
        except Exception as e:
            attempt_num = attempt + 1
            if attempt_num < max_retries:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"Unexpected error on attempt {attempt_num}/{max_retries}: {e}. Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                logging.error(f"Failed to send email after {max_retries} attempts with unexpected error: {e}")
                return False
    
    return False

def main():
    logging.info("Starting the application...")
    config = load_config()
    logging.info("Loaded configuration")

    if not init_db():
        logging.error("Failed to initialize database. Exiting.")
        return

    all_items = {}
    all_items["reddit"] = process_source("reddit", RedditClient, config)
    all_items["youtube"] = process_source("youtube", YouTubeClient, config)

    smtp_cfg = load_smtp_settings(config)
    if smtp_cfg:
        send_email(smtp_cfg, all_items)

if __name__ == "__main__":
    main()
    logging.info("Application finished successfully.")