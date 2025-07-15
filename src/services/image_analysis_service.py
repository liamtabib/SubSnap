"""Image analysis functionality."""

from typing import List
from core.config import ImageAnalysisConfig
from models.reddit_models import RedditPost
from core.validators import ImageValidator


class ImageAnalysisService:
    """Handles image detection and analysis for Reddit posts."""
    
    def __init__(self, config: ImageAnalysisConfig):
        """Initialize image analyzer."""
        self.config = config
        self.validator = ImageValidator()
    
    def should_analyze_images(self, post: RedditPost) -> bool:
        """Decide if this post warrants image analysis."""
        # Configuration check
        if not self.config.enabled:
            return False
        
        # Only for specific subreddits
        if post.subreddit not in self.config.target_subreddits:
            return False
        
        # Only for high-engagement or image-likely posts
        high_engagement = post.score >= self.config.min_post_score
        minimal_text = len(post.body) < 100
        likely_image_post = any(domain in post.url for domain in ['imgur.com', 'i.redd.it'])
        
        result = high_engagement or minimal_text or likely_image_post
        
        if self.config.test_mode and result:
            print(f"Will analyze images for post (score: {post.score}, text_len: {len(post.body)}, url: {post.url[:50]}...)")
        
        return result
    
    def detect_images(self, post: RedditPost) -> List[str]:
        """Detect and validate images in a Reddit post."""
        if not self.should_analyze_images(post):
            return []
        
        # Extract potential image URLs
        image_urls = self.validator.detect_images_from_url(post.url, post.body)
        
        if not image_urls:
            return []
        
        # Validate image accessibility
        valid_images = self.validator.validate_image_urls(image_urls)
        
        if self.config.test_mode and valid_images:
            print(f"DEBUG: Post '{post.title[:30]}...' has {len(valid_images)} valid images: {valid_images}")
        
        return valid_images
    
    def calculate_multimodal_cost(self, text_usage: dict, image_count: int) -> float:
        """Calculate estimated cost including images."""
        if not text_usage:
            return 0
        
        # GPT-4o pricing (as of 2025)
        prompt_tokens = text_usage.get('prompt_tokens', 0)
        completion_tokens = text_usage.get('completion_tokens', 0)
        
        text_cost = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000
        image_cost = image_count * 0.00765  # Per image cost for low detail
        
        return text_cost + image_cost