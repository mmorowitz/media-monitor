import pytest
import yaml
import smtplib
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

from main import load_config, process_source, load_smtp_settings, send_email, group_items_by_category_and_source, group_by_source, validate_config, _apply_env_overrides, format_email_content


class TestLoadConfig:
    @patch('builtins.open', new_callable=mock_open, read_data='reddit:\n  enabled: true')
    @patch('yaml.safe_load')
    def test_load_config_success(self, mock_yaml_load, mock_file):
        # Provide a complete valid configuration
        mock_config = {
            'reddit': {
                'enabled': True,
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'user_agent': 'test_agent',
                'subreddits': ['test']
            }
        }
        mock_yaml_load.return_value = mock_config

        result = load_config('config/test.yaml')

        mock_file.assert_called_once_with('config/test.yaml', 'r')
        mock_yaml_load.assert_called_once()
        assert result == mock_config

    def test_load_config_default_filename(self):
        with patch('builtins.open', mock_open(read_data='test: data')) as mock_file:
            with patch('yaml.safe_load', return_value={'test': 'data'}):
                with patch('main.validate_config'):  # Skip validation for this test
                    load_config()
                    mock_file.assert_called_once_with('config/config.yaml', 'r')


class TestEnvironmentOverrides:
    def test_apply_env_overrides_reddit_config(self):
        config = {'reddit': {'enabled': False, 'client_id': 'original_id'}}

        with patch.dict('os.environ', {
            'MEDIA_MONITOR_REDDIT_CLIENT_ID': 'new_id',
            'MEDIA_MONITOR_REDDIT_ENABLED': 'true',
            'MEDIA_MONITOR_REDDIT_CLIENT_SECRET': 'secret123'
        }):
            _apply_env_overrides(config)

        assert config['reddit']['client_id'] == 'new_id'
        assert config['reddit']['enabled'] is True
        assert config['reddit']['client_secret'] == 'secret123'

    def test_apply_env_overrides_smtp_config(self):
        config = {'smtp': {'port': 25}}

        with patch.dict('os.environ', {
            'MEDIA_MONITOR_SMTP_PORT': '587',
            'MEDIA_MONITOR_SMTP_PASSWORD': 'mypass',
            'MEDIA_MONITOR_SMTP_TO': 'user1@example.com, user2@example.com'
        }):
            _apply_env_overrides(config)

        assert config['smtp']['port'] == 587
        assert config['smtp']['password'] == 'mypass'
        assert config['smtp']['to'] == ['user1@example.com', 'user2@example.com']

    def test_apply_env_overrides_youtube_config(self):
        config = {}

        with patch.dict('os.environ', {
            'MEDIA_MONITOR_YOUTUBE_API_KEY': 'youtube_key_123',
            'MEDIA_MONITOR_YOUTUBE_ENABLED': '1'
        }):
            _apply_env_overrides(config)

        assert config['youtube']['api_key'] == 'youtube_key_123'
        assert config['youtube']['enabled'] is True

    def test_apply_env_overrides_boolean_values(self):
        config = {}

        with patch.dict('os.environ', {
            'MEDIA_MONITOR_REDDIT_ENABLED': 'false',
            'MEDIA_MONITOR_YOUTUBE_ENABLED': '0',
            'MEDIA_MONITOR_SMTP_ENABLED': 'no'
        }):
            _apply_env_overrides(config)

        assert config['reddit']['enabled'] is False
        assert config['youtube']['enabled'] is False
        assert config['smtp']['enabled'] is False

    def test_apply_env_overrides_invalid_port(self):
        config = {}

        with patch.dict('os.environ', {'MEDIA_MONITOR_SMTP_PORT': 'invalid_port'}):
            with patch('main.logging') as mock_logging:
                _apply_env_overrides(config)
                mock_logging.warning.assert_called_once()
                # Port should not be set due to invalid value
                assert 'smtp' not in config or 'port' not in config.get('smtp', {})

    def test_apply_env_overrides_ignores_non_matching_vars(self):
        config = {}

        with patch.dict('os.environ', {
            'OTHER_VAR': 'value',
            'MEDIA_MONITOR_': 'incomplete',
            'MEDIA_MONITOR_INVALID': 'single_part'
        }):
            _apply_env_overrides(config)

        # Config should remain empty
        assert config == {}

    def test_apply_env_overrides_underscore_fields(self):
        config = {}

        with patch.dict('os.environ', {
            'MEDIA_MONITOR_REDDIT_USER_AGENT': 'MyBot/1.0',
            'MEDIA_MONITOR_REDDIT_CLIENT_SECRET': 'secret'
        }):
            _apply_env_overrides(config)

        assert config['reddit']['user_agent'] == 'MyBot/1.0'
        assert config['reddit']['client_secret'] == 'secret'

    @patch('main._apply_env_overrides')
    @patch('builtins.open', new_callable=mock_open, read_data='reddit:\n  enabled: true')
    @patch('yaml.safe_load')
    def test_load_config_applies_env_overrides(self, mock_yaml_load, mock_file, mock_apply_env):
        mock_config = {'reddit': {'enabled': True}}
        mock_yaml_load.return_value = mock_config

        with patch('main.validate_config'):
            load_config('test.yaml')

        mock_apply_env.assert_called_once_with(mock_config)


class TestValidateConfig:
    def test_validate_config_valid_reddit(self):
        config = {
            'reddit': {
                'enabled': True,
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'user_agent': 'test_agent',
                'subreddits': ['test']
            }
        }
        # Should not raise an exception
        validate_config(config)

    def test_validate_config_missing_reddit_field(self):
        config = {
            'reddit': {
                'enabled': True,
                'client_id': 'test_id',
                # Missing client_secret
                'user_agent': 'test_agent',
                'subreddits': ['test']
            }
        }
        with pytest.raises(ValueError, match="Reddit configuration missing required field: client_secret"):
            validate_config(config)

    def test_validate_config_valid_youtube(self):
        config = {
            'youtube': {
                'enabled': True,
                'api_key': 'test_key',
                'channels': ['test_channel']
            }
        }
        # Should not raise an exception
        validate_config(config)

    def test_validate_config_missing_youtube_sources(self):
        config = {
            'youtube': {
                'enabled': True,
                'api_key': 'test_key'
                # Missing channels and categories
            }
        }
        with pytest.raises(ValueError, match="YouTube configuration must specify either 'channels' or 'categories'"):
            validate_config(config)

    def test_validate_config_valid_smtp(self):
        config = {
            'smtp': {
                'enabled': True,
                'server': 'smtp.example.com',
                'port': 587,
                'username': 'user',
                'password': 'pass',
                'from': 'from@example.com',
                'to': ['to@example.com']
            }
        }
        # Should not raise an exception
        validate_config(config)

    def test_validate_config_invalid_smtp_port(self):
        config = {
            'smtp': {
                'enabled': True,
                'server': 'smtp.example.com',
                'port': 'invalid_port',
                'username': 'user',
                'password': 'pass',
                'from': 'from@example.com',
                'to': ['to@example.com']
            }
        }
        with pytest.raises(ValueError, match="SMTP port must be a valid integer"):
            validate_config(config)

    def test_validate_config_disabled_services(self):
        config = {
            'reddit': {'enabled': False},
            'youtube': {'enabled': False},
            'smtp': {'enabled': False}
        }
        # Should not raise an exception for disabled services
        validate_config(config)


class TestFormatEmailContent:
    def test_format_email_content_no_items(self):
        all_items = {}

        plain_text, html_content = format_email_content(all_items)

        # Check that both formats are returned
        assert isinstance(plain_text, str)
        assert isinstance(html_content, str)

        # Check content indicates no items
        assert "No new items" in plain_text
        assert "No new items" in html_content or "No New Content" in html_content

    def test_format_email_content_with_items(self):
        all_items = {
            'reddit': [
                {
                    'id': 'test1',
                    'title': 'Test Reddit Post',
                    'url': 'https://reddit.com/test1',
                    'subreddit': 'python',
                    'score': 42
                }
            ],
            'youtube': [
                {
                    'id': 'test2',
                    'title': 'Test YouTube Video',
                    'url': 'https://youtube.com/test2',
                    'channel_id': 'TechChannel'
                }
            ]
        }

        plain_text, html_content = format_email_content(all_items)

        # Check that both formats are returned
        assert isinstance(plain_text, str)
        assert isinstance(html_content, str)

        # Check content includes items
        assert 'Test Reddit Post' in plain_text
        assert 'Test YouTube Video' in plain_text
        assert 'python' in plain_text
        assert 'TechChannel' in plain_text

        assert 'Test Reddit Post' in html_content
        assert 'Test YouTube Video' in html_content
        assert 'python' in html_content
        assert 'TechChannel' in html_content

        # Check HTML contains proper tags
        assert '<html' in html_content
        assert '</html>' in html_content
        assert '<a href="https://reddit.com/test1"' in html_content
        assert '<a href="https://youtube.com/test2"' in html_content

    def test_format_email_content_with_categories(self):
        all_items = {
            'reddit': [
                {
                    'id': 'news1',
                    'title': 'Breaking News',
                    'url': 'https://reddit.com/news1',
                    'subreddit': 'worldnews',
                    'category': 'news',
                    'score': 156
                },
                {
                    'id': 'tech1',
                    'title': 'Tech Update',
                    'url': 'https://reddit.com/tech1',
                    'subreddit': 'technology',
                    'category': 'tech',
                    'score': 89
                }
            ]
        }

        plain_text, html_content = format_email_content(all_items)

        # Check categories are shown
        assert 'News' in plain_text or 'NEWS' in plain_text
        assert 'Tech' in plain_text or 'TECH' in plain_text
        assert 'worldnews' in plain_text
        assert 'technology' in plain_text

        # Check scores are displayed
        assert 'Score: 156' in plain_text
        assert 'Score: 89' in plain_text

        # Check HTML formatting
        assert 'Breaking News' in html_content
        assert 'Tech Update' in html_content
        assert 'Score: 156' in html_content
        assert 'Score: 89' in html_content

    def test_format_email_content_empty_service_lists(self):
        all_items = {
            'reddit': [],
            'youtube': []
        }

        plain_text, html_content = format_email_content(all_items)

        # Should handle empty lists gracefully
        assert isinstance(plain_text, str)
        assert isinstance(html_content, str)
        assert len(plain_text) > 0
        assert len(html_content) > 0

    @patch('main.logging')
    def test_format_email_content_template_error_fallback(self, mock_logging):
        # Mock template loading to fail
        with patch('main._setup_jinja_environment') as mock_setup:
            mock_env = Mock()
            mock_env.get_template.side_effect = Exception("Template not found")
            mock_setup.return_value = mock_env

            all_items = {'reddit': [{'title': 'test'}]}

            plain_text, html_content = format_email_content(all_items)

            # Should fall back to simple content
            assert isinstance(plain_text, str)
            assert isinstance(html_content, str)
            assert 'New items found' in plain_text
            assert '<p>' in html_content

            # Should log the error
            mock_logging.error.assert_called_once()


# TestFormatServiceItems class removed - functionality moved to Jinja2 templates
# The formatting logic is now tested via TestFormatEmailContent


class TestProcessSource:
    def setup_method(self):
        self.mock_db_conn = Mock()
        self.mock_client_class = Mock()
        self.mock_client = Mock()
        self.mock_client_class.return_value = self.mock_client

    def test_process_source_disabled(self):
        config = {'reddit': {'enabled': False}}

        result = process_source('reddit', self.mock_client_class, config)

        assert result == []
        self.mock_client_class.assert_not_called()

    def test_process_source_missing_config(self):
        config = {}

        result = process_source('reddit', self.mock_client_class, config)

        assert result == []
        self.mock_client_class.assert_not_called()

    @patch('main.get_last_checked')
    @patch('main.update_last_checked')
    @patch('main.datetime')
    def test_process_source_with_previous_check(self, mock_datetime, mock_update, mock_get):
        config = {'reddit': {'enabled': True, 'subreddits': ['test']}}
        last_checked_str = '2024-01-01T12:00:00+00:00'
        mock_get.return_value = last_checked_str

        mock_items = [
            {'id': '1', 'title': 'Test Post 1', 'url': 'https://example.com/1'},
            {'id': '2', 'title': 'Test Post 2', 'url': 'https://example.com/2'}
        ]
        self.mock_client.get_new_items_since.return_value = mock_items

        current_time = datetime.now(timezone.utc)
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat = datetime.fromisoformat

        result = process_source('reddit', self.mock_client_class, config)

        assert result == mock_items
        self.mock_client_class.assert_called_once_with(config['reddit'])
        mock_get.assert_called_once_with('reddit')
        self.mock_client.get_new_items_since.assert_called_once()
        mock_update.assert_called_once_with('reddit', current_time)

    @patch('main.get_last_checked')
    @patch('main.update_last_checked')
    @patch('main.datetime')
    def test_process_source_no_previous_check(self, mock_datetime, mock_update, mock_get):
        config = {'youtube': {'enabled': True, 'channels': ['test_channel']}}
        mock_get.return_value = None

        mock_items = []
        self.mock_client.get_new_items_since.return_value = mock_items

        current_time = datetime.now(timezone.utc)
        default_time = current_time - timedelta(hours=72)
        mock_datetime.now.return_value = current_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else current_time

        result = process_source('youtube', self.mock_client_class, config)

        assert result == mock_items
        self.mock_client_class.assert_called_once_with(config['youtube'])
        mock_get.assert_called_once_with('youtube')
        self.mock_client.get_new_items_since.assert_called_once()
        mock_update.assert_called_once_with('youtube', current_time)


class TestLoadSmtpSettings:
    def test_smtp_enabled(self):
        config = {
            'smtp': {
                'enabled': True,
                'server': 'smtp.example.com',
                'port': 587
            }
        }

        result = load_smtp_settings(config)

        assert result == config['smtp']

    def test_smtp_disabled(self):
        config = {
            'smtp': {
                'enabled': False,
                'server': 'smtp.example.com'
            }
        }

        result = load_smtp_settings(config)

        assert result is None

    def test_smtp_missing(self):
        config = {}

        result = load_smtp_settings(config)

        assert result is None

    def test_smtp_enabled_missing(self):
        config = {
            'smtp': {
                'server': 'smtp.example.com'
            }
        }

        result = load_smtp_settings(config)

        assert result is None


class TestSendEmail:
    def setup_method(self):
        self.smtp_cfg = {
            'server': 'smtp.example.com',
            'port': 587,
            'username': 'test@example.com',
            'password': 'password',
            'from': 'test@example.com',
            'to': ['recipient@example.com']
        }

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_no_items(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        all_items = {}

        send_email(self.smtp_cfg, all_items)

        mock_smtp.assert_called_once_with('smtp.example.com', 587)
        mock_server.login.assert_called_once_with('test@example.com', 'password')
        mock_server.send_message.assert_called_once()

        # Check that the message contains "No new items" content
        call_args = mock_server.send_message.call_args[0][0]
        message_str = str(call_args)
        assert "No new items" in message_str or "No New Content" in message_str

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_with_items(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        all_items = {
            'reddit': [
                {'id': '1', 'title': 'Test Post', 'url': 'https://reddit.com/1', 'subreddit': 'python'}
            ],
            'youtube': [
                {'id': '2', 'title': 'Test Video', 'url': 'https://youtube.com/2', 'channel_id': 'TechChannel'}
            ]
        }

        send_email(self.smtp_cfg, all_items)

        mock_smtp.assert_called_once_with('smtp.example.com', 587)
        mock_server.login.assert_called_once_with('test@example.com', 'password')
        mock_server.send_message.assert_called_once()

        # Check that message contains the items and sources
        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        assert 'Test Post' in message_content
        assert 'Test Video' in message_content
        assert 'python' in message_content
        assert 'TechChannel' in message_content

    @patch('main.smtplib.SMTP_SSL')
    @patch('main.logging')
    @patch('main.time.sleep')  # Mock sleep to speed up test
    def test_send_email_smtp_error(self, mock_sleep, mock_logging, mock_smtp):
        mock_smtp.side_effect = Exception('SMTP connection failed')

        all_items = {}

        send_email(self.smtp_cfg, all_items)

        # Verify retry logic was triggered (should have 2 warning calls + 1 error call)
        assert mock_logging.warning.call_count == 2
        mock_logging.error.assert_called_once_with('Failed to send email after 3 attempts with unexpected error: SMTP connection failed')

        # Verify exponential backoff delays
        mock_sleep.assert_any_call(1.0)  # First retry: 1 second
        mock_sleep.assert_any_call(2.0)  # Second retry: 2 seconds

    @patch('main.smtplib.SMTP_SSL')
    @patch('main.logging')
    def test_send_email_authentication_error_no_retry(self, mock_logging, mock_smtp):
        # Authentication errors should not be retried
        mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')

        all_items = {}

        send_email(self.smtp_cfg, all_items)

        # Should not retry authentication errors
        mock_logging.warning.assert_not_called()
        mock_logging.error.assert_called_once_with('SMTP Authentication failed: (535, \'Authentication failed\')')

    @patch('main.smtplib.SMTP_SSL')
    @patch('main.logging')
    @patch('main.time.sleep')
    def test_send_email_connection_error_with_retry_success(self, mock_sleep, mock_logging, mock_smtp):
        # Set up mock to fail first time, succeed second time
        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'call_count'):
                side_effect.call_count = 0
            side_effect.call_count += 1

            if side_effect.call_count == 1:
                raise smtplib.SMTPConnectError(421, 'Connection failed')
            else:
                # Return a proper mock context manager
                mock_server = Mock()
                mock_server.__enter__ = Mock(return_value=mock_server)
                mock_server.__exit__ = Mock(return_value=None)
                return mock_server

        mock_smtp.side_effect = side_effect

        all_items = {}

        send_email(self.smtp_cfg, all_items)

        # Should have 1 warning (first failure) and 1 success info
        mock_logging.warning.assert_called_once()
        mock_logging.info.assert_called_with('Email sent successfully.')
        mock_sleep.assert_called_once_with(1.0)  # First retry delay

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_empty_items_list(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        all_items = {
            'reddit': [],
            'youtube': []
        }

        send_email(self.smtp_cfg, all_items)

        mock_server.send_message.assert_called_once()
        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        # With new template, empty lists are treated as "no items found"
        assert 'No new items' in message_content or 'No New Content' in message_content


class TestGroupBySource:
    def test_group_by_source_reddit(self):
        items = [
            {'id': '1', 'title': 'Test 1', 'subreddit': 'python'},
            {'id': '2', 'title': 'Test 2', 'subreddit': 'python'},
            {'id': '3', 'title': 'Test 3', 'subreddit': 'programming'}
        ]

        result = group_by_source(items)

        expected = {
            'python': [
                {'id': '1', 'title': 'Test 1', 'subreddit': 'python'},
                {'id': '2', 'title': 'Test 2', 'subreddit': 'python'}
            ],
            'programming': [
                {'id': '3', 'title': 'Test 3', 'subreddit': 'programming'}
            ]
        }
        assert result == expected

    def test_group_by_source_youtube(self):
        items = [
            {'id': '1', 'title': 'Video 1', 'channel_id': 'UC123', 'channel_name': 'TechChannel'},
            {'id': '2', 'title': 'Video 2', 'channel_id': 'UC456', 'channel_name': 'EduChannel'}
        ]

        result = group_by_source(items)

        expected = {
            'TechChannel': [{'id': '1', 'title': 'Video 1', 'channel_id': 'UC123', 'channel_name': 'TechChannel'}],
            'EduChannel': [{'id': '2', 'title': 'Video 2', 'channel_id': 'UC456', 'channel_name': 'EduChannel'}]
        }
        assert result == expected

    def test_group_by_source_unknown(self):
        items = [
            {'id': '1', 'title': 'Test Item'}
        ]

        result = group_by_source(items)

        expected = {
            'unknown': [{'id': '1', 'title': 'Test Item'}]
        }
        assert result == expected


class TestGroupItemsByCategoryAndSource:
    def test_group_items_no_categories(self):
        items = [
            {'id': '1', 'title': 'Test 1', 'subreddit': 'python'},
            {'id': '2', 'title': 'Test 2', 'subreddit': 'programming'}
        ]

        result = group_items_by_category_and_source(items)

        expected = {
            'uncategorized': {
                'python': [{'id': '1', 'title': 'Test 1', 'subreddit': 'python'}],
                'programming': [{'id': '2', 'title': 'Test 2', 'subreddit': 'programming'}]
            }
        }
        assert result == expected

    def test_group_items_with_categories(self):
        items = [
            {'id': '1', 'title': 'News Item', 'category': 'news', 'subreddit': 'worldnews'},
            {'id': '2', 'title': 'Tech Item', 'category': 'tech', 'subreddit': 'python'},
            {'id': '3', 'title': 'Another News', 'category': 'news', 'subreddit': 'politics'}
        ]

        result = group_items_by_category_and_source(items)

        expected = {
            'news': {
                'worldnews': [{'id': '1', 'title': 'News Item', 'category': 'news', 'subreddit': 'worldnews'}],
                'politics': [{'id': '3', 'title': 'Another News', 'category': 'news', 'subreddit': 'politics'}]
            },
            'tech': {
                'python': [{'id': '2', 'title': 'Tech Item', 'category': 'tech', 'subreddit': 'python'}]
            }
        }
        assert result == expected

    def test_group_items_mixed_categorization(self):
        items = [
            {'id': '1', 'title': 'Categorized', 'category': 'news', 'subreddit': 'worldnews'},
            {'id': '2', 'title': 'Uncategorized', 'subreddit': 'python'}
        ]

        result = group_items_by_category_and_source(items)

        expected = {
            'news': {
                'worldnews': [{'id': '1', 'title': 'Categorized', 'category': 'news', 'subreddit': 'worldnews'}]
            },
            'uncategorized': {
                'python': [{'id': '2', 'title': 'Uncategorized', 'subreddit': 'python'}]
            }
        }
        assert result == expected

    def test_group_items_empty_list(self):
        result = group_items_by_category_and_source([])
        assert result == {}


class TestSendEmailWithCategories:
    def setup_method(self):
        self.smtp_cfg = {
            'server': 'smtp.example.com',
            'port': 587,
            'username': 'test@example.com',
            'password': 'password',
            'from': 'test@example.com',
            'to': ['recipient@example.com']
        }

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_with_categorized_items(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        all_items = {
            'reddit': [
                {'id': '1', 'title': 'News Post', 'url': 'https://reddit.com/1', 'category': 'news', 'subreddit': 'worldnews'},
                {'id': '2', 'title': 'Tech Post', 'url': 'https://reddit.com/2', 'category': 'tech', 'subreddit': 'python'},
                {'id': '3', 'title': 'Another News', 'url': 'https://reddit.com/3', 'category': 'news', 'subreddit': 'politics'}
            ]
        }

        send_email(self.smtp_cfg, all_items)

        mock_smtp.assert_called_once_with('smtp.example.com', 587)
        mock_server.login.assert_called_once_with('test@example.com', 'password')
        mock_server.send_message.assert_called_once()

        # Check that message contains category and source groupings
        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        assert 'News:' in message_content
        assert 'Tech:' in message_content
        assert 'worldnews' in message_content
        assert 'python' in message_content
        assert 'politics' in message_content
        assert 'News Post' in message_content
        assert 'Tech Post' in message_content

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_mixed_sources_with_categories(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        all_items = {
            'reddit': [
                {'id': '1', 'title': 'Reddit News', 'url': 'https://reddit.com/1', 'category': 'news', 'subreddit': 'worldnews'}
            ],
            'youtube': [
                {'id': '2', 'title': 'YouTube Tech', 'url': 'https://youtube.com/2', 'category': 'tech', 'channel_id': 'TechChannel'},
                {'id': '3', 'title': 'Uncategorized Video', 'url': 'https://youtube.com/3', 'channel_id': 'EduChannel'}
            ]
        }

        send_email(self.smtp_cfg, all_items)

        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        # Template uses uppercase service names in text format
        assert 'REDDIT:' in message_content or 'Reddit' in message_content
        assert 'YOUTUBE:' in message_content or 'Youtube' in message_content
        assert 'worldnews' in message_content
        assert 'TechChannel' in message_content
        assert 'EduChannel' in message_content
        assert 'Reddit News' in message_content
        assert 'YouTube Tech' in message_content
        assert 'Uncategorized Video' in message_content
