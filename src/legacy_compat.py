"""Compatibility layer for existing tests and external integrations."""

import os
import sys
from datetime import datetime
from typing import Dict, List, Any

# Add the src directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.config import Config
from clients.reddit_client import RedditClient
from services.summarization_service import SummarizationService
from services.web_search_service import WebSearchService
from formatters.email_formatter import EmailFormatter
from handlers.email_handler import EmailHandler
from core.constants import Constants

# Initialize global configuration (backwards compatibility)
_config = Config()

# Global instances for backwards compatibility
try:
    _config.validate()
    web_search_manager = WebSearchService(_config.web_search)
    print("Compatibility layer initialized successfully")
except Exception as e:
    print(f"Warning: Configuration validation failed: {e}")
    web_search_manager = None

# Export legacy configuration dictionaries for backwards compatibility
IMAGE_ANALYSIS_CONFIG = {
    'enabled': _config.image_analysis.enabled,
    'max_images_per_post': _config.image_analysis.max_images_per_post,
    'min_post_score': _config.image_analysis.min_post_score,
    'max_cost_per_day': _config.image_analysis.max_cost_per_day,
    'target_subreddits': _config.image_analysis.target_subreddits,
    'test_mode': _config.image_analysis.test_mode
}

WEB_SEARCH_CONFIG = {
    'enabled': _config.web_search.enabled,
    'daily_limit': _config.web_search.daily_limit,
    'cost_limit_per_day': _config.web_search.cost_limit_per_day,
    'cost_per_search': _config.web_search.cost_per_search,
    'min_post_score': _config.web_search.min_post_score,
    'target_subreddits': _config.web_search.target_subreddits,
    'trigger_keywords': _config.web_search.trigger_keywords,
    'external_domains': _config.web_search.external_domains,
    'test_mode': _config.web_search.test_mode,
    'circuit_breaker_threshold': _config.web_search.circuit_breaker_threshold,
    'circuit_breaker_timeout': _config.web_search.circuit_breaker_timeout
}

# Legacy function wrappers for backwards compatibility
def connect_to_reddit():
    """Legacy function for connecting to Reddit."""
    reddit_client = RedditClient(_config.reddit)
    return reddit_client._get_reddit()

def is_today(timestamp, timezone_str='Europe/Berlin'):
    """Legacy function for date checking."""
    reddit_client = RedditClient(_config.reddit)
    return reddit_client.is_today(timestamp, timezone_str)

def fetch_reddit_posts(subreddit_names=['windsurf', 'vibecoding'], limit=10, comment_limit=3):
    """Legacy function for fetching Reddit posts."""
    reddit_client = RedditClient(_config.reddit)
    posts_dict = reddit_client.fetch_posts(
        subreddit_names=subreddit_names,
        limit=limit,
        comment_limit=comment_limit,
        min_score=_config.min_post_score,
        user_timezone=_config.user_timezone
    )
    
    # Convert to legacy format
    legacy_format = {}
    for subreddit, posts in posts_dict.items():
        legacy_format[subreddit] = [post.to_dict() for post in posts]
    
    return legacy_format

def summarize_post_content(post_data, subreddit_name):
    """Legacy function for post content summarization."""
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    summarization_service = SummarizationService(_config)
    result = summarization_service.summarize_post_content(post)
    
    return result

def summarize_comments(post_data, subreddit_name):
    """Legacy function for comment summarization."""
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    summarization_service = SummarizationService(_config)
    result = summarization_service.summarize_comments(post)
    
    return result

def summarize_post(post_data, subreddit_name):
    """Legacy function for complete post summarization."""
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    summarization_service = SummarizationService(_config)
    result = summarization_service.summarize_post(post)
    
    return result.to_dict()

def format_email_content(all_posts, all_subreddit_posts=None):
    """Legacy function for HTML email formatting."""
    email_formatter = EmailFormatter(_config.user_timezone)
    return email_formatter.format_html_email(all_posts)

def create_plain_text_content(all_posts, all_subreddit_posts=None):
    """Legacy function for plain text email formatting."""
    email_formatter = EmailFormatter(_config.user_timezone)
    return email_formatter.format_plain_text_email(all_posts)

def send_email(subject, html_content, recipient_email=None, all_subreddit_posts=None):
    """Legacy function for sending emails."""
    # For backwards compatibility, we need to extract posts from HTML or use a different approach
    # This is a simplified version that won't have all the advanced features
    email_handler = EmailHandler(_config.email, _config.user_timezone)
    
    # Create a simple message structure
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    import ssl
    
    sender_email = _config.email.sender
    recipient_email = recipient_email or _config.email.recipient
    password = _config.email.password
    
    if not all([sender_email, recipient_email, password]):
        print("Error: Missing email configuration.")
        return False
    
    # Create message
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    
    # Add HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)
    
    # Send email using the same logic as the original
    try:
        print("Attempting to connect to SMTP server...")
        context = ssl.create_default_context()
        with smtplib.SMTP(_config.email.smtp_server, _config.email.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, password.strip())
            server.sendmail(sender_email, recipient_email, message.as_string())
            print(f"Email sent successfully to {recipient_email}")
            return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Web search functions for backwards compatibility
def should_use_web_search(post_data, subreddit_name):
    """Legacy function for web search decision."""
    if not web_search_manager:
        return False
    
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post_data['subreddit'] = subreddit_name  # Ensure subreddit is set
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    return web_search_manager.should_use_web_search(post)

def calculate_web_search_score(post_data, subreddit_name):
    """Legacy function for web search scoring."""
    if not web_search_manager:
        return 0
    
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post_data['subreddit'] = subreddit_name  # Ensure subreddit is set
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    return web_search_manager.calculate_web_search_score(post)

def can_perform_search(post_data, subreddit_name):
    """Legacy function for web search capability check."""
    if not web_search_manager:
        return False, "Web search manager not available"
    
    # Convert dict to RedditPost object if necessary
    if isinstance(post_data, dict):
        from models.reddit_models import RedditPost
        post_data['subreddit'] = subreddit_name  # Ensure subreddit is set
        post = RedditPost.from_dict(post_data)
    else:
        post = post_data
    
    return web_search_manager.can_perform_search(post)

def extract_product_mentions(text):
    """Legacy function for product mention extraction."""
    from core.validators import WebSearchValidator
    return WebSearchValidator.extract_product_mentions(text)

def extract_external_domains(url):
    """Legacy function for domain extraction."""
    from core.validators import WebSearchValidator
    return WebSearchValidator.extract_external_domains(url)

# Image analysis functions for backwards compatibility
def detect_images_from_url(post_url, post_body=""):
    """Legacy function for image detection."""
    from core.validators import ImageValidator
    return ImageValidator.detect_images_from_url(post_url, post_body)

def should_analyze_images(score, body, subreddit, url):
    """Legacy function for image analysis decision."""
    # Create a temporary RedditPost object
    from models.reddit_models import RedditPost
    post = RedditPost(
        title="",
        author="test",
        score=score,
        url=url,
        body=body,
        created_time="",
        subreddit=subreddit
    )
    
    from services.image_analysis_service import ImageAnalysisService
    service = ImageAnalysisService(_config.image_analysis)
    return service.should_analyze_images(post)

def validate_image_urls(image_urls, timeout=10):
    """Legacy function for image URL validation."""
    from core.validators import ImageValidator
    return ImageValidator.validate_image_urls(image_urls, timeout)

# Main function for backwards compatibility
def main():
    """Legacy main function."""
    from app import main as new_main
    return new_main()

if __name__ == '__main__':
    main()