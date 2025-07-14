# Reddit Email Digest

This application fetches the top 3 most upvoted posts from selected subreddits along with their top 3 comments and sends them to your email.

## Features

- Fetches top posts from multiple subreddits (configurable)
- Extracts the top 3 comments for each post
- Formats the content into a readable email
- Sends daily digests or can be run on demand
- Configurable scheduling options

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file by copying the `.env.example` file:
   ```
   cp .env.example .env
   ```
4. Edit the `.env` file with your credentials

### Reddit API Setup

1. Go to https://www.reddit.com/prefs/apps
2. Click "create app" at the bottom
3. Fill in the details:
   - Name: reddit_digest (or any name you prefer)
   - Type: script
   - Description: App to fetch top posts from selected subreddits
   - About URL: (leave blank)
   - Redirect URI: http://localhost (this is required but won't be used)
4. Click "create app"
5. Copy the Client ID (the string under the app name) and Client Secret to your `.env` file

### Email Setup

If using Gmail:
1. Create an app password: https://myaccount.google.com/apppasswords
   (You'll need to have 2-factor authentication enabled)
2. Use this app password in your `.env` file instead of your regular Gmail password

## Usage

### Run once

To run the script once without scheduling:

```bash
cd /path/to/reddit_workflow
RUN_ONCE=true python src/reddit_email.py
```

### Run as a scheduled job

To run as a scheduled job (default is daily at 9:00 AM):

```bash
cd /path/to/reddit_workflow
python src/reddit_email.py
```

## Configuration Options

In the `.env` file:

- `SCHEDULE_TIME`: Time to run the daily digest (format: HH:MM)
- `INITIAL_RUN`: If set to "true", runs immediately on startup in addition to scheduled times
- `RUN_ONCE`: If set to "true", runs once and exits without scheduling

You can also configure which subreddits to monitor and how many posts to fetch by modifying the parameters in the `fetch_reddit_posts` function call in the script.

## Advanced Features

### Multimodal Image Analysis
The application includes advanced AI-powered image analysis capabilities that can:
- Analyze images from Reddit posts using multimodal AI
- Extract meaningful insights and context from visual content
- Provide detailed descriptions of images in the email digest

### Web Search Integration
Enhanced with web search capabilities for:
- Real-time information gathering
- Context enrichment for posts
- Fact-checking and additional research

### Customizable Subreddit Selection
The application supports dynamic subreddit configuration with popular defaults including:
- Technology discussions
- Programming communities
- Side projects showcase
- General interest topics

## Troubleshooting

### Common Issues
- **Authentication errors**: Double-check your Reddit API credentials and ensure they're correctly set in the `.env` file
- **Email sending failures**: Verify your email credentials and app password (for Gmail)
- **Rate limiting**: The application includes built-in rate limiting to respect Reddit's API guidelines
