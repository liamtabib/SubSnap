# SubSnap

SubSnap is a Reddit digest service that automatically curates top posts from specified subreddits and delivers them via email with AI-powered summaries and contextual information.

## Features

SubSnap provides smart curation by filtering posts based on upvotes and relevance, generates concise AI summaries of posts and comments, integrates web search for real-time fact-checking and background information, and sends clean HTML-formatted emails. The service is designed to reduce time spent browsing Reddit by delivering only the most relevant content.

## Quick Start

Install the required dependencies:
```bash
pip install -r requirements.txt
```

Create a `.env` file with your API credentials and configuration. You'll need Reddit API credentials, email settings, and optionally OpenAI API keys for enhanced features.

Run the service once to test:
```bash
python digest.py --run-once
```

## Configuration

Create a `.env` file in the root directory with the following variables:

- `SUBREDDITS` - Comma-separated list of subreddits to monitor
- `SCHEDULE_TIME` - Time for daily emails (format: "HH:MM")
- `MIN_POST_SCORE` - Minimum upvotes required for posts
- `WEB_SEARCH_ENABLED` - Enable AI web search functionality
- `IMAGE_ANALYSIS_ENABLED` - Enable image analysis features

### Reddit API Setup

Navigate to https://www.reddit.com/prefs/apps and create a new "script" application. Copy the Client ID and Client Secret to your `.env` file as `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.

### Email Configuration

For Gmail users, enable 2-factor authentication and generate an app password at https://myaccount.google.com/apppasswords. Add this to your `.env` file as `EMAIL_PASSWORD` along with your Gmail address as `EMAIL_SENDER` and `EMAIL_RECIPIENT`.

### Optional: OpenAI Integration

Add your OpenAI API key to `.env` as `OPENAI_API_KEY` to enable enhanced AI summaries, web search integration, and image analysis features.

## Usage

Run the service once:
```bash
python digest.py --run-once
```

Schedule daily emails by setting `SCHEDULE_TIME` in your `.env` file and running:
```bash
python digest.py
```

Use quiet mode to suppress output:
```bash
python digest.py --run-once --quiet
```

## Project Structure

```
SubSnap/
├── src/                  # Main application code
├── tests/                # Test suite and test runner
├── debug/                # Debug tools and utilities
├── output/               # Generated files directory
├── digest.py             # Main entry point
└── .env                  # Configuration file
```

## Testing

Run the complete test suite:
```bash
cd tests && python run_tests.py
```

Test specific functionality:
```bash
cd tests && python test_web_search.py
```

## Troubleshooting

If no posts are found, verify that the specified subreddits have recent posts meeting the minimum upvote threshold. Email sending issues are typically related to incorrect Gmail app passwords or missing 2FA setup. API errors usually indicate invalid or expired API keys or insufficient quota.

For additional debugging information, check the `output/` directory for runtime logs and generated files, or run with `--help` for available command-line options.