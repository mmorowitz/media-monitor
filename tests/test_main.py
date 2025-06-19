import pytest
import yaml
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

from main import load_config, process_source, load_smtp_settings, send_email, group_items_by_category_and_source, group_by_source


class TestLoadConfig:
    @patch('builtins.open', new_callable=mock_open, read_data='reddit:\n  enabled: true')
    @patch('yaml.safe_load')
    def test_load_config_success(self, mock_yaml_load, mock_file):
        mock_yaml_load.return_value = {'reddit': {'enabled': True}}
        
        result = load_config('config/test.yaml')
        
        mock_file.assert_called_once_with('config/test.yaml', 'r')
        mock_yaml_load.assert_called_once()
        assert result == {'reddit': {'enabled': True}}
    
    def test_load_config_default_filename(self):
        with patch('builtins.open', mock_open(read_data='test: data')) as mock_file:
            with patch('yaml.safe_load', return_value={'test': 'data'}):
                load_config()
                mock_file.assert_called_once_with('config/config.yaml', 'r')


class TestProcessSource:
    def setup_method(self):
        self.mock_db_conn = Mock()
        self.mock_client_class = Mock()
        self.mock_client = Mock()
        self.mock_client_class.return_value = self.mock_client
        
    def test_process_source_disabled(self):
        config = {'reddit': {'enabled': False}}
        
        result = process_source('reddit', self.mock_client_class, config, self.mock_db_conn)
        
        assert result == []
        self.mock_client_class.assert_not_called()
    
    def test_process_source_missing_config(self):
        config = {}
        
        result = process_source('reddit', self.mock_client_class, config, self.mock_db_conn)
        
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
        
        result = process_source('reddit', self.mock_client_class, config, self.mock_db_conn)
        
        assert result == mock_items
        self.mock_client_class.assert_called_once_with(config['reddit'])
        mock_get.assert_called_once_with(self.mock_db_conn, 'reddit')
        self.mock_client.get_new_items_since.assert_called_once()
        mock_update.assert_called_once_with(self.mock_db_conn, 'reddit', current_time)
    
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
        
        result = process_source('youtube', self.mock_client_class, config, self.mock_db_conn)
        
        assert result == mock_items
        self.mock_client_class.assert_called_once_with(config['youtube'])
        mock_get.assert_called_once_with(self.mock_db_conn, 'youtube')
        self.mock_client.get_new_items_since.assert_called_once()
        mock_update.assert_called_once_with(self.mock_db_conn, 'youtube', current_time)


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
        
        # Check that the message contains "No new items"
        call_args = mock_server.send_message.call_args[0][0]
        assert "No new items found from any source" in str(call_args)
    
    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_with_items(self, mock_smtp):
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        all_items = {
            'reddit': [
                {'id': '1', 'title': 'Test Post', 'url': 'https://reddit.com/1', 'subreddit': 'python'}
            ],
            'youtube': [
                {'id': '2', 'title': 'Test Video', 'url': 'https://youtube.com/2', 'channel_id': 'UC123'}
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
        assert 'python:' in message_content
        assert 'UC123:' in message_content
    
    @patch('main.smtplib.SMTP_SSL')
    @patch('main.logging')
    def test_send_email_smtp_error(self, mock_logging, mock_smtp):
        mock_smtp.side_effect = Exception('SMTP connection failed')
        
        all_items = {}
        
        send_email(self.smtp_cfg, all_items)
        
        mock_logging.error.assert_called_once_with('Failed to send email: SMTP connection failed')
    
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
        assert 'Reddit:' in message_content
        assert 'Youtube:' in message_content
        assert 'No new items' in message_content


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
            {'id': '1', 'title': 'Video 1', 'channel_id': 'UC123'},
            {'id': '2', 'title': 'Video 2', 'channel_id': 'UC456'}
        ]
        
        result = group_by_source(items)
        
        expected = {
            'UC123': [{'id': '1', 'title': 'Video 1', 'channel_id': 'UC123'}],
            'UC456': [{'id': '2', 'title': 'Video 2', 'channel_id': 'UC456'}]
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
        assert 'worldnews:' in message_content
        assert 'python:' in message_content
        assert 'politics:' in message_content
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
                {'id': '2', 'title': 'YouTube Tech', 'url': 'https://youtube.com/2', 'category': 'tech', 'channel_id': 'UC123'},
                {'id': '3', 'title': 'Uncategorized Video', 'url': 'https://youtube.com/3', 'channel_id': 'UC456'}
            ]
        }
        
        send_email(self.smtp_cfg, all_items)
        
        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        assert 'Reddit:' in message_content
        assert 'Youtube:' in message_content
        assert 'worldnews:' in message_content
        assert 'UC123:' in message_content
        assert 'UC456:' in message_content
        assert 'Reddit News' in message_content
        assert 'YouTube Tech' in message_content
        assert 'Uncategorized Video' in message_content
