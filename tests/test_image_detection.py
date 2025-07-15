#!/usr/bin/env python3
"""
Simple test script for image detection functionality
"""
import os
import sys
sys.path.append('../src')

# Set test environment variables
os.environ['ENABLE_IMAGE_ANALYSIS'] = 'true'
os.environ['IMAGE_ANALYSIS_TEST_MODE'] = 'true'
os.environ['IMAGE_ANALYSIS_SUBREDDITS'] = 'SideProject,ClaudeCode'

# Import the functions we want to test
from reddit_email import (
    detect_images_from_url, 
    should_analyze_images, 
    validate_image_urls,
    IMAGE_ANALYSIS_CONFIG
)

def test_image_detection():
    print("=== Testing Image Detection Functions ===")
    print(f"Config: {IMAGE_ANALYSIS_CONFIG}")
    print()
    
    # Test cases
    test_cases = [
        {
            'url': 'https://i.redd.it/abc123.jpg',
            'body': '',
            'score': 30,
            'subreddit': 'SideProject',
            'expected_images': 1
        },
        {
            'url': 'https://imgur.com/abc123',
            'body': 'Check out this screenshot: https://i.imgur.com/def456.png',
            'score': 50,
            'subreddit': 'ClaudeCode',
            'expected_images': 2
        },
        {
            'url': 'https://reddit.com/r/test/comments/abc/',
            'body': 'Just a text post',
            'score': 15,
            'subreddit': 'SideProject',
            'expected_images': 0
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"--- Test Case {i} ---")
        print(f"URL: {case['url']}")
        print(f"Body: {case['body'][:50]}{'...' if len(case['body']) > 50 else ''}")
        print(f"Score: {case['score']}, Subreddit: {case['subreddit']}")
        
        # Test should_analyze_images
        should_analyze = should_analyze_images(
            case['score'], case['body'], case['subreddit'], case['url']
        )
        print(f"Should analyze: {should_analyze}")
        
        if should_analyze:
            # Test detect_images_from_url
            images = detect_images_from_url(case['url'], case['body'])
            print(f"Detected images: {len(images)}")
            for img in images:
                print(f"  - {img}")
            
            # Test validation with actual HTTP requests (small sample)
            if len(images) > 0:
                print("Testing image validation:")
                # Only test first image to avoid too many requests
                test_urls = ['https://httpbin.org/image/png']  # Known working test image
                valid_images = validate_image_urls(test_urls)
                print(f"Validation test: {len(valid_images)} valid out of {len(test_urls)} tested")
        
        print()

if __name__ == '__main__':
    test_image_detection()