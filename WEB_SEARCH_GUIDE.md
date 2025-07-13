# Web Search Integration Guide

## Quick Start

Web search is **enabled by default** with production-ready settings. The system automatically enhances high-value posts with real-time web information.

To run with web search:
```bash
python src/reddit_email.py --run-once
```

To test with verbose logging:
```bash
export WEB_SEARCH_TEST_MODE=true
python src/reddit_email.py --run-once
```

## Overview

The Reddit Digest now supports enhanced post summarization using OpenAI's Responses API with web search capabilities. This feature augments summaries with real-time information from the web when analyzing posts about new products, services, announcements, or technical developments.

## Features

### Smart Triggering System
- **Intelligent Post Selection**: Only high-value posts trigger web search based on multiple signals
- **Scoring Algorithm**: Posts are scored based on engagement, keywords, domains, and content patterns
- **Conservative Approach**: Requires multiple positive signals to trigger web search

### Cost Management
- **Daily Limits**: Configurable limits on both search count and cost
- **Real-time Tracking**: Monitors usage and prevents overspending
- **Circuit Breaker**: Automatically disables web search if failures occur

### Safety & Reliability
- **Fallback Chain**: Web search → Multimodal → Text-only summarization
- **Error Handling**: Graceful degradation when web search fails
- **Comprehensive Logging**: Detailed monitoring and analytics

## Configuration

### Environment Variables

#### Core Settings
```bash
WEB_SEARCH_ENABLED=true           # Enable/disable web search (default: true)
WEB_SEARCH_TEST_MODE=false        # Enable verbose logging (default: false)
WEB_SEARCH_DAILY_LIMIT=15         # Max searches per day (default: 15)
WEB_SEARCH_COST_LIMIT=1.50        # Max daily cost in USD (default: $1.50)
WEB_SEARCH_COST_PER_CALL=0.03     # Cost per search call (default: $0.03)
```

#### Targeting & Triggers
```bash
WEB_SEARCH_MIN_SCORE=15                    # Minimum post score for web search
WEB_SEARCH_SUBREDDITS=SideProject,ClaudeCode,ClaudeAI,AI_Agents  # Target subreddits
WEB_SEARCH_KEYWORDS=launched,released,new version,pricing,acquired,funding,announcement,beta,available now,update,feature
WEB_SEARCH_DOMAINS=github.com,producthunt.com,ycombinator.com,techcrunch.com,apps.apple.com,play.google.com
```

#### Circuit Breaker
```bash
WEB_SEARCH_FAILURE_THRESHOLD=5     # Failures before opening circuit breaker
WEB_SEARCH_RECOVERY_TIMEOUT=1800   # Recovery timeout in seconds (30 minutes)
```

### Scoring System

Posts are scored based on multiple factors:

| Factor | Points | Description |
|--------|--------|-------------|
| Target Subreddit | +20 | Post is from SideProject, ClaudeCode, etc. |
| Trigger Keywords | +15 | Contains words like "launched", "released", "pricing" |
| High Engagement | +25 | Post score ≥ minimum threshold |
| Known Domains | +20 | Links to GitHub, Product Hunt, TechCrunch, etc. |
| Other External Links | +10 | Links to other external domains |
| Product Mentions | +15 | Contains product/company names |
| Minimal Text | +5 | Short posts (often link/image posts) |

**Threshold**: 40 points required to trigger web search

### Example Configurations

#### Conservative Production
```bash
WEB_SEARCH_ENABLED=true
WEB_SEARCH_DAILY_LIMIT=5
WEB_SEARCH_COST_LIMIT=0.25
WEB_SEARCH_MIN_SCORE=50
WEB_SEARCH_TEST_MODE=false
```

#### Testing/Development
```bash
WEB_SEARCH_ENABLED=true
WEB_SEARCH_DAILY_LIMIT=10
WEB_SEARCH_COST_LIMIT=1.00
WEB_SEARCH_MIN_SCORE=20
WEB_SEARCH_TEST_MODE=true
```

#### Disabled (Default)
```bash
WEB_SEARCH_ENABLED=false
WEB_SEARCH_TEST_MODE=false
```

## Usage Examples

### High-Scoring Posts (Will Trigger Web Search)

1. **Product Launch** (Score: ~100)
   - Title: "Just launched my new AI tool for developers"
   - Factors: Target subreddit, "launched" keyword, external domain, product mentions

2. **Tech News** (Score: ~80)
   - Title: "OpenAI announces GPT-5 pricing changes"
   - Factors: High engagement, "announces" keyword, news domain, product mentions

3. **GitHub Project** (Score: ~45)
   - Title: "My weekend React project"
   - URL: github.com/user/project
   - Factors: Target subreddit, GitHub domain

### Low-Scoring Posts (Won't Trigger Web Search)

1. **General Discussion** (Score: ~20)
   - Title: "What's your favorite code editor?"
   - Factors: Only target subreddit

2. **Tutorial/Guide** (Score: ~25)
   - Title: "How I learned Python in 30 days"
   - Factors: Target subreddit, minimal text

## Monitoring & Analytics

### Email Reports
- **Web Search Count**: Shows how many summaries used web search
- **Visual Indicators**: 🌐 badge next to web-enhanced post titles
- **Cost Tracking**: Daily cost breakdown including web search expenses

### Console Logging
When `WEB_SEARCH_TEST_MODE=true`:
```
Web Search Summary:
- Web search enabled: True
- Posts that used web search: 3
- Posts that were candidates: 5
- Daily usage: 3/8 searches
- Daily cost: $0.09/$0.50
- Circuit breaker state: closed

Web search enhanced posts:
  - 'Just launched my new AI tool for developers...' (score: 78)
  - 'OpenAI announces GPT-5 pricing changes...' (score: 156)
```

### Cost Tracking Files
- `web_search_usage.json`: Daily usage tracking
- `web_search_circuit_state.json`: Circuit breaker state

## Best Practices

### Gradual Rollout
1. **Week 1-2**: Test mode with detailed logging
2. **Week 3-4**: Limited production (5 searches/day, $0.25 budget)
3. **Month 2**: Full deployment based on value assessment

### Cost Management
- Start with conservative daily limits ($0.25-0.50)
- Monitor actual vs. expected costs closely
- Adjust triggers based on value delivered

### Value Assessment
Monitor these metrics to assess ROI:
- **Enhanced Post Quality**: Do web-enhanced summaries provide better context?
- **Cost Efficiency**: Is the additional cost justified by improved summaries?
- **User Engagement**: Do enhanced summaries improve email engagement? (if trackable)

### Troubleshooting

#### Web Search Not Triggering
1. Check `WEB_SEARCH_ENABLED=true`
2. Verify posts meet scoring threshold (≥30 points)
3. Ensure not hitting daily limits
4. Check circuit breaker state

#### High Costs
1. Reduce `WEB_SEARCH_DAILY_LIMIT`
2. Increase `WEB_SEARCH_MIN_SCORE` threshold
3. Review and refine trigger keywords
4. Monitor `WEB_SEARCH_COST_LIMIT`

#### Circuit Breaker Issues
1. Check OpenAI API key validity
2. Verify internet connectivity
3. Review recent error logs
4. Reset circuit breaker by deleting `web_search_circuit_state.json`

## Testing

Run the test suite to validate configuration:

```bash
# Test with web search disabled (default)
python test_web_search.py

# Test with web search enabled
WEB_SEARCH_ENABLED=true WEB_SEARCH_TEST_MODE=true python test_web_search.py
```

## Security Considerations

- Never commit API keys to version control
- Use environment variables for all sensitive configuration
- Monitor costs regularly to prevent unexpected charges
- Consider using separate OpenAI API keys for development/production

## Fallback Behavior

The system implements a robust fallback chain:

1. **Web Search Enhanced**: Uses Responses API with web search tool
2. **Multimodal Fallback**: Uses standard multimodal summarization (with images)
3. **Text-Only Fallback**: Uses basic text-only summarization
4. **Graceful Failure**: Returns no summary rather than breaking

This ensures the system continues to function even if web search fails.