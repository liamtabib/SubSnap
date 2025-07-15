"""Email content formatting utilities."""

import os
import pytz
from datetime import datetime
from typing import List, Dict, Any

from core.constants import Constants


class EmailFormatter:
    """Formats Reddit posts into HTML and plain text email content."""
    
    def __init__(self, timezone: str = 'Europe/Berlin'):
        """Initialize email formatter."""
        self.timezone = timezone
        self.user_timezone = pytz.timezone(timezone)
    
    def _calculate_usage_stats(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate total usage statistics from posts."""
        stats = {
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'total_images_processed': 0,
            'total_estimated_cost': 0.0,
            'total_web_searches': 0
        }
        
        for post in posts:
            summaries = post.get('summaries', {})
            if summaries:
                # Add post summary tokens
                post_usage = summaries.get('post_usage', {})
                if post_usage:
                    stats['total_prompt_tokens'] += post_usage.get('prompt_tokens', 0)
                    stats['total_completion_tokens'] += post_usage.get('completion_tokens', 0)
                    stats['total_tokens'] += post_usage.get('total_tokens', 0)
                    stats['total_images_processed'] += post_usage.get('images_processed', 0)
                    stats['total_estimated_cost'] += post_usage.get('estimated_cost', 0)
                    if post_usage.get('web_search_used', False):
                        stats['total_web_searches'] += 1
                
                # Add comments summary tokens
                comments_usage = summaries.get('comments_usage', {})
                if comments_usage:
                    stats['total_prompt_tokens'] += comments_usage.get('prompt_tokens', 0)
                    stats['total_completion_tokens'] += comments_usage.get('completion_tokens', 0)
                    stats['total_tokens'] += comments_usage.get('total_tokens', 0)
        
        return stats
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML email."""
        return f"""
        <style>
            :root {{
                --primary-color: {Constants.REDDIT_ORANGE};
                --secondary-color: {Constants.REDDIT_BLUE};
                --text-color: {Constants.REDDIT_TEXT_COLOR};
                --light-text: {Constants.REDDIT_LIGHT_TEXT};
                --background: {Constants.REDDIT_BACKGROUND};
                --card-background: {Constants.REDDIT_CARD_BACKGROUND};
                --divider: {Constants.REDDIT_DIVIDER};
                --highlight: {Constants.REDDIT_HIGHLIGHT};
                --shadow: {Constants.REDDIT_SHADOW};
                --radius: {Constants.REDDIT_RADIUS};
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
        """
    
    def format_html_email(self, posts: List[Dict[str, Any]]) -> str:
        """Format posts into HTML email content."""
        now = datetime.now(self.user_timezone)
        formatted_date = now.strftime("%A, %B %d, %Y")
        
        # Get unique subreddits
        subreddits = sorted(list(set(post['subreddit'] for post in posts)))
        
        # Calculate usage statistics
        stats = self._calculate_usage_stats(posts)
        
        # Start HTML
        html_content = f"""
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            {self._get_css_styles()}
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Reddit Digest: {', '.join([f'r/{s}' for s in subreddits])}</h1>
                    <div class="date">{formatted_date}</div>
                </div>
                
                <div class="token-usage">
                    <h3>OpenAI API Usage</h3>
                    <div class="token-item">📤 Prompt: {stats['total_prompt_tokens']}</div>
                    <div class="token-item">📥 Completion: {stats['total_completion_tokens']}</div>
                    <div class="token-item">📊 Total: {stats['total_tokens']}</div>
                    <div class="token-item">🖼️ Images: {stats['total_images_processed']}</div>
                    <div class="token-item">🌐 Web Searches: {stats['total_web_searches']}</div>
                    <div class="token-item">💰 Est. Cost: ${stats['total_estimated_cost']:.4f}</div>
                </div>
                
                <h2>Top Posts (Sorted by Upvotes)</h2>
        """
        
        # Add posts
        if not posts:
            html_content += "<p class='no-posts'>No posts found today.</p>"
        else:
            for post in posts:
                summaries = post.get('summaries', {})
                post_summary = summaries.get('post_summary') if summaries else None
                comments_summary = summaries.get('comments_summary') if summaries else None
                
                # Check for web search usage
                web_search_used = False
                if summaries:
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
                
                # Add post summary or content
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
                
                # Add comments summary or raw comments
                if comments_summary:
                    html_content += f"""
                    <div class="comments-summary">
                        <h3><span class="indicator comment-indicator"></span>Comments Summary</h3>
                        <p>{comments_summary}</p>
                    </div>
                    """
                elif post['comments']:
                    html_content += "<h3><span class='indicator comment-indicator'></span>Top Comments</h3>"
                    for comment in post['comments'][:3]:
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
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def format_plain_text_email(self, posts: List[Dict[str, Any]]) -> str:
        """Format posts into plain text email content."""
        now = datetime.now(self.user_timezone)
        date_str = now.strftime("%A, %B %d, %Y")
        
        # Get unique subreddits
        subreddits = sorted(list(set(post['subreddit'] for post in posts)))
        
        # Calculate usage statistics
        stats = self._calculate_usage_stats(posts)
        
        # Start with header
        text_content = f"REDDIT DIGEST: {', '.join([f'r/{s}' for s in subreddits])}\n"
        text_content += f"Top posts from {date_str}\n\n"
        
        # Add usage information
        text_content += "OPENAI API USAGE:\n"
        text_content += f"Prompt tokens: {stats['total_prompt_tokens']}\n"
        text_content += f"Completion tokens: {stats['total_completion_tokens']}\n"
        text_content += f"Total tokens: {stats['total_tokens']}\n"
        text_content += f"Images processed: {stats['total_images_processed']}\n"
        text_content += f"Web searches: {stats['total_web_searches']}\n"
        text_content += f"Estimated cost: ${stats['total_estimated_cost']:.4f}\n"
        text_content += "=" * 50 + "\n\n"
        
        # Add posts
        if not posts:
            text_content += "No posts found today\n\n"
        else:
            text_content += "TOP POSTS ACROSS ALL SUBREDDITS (SORTED BY UPVOTES)\n"
            text_content += "-" * 50 + "\n\n"
            
            for i, post in enumerate(posts, 1):
                summaries = post.get('summaries', {})
                post_summary = summaries.get('post_summary') if summaries else None
                comments_summary = summaries.get('comments_summary') if summaries else None
                
                text_content += f"{i}. {post['title']}\n"
                text_content += f"   r/{post['subreddit']} | Posted by u/{post['author']} | {post['score']} points | {len(post['comments'])} comments\n"
                text_content += f"   {post['url']}\n\n"
                
                # Add post summary or content
                if post_summary:
                    text_content += "POST SUMMARY:\n"
                    text_content += "-" * 15 + "\n"
                    text_content += f"{post_summary}\n\n"
                else:
                    text_content += "POST CONTENT:\n"
                    text_content += "-" * 15 + "\n"
                    content = post['body'][:500] + ('...' if len(post['body']) > 500 else '')
                    text_content += f"{content}\n\n"
                
                # Add comments summary or raw comments
                if comments_summary:
                    text_content += "COMMENTS SUMMARY:\n"
                    text_content += "-" * 15 + "\n"
                    text_content += f"{comments_summary}\n\n"
                elif post['comments']:
                    text_content += "TOP COMMENTS:\n"
                    text_content += "-" * 15 + "\n"
                    for j, comment in enumerate(post['comments'][:3], 1):
                        comment_text = comment['body'][:200] + ('...' if len(comment['body']) > 200 else '')
                        text_content += f"{j}. u/{comment['author']} ({comment['score']} points): {comment_text}\n\n"
                
                text_content += "=" * 50 + "\n\n"
        
        return text_content