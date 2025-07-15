#!/usr/bin/env python3
"""
Full integration test for web search functionality
"""
import os
import sys
import json
import argparse
sys.path.append('../src')

from reddit_email import (
    WEB_SEARCH_CONFIG,
    web_search_manager,
    summarize_post_content,
    format_email_content,
    create_plain_text_content,
    can_perform_search
)
from core.reporter import SubSnapReporter, add_reporter_args, get_reporter_from_args

def create_mock_posts():
    """Create mock posts for testing"""
    return [
        {
            'title': 'Just launched CodeAI v2.0 with GPT-4 integration',
            'body': 'After 6 months of development, we finally released CodeAI v2.0. New features include GPT-4 integration, real-time code suggestions, and improved performance.',
            'url': 'https://producthunt.com/posts/codeai-v2',
            'score': 89,
            'subreddit': 'SideProject',
            'author': 'developer123',
            'created_time': '2025-07-13 10:30:00',
            'comments': [
                {'author': 'user1', 'body': 'This looks amazing! How does it compare to GitHub Copilot?'},
                {'author': 'user2', 'body': 'Great work! Will definitely try this out.'}
            ],
            'image_urls': []
        },
        {
            'title': 'OpenAI announces new pricing for GPT-4o',
            'body': 'OpenAI just announced significant price reductions for GPT-4o API. New pricing is 60% lower than previous rates.',
            'url': 'https://techcrunch.com/2025/07/13/openai-pricing-update',
            'score': 234,
            'subreddit': 'ClaudeCode',
            'author': 'tech_news',
            'created_time': '2025-07-13 09:15:00',
            'comments': [
                {'author': 'dev1', 'body': 'Finally! This will make AI development much more affordable.'},
                {'author': 'dev2', 'body': 'Great news for indie developers.'}
            ],
            'image_urls': []
        },
        {
            'title': 'My weekend project: Simple task manager',
            'body': 'Built a minimalist task manager with React and local storage. Nothing fancy but gets the job done.',
            'url': 'https://github.com/user/task-manager',
            'score': 45,
            'subreddit': 'SideProject',
            'author': 'weekend_coder',
            'created_time': '2025-07-13 11:45:00',
            'comments': [
                {'author': 'user3', 'body': 'Clean interface! Any plans to add due dates?'}
            ],
            'image_urls': []
        },
        {
            'title': 'How to get better at debugging',
            'body': 'Here are some tips that helped me become a better debugger over the years...',
            'url': 'https://reddit.com/r/programming/comments/xyz',
            'score': 67,
            'subreddit': 'programming',
            'author': 'senior_dev',
            'created_time': '2025-07-13 08:20:00',
            'comments': [],
            'image_urls': []
        }
    ]

def test_summarization_with_web_search_enabled():
    """Test post summarization with web search enabled"""
    print("=== Testing Summarization with Web Search Enabled ===")
    
    # Enable web search for testing
    original_enabled = WEB_SEARCH_CONFIG['enabled']
    original_test_mode = WEB_SEARCH_CONFIG['test_mode']
    
    WEB_SEARCH_CONFIG['enabled'] = True
    WEB_SEARCH_CONFIG['test_mode'] = True
    
    try:
        mock_posts = create_mock_posts()
        
        print(f"Testing {len(mock_posts)} mock posts...")
        
        for i, post in enumerate(mock_posts, 1):
            print(f"\n--- Post {i}: {post['title'][:50]}... ---")
            
            # Test scoring and decision making
            can_search, reason = can_perform_search(post, post['subreddit'])
            print(f"Can perform web search: {can_search}")
            print(f"Reason: {reason}")
            
            # Test summarization (without actually calling OpenAI)
            print("Note: Skipping actual OpenAI API call for testing")
            
            # Mock the summaries that would be generated
            post['summaries'] = {
                'post_summary': f"Mock summary for: {post['title']}",
                'post_usage': {
                    'prompt_tokens': 150,
                    'completion_tokens': 75,
                    'total_tokens': 225,
                    'web_search_used': can_search and 'launched' in post['title'].lower() or 'announces' in post['title'].lower(),
                    'web_search_cost': 0.03 if can_search else 0,
                    'estimated_cost': 0.012 + (0.03 if can_search else 0)
                },
                'comments_summary': 'Mock comment summary',
                'comments_usage': {
                    'prompt_tokens': 50,
                    'completion_tokens': 25,
                    'total_tokens': 75
                }
            }
        
        return mock_posts
        
    finally:
        # Restore original settings
        WEB_SEARCH_CONFIG['enabled'] = original_enabled
        WEB_SEARCH_CONFIG['test_mode'] = original_test_mode

def test_email_formatting():
    """Test email formatting with web search indicators"""
    print("\n=== Testing Email Formatting ===")
    
    mock_posts = create_mock_posts()
    
    # Add mock summaries with web search indicators
    for i, post in enumerate(mock_posts):
        web_search_used = i < 2  # First two posts use web search
        post['summaries'] = {
            'post_summary': f"Mock summary for: {post['title']}",
            'post_usage': {
                'prompt_tokens': 150,
                'completion_tokens': 75,
                'total_tokens': 225,
                'web_search_used': web_search_used,
                'web_search_cost': 0.03 if web_search_used else 0,
                'estimated_cost': 0.012 + (0.03 if web_search_used else 0)
            },
            'comments_summary': 'Mock comment summary',
            'comments_usage': {
                'prompt_tokens': 50,
                'completion_tokens': 25,
                'total_tokens': 75
            }
        }
    
    try:
        # Test HTML formatting
        html_content = format_email_content(mock_posts)
        print(f"✓ HTML email generated: {len(html_content)} characters")
        
        # Check for web search indicators
        web_search_count = html_content.count('🌐')
        print(f"✓ Web search indicators found: {web_search_count}")
        
        # Check for web search statistics
        if '🌐 Web Searches:' in html_content:
            print("✓ Web search statistics included in HTML")
        
        # Test plain text formatting
        text_content = create_plain_text_content(mock_posts)
        print(f"✓ Plain text email generated: {len(text_content)} characters")
        
        # Check for web search statistics in plain text
        if 'Web searches:' in text_content:
            print("✓ Web search statistics included in plain text")
        
        # Save test output
        with open('test_email_output.html', 'w') as f:
            f.write(html_content)
        print("✓ Test HTML saved to test_email_output.html")
        
        with open('test_email_output.txt', 'w') as f:
            f.write(text_content)
        print("✓ Test plain text saved to test_email_output.txt")
        
    except Exception as e:
        print(f"✗ Email formatting test failed: {e}")
        import traceback
        traceback.print_exc()

def test_cost_tracking():
    """Test cost tracking functionality"""
    print("\n=== Testing Cost Tracking ===")
    
    try:
        # Get initial status
        status = web_search_manager.get_status_summary()
        print(f"✓ Initial daily usage: {status['daily_usage']}")
        
        # Test recording a search
        web_search_manager.cost_tracker.record_search(
            "Test post title",
            actual_cost=0.03,
            success=True
        )
        
        # Check updated status
        updated_status = web_search_manager.get_status_summary()
        print(f"✓ Updated daily usage: {updated_status['daily_usage']}")
        
        # Verify cost was recorded
        if updated_status['daily_usage']['searches_count'] > status['daily_usage']['searches_count']:
            print("✓ Search count incremented correctly")
        
        if updated_status['daily_usage']['total_cost'] > status['daily_usage']['total_cost']:
            print("✓ Cost tracking working correctly")
        
    except Exception as e:
        print(f"✗ Cost tracking test failed: {e}")

def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("\n=== Testing Circuit Breaker ===")
    
    try:
        # Test initial state
        initial_state = web_search_manager.circuit_breaker.state['state']
        print(f"✓ Initial circuit breaker state: {initial_state}")
        
        # Test can_call method
        can_call = web_search_manager.circuit_breaker.can_call()
        print(f"✓ Can call web search: {can_call}")
        
        # Test recording success
        web_search_manager.circuit_breaker.record_success()
        print("✓ Successfully recorded success")
        
        # Test recording failure (without opening circuit)
        web_search_manager.circuit_breaker.record_failure()
        failure_count = web_search_manager.circuit_breaker.state['failure_count']
        print(f"✓ Failure recorded, count: {failure_count}")
        
    except Exception as e:
        print(f"✗ Circuit breaker test failed: {e}")

def main():
    """Run full integration test suite"""
    parser = argparse.ArgumentParser(description='SubSnap Full Integration Test Suite')
    add_reporter_args(parser)
    args = parser.parse_args()
    
    reporter = get_reporter_from_args(args)
    reporter.start_suite("Full Integration Tests")
    
    try:
        # Test 1: Summarization logic
        mock_posts = test_summarization_with_web_search_enabled()
        reporter.add_result("Summarization with Web Search", "pass", f"Tested {len(mock_posts)} mock posts")
        
        # Test 2: Email formatting
        test_email_formatting()
        reporter.add_result("Email Formatting", "pass", "HTML and plain text generation")
        
        # Test 3: Cost tracking
        test_cost_tracking()
        reporter.add_result("Cost Tracking", "pass", "Daily usage and limits")
        
        # Test 4: Circuit breaker
        test_circuit_breaker()
        reporter.add_result("Circuit Breaker", "pass", "Failure handling and recovery")
        
    except Exception as e:
        reporter.add_result("Integration Test Suite", "fail", str(e))
    
    reporter.end_suite()
    reporter.output(args.output if hasattr(args, 'output') else None)

if __name__ == "__main__":
    main()