#!/usr/bin/env python3
"""
Validate the scoring system with realistic Reddit post examples
"""
import os
import sys
sys.path.append('src')

# Enable test mode for detailed scoring
os.environ['WEB_SEARCH_ENABLED'] = 'true'
os.environ['WEB_SEARCH_TEST_MODE'] = 'true'

from reddit_email import should_use_web_search, calculate_web_search_score

def test_realistic_posts():
    """Test with realistic Reddit post scenarios"""
    
    realistic_posts = [
        {
            'title': 'I just launched my SaaS for developers - got 100 signups in 24h!',
            'body': 'After 8 months of building DevTools Pro, we went live yesterday. Features include code analysis, automated testing, and deployment pipelines.',
            'url': 'https://producthunt.com/posts/devtools-pro',
            'score': 127,
            'subreddit': 'SideProject',
            'expected': True,
            'reason': 'High score: launched keyword + target subreddit + high engagement + PH domain + product mentions'
        },
        {
            'title': 'Anthropic releases Claude 4 with improved reasoning',
            'body': 'Just announced: Claude 4 is now available with significantly better reasoning capabilities and faster response times.',
            'url': 'https://techcrunch.com/2025/anthropic-claude-4-release',
            'score': 892,
            'subreddit': 'ClaudeCode',
            'expected': True,
            'reason': 'Very high score: releases keyword + target subreddit + very high engagement + news domain'
        },
        {
            'title': 'My simple React calculator app',
            'body': 'Built this over the weekend as a learning project. Basic operations only but learned a lot about React hooks.',
            'url': 'https://github.com/user/react-calculator',
            'score': 23,
            'subreddit': 'SideProject',
            'expected': False,
            'reason': 'Low score: low engagement (23 < 25), only gets target subreddit + GitHub domain'
        },
        {
            'title': 'Check out my weekend project - Task Manager with AI',
            'body': 'Built a task manager that uses GPT-4 to auto-categorize and prioritize your tasks. Still in beta but working well!',
            'url': 'https://github.com/user/ai-task-manager',
            'score': 45,
            'subreddit': 'SideProject',
            'expected': True,
            'reason': 'Mid score: target subreddit + high engagement + GitHub domain + beta keyword + product mentions'
        },
        {
            'title': 'How I became a better programmer',
            'body': 'Here are 10 tips that helped me improve my coding skills over the past 5 years...',
            'url': 'https://medium.com/@user/better-programmer',
            'score': 156,
            'subreddit': 'programming',
            'expected': False,
            'reason': 'Low score: not target subreddit, no trigger keywords, medium.com not in external domains'
        },
        {
            'title': 'GitHub announces new pricing tiers for enterprises',
            'body': 'GitHub just updated their enterprise pricing with new tiers and features. Significant changes to API rate limits.',
            'url': 'https://github.blog/enterprise-pricing-update',
            'score': 234,
            'subreddit': 'ClaudeCode',
            'expected': True,
            'reason': 'High score: announces + pricing keywords + target subreddit + high engagement'
        },
        {
            'title': 'What IDE do you prefer?',
            'body': 'Curious about what development environments people are using these days. VS Code? IntelliJ? Vim?',
            'url': 'https://reddit.com/r/programming/poll',
            'score': 89,
            'subreddit': 'programming',
            'expected': False,
            'reason': 'Low score: not target subreddit, no trigger keywords, reddit domain excluded'
        }
    ]
    
    print("Validating Web Search Scoring System")
    print("=" * 60)
    
    correct_predictions = 0
    total_tests = len(realistic_posts)
    
    for i, post in enumerate(realistic_posts, 1):
        print(f"\n{i}. {post['title']}")
        print(f"   URL: {post['url']}")
        print(f"   Score: {post['score']} | Subreddit: r/{post['subreddit']}")
        
        # Calculate score with debug info
        score = calculate_web_search_score(post, post['subreddit'])
        result = should_use_web_search(post, post['subreddit'])
        
        # Check prediction
        correct = result == post['expected']
        status = "✓" if correct else "✗"
        
        print(f"   {status} Predicted: {result} | Expected: {post['expected']}")
        print(f"   Final Score: {score}/40 threshold")
        print(f"   Reason: {post['reason']}")
        
        if correct:
            correct_predictions += 1
        
    print("\n" + "=" * 60)
    print(f"Accuracy: {correct_predictions}/{total_tests} ({correct_predictions/total_tests*100:.1f}%)")
    
    if correct_predictions == total_tests:
        print("🎉 All predictions correct! Scoring system working as expected.")
    else:
        print("⚠️  Some predictions incorrect. Review scoring logic.")
    
    return correct_predictions == total_tests

if __name__ == "__main__":
    success = test_realistic_posts()
    sys.exit(0 if success else 1)