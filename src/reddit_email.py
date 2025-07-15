#!/usr/bin/env python3
"""
Reddit Email Service - Legacy compatibility wrapper.

This file provides backwards compatibility with the original monolithic structure.
All functionality has been moved to the new modular architecture.
"""

# Import everything from the compatibility layer
from legacy_compat import *

# Explicit exports for clarity
__all__ = [
    'WEB_SEARCH_CONFIG', 'IMAGE_ANALYSIS_CONFIG', 'web_search_manager',
    'connect_to_reddit', 'is_today', 'fetch_reddit_posts',
    'summarize_post_content', 'summarize_comments', 'summarize_post',
    'format_email_content', 'create_plain_text_content', 'send_email',
    'should_use_web_search', 'calculate_web_search_score', 'can_perform_search',
    'extract_product_mentions', 'extract_external_domains', 'main'
]

# Maintain the original entry point
if __name__ == '__main__':
    main()