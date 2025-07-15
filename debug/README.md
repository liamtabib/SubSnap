# SubSnap Debug Directory

This directory contains debug scripts and runtime data files for SubSnap.

## Debug Scripts

### `debug_reddit.py`
Simple script to test Reddit API connectivity and fetch sample posts.

```bash
cd debug
python debug_reddit.py
```

## Runtime Data Files

### Web Search Data
- **`web_search_usage.json`** - Daily usage tracking for web search feature
- **`web_search_circuit_state.json`** - Circuit breaker state for web search

### Email Output Samples
- **`last_email_content.html`** - Last generated email content (HTML format)

## File Management

These files are automatically generated during application runtime:
- **JSON files** are created and updated by the cost tracking system
- **HTML files** contain sample outputs for debugging email formatting
- **Log files** may be created during debugging sessions

## Cleanup

To clean up debug files:
```bash
cd debug
rm -f *.json *.html *.log
```

## Development Usage

When developing new features:
1. Run debug scripts to test individual components
2. Check runtime data files to understand application behavior
3. Examine email output samples to verify formatting
4. Monitor cost tracking files during web search development

## Important Notes

- **Never commit API keys** - Debug scripts use environment variables
- **Runtime data files** should not be committed to version control
- **Email samples** may contain sensitive information from Reddit posts