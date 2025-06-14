# Reddit Email Digest

This application fetches the top 3 most upvoted posts from the r/cursor subreddit along with their top 3 comments and sends them to your email.

## Features

- Fetches top posts from r/cursor subreddit (configurable)
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
   - Name: cursor_subreddit_digest (or any name you prefer)
   - Type: script
   - Description: App to fetch top posts from r/cursor
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

You can also configure which subreddit to monitor and how many posts to fetch by modifying the parameters in the `fetch_top_posts` function call in the script.
