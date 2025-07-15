"""Data models for Reddit content."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Comment:
    """Represents a Reddit comment."""
    author: str
    body: str
    score: int
    created_time: Optional[datetime] = None


@dataclass
class RedditPost:
    """Represents a Reddit post."""
    title: str
    author: str
    score: int
    url: str
    body: str
    created_time: str
    subreddit: str
    comments: List[Comment] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for backwards compatibility."""
        return {
            'title': self.title,
            'author': self.author,
            'score': self.score,
            'url': self.url,
            'body': self.body,
            'created_time': self.created_time,
            'subreddit': self.subreddit,
            'comments': [
                {
                    'author': comment.author,
                    'body': comment.body,
                    'score': comment.score
                }
                for comment in self.comments
            ],
            'image_urls': self.image_urls
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RedditPost':
        """Create RedditPost from dictionary."""
        comments = []
        for comment in data.get('comments', []):
            if isinstance(comment, dict):
                comments.append(Comment(
                    author=comment.get('author', 'unknown'),
                    body=comment.get('body', ''),
                    score=comment.get('score', 0)
                ))
            else:
                comments.append(comment)
        
        return cls(
            title=data.get('title', ''),
            author=data.get('author', 'unknown'),
            score=data.get('score', 0),
            url=data.get('url', ''),
            body=data.get('body', ''),
            created_time=data.get('created_time', ''),
            subreddit=data.get('subreddit', ''),
            comments=comments,
            image_urls=data.get('image_urls', [])
        )