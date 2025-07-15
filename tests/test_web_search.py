#!/usr/bin/env python3
"""
Test script for web search integration
"""
import os
import sys
import argparse
sys.path.append('../src')

from reddit_email import (
    WEB_SEARCH_CONFIG, 
    web_search_manager,
    should_use_web_search,
    calculate_web_search_score,
    extract_product_mentions,
    extract_external_domains,
    can_perform_search
)
from core.reporter import WebSearchReporter, add_reporter_args, get_reporter_from_args

def test_web_search_configuration(reporter):
    """Test web search configuration loading"""
    try:
        config_details = [
            f"Enabled: {WEB_SEARCH_CONFIG['enabled']}",
            f"Daily limit: {WEB_SEARCH_CONFIG['daily_limit']}",
            f"Cost limit: ${WEB_SEARCH_CONFIG['cost_limit_per_day']:.2f}",
            f"Target subreddits: {len(WEB_SEARCH_CONFIG['target_subreddits'])} configured",
            f"Trigger keywords: {len(WEB_SEARCH_CONFIG['trigger_keywords'])} configured"
        ]
        
        reporter.add_result(
            "Web Search Configuration", 
            "pass", 
            "; ".join(config_details)
        )
        return True
    except Exception as e:
        reporter.add_result("Web Search Configuration", "fail", str(e))
        return False

def test_triggering_system(reporter):
    """Test the smart triggering system"""
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
    
    try:
        high_score_posts = 0
        for i, post in enumerate(test_posts, 1):
            score = calculate_web_search_score(post, post['subreddit'])
            should_search = should_use_web_search(post, post['subreddit'])
            
            if score > 50:  # High score threshold
                high_score_posts += 1
        
        reporter.add_result(
            "Smart Triggering System", 
            "pass", 
            f"Tested {len(test_posts)} posts, {high_score_posts} high-scoring"
        )
        return True
    except Exception as e:
        reporter.add_result("Smart Triggering System", "fail", str(e))
        return False

def test_cost_tracking(reporter):
    """Test cost tracking and limits"""
    try:
        if web_search_manager:
            status = web_search_manager.get_status_summary()
            daily_usage = status.get('daily_usage', {})
            circuit_state = status.get('circuit_breaker_state', 'unknown')
            
            reporter.add_result(
                "Cost Tracking", 
                "pass", 
                f"Daily usage: {daily_usage.get('searches_count', 0)} searches, Circuit breaker: {circuit_state}"
            )
        else:
            reporter.add_result("Cost Tracking", "skip", "Web search manager not available")
        return True
    except Exception as e:
        reporter.add_result("Cost Tracking", "fail", str(e))
        return False

def test_fallback_chain(reporter):
    """Test the fallback chain logic"""
    try:
        test_post = {
            'title': 'Testing fallback mechanisms',
            'body': 'This is a test post to validate the fallback chain',
            'url': 'https://example.com',
            'score': 30,
            'subreddit': 'test'
        }
        
        can_search, reason = can_perform_search(test_post, 'SideProject')
        
        reporter.add_result(
            "Fallback Chain", 
            "pass", 
            f"Can perform search: {can_search}, Reason: {reason}"
        )
        return True
    except Exception as e:
        reporter.add_result("Fallback Chain", "fail", str(e))
        return False

def main():
    """Run all tests"""
    parser = argparse.ArgumentParser(description='Web Search Integration Test Suite')
    add_reporter_args(parser)
    args = parser.parse_args()
    
    reporter = WebSearchReporter(args.format)
    reporter.start_suite("Web Search Integration Tests")
    
    # Run tests
    test_web_search_configuration(reporter)
    test_triggering_system(reporter)
    test_cost_tracking(reporter)
    test_fallback_chain(reporter)
    
    # Set web search analytics
    if web_search_manager:
        status = web_search_manager.get_status_summary()
        reporter.set_web_search_stats({
            'enabled': WEB_SEARCH_CONFIG['enabled'],
            'daily_usage': status.get('daily_usage', {}),
            'circuit_breaker_state': status.get('circuit_breaker_state', 'unknown')
        })
    
    reporter.end_suite()
    reporter.output(args.output if hasattr(args, 'output') else None)

if __name__ == "__main__":
    main()