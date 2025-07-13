#!/usr/bin/env python3
"""
Test script for web search integration
"""
import os
import sys
sys.path.append('src')

from reddit_email import (
    WEB_SEARCH_CONFIG, 
    web_search_manager,
    should_use_web_search,
    calculate_web_search_score,
    extract_product_mentions,
    extract_external_domains
)

def test_web_search_configuration():
    """Test web search configuration loading"""
    print("=== Testing Web Search Configuration ===")
    print(f"Enabled: {WEB_SEARCH_CONFIG['enabled']}")
    print(f"Daily limit: {WEB_SEARCH_CONFIG['daily_limit']}")
    print(f"Cost limit: ${WEB_SEARCH_CONFIG['cost_limit_per_day']:.2f}")
    print(f"Target subreddits: {WEB_SEARCH_CONFIG['target_subreddits']}")
    print(f"Trigger keywords: {WEB_SEARCH_CONFIG['trigger_keywords'][:5]}...")
    print(f"Test mode: {WEB_SEARCH_CONFIG['test_mode']}")
    print()

def test_triggering_system():
    """Test the smart triggering system"""
    print("=== Testing Smart Triggering System ===")
    
    # Test posts
    test_posts = [
        {
            'title': 'Just launched my new AI tool for developers',
            'body': 'After months of work, I finally released CodeAI v2.0 with GPT-4 integration',
            'url': 'https://producthunt.com/posts/codeai',
            'score': 45,
            'subreddit': 'SideProject'
        },
        {
            'title': 'My weekend project: A simple calculator',
            'body': 'Built this calculator app in React. Nothing fancy but works well.',
            'url': 'https://github.com/user/calculator',
            'score': 15,
            'subreddit': 'SideProject'  
        },
        {
            'title': 'Claude Code is amazing for terminal workflows',
            'body': 'Been using Claude Code for a week and it has changed how I code',
            'url': 'https://reddit.com/r/ClaudeCode/comments/xyz',
            'score': 78,
            'subreddit': 'ClaudeCode'
        },
        {
            'title': 'OpenAI just announced GPT-5 pricing',
            'body': 'New pricing tiers released today. Much cheaper than expected!',
            'url': 'https://techcrunch.com/openai-gpt5-pricing',
            'score': 156,
            'subreddit': 'ClaudeCode'
        }
    ]
    
    for i, post in enumerate(test_posts, 1):
        print(f"Test Post {i}: {post['title'][:50]}...")
        
        # Test scoring
        score = calculate_web_search_score(post, post['subreddit'])
        should_search = should_use_web_search(post, post['subreddit'])
        
        print(f"  Score: {score}")
        print(f"  Should use web search: {should_search}")
        
        # Test product extraction
        products = extract_product_mentions(post['title'] + ' ' + post['body'])
        if products:
            print(f"  Products mentioned: {products}")
        
        # Test domain extraction
        domains = extract_external_domains(post['url'])
        if domains:
            print(f"  External domains: {domains}")
        
        print()

def test_cost_tracking():
    """Test cost tracking and limits"""
    print("=== Testing Cost Tracking ===")
    
    # Get status
    status = web_search_manager.get_status_summary()
    print(f"Daily usage: {status['daily_usage']}")
    print(f"Circuit breaker state: {status['circuit_breaker_state']}")
    print()

def test_fallback_chain():
    """Test the fallback chain logic"""
    print("=== Testing Fallback Chain ===")
    
    # Create a test post
    test_post = {
        'title': 'Testing fallback mechanisms',
        'body': 'This is a test post to validate the fallback chain',
        'url': 'https://example.com',
        'score': 30,
        'subreddit': 'test'
    }
    
    # Test web search check
    can_search, reason = web_search_manager.can_perform_search(test_post, 'SideProject')
    print(f"Can perform web search: {can_search}")
    print(f"Reason: {reason}")
    print()

def main():
    """Run all tests"""
    print("Web Search Integration Test Suite")
    print("=" * 50)
    print()
    
    test_web_search_configuration()
    test_triggering_system()
    test_cost_tracking()
    test_fallback_chain()
    
    print("✓ All tests completed!")
    print()
    print("To enable web search in test mode, set:")
    print("export WEB_SEARCH_ENABLED=true")
    print("export WEB_SEARCH_TEST_MODE=true")

if __name__ == "__main__":
    main()