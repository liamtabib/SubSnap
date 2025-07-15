"""Data models for AI components."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    images_processed: int = 0
    web_search_used: bool = False
    web_search_cost: float = 0.0
    estimated_cost: float = 0.0


@dataclass
class PostSummary:
    """Summary of a Reddit post."""
    post_summary: Optional[str] = None
    comments_summary: Optional[str] = None
    post_usage: Optional[UsageStats] = None
    comments_usage: Optional[UsageStats] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for backwards compatibility."""
        return {
            'post_summary': self.post_summary,
            'comments_summary': self.comments_summary,
            'post_usage': self.post_usage.__dict__ if self.post_usage else None,
            'comments_usage': self.comments_usage.__dict__ if self.comments_usage else None
        }