import pytest
import os
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta

from main import main, load_config, process_source, send_email, load_smtp_settings
from src.reddit_client import RedditClient
from src.youtube_client import YouTubeClient
from src.db import init_db, get_last_checked_with_conn as get_last_checked, update_last_checked_with_conn as update_last_checked


# Mark all tests in this class as requiring explicit invocation
pytestmark = pytest.mark.integration


class TestFullIntegration:
    """
    Full integration tests that use real APIs and send actual emails.
    
    IMPORTANT: Before running these tests, you MUST:
    1. Copy config/integration_test.yaml to config/integration_test_real.yaml
    2. Fill in real API credentials:
       - Reddit: client_id, client_secret, user_agent
       - YouTube: api_key  
       - SMTP: server, username, password, from, to emails
    3. Set environment variable: INTEGRATION_TEST_CONFIG=config/integration_test_real.yaml
    
    These tests will:
    - Make real API calls to Reddit and YouTube
    - Send actual email notifications
    - Use a temporary database for isolation
    
    Run with: pytest tests/test_integration.py -v -s
    """
    
    @pytest.fixture
    def config_file(self):
        """Get the integration test config file path from environment or skip test."""
        config_path = os.environ.get('INTEGRATION_TEST_CONFIG')
        if not config_path:
            pytest.skip("Set INTEGRATION_TEST_CONFIG environment variable to run integration tests")
        
        if not os.path.exists(config_path):
            pytest.skip(f"Integration test config file not found: {config_path}")
        
        return config_path
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize the database manually since init_db() creates its own connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS last_checked (
                source TEXT NOT NULL,
                last_checked TIMESTAMP NOT NULL,
                PRIMARY KEY (source) 
            );
        ''')
        conn.commit()
        
        yield conn
        
        # Cleanup
        conn.close()
        os.unlink(db_path)
    
    @pytest.fixture
    def integration_config(self, config_file):
        """Load the integration test configuration."""
        config = load_config(config_file)
        
        # Validate required credentials are present
        if config.get('reddit', {}).get('enabled'):
            reddit_cfg = config['reddit']
            required_reddit = ['client_id', 'client_secret', 'user_agent']
            for field in required_reddit:
                if not reddit_cfg.get(field) or reddit_cfg[field].startswith('YOUR_'):
                    pytest.skip(f"Reddit {field} not configured in {config_file}")
        
        if config.get('youtube', {}).get('enabled'):
            youtube_cfg = config['youtube']
            if not youtube_cfg.get('api_key') or youtube_cfg['api_key'].startswith('YOUR_'):
                pytest.skip(f"YouTube API key not configured in {config_file}")
        
        if config.get('smtp', {}).get('enabled'):
            smtp_cfg = config['smtp']
            required_smtp = ['server', 'username', 'password', 'from', 'to']
            for field in required_smtp:
                if not smtp_cfg.get(field) or (isinstance(smtp_cfg[field], str) and smtp_cfg[field].startswith('your_')):
                    pytest.skip(f"SMTP {field} not configured in {config_file}")
        
        return config
    
    def test_reddit_client_real_api(self, integration_config):
        """Test Reddit client with real API calls."""
        if not integration_config.get('reddit', {}).get('enabled'):
            pytest.skip("Reddit not enabled in integration config")
        
        print("\n=== Testing Reddit Client with Real API ===")
        
        # Test that we can create a client and fetch data
        reddit_client = RedditClient(integration_config['reddit'])
        
        # Set a recent timestamp to get some recent posts
        since_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        items = reddit_client.get_new_items_since(since_time)
        
        print(f"Retrieved {len(items)} Reddit items from the last 24 hours")
        
        # Verify structure of returned items
        if items:
            item = items[0]
            required_fields = ['id', 'title', 'url', 'created_utc', 'score']
            for field in required_fields:
                assert field in item, f"Missing field {field} in Reddit item"
            
            print(f"Sample item: {item['title'][:50]}...")
            
            # Test with categories if configured
            if 'category' in item:
                print(f"Item category: {item['category']}")
        
        assert isinstance(items, list)
    
    def test_youtube_client_real_api(self, integration_config):
        """Test YouTube client with real API calls."""
        if not integration_config.get('youtube', {}).get('enabled'):
            pytest.skip("YouTube not enabled in integration config")
        
        print("\n=== Testing YouTube Client with Real API ===")
        
        # Test that we can create a client and fetch data
        youtube_client = YouTubeClient(integration_config['youtube'])
        
        # Set a recent timestamp to get some recent videos
        since_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        items = youtube_client.get_new_items_since(since_time)
        
        print(f"Retrieved {len(items)} YouTube items from the last 24 hours")
        
        # Verify structure of returned items
        if items:
            item = items[0]
            required_fields = ['id', 'title', 'url', 'published_at', 'channel_id']
            for field in required_fields:
                assert field in item, f"Missing field {field} in YouTube item"
            
            print(f"Sample item: {item['title'][:50]}...")
            print(f"Channel: {item['channel_id']}")
            
            # Verify channel_id contains a human-readable name, not just an ID
            channel_id = item['channel_id']
            assert not channel_id.startswith('UC'), f"Channel ID should be human-readable name, got: {channel_id}"
            
            # Test with categories if configured
            if 'category' in item:
                print(f"Item category: {item['category']}")
        
        assert isinstance(items, list)
    
    def test_database_operations(self, temp_db):
        """Test database operations with real database."""
        print("\n=== Testing Database Operations ===")
        
        # Test getting last checked when no record exists
        last_checked = get_last_checked(temp_db, 'reddit')
        assert last_checked is None
        
        # Test updating last checked
        now = datetime.now(timezone.utc)
        update_last_checked(temp_db, 'reddit', now)
        
        # Test getting last checked after update
        last_checked = get_last_checked(temp_db, 'reddit')
        assert last_checked is not None
        
        # Parse the returned timestamp and verify it's close to what we set
        parsed_time = datetime.fromisoformat(last_checked)
        time_diff = abs((parsed_time - now).total_seconds())
        assert time_diff < 1  # Should be within 1 second
        
        print(f"Database operations working correctly. Last checked: {last_checked}")
    
    def test_process_source_integration(self, integration_config, temp_db):
        """Test process_source function with real clients."""
        print("\n=== Testing Source Processing Integration ===")
        
        # Test Reddit if enabled
        if integration_config.get('reddit', {}).get('enabled'):
            # Create a wrapper to use legacy database connection pattern
            def process_source_with_db(source_name, client_class, config, db_conn):
                # Temporarily monkey patch the database functions to use the connection
                import main
                original_get = main.get_last_checked
                original_update = main.update_last_checked
                
                main.get_last_checked = lambda source: get_last_checked(db_conn, source)
                main.update_last_checked = lambda source, timestamp: update_last_checked(db_conn, source, timestamp)
                
                try:
                    return main.process_source(source_name, client_class, config)
                finally:
                    main.get_last_checked = original_get
                    main.update_last_checked = original_update
            
            reddit_items = process_source_with_db('reddit', RedditClient, integration_config, temp_db)
            print(f"Reddit process_source returned {len(reddit_items)} items")
            assert isinstance(reddit_items, list)
            
            # Verify last checked was updated
            last_checked = get_last_checked(temp_db, 'reddit')
            assert last_checked is not None
            print(f"Reddit last checked updated to: {last_checked}")
        
        # Test YouTube if enabled
        if integration_config.get('youtube', {}).get('enabled'):
            youtube_items = process_source_with_db('youtube', YouTubeClient, integration_config, temp_db)
            print(f"YouTube process_source returned {len(youtube_items)} items")
            assert isinstance(youtube_items, list)
            
            # Verify last checked was updated
            last_checked = get_last_checked(temp_db, 'youtube')
            assert last_checked is not None
            print(f"YouTube last checked updated to: {last_checked}")
    
    def test_email_integration(self, integration_config):
        """Test sending actual email with real SMTP."""
        smtp_settings = load_smtp_settings(integration_config)
        if not smtp_settings:
            pytest.skip("SMTP not enabled in integration config")
        
        print("\n=== Testing Email Integration ===")
        
        # Create test data with categories and sources
        test_items = {
            'reddit': [
                {
                    'id': 'test_reddit_1',
                    'title': 'Integration Test Reddit Post',
                    'url': 'https://reddit.com/r/test/comments/test1',
                    'created_utc': datetime.now(timezone.utc),
                    'category': 'test',
                    'subreddit': 'test',
                    'score': 42
                }
            ],
            'youtube': [
                {
                    'id': 'test_youtube_1', 
                    'title': 'Integration Test YouTube Video',
                    'url': 'https://youtube.com/watch?v=test1',
                    'published_at': datetime.now(timezone.utc),
                    'category': 'test',
                    'channel_id': 'Test Channel'
                }
            ]
        }
        
        print(f"Sending test email to: {smtp_settings['to']}")
        print("Email will contain test data to verify integration")
        
        # This will send an actual email
        send_email(smtp_settings, test_items)
        
        print("✅ Email sent successfully!")
        print("Check your email inbox to verify the email was received.")
    
    def test_full_application_integration(self, integration_config, temp_db, monkeypatch):
        """Test the complete application workflow with real APIs and email."""
        print("\n=== Testing Full Application Integration ===")
        
        # Mock the config loading to use our test config
        def mock_load_config(_=None):
            return integration_config
        
        # Mock database connection to use our temp database
        def mock_connect(_):
            return temp_db
        
        # Mock the database path in main.py
        monkeypatch.setattr('main.load_config', mock_load_config)
        monkeypatch.setattr('sqlite3.connect', mock_connect)
        
        print("Running full application with real APIs and email...")
        print("This will:")
        print("1. Fetch real data from Reddit/YouTube APIs")
        print("2. Update database with timestamps") 
        print("3. Send actual email notification")
        
        # Run the main application
        main()
        
        print("✅ Full application integration test completed!")
        print("Check your email for the notification with real data.")
        print("Database was updated during the main() execution.")


if __name__ == "__main__":
    """
    To run these tests manually:
    
    1. Set up your config file:
       cp config/integration_test.yaml config/integration_test_real.yaml
       # Edit integration_test_real.yaml with real credentials
    
    2. Set environment variable:
       export INTEGRATION_TEST_CONFIG=config/integration_test_real.yaml
    
    3. Run the tests:
       python -m pytest tests/test_integration.py -v -s
    """
    import sys
    print("Integration tests require real API credentials and will send actual emails.")
    print("See the docstring in this file for setup instructions.")
    sys.exit(1)