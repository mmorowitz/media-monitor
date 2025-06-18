from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone, timedelta

from main import load_config, process_source, load_smtp_settings, send_email


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
                {'id': '1', 'title': 'Test Post', 'url': 'https://reddit.com/1'}
            ],
            'youtube': [
                {'id': '2', 'title': 'Test Video', 'url': 'https://youtube.com/2'}
            ]
        }
        
        send_email(self.smtp_cfg, all_items)
        
        mock_smtp.assert_called_once_with('smtp.example.com', 587)
        mock_server.login.assert_called_once_with('test@example.com', 'password')
        mock_server.send_message.assert_called_once()
        
        # Check that message contains the items
        call_args = mock_server.send_message.call_args[0][0]
        message_content = str(call_args)
        assert 'Test Post' in message_content
        assert 'Test Video' in message_content
    
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
