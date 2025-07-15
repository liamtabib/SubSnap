"""Main application orchestrator for Reddit Email Digest."""

import os
import argparse
import schedule
import time
from datetime import datetime
from typing import List, Dict, Any

from core.config import Config
from clients.reddit_client import RedditClient
from services.summarization_service import SummarizationService
from handlers.email_handler import EmailHandler
from core.constants import Constants


class DigestOrchestrator:
    """Main orchestrator for the Reddit email digest application."""
    
    def __init__(self, config: Config):
        """Initialize the orchestrator with configuration."""
        self.config = config
        
        # Initialize components
        self.reddit_client = RedditClient(config.reddit)
        self.summarization_service = SummarizationService(config)
        self.email_handler = EmailHandler(config.email, config.user_timezone)
        
        print(f"Reddit Digest Orchestrator initialized")
        print(f"- Subreddits: {', '.join(config.subreddits)}")
        print(f"- Web search enabled: {config.web_search.enabled}")
        print(f"- Image analysis enabled: {config.image_analysis.enabled}")
    
    def run_digest(self) -> None:
        """Run the complete digest process."""
        try:
            from pytz import timezone as pytz_timezone
            tz = pytz_timezone(self.config.user_timezone)
            print(f"Starting Reddit digest at {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Fetch posts from all subreddits
            print(f"Fetching posts from {len(self.config.subreddits)} subreddits...")
            all_subreddit_posts = self.reddit_client.fetch_posts(
                subreddit_names=self.config.subreddits,
                limit=10,  # Fetch more initially for filtering
                comment_limit=self.config.comment_limit,
                min_score=self.config.min_post_score,
                user_timezone=self.config.user_timezone
            )
            
            # Debug output
            print("\\nDEBUG: Subreddits and post counts:")
            for subreddit, posts in all_subreddit_posts.items():
                print(f"- r/{subreddit}: {len(posts)} posts")
            
            # Check if we have any posts
            total_posts = sum(len(posts) for posts in all_subreddit_posts.values())
            if total_posts == 0:
                print("No posts found from any subreddit, exiting")
                return
            
            # Generate summaries for all posts
            print("Generating summaries for all posts...")
            all_posts = []
            
            for subreddit, posts in all_subreddit_posts.items():
                print(f"Summarizing posts from r/{subreddit}...")
                
                for post in posts:
                    # Generate summaries for this post
                    post_summary = self.summarization_service.summarize_post(post)
                    
                    # Convert to dict format for backwards compatibility
                    post_dict = post.to_dict()
                    post_dict['summaries'] = post_summary.to_dict()
                    
                    all_posts.append(post_dict)
            
            # Sort all posts by score (upvotes) in descending order
            all_posts.sort(key=lambda x: x['score'], reverse=True)
            print(f"Total posts across all subreddits: {len(all_posts)}")
            print(f"Posts reordered by upvotes (highest first)")
            
            # Log advanced features usage
            self._log_advanced_features_usage(all_posts)
            
            # Format and send email
            print("\\nGenerating and sending email...")
            subject = self._create_email_subject()
            
            if self.email_handler.send_digest(all_posts, subject):
                print("Email sent successfully")
            else:
                print("Failed to send email")
            
            # Save debug files
            self._save_debug_files(all_posts, all_subreddit_posts)
            
        except Exception as e:
            print(f"Error in run_digest: {e}")
            import traceback
            traceback.print_exc()
    
    def _log_advanced_features_usage(self, posts: List[Dict[str, Any]]) -> None:
        """Log usage of advanced features like image analysis and web search."""
        # Image analysis logging
        if self.config.image_analysis.test_mode:
            posts_with_images = [p for p in posts if p.get('image_urls')]
            print(f"\\nImage Analysis Summary:")
            print(f"- Posts with detected images: {len(posts_with_images)}")
            for post in posts_with_images:
                print(f"  - '{post['title'][:40]}...' has {len(post['image_urls'])} images")
        
        # Web search logging
        if self.config.web_search.enabled or self.config.web_search.test_mode:
            posts_with_web_search = []
            web_search_candidates = []
            
            for post in posts:
                summaries = post.get('summaries', {})
                if summaries:
                    post_usage = summaries.get('post_usage', {})
                    if post_usage and post_usage.get('web_search_used', False):
                        posts_with_web_search.append(post)
                
                # Check which posts were candidates for web search
                # Convert dict to RedditPost object for web search service
                from models.reddit_models import RedditPost
                reddit_post = RedditPost.from_dict(post)
                if self.summarization_service.web_search_manager.should_use_web_search(reddit_post):
                    web_search_candidates.append(post)
            
            print(f"\\nWeb Search Summary:")
            print(f"- Web search enabled: {self.config.web_search.enabled}")
            print(f"- Posts that used web search: {len(posts_with_web_search)}")
            print(f"- Posts that were candidates: {len(web_search_candidates)}")
            
            # Show web search status
            status = self.summarization_service.web_search_manager.get_status_summary()
            print(f"- Daily usage: {status['daily_usage']['searches_count']}/{self.config.web_search.daily_limit} searches")
            print(f"- Daily cost: ${status['daily_usage']['total_cost']:.4f}/${self.config.web_search.cost_limit_per_day:.2f}")
            print(f"- Circuit breaker state: {status['circuit_breaker_state']}")
            
            if posts_with_web_search:
                print("Web search enhanced posts:")
                for post in posts_with_web_search:
                    print(f"  - '{post['title'][:40]}...' (score: {post['score']})")
    
    def _create_email_subject(self) -> str:
        """Create dynamic email subject."""
        subreddits = self.config.subreddits
        if len(subreddits) > 1:
            subreddit_list = ', '.join([f'r/{sub}' for sub in subreddits[:-1]]) + f' & r/{subreddits[-1]}'
        else:
            subreddit_list = f'r/{subreddits[0]}'
        
        return f"Reddit Digest ({subreddit_list}) - {datetime.now().strftime('%Y-%m-%d')}"
    
    def _save_debug_files(self, posts: List[Dict[str, Any]], subreddit_posts: Dict[str, List]) -> None:
        """Save debug files for inspection."""
        # Save HTML content
        html_content = self.email_handler.formatter.format_html_email(posts)
        with open(Constants.LAST_EMAIL_CONTENT_FILE, "w") as f:
            f.write(html_content)
            print(f"Email content saved to {Constants.LAST_EMAIL_CONTENT_FILE}")
        
        # Save subreddit data
        with open(Constants.SUBREDDIT_DATA_FILE, "w") as f:
            for subreddit, posts_list in subreddit_posts.items():
                f.write(f"Subreddit: {subreddit}, Posts: {len(posts_list)}\\n")
                for post in posts_list:
                    title = post.title if hasattr(post, 'title') else post.get('title', 'Unknown')
                    f.write(f"  - {title[:50]}...\\n")
            print(f"Subreddit data saved to {Constants.SUBREDDIT_DATA_FILE}")
    
    def schedule_job(self) -> None:
        """Set up scheduled job."""
        schedule.every().day.at(self.config.schedule_time).do(self.run_digest)
        print(f"Scheduled daily digest to run at {self.config.schedule_time}")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='SubSnap - Reddit Email Digest Service')
    parser.add_argument('--run-once', action='store_true', help='Run once immediately and exit')
    parser.add_argument('--quiet', action='store_true', help='Run quietly with minimal output')
    args = parser.parse_args()
    
    # Load and validate configuration
    try:
        config = Config()
        config.validate()
        if not args.quiet:
            print("Configuration loaded and validated successfully")
    except Exception as e:
        print(f"Configuration error: {e}")
        return 1
    
    # Create orchestrator
    orchestrator = DigestOrchestrator(config)
    
    # Check command line args and environment variables
    if args.run_once or config.run_once:
        if not args.quiet:
            print("Running once and exiting")
        orchestrator.run_digest()
    else:
        if not args.quiet:
            print("Starting scheduled service...")
        orchestrator.schedule_job()
    
    return 0


if __name__ == '__main__':
    exit(main())