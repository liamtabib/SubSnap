"""Configuration settings for Reddit Email Digest."""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')


def env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    return int(os.getenv(key, str(default)))


def env_float(key: str, default: float) -> float:
    """Get float environment variable."""
    return float(os.getenv(key, str(default)))


def env_list(key: str, default: str = '', separator: str = ',') -> List[str]:
    """Get list environment variable."""
    value = os.getenv(key, default)
    return [item.strip() for item in value.split(separator) if item.strip()]


@dataclass
class RedditConfig:
    """Reddit API configuration."""
    client_id: str = os.getenv('REDDIT_CLIENT_ID', '')
    client_secret: str = os.getenv('REDDIT_CLIENT_SECRET', '')
    user_agent: str = os.getenv('REDDIT_USER_AGENT', 'reddit_digest_bot')
    
    def validate(self) -> None:
        """Validate Reddit configuration."""
        if not self.client_id:
            raise ValueError("REDDIT_CLIENT_ID is required")
        if not self.client_secret:
            raise ValueError("REDDIT_CLIENT_SECRET is required")


@dataclass
class EmailConfig:
    """Email configuration."""
    sender: str = os.getenv('EMAIL_SENDER', '')
    recipient: str = os.getenv('EMAIL_RECIPIENT', '')
    password: str = os.getenv('EMAIL_PASSWORD', '')
    smtp_server: str = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port: int = env_int('SMTP_PORT', 587)
    
    def validate(self) -> None:
        """Validate email configuration."""
        if not self.sender:
            raise ValueError("EMAIL_SENDER is required")
        if not self.recipient:
            raise ValueError("EMAIL_RECIPIENT is required")
        if not self.password:
            raise ValueError("EMAIL_PASSWORD is required")


@dataclass
class ImageAnalysisConfig:
    """Image analysis configuration."""
    enabled: bool = env_bool('ENABLE_IMAGE_ANALYSIS', True)
    max_images_per_post: int = env_int('MAX_IMAGES_PER_POST', 2)
    min_post_score: int = env_int('IMAGE_ANALYSIS_MIN_SCORE', 25)
    max_cost_per_day: float = env_float('IMAGE_ANALYSIS_MAX_COST_PER_DAY', 1.00)
    target_subreddits: List[str] = field(default_factory=lambda: env_list('IMAGE_ANALYSIS_SUBREDDITS', 'SideProject,ClaudeCode'))
    test_mode: bool = env_bool('IMAGE_ANALYSIS_TEST_MODE', False)
    
    def validate(self) -> None:
        """Validate image analysis configuration."""
        if self.max_images_per_post < 1:
            raise ValueError("MAX_IMAGES_PER_POST must be at least 1")
        if self.min_post_score < 0:
            raise ValueError("IMAGE_ANALYSIS_MIN_SCORE must be non-negative")
        if self.max_cost_per_day <= 0:
            raise ValueError("IMAGE_ANALYSIS_MAX_COST_PER_DAY must be positive")


@dataclass
class WebSearchConfig:
    """Web search configuration."""
    enabled: bool = env_bool('WEB_SEARCH_ENABLED', True)
    daily_limit: int = env_int('WEB_SEARCH_DAILY_LIMIT', 15)
    cost_limit_per_day: float = env_float('WEB_SEARCH_COST_LIMIT', 1.50)
    cost_per_search: float = env_float('WEB_SEARCH_COST_PER_CALL', 0.03)
    min_post_score: int = env_int('WEB_SEARCH_MIN_SCORE', 15)
    target_subreddits: List[str] = field(default_factory=lambda: env_list('WEB_SEARCH_SUBREDDITS', 'SideProject,ClaudeCode,ClaudeAI,AI_Agents'))
    trigger_keywords: List[str] = field(default_factory=lambda: env_list('WEB_SEARCH_KEYWORDS', 'launched,released,new version,pricing,acquired,funding,announcement,beta,available now,update,feature'))
    external_domains: List[str] = field(default_factory=lambda: env_list('WEB_SEARCH_DOMAINS', 'github.com,producthunt.com,ycombinator.com,techcrunch.com,apps.apple.com,play.google.com'))
    test_mode: bool = env_bool('WEB_SEARCH_TEST_MODE', False)
    circuit_breaker_threshold: int = env_int('WEB_SEARCH_FAILURE_THRESHOLD', 5)
    circuit_breaker_timeout: int = env_int('WEB_SEARCH_RECOVERY_TIMEOUT', 1800)
    
    def validate(self) -> None:
        """Validate web search configuration."""
        if self.daily_limit < 1:
            raise ValueError("WEB_SEARCH_DAILY_LIMIT must be at least 1")
        if self.cost_limit_per_day <= 0:
            raise ValueError("WEB_SEARCH_COST_LIMIT must be positive")
        if self.cost_per_search <= 0:
            raise ValueError("WEB_SEARCH_COST_PER_CALL must be positive")
        if self.min_post_score < 0:
            raise ValueError("WEB_SEARCH_MIN_SCORE must be non-negative")


@dataclass
class Config:
    """Main configuration class."""
    reddit: RedditConfig = field(default_factory=RedditConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    image_analysis: ImageAnalysisConfig = field(default_factory=ImageAnalysisConfig)
    web_search: WebSearchConfig = field(default_factory=WebSearchConfig)
    
    # Application settings
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    user_timezone: str = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    schedule_time: str = os.getenv('SCHEDULE_TIME', '09:00')
    initial_run: bool = env_bool('INITIAL_RUN', False)
    run_once: bool = env_bool('RUN_ONCE', False)
    
    # Subreddit settings
    subreddits: List[str] = field(default_factory=lambda: env_list('SUBREDDITS', 'SideProject,vibecoding,Anthropic,AI_Agents,Linear,ClaudeCode,ClaudeAI'))
    posts_per_subreddit: int = env_int('POSTS_PER_SUBREDDIT', 3)
    comment_limit: int = env_int('COMMENT_LIMIT', 3)
    min_post_score: int = env_int('MIN_POST_SCORE', 10)
    
    def validate(self) -> None:
        """Validate all configuration sections."""
        self.reddit.validate()
        self.email.validate()
        self.image_analysis.validate()
        self.web_search.validate()
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if self.posts_per_subreddit < 1:
            raise ValueError("POSTS_PER_SUBREDDIT must be at least 1")
        if self.comment_limit < 0:
            raise ValueError("COMMENT_LIMIT must be non-negative")
        if self.min_post_score < 0:
            raise ValueError("MIN_POST_SCORE must be non-negative")