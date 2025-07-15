"""Web search integration for enhanced post summarization."""

import json
import os
from datetime import datetime
from typing import Dict, Any, Tuple

from core.config import WebSearchConfig
from models.reddit_models import RedditPost
from core.validators import WebSearchValidator
from handlers.cost_tracker import WebSearchCostTracker
from core.constants import Constants


class WebSearchCircuitBreaker:
    """Implements circuit breaker pattern for web search reliability."""
    
    def __init__(self, failure_threshold: int, recovery_timeout: int):
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state_file = Constants.WEB_SEARCH_CIRCUIT_STATE_FILE
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load circuit breaker state."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Check if recovery timeout has passed
                    if state.get('state') == 'open':
                        last_failure = datetime.fromisoformat(state.get('last_failure', '2000-01-01'))
                        if (datetime.now() - last_failure).total_seconds() > self.recovery_timeout:
                            state['state'] = 'half_open'
                            state['failure_count'] = 0
                    return state
            
            return {
                'state': 'closed',  # closed, open, half_open
                'failure_count': 0,
                'last_failure': None
            }
        except Exception as e:
            print(f"Error loading circuit breaker state: {e}")
            return {'state': 'closed', 'failure_count': 0, 'last_failure': None}
    
    def save_state(self) -> None:
        """Save circuit breaker state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving circuit breaker state: {e}")
    
    def can_call(self) -> bool:
        """Check if web search calls are allowed."""
        return self.state['state'] in ['closed', 'half_open']
    
    def record_success(self) -> None:
        """Record successful web search call."""
        self.state['state'] = 'closed'
        self.state['failure_count'] = 0
        self.state['last_failure'] = None
        self.save_state()
    
    def record_failure(self) -> None:
        """Record failed web search call."""
        self.state['failure_count'] += 1
        self.state['last_failure'] = datetime.now().isoformat()
        
        if self.state['failure_count'] >= self.failure_threshold:
            self.state['state'] = 'open'
        
        self.save_state()


class WebSearchService:
    """Main service for web search functionality with safety mechanisms."""
    
    def __init__(self, config: WebSearchConfig):
        """Initialize web search manager."""
        self.config = config
        self.validator = WebSearchValidator()
        self.cost_tracker = WebSearchCostTracker(
            config.daily_limit,
            config.cost_limit_per_day
        )
        self.circuit_breaker = WebSearchCircuitBreaker(
            config.circuit_breaker_threshold,
            config.circuit_breaker_timeout
        )
    
    def calculate_web_search_score(self, post: RedditPost) -> int:
        """Calculate a score to determine if post warrants web search."""
        if not self.config.enabled:
            return 0
        
        score = 0
        title = post.title.lower()
        body = post.body.lower()
        
        # Subreddit targeting (high value for tech subreddits)
        if post.subreddit in self.config.target_subreddits:
            score += 20
            if self.config.test_mode:
                print(f"  +20 for target subreddit: {post.subreddit}")
        
        # Keyword triggers (product launches, announcements, etc.)
        title_body = title + ' ' + body
        for keyword in self.config.trigger_keywords:
            if keyword.lower() in title_body:
                score += 15
                if self.config.test_mode:
                    print(f"  +15 for keyword: {keyword}")
                break  # Only count once per post
        
        # High engagement posts
        if post.score >= self.config.min_post_score:
            score += 25
            if self.config.test_mode:
                print(f"  +25 for high engagement: {post.score}")
        
        # External domain links (news sites, product pages)
        domains = self.validator.extract_external_domains(post.url)
        for domain in domains:
            if domain in self.config.external_domains:
                score += 20
                if self.config.test_mode:
                    print(f"  +20 for external domain: {domain}")
            elif domain not in ['reddit.com', 'imgur.com', 'i.redd.it']:
                score += 10
                if self.config.test_mode:
                    print(f"  +10 for other external domain: {domain}")
        
        # Product mentions in title/body
        products = self.validator.extract_product_mentions(title_body)
        if products:
            score += 15
            if self.config.test_mode:
                print(f"  +15 for product mentions: {products}")
        
        # Minimal text content (often image/link posts about new things)
        if len(body) < 100:
            score += 5
            if self.config.test_mode:
                print(f"  +5 for minimal text content")
        
        return score
    
    def should_use_web_search(self, post: RedditPost) -> bool:
        """Determine if a post should use web search for enhanced context."""
        if not self.config.enabled:
            return False
        
        score = self.calculate_web_search_score(post)
        threshold = Constants.WEB_SEARCH_SCORE_THRESHOLD
        
        result = score >= threshold
        
        if self.config.test_mode:
            print(f"Web search decision for '{post.title[:50]}...': score={score}, threshold={threshold}, result={result}")
        
        return result
    
    def can_perform_search(self, post: RedditPost) -> Tuple[bool, str]:
        """Check if we can perform a web search for this post."""
        # Check configuration
        if not self.config.enabled:
            return False, "Web search disabled in configuration"
        
        # Check if post warrants web search
        if not self.should_use_web_search(post):
            return False, "Post doesn't meet web search criteria"
        
        # Check daily limits
        if not self.cost_tracker.can_search():
            return False, "Daily search limits exceeded"
        
        # Check circuit breaker
        if not self.circuit_breaker.can_call():
            return False, "Circuit breaker is open due to previous failures"
        
        return True, "All checks passed"
    
    def create_search_guidance_context(self, post: RedditPost) -> str:
        """Generate specific search guidance for the model."""
        title = post.title
        body = post.body
        
        # Extract entities that might need current information
        products = self.validator.extract_product_mentions(title + ' ' + body)
        domains = self.validator.extract_external_domains(post.url)
        
        guidance_parts = []
        
        if products:
            guidance_parts.append(f"Consider searching for current information about: {', '.join(products[:3])}")
        
        # Check for time-sensitive keywords
        time_keywords = ['new', 'latest', 'just', 'recently', 'announced', 'launched', 'released', 'updated']
        if any(keyword in title.lower() + body.lower() for keyword in time_keywords):
            guidance_parts.append("This post mentions recent developments - verify current status")
        
        if domains:
            guidance_parts.append(f"External links detected - may warrant verification")
        
        return '. '.join(guidance_parts) + '.' if guidance_parts else ''
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status of web search system."""
        cost_summary = self.cost_tracker.get_daily_summary()
        circuit_state = self.circuit_breaker.state['state']
        
        return {
            'enabled': self.config.enabled,
            'daily_usage': cost_summary,
            'circuit_breaker_state': circuit_state,
            'last_failure': self.circuit_breaker.state.get('last_failure'),
            'failure_count': self.circuit_breaker.state.get('failure_count', 0)
        }