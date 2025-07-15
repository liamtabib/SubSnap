"""Reddit API client."""

import praw
from datetime import datetime
from typing import Dict, List
import pytz
from pytz import timezone as pytz_timezone

from core.config import RedditConfig
from models.reddit_models import RedditPost, Comment


class RedditClient:
    """Reddit API client wrapper."""
    
    def __init__(self, config: RedditConfig):
        """Initialize Reddit client."""
        self.config = config
        self._reddit = None
    
    def _get_reddit(self) -> praw.Reddit:
        """Get or create Reddit instance."""
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                user_agent=self.config.user_agent
            )
        return self._reddit
    
    def is_today(self, timestamp: float, timezone_str: str = 'Europe/Berlin') -> bool:
        """Check if a timestamp is from today in the specified timezone."""
        # Get the current time in the user's timezone
        tz = pytz_timezone(timezone_str)
        now = datetime.now(tz)
        
        # Convert Unix timestamp to datetime in the user's timezone
        post_time = datetime.fromtimestamp(timestamp, tz)
        
        # Check if the post is from today
        return (post_time.year == now.year and 
                post_time.month == now.month and 
                post_time.day == now.day)
    
    def fetch_posts(self, subreddit_names: List[str], limit: int = 10, 
                   comment_limit: int = 3, min_score: int = 10,
                   user_timezone: str = 'Europe/Berlin') -> Dict[str, List[RedditPost]]:
        """Fetch today's posts from multiple subreddits.
        
        Args:
            subreddit_names: List of subreddit names to fetch from
            limit: Maximum number of posts to fetch per subreddit
            comment_limit: Maximum number of comments per post
            min_score: Minimum upvote score for posts
            user_timezone: User's timezone for date filtering
            
        Returns:
            Dictionary mapping subreddit names to lists of RedditPost objects
        """
        reddit = self._get_reddit()
        all_subreddit_posts = {}
        
        print(f"Using timezone: {user_timezone}")
        print(f"Filtering for posts with at least {min_score} upvotes")
        
        for subreddit_name in subreddit_names:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                today_posts = []
                
                # Fetch posts and filter by date and score
                for post in subreddit.hot(limit=limit):
                    if self.is_today(post.created_utc, user_timezone) and post.score >= min_score:
                        # Extract comments
                        comments = []
                        post.comment_sort = 'top'
                        post.comments.replace_more(limit=0)
                        
                        for comment in post.comments[:comment_limit]:
                            comments.append(Comment(
                                author=comment.author.name if comment.author else '[deleted]',
                                body=comment.body,
                                score=comment.score
                            ))
                        
                        # Create RedditPost object
                        reddit_post = RedditPost(
                            title=post.title,
                            author=post.author.name if post.author else '[deleted]',
                            score=post.score,
                            url=f'https://www.reddit.com{post.permalink}',
                            body=post.selftext,
                            created_time=datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                            subreddit=subreddit_name,
                            comments=comments,
                            image_urls=[]  # Will be populated by image analyzer
                        )
                        
                        today_posts.append(reddit_post)
                
                # Sort posts by score in descending order
                today_posts.sort(key=lambda x: x.score, reverse=True)
                
                # Limit to top posts by score
                all_subreddit_posts[subreddit_name] = today_posts[:3]
                
                print(f"Found {len(today_posts)} posts from today in r/{subreddit_name}, using top {len(all_subreddit_posts[subreddit_name])} by upvotes")
                
                # Debug log to show selected posts and scores
                for i, post in enumerate(all_subreddit_posts[subreddit_name]):
                    print(f"  {i+1}. {post.title[:40]}... ({post.score} upvotes)")
                print("")
                
            except Exception as e:
                print(f"Error fetching posts from r/{subreddit_name}: {e}")
                all_subreddit_posts[subreddit_name] = []
        
        return all_subreddit_posts