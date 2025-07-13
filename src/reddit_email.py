#!/usr/bin/env python3
"""
Reddit Email Service - Fetches top posts from selected subreddits and sends them via email
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import praw
from dotenv import load_dotenv
import schedule
import time
import argparse
from pytz import timezone as pytz_timezone
import pytz
import openai
from typing import List, Dict, Any
import re
import requests
import json
import traceback
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Initialize OpenAI API client
openai_api_key = os.getenv('OPENAI_API_KEY')
print(f"OpenAI API key available: {bool(openai_api_key)}") 
print(f"OpenAI API key length: {len(openai_api_key) if openai_api_key else 0}")

# Use modern OpenAI client (v1.0+)
if openai_api_key:
    try:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        print("OpenAI API key available: True")
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        openai_client = None
else:
    openai_client = None
    print("WARNING: OpenAI API key not available - summaries will be skipped")

# Image analysis configuration
IMAGE_ANALYSIS_CONFIG = {
    'enabled': os.getenv('ENABLE_IMAGE_ANALYSIS', 'true').lower() == 'true',
    'max_images_per_post': int(os.getenv('MAX_IMAGES_PER_POST', '2')),
    'min_post_score': int(os.getenv('IMAGE_ANALYSIS_MIN_SCORE', '25')),
    'max_cost_per_day': float(os.getenv('IMAGE_ANALYSIS_MAX_COST_PER_DAY', '1.00')),
    'target_subreddits': [s.strip() for s in os.getenv('IMAGE_ANALYSIS_SUBREDDITS', 'SideProject,ClaudeCode').split(',') if s.strip()],
    'test_mode': os.getenv('IMAGE_ANALYSIS_TEST_MODE', 'false').lower() == 'true'
}

print(f"Image analysis config: {IMAGE_ANALYSIS_CONFIG}")

# Web search configuration
WEB_SEARCH_CONFIG = {
    'enabled': os.getenv('WEB_SEARCH_ENABLED', 'false').lower() == 'true',
    'daily_limit': int(os.getenv('WEB_SEARCH_DAILY_LIMIT', '8')),
    'cost_limit_per_day': float(os.getenv('WEB_SEARCH_COST_LIMIT', '0.50')),
    'cost_per_search': float(os.getenv('WEB_SEARCH_COST_PER_CALL', '0.03')),
    'min_post_score': int(os.getenv('WEB_SEARCH_MIN_SCORE', '25')),
    'target_subreddits': [s.strip() for s in os.getenv('WEB_SEARCH_SUBREDDITS', 'SideProject,ClaudeCode').split(',') if s.strip()],
    'trigger_keywords': [s.strip() for s in os.getenv('WEB_SEARCH_KEYWORDS', 'launched,released,new version,pricing,acquired,funding,announcement,beta,available now').split(',') if s.strip()],
    'external_domains': [s.strip() for s in os.getenv('WEB_SEARCH_DOMAINS', 'github.com,producthunt.com,ycombinator.com,techcrunch.com').split(',') if s.strip()],
    'test_mode': os.getenv('WEB_SEARCH_TEST_MODE', 'false').lower() == 'true',
    'circuit_breaker_threshold': int(os.getenv('WEB_SEARCH_FAILURE_THRESHOLD', '3')),
    'circuit_breaker_timeout': int(os.getenv('WEB_SEARCH_RECOVERY_TIMEOUT', '3600'))  # 1 hour
}

print(f"Web search config: {WEB_SEARCH_CONFIG}")

def connect_to_reddit():
    """Connect to Reddit API"""
    return praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT', 'reddit_digest_bot')
    )

def is_today(timestamp, timezone_str='Europe/Berlin'):
    """Check if a timestamp is from today in the specified timezone"""
    # Get the current time in the user's timezone
    tz = pytz_timezone(timezone_str)
    now = datetime.now(tz)
    
    # Convert Unix timestamp to datetime in the user's timezone
    post_time = datetime.fromtimestamp(timestamp, tz)
    
    # Check if the post is from today
    return (post_time.year == now.year and 
            post_time.month == now.month and 
            post_time.day == now.day)

def detect_images_from_url(post_url, post_body=""):
    """Extract image URLs from Reddit post URL and body - no PRAW needed"""
    images = []
    
    # Direct Reddit image posts (i.redd.it)
    if 'i.redd.it' in post_url:
        images.append(post_url)
    
    # Imgur direct links
    elif 'imgur.com' in post_url and not post_url.endswith('/'):
        normalized_url = normalize_imgur_url(post_url)
        if normalized_url:
            images.append(normalized_url)
    
    # Extract image URLs from post body text
    if post_body:
        body_images = extract_image_urls_from_text(post_body)
        images.extend(body_images)
    
    # Remove duplicates and limit to 2 images for cost control
    unique_images = list(dict.fromkeys(images))
    return unique_images[:2]

def normalize_imgur_url(url):
    """Convert imgur.com/abc to i.imgur.com/abc.jpg"""
    try:
        if 'i.imgur.com' in url:
            return url
        if 'imgur.com/' in url:
            # Extract image ID from URL
            parts = url.split('/')
            if len(parts) > 3:
                img_id = parts[-1].split('.')[0]  # Remove extension if present
                return f"https://i.imgur.com/{img_id}.jpg"
    except Exception as e:
        print(f"Error normalizing imgur URL {url}: {e}")
    return None

def extract_image_urls_from_text(text):
    """Extract image URLs from text using regex"""
    image_urls = []
    
    # Common image URL patterns (no capture groups to avoid tuple returns)
    url_patterns = [
        r'https?://i\.redd\.it/[^\s]+',
        r'https?://i\.imgur\.com/[^\s]+\.(?:jpg|jpeg|png|gif|webp)',
        r'https?://imgur\.com/[^\s]+',
        r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)'
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        image_urls.extend(matches)
    
    # Normalize imgur URLs
    normalized_urls = []
    for url in image_urls:
        if 'imgur.com' in url and 'i.imgur.com' not in url:
            normalized = normalize_imgur_url(url)
            if normalized:
                normalized_urls.append(normalized)
        else:
            normalized_urls.append(url)
    
    return normalized_urls

def should_analyze_images(post_score, post_body, subreddit_name, post_url):
    """Decide if this post warrants image analysis"""
    # Configuration check
    if not IMAGE_ANALYSIS_CONFIG['enabled']:
        return False
    
    # Only for specific subreddits
    if subreddit_name not in IMAGE_ANALYSIS_CONFIG['target_subreddits']:
        return False
    
    # Only for high-engagement or image-likely posts
    high_engagement = post_score >= IMAGE_ANALYSIS_CONFIG['min_post_score']
    minimal_text = len(post_body) < 100
    likely_image_post = any(domain in post_url for domain in ['imgur.com', 'i.redd.it'])
    
    result = high_engagement or minimal_text or likely_image_post
    
    if IMAGE_ANALYSIS_CONFIG['test_mode'] and result:
        print(f"Will analyze images for post (score: {post_score}, text_len: {len(post_body)}, url: {post_url[:50]}...)")
    
    return result

def validate_image_urls(image_urls, timeout=5):
    """Check if images are actually accessible"""
    valid_urls = []
    
    for url in image_urls:
        try:
            # Quick HEAD request to check if image exists
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                if 'image' in content_type:
                    valid_urls.append(url)
                    print(f"Valid image found: {url}")
                else:
                    print(f"URL not an image: {url} (content-type: {content_type})")
            else:
                print(f"Image not accessible: {url} (status: {response.status_code})")
        except requests.RequestException as e:
            print(f"Error validating image {url}: {e}")
        except Exception as e:
            print(f"Unexpected error validating image {url}: {e}")
    
    return valid_urls

def calculate_multimodal_cost(text_usage, image_count):
    """Calculate estimated cost including images"""
    if not text_usage:
        return 0
    
    # GPT-4o pricing (as of 2025)
    prompt_tokens = text_usage.get('prompt_tokens', 0)
    completion_tokens = text_usage.get('completion_tokens', 0)
    
    text_cost = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000
    image_cost = image_count * 0.00765  # Per image cost for low detail
    
    return text_cost + image_cost

# Web search triggering functions
def extract_external_domains(url):
    """Extract domains from URL that might indicate newsworthy content"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return [domain] if domain else []
    except Exception:
        return []

def extract_product_mentions(text):
    """Extract potential product/company names from text"""
    # Common tech product patterns
    patterns = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:v\d|version|release|beta|alpha)\b',  # Version mentions
        r'\b[A-Z][a-zA-Z]*(?:AI|API|SDK|CLI|IDE|OS)\b',  # Tech acronyms
        r'\b(?:launched|released|announced)\s+([A-Z][a-zA-Z\s]+)',  # "launched ProductName"
        r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:just|now|today)\s+(?:launched|released)',  # "ProductName just launched"
    ]
    
    mentions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Handle both string matches and tuple matches from capture groups
            for match in matches:
                if isinstance(match, tuple):
                    mentions.extend([m for m in match if m])  # Add non-empty captures
                else:
                    mentions.append(match)
    
    # Filter out common false positives
    false_positives = {'the', 'and', 'for', 'with', 'this', 'that', 'have', 'been', 'will', 'would', 'could', 'should'}
    return [mention.strip() for mention in mentions if mention.lower().strip() not in false_positives]

def calculate_web_search_score(post_data, subreddit_name):
    """Calculate a score to determine if post warrants web search"""
    if not WEB_SEARCH_CONFIG['enabled']:
        return 0
    
    score = 0
    title = post_data.get('title', '').lower()
    body = post_data.get('body', '').lower()
    post_url = post_data.get('url', '')
    post_score = post_data.get('score', 0)
    
    # Subreddit targeting (high value for tech subreddits)
    if subreddit_name in WEB_SEARCH_CONFIG['target_subreddits']:
        score += 20
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"  +20 for target subreddit: {subreddit_name}")
    
    # Keyword triggers (product launches, announcements, etc.)
    title_body = title + ' ' + body
    for keyword in WEB_SEARCH_CONFIG['trigger_keywords']:
        if keyword.lower() in title_body:
            score += 15
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"  +15 for keyword: {keyword}")
            break  # Only count once per post
    
    # High engagement posts
    if post_score >= WEB_SEARCH_CONFIG['min_post_score']:
        score += 25
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"  +25 for high engagement: {post_score}")
    
    # External domain links (news sites, product pages)
    domains = extract_external_domains(post_url)
    for domain in domains:
        if domain in WEB_SEARCH_CONFIG['external_domains']:
            score += 20
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"  +20 for external domain: {domain}")
        elif domain not in ['reddit.com', 'imgur.com', 'i.redd.it']:
            score += 10
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"  +10 for other external domain: {domain}")
    
    # Product mentions in title/body
    products = extract_product_mentions(title_body)
    if products:
        score += 15
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"  +15 for product mentions: {products}")
    
    # Minimal text content (often image/link posts about new things)
    if len(body) < 100:
        score += 5
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"  +5 for minimal text content")
    
    return score

def should_use_web_search(post_data, subreddit_name):
    """Determine if a post should use web search for enhanced context"""
    if not WEB_SEARCH_CONFIG['enabled']:
        return False
    
    score = calculate_web_search_score(post_data, subreddit_name)
    threshold = 40  # Require multiple signals
    
    result = score >= threshold
    
    if WEB_SEARCH_CONFIG['test_mode']:
        print(f"Web search decision for '{post_data['title'][:50]}...': score={score}, threshold={threshold}, result={result}")
    
    return result

# Cost tracking and daily limit management
class WebSearchCostTracker:
    """Tracks daily web search usage and costs"""
    
    def __init__(self):
        self.usage_file = "web_search_usage.json"
        self.usage_data = self.load_usage_data()
    
    def load_usage_data(self):
        """Load daily usage data from file"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    # Clean old data (keep only today's data)
                    today = datetime.now().strftime('%Y-%m-%d')
                    if data.get('date') == today:
                        return data
            
            # Return fresh data for today
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'searches_count': 0,
                'total_cost': 0.0,
                'searches': []
            }
        except Exception as e:
            print(f"Error loading web search usage data: {e}")
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'searches_count': 0,
                'total_cost': 0.0,
                'searches': []
            }
    
    def save_usage_data(self):
        """Save usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            print(f"Error saving web search usage data: {e}")
    
    def can_search(self):
        """Check if we're within daily limits"""
        if not WEB_SEARCH_CONFIG['enabled']:
            return False
        
        # Check count limit
        if self.usage_data['searches_count'] >= WEB_SEARCH_CONFIG['daily_limit']:
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"Daily search limit reached: {self.usage_data['searches_count']}/{WEB_SEARCH_CONFIG['daily_limit']}")
            return False
        
        # Check cost limit
        estimated_new_cost = self.usage_data['total_cost'] + WEB_SEARCH_CONFIG['cost_per_search']
        if estimated_new_cost > WEB_SEARCH_CONFIG['cost_limit_per_day']:
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"Daily cost limit would be exceeded: ${estimated_new_cost:.4f} > ${WEB_SEARCH_CONFIG['cost_limit_per_day']:.4f}")
            return False
        
        return True
    
    def record_search(self, post_title, actual_cost=None, success=True):
        """Record a web search usage"""
        cost = actual_cost if actual_cost is not None else WEB_SEARCH_CONFIG['cost_per_search']
        
        search_record = {
            'timestamp': datetime.now().isoformat(),
            'post_title': post_title[:50] + '...' if len(post_title) > 50 else post_title,
            'cost': cost,
            'success': success
        }
        
        self.usage_data['searches_count'] += 1
        self.usage_data['total_cost'] += cost
        self.usage_data['searches'].append(search_record)
        
        self.save_usage_data()
        
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"Recorded web search: {search_record}")
    
    def get_daily_summary(self):
        """Get summary of today's web search usage"""
        return {
            'date': self.usage_data['date'],
            'searches_count': self.usage_data['searches_count'],
            'total_cost': self.usage_data['total_cost'],
            'remaining_searches': max(0, WEB_SEARCH_CONFIG['daily_limit'] - self.usage_data['searches_count']),
            'remaining_budget': max(0, WEB_SEARCH_CONFIG['cost_limit_per_day'] - self.usage_data['total_cost'])
        }

# Circuit breaker for web search reliability
class WebSearchCircuitBreaker:
    """Implements circuit breaker pattern for web search reliability"""
    
    def __init__(self):
        self.state_file = "web_search_circuit_state.json"
        self.state = self.load_state()
    
    def load_state(self):
        """Load circuit breaker state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Check if recovery timeout has passed
                    if state.get('state') == 'open':
                        last_failure = datetime.fromisoformat(state.get('last_failure', '2000-01-01'))
                        timeout_seconds = WEB_SEARCH_CONFIG['circuit_breaker_timeout']
                        if (datetime.now() - last_failure).total_seconds() > timeout_seconds:
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
    
    def save_state(self):
        """Save circuit breaker state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving circuit breaker state: {e}")
    
    def can_call(self):
        """Check if web search calls are allowed"""
        return self.state['state'] in ['closed', 'half_open']
    
    def record_success(self):
        """Record successful web search call"""
        self.state['state'] = 'closed'
        self.state['failure_count'] = 0
        self.state['last_failure'] = None
        self.save_state()
    
    def record_failure(self):
        """Record failed web search call"""
        self.state['failure_count'] += 1
        self.state['last_failure'] = datetime.now().isoformat()
        
        threshold = WEB_SEARCH_CONFIG['circuit_breaker_threshold']
        if self.state['failure_count'] >= threshold:
            self.state['state'] = 'open'
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"Circuit breaker opened after {self.state['failure_count']} failures")
        
        self.save_state()

# Main web search manager
class WebSearchManager:
    """Main manager for web search functionality with safety mechanisms"""
    
    def __init__(self):
        self.cost_tracker = WebSearchCostTracker()
        self.circuit_breaker = WebSearchCircuitBreaker()
    
    def can_perform_search(self, post_data, subreddit_name):
        """Check if we can perform a web search for this post"""
        # Check configuration
        if not WEB_SEARCH_CONFIG['enabled']:
            return False, "Web search disabled in configuration"
        
        # Check if post warrants web search
        if not should_use_web_search(post_data, subreddit_name):
            return False, "Post doesn't meet web search criteria"
        
        # Check daily limits
        if not self.cost_tracker.can_search():
            return False, "Daily search limits exceeded"
        
        # Check circuit breaker
        if not self.circuit_breaker.can_call():
            return False, "Circuit breaker is open due to previous failures"
        
        return True, "All checks passed"
    
    def get_status_summary(self):
        """Get current status of web search system"""
        cost_summary = self.cost_tracker.get_daily_summary()
        circuit_state = self.circuit_breaker.state['state']
        
        return {
            'enabled': WEB_SEARCH_CONFIG['enabled'],
            'daily_usage': cost_summary,
            'circuit_breaker_state': circuit_state,
            'last_failure': self.circuit_breaker.state.get('last_failure'),
            'failure_count': self.circuit_breaker.state.get('failure_count', 0)
        }

# Global web search manager instance
web_search_manager = WebSearchManager()

def fetch_reddit_posts(subreddit_names=['windsurf', 'vibecoding'], limit=10, comment_limit=3):
    """Fetch today's posts from multiple subreddits and their comments
    
    Only includes posts with at least 10 upvotes.
    """
    # Connect to Reddit API
    reddit = connect_to_reddit()
    
    # Get timezone from environment or default to Europe/Berlin (CEST)
    user_timezone = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    print(f"Using timezone: {user_timezone}")
    print("Filtering for posts with at least 10 upvotes")
        
    all_subreddit_posts = {}
    
    for subreddit_name in subreddit_names:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            posts = []
            today_posts = []
            
            # We need to fetch more posts initially since we'll be filtering
            for post in subreddit.hot(limit=limit):
                # Check if post is from today in user's timezone and has at least 10 upvotes
                if is_today(post.created_utc, user_timezone) and post.score >= 10:
                    post_data = {
                        'title': post.title,
                        'author': post.author.name if post.author else '[deleted]',
                        'score': post.score,
                        'url': f'https://www.reddit.com{post.permalink}',
                        'body': post.selftext,
                        'created_time': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'comments': [],
                        'image_urls': detect_images_from_url(
                            post.url, post.selftext
                        ) if should_analyze_images(post.score, post.selftext, subreddit_name, post.url) else []
                    }
                    
                    # Debug logging for image detection
                    if IMAGE_ANALYSIS_CONFIG['test_mode'] and post_data['image_urls']:
                        print(f"DEBUG: Post '{post.title[:30]}...' has {len(post_data['image_urls'])} images: {post_data['image_urls']}")
                    
                    post.comment_sort = 'top'
                    post.comments.replace_more(limit=0)
                    
                    for comment in post.comments[:comment_limit]:
                        comment_data = {
                            'author': comment.author.name if comment.author else '[deleted]',
                            'body': comment.body,
                            'score': comment.score
                        }
                        post_data['comments'].append(comment_data)
                    
                    today_posts.append(post_data)
                
            # Sort posts by score (upvotes) in descending order
            today_posts.sort(key=lambda x: x['score'], reverse=True)
            
            all_subreddit_posts[subreddit_name] = today_posts[:3]  # Limit to top 3 by score
            print(f"Found {len(today_posts)} posts from today in r/{subreddit_name}, using top {len(all_subreddit_posts[subreddit_name])} by upvotes")
            
            # Debug log to show selected posts and scores
            for i, post in enumerate(all_subreddit_posts[subreddit_name]):
                print(f"  {i+1}. {post['title'][:40]}... ({post['score']} upvotes)")
            print("")
            
        except Exception as e:
            print(f"Error fetching posts from r/{subreddit_name}: {e}")
            all_subreddit_posts[subreddit_name] = []
    
    return all_subreddit_posts

def count_tokens(text):
    """Count the approximate number of tokens in a text string"""
    # Simple approximation: 1 token ≈ 4 characters for English text
    # This is a rough estimate, actual tokenization varies by model and text content
    return len(text) // 4


def truncate_to_tokens(text, max_tokens):
    """Truncate text to approximately the specified number of tokens"""
    # If text is already within limit, return as is
    if count_tokens(text) <= max_tokens:
        return text
    
    # Approximate truncation (rough estimate)
    # Leave some room for truncation indicator
    char_limit = max_tokens * 4 - 10
    return text[:char_limit] + "... [truncated]"


def create_multimodal_system_prompt(subreddit_name, has_images):
    """Create system prompt optimized for multimodal content"""
    base_prompt = f"You are summarizing a Reddit post from r/{subreddit_name}. "
    
    if has_images:
        base_prompt += """
The post includes both text and images. When analyzing images:
- For screenshots: Describe key UI elements, code, or technical details shown
- For diagrams: Explain the concepts or architecture illustrated  
- For product demos: Describe what's being showcased
- For code/terminal screenshots: Mention key technical details visible
- Integrate visual and text information into a cohesive summary

IMPORTANT: Keep image descriptions concise and relevant to the post's main point.
"""
    
    base_prompt += """
IMPORTANT CURRENT KNOWLEDGE (2025):
- Claude Code: Anthropic's official CLI tool for Claude, enables terminal-based AI coding assistance with file editing and command execution
- Vibe Coding: A development approach centered on using AI-driven workflows and tools for coding efficiency
- MCP (Model Context Protocol): A protocol that allows AI models to interface with external tools and systems
- o3: An OpenAI large language model similar to GPT-4o but with specific tooling optimizations
- RAG: Retrieval Augmented Generation, a technique for enhancing AI responses with retrieved context
- Claude 4: Anthropic's flagship large language model released in 2024-2025
- AI Agents: Autonomous systems that can perform tasks, make decisions, and interact with APIs/tools
- SideProject: Term for personal projects developers build in their spare time, often to solve problems or learn new technologies
- Linear: A project management and issue tracking tool popular with development teams
- Anthropic: AI safety company that created Claude, focused on developing helpful, harmless, and honest AI systems

Use casual, conversational language. Keep summaries proportional to content complexity.
DO NOT use emojis. DO NOT address the reader directly. Give a concise, brief summary of what the post actually says.
"""
    
    return base_prompt

def create_web_search_system_prompt(subreddit_name, has_images):
    """Create system prompt for web search enabled summarization"""
    base_prompt = create_multimodal_system_prompt(subreddit_name, has_images)
    
    # Add web search specific instructions
    web_search_instructions = """

WEB SEARCH CAPABILITIES:
You have access to web search to find current information. Use it when:
- The post mentions specific products, services, or companies that might have recent updates
- There are claims about pricing, availability, or features that should be verified
- New announcements, launches, or releases are discussed
- You need current context to provide accurate information

When using web search results in your summary:
- Briefly mention current information found (e.g., "Current pricing shows..." or "Recent updates indicate...")
- Only include information that adds valuable context to the post
- Keep web-sourced information concise and relevant
"""
    
    return base_prompt + web_search_instructions

def create_search_guidance_context(post_data):
    """Generate specific search guidance for the model"""
    title = post_data.get('title', '')
    body = post_data.get('body', '')
    
    # Extract entities that might need current information
    products = extract_product_mentions(title + ' ' + body)
    domains = extract_external_domains(post_data.get('url', ''))
    
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

def summarize_post_content_with_web_search(post_data, subreddit_name):
    """Enhanced post summarization using OpenAI Responses API with web search"""
    print(f"Attempting web search summarization: {post_data['title'][:30]}...")
    
    if not openai_client:
        print("OpenAI API key not available. Skipping post summarization.")
        return None
    
    # Check if we can and should perform web search
    can_search, reason = web_search_manager.can_perform_search(post_data, subreddit_name)
    if not can_search:
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"Cannot perform web search: {reason}")
        return None
    
    # Check if we have images to process
    image_urls = post_data.get('image_urls', [])
    has_images = len(image_urls) > 0
    
    # Validate images if we have them
    valid_images = []
    if has_images:
        valid_images = validate_image_urls(image_urls)
        has_images = len(valid_images) > 0
    
    try:
        # Prepare content for API call
        content_array = []
        
        # Add text content
        title = post_data['title']
        body = truncate_to_tokens(post_data['body'], 700)
        search_guidance = create_search_guidance_context(post_data)
        
        text_content = f"Title: {title}\n\nContent: {body}"
        if search_guidance:
            text_content += f"\n\nSearch guidance: {search_guidance}"
        
        content_array.append({"type": "text", "text": text_content})
        
        # Add images if we have them
        if has_images:
            max_images = min(len(valid_images), IMAGE_ANALYSIS_CONFIG['max_images_per_post'])
            for img_url in valid_images[:max_images]:
                content_array.append({
                    "type": "image_url",
                    "image_url": {"url": img_url, "detail": "low"}
                })
        
        # Create system message
        system_message = {
            "role": "system",
            "content": create_web_search_system_prompt(subreddit_name, has_images)
        }
        
        # Create message array
        messages = [
            system_message,
            {"role": "user", "content": content_array}
        ]
        
        # Track the search attempt
        web_search_manager.cost_tracker.record_search(post_data['title'], success=False)  # Will update on success
        
        # API call with web search tool using Responses API
        response = openai_client.responses.create(
            model="gpt-4o",
            messages=messages,
            tools=[{"type": "web_search"}],
            max_tokens=250,
            temperature=0.5
        )
        
        # Record successful search
        web_search_manager.circuit_breaker.record_success()
        
        # Extract summary and usage
        summary = response.choices[0].message.content.strip()
        
        # Check if web search was actually used
        web_search_used = any(
            hasattr(choice.message, 'tool_calls') and choice.message.tool_calls 
            for choice in response.choices
        ) if hasattr(response, 'choices') else False
        
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "images_processed": len(valid_images[:max_images]) if has_images else 0,
            "web_search_used": web_search_used,
            "web_search_cost": WEB_SEARCH_CONFIG['cost_per_search'] if web_search_used else 0,
            "estimated_cost": calculate_multimodal_cost(
                response.usage.__dict__, 
                len(valid_images[:max_images]) if has_images else 0
            ) + (WEB_SEARCH_CONFIG['cost_per_search'] if web_search_used else 0)
        }
        
        # Update cost tracking with actual usage
        if web_search_used:
            web_search_manager.cost_tracker.record_search(
                post_data['title'], 
                actual_cost=usage['web_search_cost'],
                success=True
            )
        
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"Web search summary completed: web_search_used={web_search_used}, cost=${usage['estimated_cost']:.4f}")
        
        return {"summary": summary, "usage": usage}
        
    except Exception as e:
        print(f"ERROR in web search summarization: {e}")
        
        # Record failure for circuit breaker
        web_search_manager.circuit_breaker.record_failure()
        
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"Web search failed: {e}")
            print(f"Traceback: {traceback.format_exc()}")
        
        return None

def summarize_post_content_multimodal(post_data, subreddit_name):
    """Enhanced post summarization with optional image analysis"""
    print(f"Attempting to summarize post: {post_data['title'][:30]}...")
    
    if not openai_client:
        print("OpenAI API key not available. Skipping post summarization.")
        return None
    
    # Check if we have images to process
    image_urls = post_data.get('image_urls', [])
    has_images = len(image_urls) > 0
    
    # Validate images if we have them
    valid_images = []
    if has_images:
        print(f"Found {len(image_urls)} potential images, validating...")
        valid_images = validate_image_urls(image_urls)
        print(f"Validated {len(valid_images)} accessible images")
        has_images = len(valid_images) > 0
    
    try:
        # Prepare content for API call
        if has_images:
            # Multimodal content array
            content_array = []
            
            # Add text content
            title = post_data['title']
            body = truncate_to_tokens(post_data['body'], 700)
            text_content = f"Title: {title}\n\nContent: {body}"
            content_array.append({"type": "text", "text": text_content})
            
            # Add images (limit to config max)
            max_images = IMAGE_ANALYSIS_CONFIG['max_images_per_post']
            for img_url in valid_images[:max_images]:
                content_array.append({
                    "type": "image_url",
                    "image_url": {"url": img_url, "detail": "low"}  # Use low detail for cost efficiency
                })
            
            print(f"Processing {len(valid_images[:max_images])} images with text content")
        else:
            # Text-only content
            title = post_data['title']
            body = truncate_to_tokens(post_data['body'], 700)
            content_array = f"Title: {title}\n\nContent: {body}"
        
        # Create system message
        system_message = {
            "role": "system",
            "content": create_multimodal_system_prompt(subreddit_name, has_images)
        }
        
        # Create message array
        messages = [
            system_message,
            {"role": "user", "content": content_array}
        ]
        
        # API call with potential image support
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=200 if has_images else 150,  # More tokens for image descriptions
            temperature=0.5
        )
        
        summary = response.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "images_processed": len(valid_images[:max_images]) if has_images else 0,
            "estimated_cost": calculate_multimodal_cost(response.usage.__dict__, len(valid_images[:max_images]) if has_images else 0)
        }
        
        if has_images:
            print(f"Multimodal summary generated with {len(valid_images[:max_images])} images (cost: ${usage['estimated_cost']:.4f})")
        else:
            print("Text-only summary generated")
        
        return {"summary": summary, "usage": usage}
        
    except Exception as e:
        print(f"ERROR generating multimodal summary: {e}")
        # Fallback to text-only if multimodal fails
        if has_images:
            print("Falling back to text-only summary...")
            post_data_copy = post_data.copy()
            post_data_copy['image_urls'] = []  # Remove images for fallback
            return summarize_post_content_text_only(post_data_copy, subreddit_name)
        return None

def summarize_post_content_text_only(post_data, subreddit_name):
    """Original text-only summarization (fallback)"""
    print(f"Attempting to summarize post (text-only): {post_data['title'][:30]}...")
    if not openai_client:
        print("OpenAI API key not available. Skipping post summarization.")
        return None
    
    try:
        # Prepare and truncate the content to summarize (max 750 tokens)
        title = post_data['title']
        body = truncate_to_tokens(post_data['body'], 700)  # Leave room for title
        post_content = f"Title: {title}\n\nContent: {body}"
        print(f"Post content prepared, length: {len(post_content)} chars")
        
        # Create system message specifically for post content
        system_message = {
            "role": "system",
            "content": f"You are summarizing a Reddit post from r/{subreddit_name}. "
                       "IMPORTANT CURRENT KNOWLEDGE (2025): "
                       "- Claude Code: Anthropic's official CLI tool for Claude, enables terminal-based AI coding assistance with file editing and command execution. "
                       "- Vibe Coding: A development approach centered on using AI-driven workflows and tools for coding efficiency. "
                       "- MCP (Model Context Protocol): A protocol that allows AI models to interface with external tools and systems. "
                       "- o3: An OpenAI large language model similar to GPT-4o but with specific tooling optimizations. "
                       "- RAG: Retrieval Augmented Generation, a technique for enhancing AI responses with retrieved context. "
                       "- Claude 4: Anthropic's flagship large language model released in 2024-2025. "
                       "- AI Agents: Autonomous systems that can perform tasks, make decisions, and interact with APIs/tools. "
                       "- SideProject: Term for personal projects developers build in their spare time, often to solve problems or learn new technologies. "
                       "- Linear: A project management and issue tracking tool popular with development teams. "
                       "- Anthropic: AI safety company that created Claude, focused on developing helpful, harmless, and honest AI systems. "
                       "IMPORTANT: Give a concise, brief summary of ONLY what the post actually says. DO NOT respond to the post. "
                       "DO NOT add your own commentary, questions, or direct address to the reader. "
                       "DO NOT use emojis or emoticons in your summary. "
                       "Use very casual, human speech-like language in your summaries. Write like people actually talk. "
                       "Use direct references (like 'they' instead of 'the author suggests') and informal, conversational language. "
                       "Keep summary length proportional to actual content - shorter summaries for simpler posts (2-3 sentences max), "
                       "longer only if there's substantial technical content to summarize."
        }
        
        # Create message array with system message and user content
        messages = [
            system_message,
            {"role": "user", "content": post_content}
        ]
        
        # Use modern OpenAI client API (v1.0+)
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=150,
                temperature=0.5
            )
            summary = response.choices[0].message.content.strip()
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            # Return as a dictionary that can be accessed with .get() method
            return {"summary": summary, "usage": usage}
        except Exception as api_error:
            print(f"Error during OpenAI API call: {api_error}")
            raise
            
    except Exception as e:
        print(f"ERROR generating post summary with OpenAI API: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def summarize_post_content(post_data, subreddit_name):
    """Main entry point for post summarization with fallback chain"""
    
    # Try web search enhanced summarization first (if enabled and applicable)
    if WEB_SEARCH_CONFIG['enabled']:
        try:
            result = summarize_post_content_with_web_search(post_data, subreddit_name)
            if result is not None:
                if WEB_SEARCH_CONFIG['test_mode']:
                    print("✓ Used web search enhanced summarization")
                return result
        except Exception as e:
            if WEB_SEARCH_CONFIG['test_mode']:
                print(f"✗ Web search summarization failed: {e}")
    
    # Fallback to multimodal summarization
    try:
        result = summarize_post_content_multimodal(post_data, subreddit_name)
        if result is not None:
            if WEB_SEARCH_CONFIG['test_mode']:
                print("✓ Used multimodal summarization (fallback)")
            return result
    except Exception as e:
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"✗ Multimodal summarization failed: {e}")
    
    # Final fallback to text-only summarization
    try:
        result = summarize_post_content_text_only(post_data, subreddit_name)
        if result is not None:
            if WEB_SEARCH_CONFIG['test_mode']:
                print("✓ Used text-only summarization (final fallback)")
            return result
    except Exception as e:
        if WEB_SEARCH_CONFIG['test_mode']:
            print(f"✗ Text-only summarization failed: {e}")
    
    # All methods failed
    print(f"ERROR: All summarization methods failed for post: {post_data['title'][:50]}...")
    return None


def summarize_comments(post_data, subreddit_name):
    """Generate a summary of the post comments using OpenAI API"""
    if not openai_client:
        print("WARNING: OpenAI client not available, skipping comment summary generation")
        return None
        
    # Check if there are comments to summarize
    if not post_data['comments']:
        return {"summary": "No comments to summarize.", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    
    try:
        # Prepare the comments to summarize with truncation
        comments_content = f"Post Title: {post_data['title']}\n\nComments:\n"
        remaining_tokens = 250  # Max tokens for each comment
        tokens_per_comment = remaining_tokens // len(post_data['comments']) if len(post_data['comments']) > 0 else remaining_tokens
        
        for i, comment in enumerate(post_data['comments'], 1):
            truncated_comment = truncate_to_tokens(comment['body'], tokens_per_comment)
            comments_content += f"{i}. By u/{comment['author']}: {truncated_comment}\n"
        
        # Create system message specifically for comments
        system_message = {
            "role": "system",
            "content": f"You are summarizing comments on a Reddit post from r/{subreddit_name}. "
                       "IMPORTANT CURRENT KNOWLEDGE (2025): "
                       "- Cursor: An AI-powered code editor with GPT-4o integration and code generation capabilities. "
                       "- Windsurf: A competing AI IDE, owned by OpenAI as of 2024, with advanced coding assistance and code editing features. "
                       "- Vibe Coding: A development approach centered on using AI-driven workflows and tools for coding efficiency. "
                       "- MCP (Model Context Protocol): A protocol that allows AI models to interface with external tools and systems, defining how models interact with API endpoints. "
                       "- o3: An OpenAI large language model similar to GPT-4o but with specific tooling optimizations. "
                       "- RAG: Retrieval Augmented Generation, a technique for enhancing AI responses with retrieved context. "
                       "- Claude 4: Anthropic's flagship large language model released in 2024-2025. "
                       "IMPORTANT: Give a concise, factual summary of the comments. DO NOT write as if you're having a conversation. "
                       "DO NOT add your own commentary, questions, or address the reader directly. "
                       "DO NOT use emojis or emoticons in your summary. "
                       "DO NOT include usernames (u/username) when attributing key points. Instead, use phrases like 'one user said', 'another person mentioned', etc. "
                       "Use very casual, human speech-like language. Write like people actually talk. "
                       "Use direct references and informal, conversational language. "
                       "Keep summary length proportional to actual content - brief for simple discussions (2-3 sentences), "
                       "longer only if there are multiple detailed technical viewpoints to summarize."
        }
        
        messages = [
            system_message,
            {"role": "user", "content": comments_content}
        ]
        
        # Use modern OpenAI client API (v1.0+)
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=100,
                temperature=0.5
            )
            # Access via object attributes
            summary = response.choices[0].message.content.strip()
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            print("Comments summary generated successfully")
            return {"summary": summary, "usage": usage}
        except Exception as api_error:
            print(f"Error generating comments summary with OpenAI API: {api_error}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None
    except Exception as e:
        print(f"Error generating comments summary with OpenAI API: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def summarize_post(post_data, subreddit_name):
    """Generate separate summaries for the post content and its comments"""
    # Create a result dictionary
    result = {}
    
    # Generate post content summary
    post_summary_data = summarize_post_content(post_data, subreddit_name)
    if post_summary_data:
        result['post_summary'] = post_summary_data.get('summary')
        result['post_usage'] = post_summary_data.get('usage')
    else:
        result['post_summary'] = None
        result['post_usage'] = None
    
    # Generate comments summary
    comments_summary_data = summarize_comments(post_data, subreddit_name)
    if comments_summary_data:
        result['comments_summary'] = comments_summary_data.get('summary')
        result['comments_usage'] = comments_summary_data.get('usage')
    else:
        result['comments_summary'] = None
        result['comments_usage'] = None
    
    return result

def format_email_content(all_posts, all_subreddit_posts=None):
    """Format the posts from multiple subreddits into HTML email content"""
    # Get timezone from environment or default to Europe/Berlin (CEST)
    timezone_str = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    user_timezone = pytz.timezone(timezone_str)
    now = datetime.now(user_timezone)
    formatted_date = now.strftime("%A, %B %d, %Y")
    
    # Get unique subreddits from the posts
    subreddits = sorted(list(set(post['subreddit'] for post in all_posts)))
    
    # Calculate total token usage including images and web searches
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_images_processed = 0
    total_estimated_cost = 0
    total_web_searches = 0
    
    for post in all_posts:
            summaries = post.get('summaries', {})
            if summaries:
                # Add post summary tokens
                post_usage = summaries.get('post_usage', {})
                if post_usage:
                    total_prompt_tokens += post_usage.get('prompt_tokens', 0)
                    total_completion_tokens += post_usage.get('completion_tokens', 0)
                    total_tokens += post_usage.get('total_tokens', 0)
                    total_images_processed += post_usage.get('images_processed', 0)
                    total_estimated_cost += post_usage.get('estimated_cost', 0)
                    if post_usage.get('web_search_used', False):
                        total_web_searches += 1
                
                # Add comments summary tokens
                comments_usage = summaries.get('comments_usage', {})
                if comments_usage:
                    total_prompt_tokens += comments_usage.get('prompt_tokens', 0)
                    total_completion_tokens += comments_usage.get('completion_tokens', 0)
                    total_tokens += comments_usage.get('total_tokens', 0)
    
    # Start with basic HTML header
    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{
                --primary-color: #FF4500;      /* Reddit orange */
                --secondary-color: #0079D3;     /* Reddit blue */
                --text-color: #1A1A1B;          /* Near black for text */
                --light-text: #7C7C7C;          /* Lighter text for meta info */
                --background: #F8F9FA;          /* Light background */
                --card-background: #FFFFFF;     /* Card background */
                --divider: #EDEFF1;              /* Divider color */
                --highlight: #f0f7ff;            /* Light highlight color */
                --shadow: rgba(0, 0, 0, 0.1);    /* Shadow color */
                --radius: 10px;                  /* Border radius */
            }}
            
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
                margin: 0; 
                padding: 12px; 
                line-height: 1.4; 
                background-color: var(--background);
                color: var(--text-color);
            }}
            
            h1 {{ 
                color: var(--primary-color); 
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 5px;
                margin-top: 0;
            }}
            
            h2 {{ 
                color: var(--secondary-color); 
                font-size: 20px;
                font-weight: 500;
                padding: 8px 15px;
                margin: 20px 0 12px 0; 
                border-radius: var(--radius);
                background: linear-gradient(90deg, var(--secondary-color), #2A95E9);
                color: white;
                box-shadow: 0 1px 5px var(--shadow);
            }}
            
            h3 {{ 
                color: var(--secondary-color); 
                font-size: 16px;
                font-weight: 500;
                margin: 10px 0 3px 0;
            }}

            a {{ 
                color: var(--secondary-color); 
                text-decoration: none; 
            }}

            a:hover {{ 
                text-decoration: underline; 
            }}

            p {{ 
                margin: 6px 0; 
            }}

            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}

            .header {{
                text-align: center;
                padding: 12px 0;
                border-bottom: 1px solid var(--divider);
                margin-bottom: 12px;
            }}

            .date {{
                color: var(--light-text);
                font-size: 14px;
                margin-bottom: 10px;
            }}

            .token-usage {{ 
                background-color: var(--highlight); 
                padding: 10px;
                border-radius: var(--radius);
                margin-bottom: 15px; 
                box-shadow: 0 1px 3px var(--shadow);
                display: flex;
                flex-wrap: wrap;
                justify-content: space-around;
                align-items: center;
            }}

            .token-usage h3 {{
                width: 100%;
                text-align: center;
                margin: 0 0 8px 0;
                font-size: 15px;
            }}

            .token-item {{
                display: inline-block;
                padding: 5px 10px;
                border-radius: 15px;
                background: white;
                margin: 3px;
                font-size: 13px;
                box-shadow: 0 1px 2px var(--shadow);
            }}

            .post {{ 
                margin-bottom: 18px; 
                padding: 12px;
                background-color: var(--card-background);
                border-radius: var(--radius);
                box-shadow: 0 1px 6px var(--shadow);
            }}

            .post-title {{ 
                font-size: 18px; 
                font-weight: bold; 
                color: var(--text-color); 
                line-height: 1.3;
                margin-bottom: 3px;
            }}

            .post-title a {{
                color: inherit;
            }}

            .post-meta {{ 
                color: var(--light-text); 
                font-size: 13px; 
                margin: 5px 0;
                display: flex;
                align-items: center;
                flex-wrap: wrap;
            }}

            .meta-item {{
                margin-right: 10px;
                display: flex;
                align-items: center;
            }}

            .upvotes {{
                color: var(--primary-color);
                font-weight: 600;
                background-color: rgba(255, 69, 0, 0.1);
                padding: 2px 8px;
                border-radius: 12px;
                margin-right: 8px;
                font-size: 13px;
            }}

            .comments-count {{
                color: var(--secondary-color);
                background-color: rgba(0, 121, 211, 0.1);
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 13px;
            }}

            .summary {{ 
                background-color: #FFFFFF; 
                padding: 10px;
                border-radius: var(--radius); 
                margin: 10px 0;
                box-shadow: 0 1px 2px var(--shadow);
                border-left: 3px solid var(--primary-color);
            }}

            .comments-summary {{ 
                border-left: 3px solid var(--secondary-color); 
                padding: 10px;
                margin: 10px 0; 
                background-color: #FFFFFF;
                border-radius: var(--radius);
                box-shadow: 0 1px 2px var(--shadow);
            }}

            .comment {{ 
                margin: 10px 0; 
                padding: 8px 10px;
                border-bottom: 1px solid var(--divider);
                background-color: #FFFFFF;
                border-radius: var(--radius);
            }}

            .comment-meta {{ 
                color: var(--light-text); 
                font-size: 14px; 
                display: flex;
                align-items: center;
                margin-bottom: 5px;
            }}

            .no-posts {{ 
                color: var(--light-text); 
                font-style: italic; 
                text-align: center;
                padding: 30px;
            }}

            .indicator {{
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 8px;
            }}

            .post-indicator {{
                background-color: var(--primary-color);
            }}

            .comment-indicator {{
                background-color: var(--secondary-color);
            }}

            @media only screen and (max-width: 600px) {{
                body {{ 
                    padding: 10px; 
                }}

                .post {{ 
                    padding: 15px; 
                }}

                h1 {{
                    font-size: 24px;
                }}

                h2 {{
                    font-size: 20px;
                    padding: 10px 15px;
                }}

            }}
        </style>

    </head>

    <body>

        <div class="container">

            <div class="header">

                <h1>Reddit Digest: {', '.join([f'r/{s}' for s in subreddits])}</h1>

                <div class="date">{formatted_date}</div>

            </div>

            <div class="token-usage">

                <h3>OpenAI API Usage</h3>

                <div class="token-item">📤 Prompt: {total_prompt_tokens}</div>

                <div class="token-item">📥 Completion: {total_completion_tokens}</div>

                <div class="token-item">📊 Total: {total_tokens}</div>

                <div class="token-item">🖼️ Images: {total_images_processed}</div>

                <div class="token-item">🌐 Web Searches: {total_web_searches}</div>

                <div class="token-item">💰 Est. Cost: ${total_estimated_cost:.4f}</div>

            </div>
    """
    
    # Add all posts sorted by upvotes (highest first)
    html_content += "<h2>Top Posts (Sorted by Upvotes)</h2>"
    
    if not all_posts:
        html_content += "<p class='no-posts'>No posts found today.</p>"
    
    for i, post in enumerate(all_posts, 1):
            # Get summaries if available
            summaries = post.get('summaries', {})
            post_summary = None
            comments_summary = None
            web_search_used = False
            
            if summaries:
                post_summary = summaries.get('post_summary')
                comments_summary = summaries.get('comments_summary')
                post_usage = summaries.get('post_usage', {})
                web_search_used = post_usage.get('web_search_used', False)
            
            web_search_indicator = ' <span class="web-search-badge" title="Enhanced with web search">🌐</span>' if web_search_used else ''
            
            html_content += f"""
            <div class="post">
                <div class="post-title">
                    <span class="upvotes">{post['score']}</span>
                    <a href="{post['url']}" target="_blank">{post['title']}</a>{web_search_indicator}
                </div>
                <div class="post-meta">
                    <div class="meta-item">r/{post['subreddit']}</div>
                    <div class="meta-item">Posted by u/{post['author']}</div>
                    <div class="meta-item comments-count">{len(post['comments'])} comments</div>
                </div>
            """
            
            # Add post summary if available, otherwise show the raw post text
            if post_summary:
                html_content += f"""
                <div class="summary">
                    <h3><span class="indicator post-indicator"></span>Post Summary</h3>
                    <p>{post_summary}</p>
                </div>
                """
            else:
                html_content += f"""
                <div class="post-content">
                    {post['body'][:500]}{'...' if len(post['body']) > 500 else ''}
                </div>
                """
                
            # Add comments summary if available, otherwise show raw comments
            if comments_summary:
                html_content += f"""
                <div class="comments-summary">
                    <h3><span class="indicator comment-indicator"></span>Comments Summary</h3>
                    <p>{comments_summary}</p>
                </div>
                """
            elif post['comments']:
                html_content += "<h3><span class='indicator comment-indicator'></span>Top Comments</h3>"
                # Show up to 3 comments
                for j, comment in enumerate(post['comments'][:3], 1):
                    html_content += f"""
                    <div class="comment">
                        <div class="comment-meta">
                            <div class="meta-item">u/{comment['author']}</div>
                            <div class="meta-item">{comment['score']} points</div>
                        </div>
                        <p>{comment['body'][:200]}{'...' if len(comment['body']) > 200 else ''}</p>
                    </div>
                    """
            
            html_content += "</div>"  # Close post div
    
    # Close HTML
    html_content += """
    </body>
    </html>
    """
    
    return html_content

def create_plain_text_content(all_posts, all_subreddit_posts=None):
    """Create a plain text version of the email content"""
    # Get timezone from environment or default to Europe/Berlin (CEST)
    timezone_str = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    user_timezone = pytz.timezone(timezone_str)
    now = datetime.now(user_timezone)
    date_str = now.strftime("%A, %B %d, %Y")
    
    # Get unique subreddits from all posts
    subreddits = sorted(list(set(post['subreddit'] for post in all_posts)))
    
    # Calculate total token usage including images and web searches
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_images_processed = 0
    total_estimated_cost = 0
    total_web_searches = 0
    
    for post in all_posts:
            summaries = post.get('summaries', {})
            if summaries:
                # Add post summary tokens
                post_usage = summaries.get('post_usage', {})
                if post_usage:
                    total_prompt_tokens += post_usage.get('prompt_tokens', 0)
                    total_completion_tokens += post_usage.get('completion_tokens', 0)
                    total_tokens += post_usage.get('total_tokens', 0)
                    total_images_processed += post_usage.get('images_processed', 0)
                    total_estimated_cost += post_usage.get('estimated_cost', 0)
                    if post_usage.get('web_search_used', False):
                        total_web_searches += 1
                
                # Add comments summary tokens
                comments_usage = summaries.get('comments_usage', {})
                if comments_usage:
                    total_prompt_tokens += comments_usage.get('prompt_tokens', 0)
                    total_completion_tokens += comments_usage.get('completion_tokens', 0)
                    total_tokens += comments_usage.get('total_tokens', 0)
    
    # Start with header
    text_content = f"REDDIT DIGEST: {', '.join([f'r/{s}' for s in subreddits])}\n"
    text_content += f"Top posts from {date_str}\n\n"
    
    # Add token usage information
    text_content += "OPENAI API USAGE:\n"
    text_content += f"Prompt tokens: {total_prompt_tokens}\n"
    text_content += f"Completion tokens: {total_completion_tokens}\n"
    text_content += f"Total tokens: {total_tokens}\n"
    text_content += f"Images processed: {total_images_processed}\n"
    text_content += f"Web searches: {total_web_searches}\n"
    text_content += f"Estimated cost: ${total_estimated_cost:.4f}\n"
    text_content += "=" * 50 + "\n\n"
    
    # Check if we have any posts
    if not all_posts:
        text_content += "No posts found today\n\n"
    else:
        text_content += "TOP POSTS ACROSS ALL SUBREDDITS (SORTED BY UPVOTES)\n"
        text_content += "-" * 50 + "\n\n"
        
        # For each post, sorted by upvotes
        for i, post in enumerate(all_posts, 1):
            # Get summaries
            summaries = post.get('summaries', {})
            post_summary = None
            comments_summary = None
            
            if summaries:
                post_summary = summaries.get('post_summary')
                comments_summary = summaries.get('comments_summary')
                
            text_content += f"{i}. {post['title']}\n"
            text_content += f"   r/{post['subreddit']} | Posted by u/{post['author']} | {post['score']} points | {len(post['comments'])} comments\n"
            text_content += f"   {post['url']}\n\n"
            
            # Add post summary
            if post_summary:
                text_content += "POST SUMMARY:\n"
                text_content += "-" * 15 + "\n"
                text_content += f"{post_summary}\n\n"
            else:
                text_content += "POST CONTENT:\n"
                text_content += "-" * 15 + "\n"
                # Truncate post content if needed
                content = post['body'][:500] + ('...' if len(post['body']) > 500 else '')
                text_content += f"{content}\n\n"
            
            # Add comments summary
            if comments_summary:
                text_content += "COMMENTS SUMMARY:\n"
                text_content += "-" * 15 + "\n"
                text_content += f"{comments_summary}\n\n"
            elif post['comments']:
                text_content += "TOP COMMENTS:\n"
                text_content += "-" * 15 + "\n"
                # Show up to 3 comments
                for j, comment in enumerate(post['comments'][:3], 1):
                    # Truncate comment if needed
                    comment_text = comment['body'][:200] + ('...' if len(comment['body']) > 200 else '')
                    text_content += f"{j}. u/{comment['author']} ({comment['score']} points): {comment_text}\n\n"
            
            text_content += "=" * 50 + "\n\n"
    
    return text_content

def send_email(subject, html_content, recipient_email=None, all_subreddit_posts=None):
    """Send an email with the formatted content using SMTP (Gmail)"""
    sender_email = os.getenv('EMAIL_SENDER')
    recipient_email = recipient_email or os.getenv('EMAIL_RECIPIENT')
    password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    
    # Print debug info (without exposing full password)
    print(f"SMTP Email configuration:")
    print(f"- Sender: {sender_email}")
    print(f"- Recipient: {recipient_email}")
    print(f"- Password exists: {bool(password)}")
    print(f"- Password length: {len(password) if password else 0}")
    print(f"- SMTP Server: {smtp_server}")
    print(f"- SMTP Port: {smtp_port}")
    
    if not all([sender_email, recipient_email, password]):
        print("Error: Missing email configuration. Check environment variables.")
        return False
    
    # Create a more compatible email structure
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    message["MIME-Version"] = "1.0"
    
    # Create plain text version
    if all_subreddit_posts:
        # Extract flattened list from the dictionary structure
        all_flattened_posts = []
        for posts in all_subreddit_posts.values():
            all_flattened_posts.extend(posts)
        # Sort by score in descending order
        all_flattened_posts.sort(key=lambda x: x['score'], reverse=True)
        
        plain_text = create_plain_text_content(all_flattened_posts, all_subreddit_posts)
    else:
        plain_text = "This is the Reddit digest from multiple subreddits - please view in HTML format for better experience."
    
    # Create MIME parts
    # The order matters for some email clients
    html_part = MIMEText(html_content, "html")
    text_part = MIMEText(plain_text, "plain")
    
    # Create the multipart/alternative part
    alternative = MIMEMultipart("alternative")
    alternative.attach(text_part)
    alternative.attach(html_part)
    
    # Attach the alternative part to the message
    message.attach(alternative)
    
    try:
        print("Attempting to connect to SMTP server...")
        # First try with TLS
        try:
            print("Trying STARTTLS method...")
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                print("Login to SMTP server...")
                server.login(sender_email, password.strip())  # Strip any spaces from password
                print("Sending email...")
                server.sendmail(sender_email, recipient_email, message.as_string())
                print(f"Email sent successfully to {recipient_email}")
                return True
        except Exception as tls_error:
            print(f"TLS method failed: {tls_error}")
            
            # If TLS fails, try SSL
            try:
                print("Trying SSL method...")
                with smtplib.SMTP_SSL(smtp_server, 465, timeout=10) as server:
                    server.ehlo()
                    server.login(sender_email, password.strip())
                    server.sendmail(sender_email, recipient_email, message.as_string())
                    print(f"Email sent successfully to {recipient_email} (using SSL)")
                    return True
            except Exception as ssl_error:
                raise Exception(f"Both TLS and SSL methods failed. TLS error: {tls_error}, SSL error: {ssl_error}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        print("Check your app password and make sure it doesn't have spaces.")
        print("Also verify that 'Less secure app access' is enabled or you're using an App Password.")
        return False

def main():
    """Main function to run the Reddit email digest"""
    try:
        user_timezone = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
        tz = pytz_timezone(user_timezone)
        print(f"Starting Reddit digest at {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Fetch reddit posts from all subreddits
        subreddits = ['SideProject', 'vibecoding', 'Anthropic', 'AI_Agents', 'Linear', 'ClaudeCode', 'ClaudeAI']
        all_subreddit_posts = fetch_reddit_posts(subreddits)
        
        # Debug output for subreddit posts
        print("\nDEBUG: Subreddits and post counts:")
        for subreddit, posts in all_subreddit_posts.items():
            print(f"- r/{subreddit}: {len(posts)} posts")
        
        # Check if we have any posts
        total_posts = sum(len(posts) for posts in all_subreddit_posts.values())
        if total_posts == 0:
            print("No posts found from any subreddit, exiting")
            return
        
        # Generate summaries for all posts
        print("Generating summaries for all posts...")
        for subreddit, posts in all_subreddit_posts.items():
            print(f"Summarizing posts from r/{subreddit}...")
            for post in posts:
                # Add subreddit info to the post data
                post['subreddit'] = subreddit
                # Generate summaries for this post
                summaries = summarize_post(post, subreddit)
                # Store summaries in the post data
                post['summaries'] = summaries
                
        # Flatten all posts into a single list and sort by upvotes
        all_posts = []
        for subreddit, posts in all_subreddit_posts.items():
            all_posts.extend(posts)
        
        # Sort all posts by score (upvotes) in descending order
        all_posts.sort(key=lambda x: x['score'], reverse=True)
        print(f"Total posts across all subreddits: {len(all_posts)}")
        print(f"Posts reordered by upvotes (highest first)")
        
        # Log image analysis results if in test mode
        if IMAGE_ANALYSIS_CONFIG['test_mode']:
            posts_with_images = [p for p in all_posts if p.get('image_urls')]
            print(f"\nImage Analysis Summary:")
            print(f"- Posts with detected images: {len(posts_with_images)}")
            for post in posts_with_images:
                print(f"  - '{post['title'][:40]}...' has {len(post['image_urls'])} images")
        
        # Log web search results
        if WEB_SEARCH_CONFIG['enabled'] or WEB_SEARCH_CONFIG['test_mode']:
            posts_with_web_search = []
            web_search_candidates = []
            
            for post in all_posts:
                summaries = post.get('summaries', {})
                if summaries:
                    post_usage = summaries.get('post_usage', {})
                    if post_usage.get('web_search_used', False):
                        posts_with_web_search.append(post)
                
                # Check which posts were candidates for web search
                if should_use_web_search(post, post['subreddit']):
                    web_search_candidates.append(post)
            
            print(f"\nWeb Search Summary:")
            print(f"- Web search enabled: {WEB_SEARCH_CONFIG['enabled']}")
            print(f"- Posts that used web search: {len(posts_with_web_search)}")
            print(f"- Posts that were candidates: {len(web_search_candidates)}")
            
            # Show web search status
            status = web_search_manager.get_status_summary()
            print(f"- Daily usage: {status['daily_usage']['searches_count']}/{WEB_SEARCH_CONFIG['daily_limit']} searches")
            print(f"- Daily cost: ${status['daily_usage']['total_cost']:.4f}/${WEB_SEARCH_CONFIG['cost_limit_per_day']:.2f}")
            print(f"- Circuit breaker state: {status['circuit_breaker_state']}")
            
            if posts_with_web_search:
                print("Web search enhanced posts:")
                for post in posts_with_web_search:
                    print(f"  - '{post['title'][:40]}...' (score: {post['score']})")
            
            if WEB_SEARCH_CONFIG['test_mode'] and web_search_candidates:
                print("Web search candidates:")
                for post in web_search_candidates:
                    can_search, reason = web_search_manager.can_perform_search(post, post['subreddit'])
                    status_icon = "✓" if can_search else "✗"
                    print(f"  {status_icon} '{post['title'][:40]}...' - {reason}")
                
        # Format email content
        print("\nGenerating email content...")
        html_content = format_email_content(all_posts, all_subreddit_posts)
        
        # Debug info about content size
        print(f"Email content generated: {len(html_content)} characters")
        
        # Save HTML to file for inspection
        with open("last_email_content.html", "w") as f:
            f.write(html_content)
            print("Email content saved to last_email_content.html")
        
        # Save subreddit data to debug file
        with open("subreddit_data.txt", "w") as f:
            for subreddit, posts in all_subreddit_posts.items():
                f.write(f"Subreddit: {subreddit}, Posts: {len(posts)}\n")
                for post in posts:
                    f.write(f"  - {post['title'][:50]}...\n")
            print("Subreddit data saved to subreddit_data.txt")
        
        # Send email
        # Create dynamic subject that lists all subreddits
        subreddit_list = ', '.join([f'r/{sub}' for sub in subreddits[:-1]]) + f' & r/{subreddits[-1]}' if len(subreddits) > 1 else f'r/{subreddits[0]}'
        subject = f"Reddit Digest ({subreddit_list}) - {datetime.now().strftime('%Y-%m-%d')}"
        if send_email(subject, html_content, all_subreddit_posts=all_subreddit_posts):
            print("Email sent successfully")
        else:
            print("Failed to send email")
            
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()

def schedule_job():
    """Set up scheduled job"""
    schedule_time = os.getenv('SCHEDULE_TIME', '09:00')
    
    schedule.every().day.at(schedule_time).do(main)
    
    print(f"Scheduled daily digest to run at {schedule_time}")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reddit Digest Email Service')
    parser.add_argument('--run-once', action='store_true', help='Run once immediately and exit')
    args = parser.parse_args()
    
    # Check command line args first, then environment variables
    if args.run_once or os.getenv('RUN_ONCE', 'false').lower() == 'true':
        print("Running once and exiting")
        main()
    else:
        print("Starting scheduled service...")
        schedule_job()
