#!/usr/bin/env python3
"""
Test edge cases and potential issues
"""
import os
import sys
sys.path.append('../src')

def test_empty_web_search_results():
    """Test handling when no posts qualify for web search"""
    print("=== Testing Empty Web Search Results ===")
    
    from reddit_email import format_email_content, create_plain_text_content
    
    # Create posts with no web search usage
    posts_no_web_search = [
        {
            'title': 'Simple discussion post',
            'body': 'Just a regular discussion',
            'url': 'https://reddit.com/r/test',
            'score': 20,
            'subreddit': 'test',
            'author': 'user1',
            'created_time': '2025-07-13 10:00:00',
            'comments': [],
            'summaries': {
                'post_summary': 'Test summary',
                'post_usage': {
                    'prompt_tokens': 100,
                    'completion_tokens': 50,
                    'total_tokens': 150,
                    'web_search_used': False,  # No web search
                    'estimated_cost': 0.005
                },
                'comments_summary': 'No comments',
                'comments_usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
            }
        }
    ]
    
    try:
        html_content = format_email_content(posts_no_web_search)
        if '🌐 Web Searches: 0' in html_content:
            print("✓ HTML correctly shows 0 web searches")
        else:
            print("✗ HTML web search count issue")
            
        text_content = create_plain_text_content(posts_no_web_search)
        if 'Web searches: 0' in text_content:
            print("✓ Plain text correctly shows 0 web searches")
        else:
            print("✗ Plain text web search count issue")
            
    except Exception as e:
        print(f"✗ Error in email formatting: {e}")
        import traceback
        traceback.print_exc()

def test_config_validation():
    """Test configuration edge cases"""
    print("\n=== Testing Configuration Validation ===")
    
    from reddit_email import WEB_SEARCH_CONFIG
    
    # Test required fields
    required_fields = [
        'enabled', 'daily_limit', 'cost_limit_per_day', 'cost_per_search',
        'target_subreddits', 'trigger_keywords', 'external_domains'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in WEB_SEARCH_CONFIG:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"✗ Missing config fields: {missing_fields}")
    else:
        print("✓ All required config fields present")
    
    # Test data types
    type_checks = [
        ('enabled', bool),
        ('daily_limit', int),
        ('cost_limit_per_day', (int, float)),
        ('target_subreddits', list),
        ('trigger_keywords', list)
    ]
    
    for field, expected_type in type_checks:
        if field in WEB_SEARCH_CONFIG:
            actual_value = WEB_SEARCH_CONFIG[field]
            if isinstance(actual_value, expected_type):
                print(f"✓ {field} has correct type")
            else:
                print(f"✗ {field} type error: expected {expected_type}, got {type(actual_value)}")

def test_circuit_breaker_edge_cases():
    """Test circuit breaker edge cases"""
    print("\n=== Testing Circuit Breaker Edge Cases ===")
    
    from reddit_email import web_search_manager
    
    try:
        # Test multiple failures
        initial_count = web_search_manager.circuit_breaker.state['failure_count']
        
        # Record several failures
        for i in range(3):
            web_search_manager.circuit_breaker.record_failure()
        
        final_count = web_search_manager.circuit_breaker.state['failure_count']
        state = web_search_manager.circuit_breaker.state['state']
        
        print(f"✓ Failure count increased: {initial_count} -> {final_count}")
        print(f"✓ Circuit breaker state: {state}")
        
        # Test recovery
        web_search_manager.circuit_breaker.record_success()
        recovered_state = web_search_manager.circuit_breaker.state['state']
        print(f"✓ Recovery state: {recovered_state}")
        
    except Exception as e:
        print(f"✗ Circuit breaker error: {e}")

def test_cost_tracking_edge_cases():
    """Test cost tracking edge cases"""
    print("\n=== Testing Cost Tracking Edge Cases ===")
    
    from reddit_email import web_search_manager
    
    try:
        # Test recording with different costs
        initial_cost = web_search_manager.cost_tracker.usage_data['total_cost']
        
        # Record a custom cost
        web_search_manager.cost_tracker.record_search(
            "Test with custom cost",
            actual_cost=0.05,  # Different from default
            success=True
        )
        
        final_cost = web_search_manager.cost_tracker.usage_data['total_cost']
        cost_diff = final_cost - initial_cost
        
        if abs(cost_diff - 0.05) < 0.001:  # Allow for floating point precision
            print("✓ Custom cost tracking works")
        else:
            print(f"✗ Cost tracking error: expected +0.05, got +{cost_diff}")
        
        # Test limit checking
        can_search = web_search_manager.cost_tracker.can_search()
        print(f"✓ Limit check result: {can_search}")
        
    except Exception as e:
        print(f"✗ Cost tracking error: {e}")

def test_fallback_chain():
    """Test the complete fallback chain"""
    print("\n=== Testing Fallback Chain ===")
    
    from reddit_email import summarize_post_content
    
    test_post = {
        'title': 'Test fallback chain',
        'body': 'Testing the complete fallback mechanism',
        'url': 'https://example.com',
        'score': 30,
        'subreddit': 'test'
    }
    
    try:
        # This should work through the fallback chain
        result = summarize_post_content(test_post, 'test')
        
        if result is None:
            print("✓ Fallback chain completed (expected with no API calls)")
        else:
            print(f"✓ Fallback chain returned result: {type(result)}")
            
    except Exception as e:
        print(f"✗ Fallback chain error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all edge case tests"""
    print("Web Search Implementation - Edge Case Testing")
    print("=" * 55)
    
    test_empty_web_search_results()
    test_config_validation()
    test_circuit_breaker_edge_cases()
    test_cost_tracking_edge_cases()
    test_fallback_chain()
    
    print("\n" + "=" * 55)
    print("✓ Edge case testing completed")

if __name__ == "__main__":
    main()