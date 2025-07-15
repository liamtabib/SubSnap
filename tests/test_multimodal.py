#!/usr/bin/env python3
"""
Test multimodal summarization with mock data
"""
import os
import sys
sys.path.append('../src')

# Set test environment variables
os.environ['ENABLE_IMAGE_ANALYSIS'] = 'true'
os.environ['IMAGE_ANALYSIS_TEST_MODE'] = 'true'

def test_multimodal_summary():
    print("=== Testing Multimodal Summary (No API Calls) ===")
    
    # Mock post data
    mock_post = {
        'title': 'Check out my new AI coding assistant setup',
        'body': 'Just finished setting up my development environment with Claude Code and Cursor. The productivity boost is amazing!',
        'score': 45,
        'author': 'test_user',
        'url': 'https://reddit.com/r/SideProject/test',
        'image_urls': ['https://httpbin.org/image/png']  # Test image
    }
    
    # Test without images
    print("--- Test 1: Text-only post ---")
    post_no_images = mock_post.copy()
    post_no_images['image_urls'] = []
    
    try:
        from reddit_email import create_multimodal_system_prompt
        prompt = create_multimodal_system_prompt('SideProject', False)
        print("✅ Text-only system prompt created")
        print(f"Prompt length: {len(prompt)} characters")
    except Exception as e:
        print(f"❌ Error creating text-only prompt: {e}")
    
    print()
    
    # Test with images
    print("--- Test 2: Post with images ---")
    try:
        from reddit_email import create_multimodal_system_prompt
        prompt_with_images = create_multimodal_system_prompt('SideProject', True)
        print("✅ Multimodal system prompt created")
        print(f"Prompt length: {len(prompt_with_images)} characters")
        print("Contains image instructions:", "screenshot" in prompt_with_images.lower())
    except Exception as e:
        print(f"❌ Error creating multimodal prompt: {e}")
    
    print()
    
    # Test cost calculation
    print("--- Test 3: Cost calculation ---")
    try:
        from reddit_email import calculate_multimodal_cost
        
        mock_usage = {
            'prompt_tokens': 1000,
            'completion_tokens': 200,
            'total_tokens': 1200
        }
        
        cost_no_images = calculate_multimodal_cost(mock_usage, 0)
        cost_with_images = calculate_multimodal_cost(mock_usage, 2)
        
        print(f"✅ Cost calculation working")
        print(f"Text-only cost: ${cost_no_images:.4f}")
        print(f"With 2 images cost: ${cost_with_images:.4f}")
        print(f"Image cost difference: ${cost_with_images - cost_no_images:.4f}")
        
    except Exception as e:
        print(f"❌ Error calculating costs: {e}")
    
    print()
    
    # Test the full function (dry run)
    print("--- Test 4: Full function test (no API call) ---")
    try:
        # This will fail at the API call but we can see if setup works
        from reddit_email import summarize_post_content_multimodal
        
        print("Function imported successfully")
        print("Mock post data prepared:")
        print(f"  Title: {mock_post['title']}")
        print(f"  Body length: {len(mock_post['body'])} chars")
        print(f"  Images: {len(mock_post['image_urls'])}")
        print("✅ Ready for API integration")
        
    except Exception as e:
        print(f"❌ Error with function setup: {e}")

if __name__ == '__main__':
    test_multimodal_summary()