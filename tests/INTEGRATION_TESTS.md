# Integration Tests

This directory contains full integration tests that use real APIs and send actual emails.

## ⚠️ Important Safety Notice

These tests will:
- Make real API calls to Reddit and YouTube (consuming API quotas)
- Send actual email notifications to configured recipients
- Use real SMTP servers

**Only run these tests when you want to verify the complete end-to-end functionality.**

## Setup Instructions

### 1. Create Real Credentials Config

```bash
# Copy the template
cp config/integration_test.yaml config/integration_test_real.yaml

# Edit with your real credentials
nano config/integration_test_real.yaml
```

### 2. Configure Real API Credentials

#### Reddit API Setup
1. Go to https://www.reddit.com/prefs/apps
2. Create a new app (script type)
3. Note your `client_id` and `client_secret`
4. Update the config file:
   ```yaml
   reddit:
     client_id: your_actual_client_id
     client_secret: your_actual_client_secret  
     user_agent: media-monitor-integration-test/1.0
   ```

#### YouTube API Setup
1. Go to https://console.developers.google.com/
2. Enable YouTube Data API v3
3. Create API credentials (API key)
4. Update the config file:
   ```yaml
   youtube:
     api_key: your_actual_api_key
   ```

#### SMTP Setup (Gmail Example)
1. Enable 2FA on your Gmail account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Update the config file:
   ```yaml
   smtp:
     enabled: true
     server: smtp.gmail.com
     port: 587
     username: your_email@gmail.com
     password: your_16_char_app_password
     from: your_email@gmail.com
     to:
       - your_email@gmail.com  # Send to yourself for safety
   ```

### 3. Set Environment Variable

```bash
export INTEGRATION_TEST_CONFIG=config/integration_test_real.yaml
```

### 4. Run Integration Tests

These tests are marked with `@pytest.mark.integration` and will NOT run as part of the regular test suite.

```bash
# Run all integration tests explicitly
python -m pytest -m integration -v -s

# Or run the integration test file directly
python -m pytest tests/test_integration.py -v -s

# Run specific integration test
python -m pytest tests/test_integration.py::TestFullIntegration::test_reddit_client_real_api -v -s

# Verify integration tests are excluded from regular test runs
python -m pytest tests/ -v  # Will skip integration tests
```

**Important**: The integration tests will be automatically skipped when running the full test suite (`pytest tests/`) to prevent accidental API calls and email sending.

## Test Coverage

The integration tests cover:

1. **Individual Client Testing**
   - `test_reddit_client_real_api` - Real Reddit API calls
   - `test_youtube_client_real_api` - Real YouTube API calls

2. **Database Integration**
   - `test_database_operations` - SQLite operations with temp database
   - `test_process_source_integration` - Source processing with real clients

3. **Email Integration**
   - `test_email_integration` - Sends actual test email via SMTP

4. **Full Application Integration**
   - `test_full_application_integration` - Complete end-to-end workflow

## Safety Measures

The integration tests include several safety measures:

1. **Config Validation**: Tests will skip if credentials are not properly configured
2. **Temporary Database**: Uses isolated temporary database for each test
3. **Email to Self**: Default config sends emails to the same address as sender
4. **Limited Data**: Uses small subreddits and channels to minimize API usage
5. **Environment Variable**: Requires explicit environment variable to run

## Troubleshooting

### Tests Skip with "Set INTEGRATION_TEST_CONFIG"
- Ensure you've set the environment variable
- Verify the config file path exists

### Tests Skip with "not configured" 
- Check that all placeholder values (starting with 'YOUR_' or 'your_') are replaced with real credentials
- Verify API keys and credentials are valid

### API Rate Limits
- Reddit: 60 requests per minute per client
- YouTube: 10,000 units per day (quota)
- Consider running tests sparingly to avoid hitting limits

### Email Authentication Errors
- For Gmail, ensure you're using an App Password, not your regular password
- Check that SMTP server and port are correct for your provider
- Verify 2FA is enabled if using App Passwords

## Running Tests in CI/CD

These tests are **NOT** suitable for automated CI/CD pipelines because they:
- Require real API credentials
- Send actual emails
- Consume API quotas
- Have external dependencies

Use the unit tests in `test_main.py` for automated testing instead.