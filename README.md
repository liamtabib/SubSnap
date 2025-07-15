# SubSnap

**Get the best Reddit content delivered to your inbox with AI-powered summaries.**

SubSnap automatically curates top posts from your favorite subreddits and sends you a daily digest with intelligent summaries, context, and insights.

## ✨ What You Get

- **Smart Curation** - Only the most engaging posts, filtered by upvotes and relevance
- **AI Summaries** - Concise, intelligent summaries of posts and comments
- **Rich Context** - Web search integration for real-time fact-checking and background info
- **Beautiful Emails** - Clean, responsive HTML formatting that looks great on any device
- **Time Saving** - Skip endless scrolling, get just the highlights that matter

## 🚀 Quick Start

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run**
   ```bash
   python digest.py --run-once
   ```

That's it! Check your email for your first digest.

## ⚙️ Setup

### Reddit API
1. Go to https://www.reddit.com/prefs/apps
2. Create a new "script" app
3. Add the Client ID and Secret to your `.env` file

### Email (Gmail)
1. Enable 2-factor authentication
2. Generate app password at https://myaccount.google.com/apppasswords
3. Add to your `.env` file

### OpenAI (Optional)
Add your OpenAI API key to `.env` for enhanced AI summaries

## 📋 Usage

```bash
# Run once
python digest.py --run-once

# Schedule daily emails (set SCHEDULE_TIME in .env)
python digest.py

# Quiet mode
python digest.py --run-once --quiet
```

## 🔧 Configuration

Edit `.env` to customize:
- `SUBREDDITS` - Which subreddits to monitor
- `SCHEDULE_TIME` - When to send daily emails (e.g., "09:00")
- `MIN_POST_SCORE` - Minimum upvotes required
- `WEB_SEARCH_ENABLED` - Enable AI web search (requires OpenAI)
- `IMAGE_ANALYSIS_ENABLED` - Enable image analysis (requires OpenAI)

## 📁 Project Structure

```
SubSnap/
├── src/                  # Main application
├── tests/                # Test suite
├── debug/                # Debug tools & runtime data
├── digest.py             # Entry point
└── .env                  # Your configuration
```

## 🧪 Testing

```bash
# Run all tests
cd tests && python run_tests.py

# Test specific feature
cd tests && python test_web_search.py
```

## 🐛 Troubleshooting

- **No posts found**: Check if subreddits have recent posts with enough upvotes
- **Email not sending**: Verify Gmail app password and 2FA is enabled
- **API errors**: Ensure Reddit/OpenAI API keys are valid and have sufficient quota

## 📧 Support

Run `python digest.py --help` for more options or check the `debug/` folder for runtime logs.

---

**Made with ❤️ for Reddit enthusiasts who want to stay informed without the noise.**