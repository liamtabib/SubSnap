#!/usr/bin/env python3
"""
Reddit Email Service - Fetches top posts from r/cursor and sends them via email
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

# Load environment variables
load_dotenv()

# Set up OpenAI client if API key is available
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = None
if openai_api_key:
    openai_client = openai.OpenAI(api_key=openai_api_key)

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

def fetch_reddit_posts(subreddit_names=['cursor', 'windsurf'], limit=10, comment_limit=3):
    """Fetch today's posts from multiple subreddits and their comments"""
    # Connect to Reddit API
    reddit = connect_to_reddit()
    
    # Get timezone from environment or default to Europe/Berlin (CEST)
    user_timezone = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    print(f"Using timezone: {user_timezone}")
        
    all_subreddit_posts = {}
    
    for subreddit_name in subreddit_names:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            posts = []
            today_posts = []
            
            # We need to fetch more posts initially since we'll be filtering
            for post in subreddit.hot(limit=limit):
                # Check if post is from today in user's timezone
                if is_today(post.created_utc, user_timezone):
                    post_data = {
                        'title': post.title,
                        'author': post.author.name if post.author else '[deleted]',
                        'score': post.score,
                        'url': f'https://www.reddit.com{post.permalink}',
                        'body': post.selftext,
                        'created_time': datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'comments': []
                    }
                    
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


def summarize_post_content(post_data, subreddit_name):
    """Use OpenAI to summarize just the Reddit post content"""
    if not openai_client:
        print("OpenAI API key not available. Skipping post summarization.")
        return None
    
    try:
        # Prepare and truncate the content to summarize (max 750 tokens)
        title = post_data['title']
        body = truncate_to_tokens(post_data['body'], 700)  # Leave room for title
        post_content = f"Title: {title}\n\nContent: {body}"
        
        # Create system message for post content
        system_message = {
            "role": "system",
            "content": "You are a technical summarizer for Reddit posts from r/cursor (an AI-powered code editor), "
                       "r/windsurf (a competing AI IDE), and r/vibecoding (AI-driven software development workflows). "
                       "Summarize the post content using a direct, concise tone. Focus on concrete information such as new features, "
                       "bugs, workflows, models, version changes, or community feedback. Include specific technical details "
                       "when present (e.g. tool names, implementation patterns, performance metrics). Do not add commentary, "
                       "fluff, or casual phrasing. If a post is non-technical, summarize it plainly without judgment. "
                       f"This post is from r/{subreddit_name}."
        }
        
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[system_message, {"role": "user", "content": post_content}],
            max_tokens=150  # Limit output to 150 tokens
        )
        
        # Get the summary and usage data
        summary = response.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        print(f"Generated post summary for: {post_data['title'][:30]}...")
        return {"summary": summary, "usage": usage}
        
    except Exception as e:
        print(f"Error generating post summary with OpenAI API: {e}")
        return None


def summarize_comments(post_data, subreddit_name):
    """Use OpenAI to summarize the comments of a Reddit post"""
    if not openai_client:
        print("OpenAI API key not available. Skipping comments summarization.")
        return None
    
    # Check if there are comments to summarize
    if not post_data['comments']:
        return {"summary": "No comments to summarize.", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    
    try:
        # Prepare the comments to summarize with truncation
        comments_content = f"Post Title: {post_data['title']}\n\nComments:\n"
        remaining_tokens = 250  # Max tokens for each comment
        tokens_per_comment = remaining_tokens // len(post_data['comments'])
        
        for i, comment in enumerate(post_data['comments'], 1):
            truncated_comment = truncate_to_tokens(comment['body'], tokens_per_comment)
            comments_content += f"{i}. By u/{comment['author']}: {truncated_comment}\n"
        
        # Create system message specifically for comments
        system_message = {
            "role": "system",
            "content": "You are a technical summarizer for comments on Reddit posts from r/cursor (an AI-powered code editor), "
                       "r/windsurf (a competing AI IDE), and r/vibecoding (AI-driven software development workflows). "
                       "Summarize the key points from comments using a direct, concise tone. Highlight user experiences, "
                       "disagreements, consensus views, troubleshooting suggestions, or additional information provided. "
                       "Focus on factual content and technical details. If the comments are primarily non-technical, "
                       "summarize their general sentiment or feedback plainly. "
                       f"These comments are on a post in r/{subreddit_name}."
        }
        
        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[system_message, {"role": "user", "content": comments_content}],
            max_tokens=100  # Limit output to 100 tokens
        )
        
        # Get the summary and usage data
        summary = response.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        print(f"Generated comments summary for: {post_data['title'][:30]}...")
        return {"summary": summary, "usage": usage}
        
    except Exception as e:
        print(f"Error generating comments summary with OpenAI API: {e}")
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

def format_email_content(all_subreddit_posts):
    """Format the posts from multiple subreddits into HTML email content"""
    # Get timezone from environment or default to Europe/Berlin (CEST)
    timezone_str = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    user_timezone = pytz.timezone(timezone_str)
    now = datetime.now(user_timezone)
    formatted_date = now.strftime("%A, %B %d, %Y")
    
    subreddits = list(all_subreddit_posts.keys())
    
    # Calculate total token usage
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    
    for subreddit in subreddits:
        for post in all_subreddit_posts[subreddit]:
            summaries = post.get('summaries', {})
            if summaries:
                # Add post summary tokens
                post_usage = summaries.get('post_usage', {})
                if post_usage:
                    total_prompt_tokens += post_usage.get('prompt_tokens', 0)
                    total_completion_tokens += post_usage.get('completion_tokens', 0)
                    total_tokens += post_usage.get('total_tokens', 0)
                
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
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            h1 {{ color: #333366; }}
            h2 {{ color: #666699; background-color: #f2f2f2; padding: 10px; border-radius: 5px; }}
            h3 {{ color: #5555AA; }}
            .token-usage {{ background-color: #e6e6ff; padding: 10px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #ccccff; }}
            .post {{ margin-bottom: 30px; border-bottom: 1px solid #ddd; padding-bottom: 20px; }}
            .post-title {{ font-size: 18px; font-weight: bold; color: #333366; }}
            .post-meta {{ color: #666; font-size: 14px; margin: 5px 0; }}
            .post-content {{ margin: 10px 0; padding: 0 15px; }}
            .summary {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .comments-summary {{ border-left: 4px solid #666699; padding-left: 15px; margin: 10px 0; background-color: #fafafa; padding: 10px; }}
            .comment {{ margin: 10px 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            .comment-meta {{ color: #666; font-size: 14px; }}
            .no-posts {{ color: #999; font-style: italic; }}
        </style>
    </head>
    <body>
        <h1>Reddit Digest: {', '.join([f'r/{s}' for s in subreddits])}</h1>
        <p>Top posts from {formatted_date}</p>
        <div class="token-usage">
            <h3>OpenAI API Usage:</h3>
            <p>Prompt tokens: {total_prompt_tokens}</p>
            <p>Completion tokens: {total_completion_tokens}</p>
            <p>Total tokens: {total_tokens}</p>
        </div>
    """
    
    # Add each subreddit's posts
    for subreddit in subreddits:
        html_content += f"<h2>r/{subreddit}</h2>"
        posts = all_subreddit_posts[subreddit]
        
        if not posts:
            html_content += "<p class='no-posts'>No posts today.</p>"
            continue
        
        for i, post in enumerate(posts, 1):
            # Get summaries if available
            summaries = post.get('summaries', {})
            post_summary = None
            comments_summary = None
            
            if summaries:
                post_summary = summaries.get('post_summary')
                comments_summary = summaries.get('comments_summary')
            
            html_content += f"""
            <div class="post">
                <div class="post-title">{i}. <a href="{post['url']}" target="_blank">{post['title']}</a></div>
                <div class="post-meta">Posted by u/{post['author']} • {post['score']} points • {len(post['comments'])} comments</div>
            """
            
            # Add post summary if available, otherwise show the raw post text
            if post_summary:
                html_content += f"""
                <div class="summary">
                    <h3>Post Summary:</h3>
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
                    <h3>Comments Summary:</h3>
                    <p>{comments_summary}</p>
                </div>
                """
            elif post['comments']:
                html_content += "<h3>Top Comments:</h3>"
                # Show up to 3 comments
                for j, comment in enumerate(post['comments'][:3], 1):
                    html_content += f"""
                    <div class="comment">
                        <div class="comment-meta">Comment by u/{comment['author']} • {comment['score']} points</div>
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

def create_plain_text_content(all_subreddit_posts):
    """Create a plain text version of the email content"""
    # Get timezone from environment or default to Europe/Berlin (CEST)
    timezone_str = os.getenv('USER_TIMEZONE', 'Europe/Berlin')
    user_timezone = pytz.timezone(timezone_str)
    now = datetime.now(user_timezone)
    date_str = now.strftime("%A, %B %d, %Y")
    
    subreddits = list(all_subreddit_posts.keys())
    
    # Calculate total token usage
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    
    for subreddit in subreddits:
        for post in all_subreddit_posts[subreddit]:
            summaries = post.get('summaries', {})
            if summaries:
                # Add post summary tokens
                post_usage = summaries.get('post_usage', {})
                if post_usage:
                    total_prompt_tokens += post_usage.get('prompt_tokens', 0)
                    total_completion_tokens += post_usage.get('completion_tokens', 0)
                    total_tokens += post_usage.get('total_tokens', 0)
                
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
    text_content += "=" * 50 + "\n\n"
    
    # For each subreddit
    for subreddit in subreddits:
        posts = all_subreddit_posts[subreddit]
        if not posts:
            text_content += f"No posts found from r/{subreddit}\n\n"
            continue
            
        text_content += f"TOP POSTS FROM r/{subreddit}\n"
        text_content += "-" * 50 + "\n\n"
        
        # For each post
        for i, post in enumerate(posts, 1):
            # Get summaries
            summaries = post.get('summaries', {})
            post_summary = None
            comments_summary = None
            
            if summaries:
                post_summary = summaries.get('post_summary')
                comments_summary = summaries.get('comments_summary')
                
            text_content += f"{i}. {post['title']}\n"
            text_content += f"   Posted by u/{post['author']} | {post['score']} points | {len(post['comments'])} comments\n"
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
        plain_text = create_plain_text_content(all_subreddit_posts)
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
        subreddits = ['cursor', 'windsurf', 'vibecoding']
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
            
        # Format email content
        print("\nGenerating email content...")
        html_content = format_email_content(all_subreddit_posts)
        
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
        subject = f"Reddit Digest (r/cursor, r/windsurf & r/vibecoding) - {datetime.now().strftime('%Y-%m-%d')}"
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
