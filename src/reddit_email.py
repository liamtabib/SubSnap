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

# Load environment variables
load_dotenv()

def connect_to_reddit():
    """Connect to Reddit API using credentials from .env file"""
    return praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT', 'cursor_subreddit_digest_bot')
    )

def fetch_top_posts(reddit_client, subreddit_name='cursor', post_limit=3, time_filter='day'):
    """Fetch top upvoted posts from the specified subreddit"""
    subreddit = reddit_client.subreddit(subreddit_name)
    top_posts = subreddit.top(time_filter=time_filter, limit=post_limit)
    
    posts_data = []
    for post in top_posts:
        post_data = {
            'title': post.title,
            'author': post.author.name if post.author else '[deleted]',
            'score': post.score,
            'url': f"https://www.reddit.com{post.permalink}",
            'body': post.selftext if hasattr(post, 'selftext') else '',
            'comments': []
        }
        
        # Get top 3 comments
        post.comment_sort = 'top'
        post.comments.replace_more(limit=0)  # Skip "load more comments" objects
        for comment in list(post.comments)[:3]:
            post_data['comments'].append({
                'author': comment.author.name if comment.author else '[deleted]',
                'body': comment.body,
                'score': comment.score
            })
        
        posts_data.append(post_data)
    
    return posts_data

def format_email_content(posts_data):
    """Format the posts and comments into a readable email format"""
    email_content = f"<h1>Top Posts from r/cursor - {datetime.now().strftime('%Y-%m-%d')}</h1>"
    
    for i, post in enumerate(posts_data, 1):
        email_content += f"""
        <div style="margin-bottom: 30px; border-bottom: 1px solid #ccc; padding-bottom: 20px;">
            <h2>{i}. {post['title']}</h2>
            <p><strong>Posted by:</strong> u/{post['author']} | <strong>Score:</strong> {post['score']}</p>
            <p><a href="{post['url']}">View on Reddit</a></p>
            
            {f'<div style="background-color: #f5f5f5; padding: 10px; margin: 10px 0;"><p>{post["body"]}</p></div>' if post['body'] else ''}
            
            <h3>Top Comments:</h3>
            <div style="margin-left: 20px;">
        """
        
        if not post['comments']:
            email_content += "<p><i>No comments found</i></p>"
        else:
            for j, comment in enumerate(post['comments'], 1):
                email_content += f"""
                <div style="margin-bottom: 15px;">
                    <p><strong>u/{comment['author']}</strong> ({comment['score']} points)</p>
                    <p>{comment['body']}</p>
                </div>
                """
        
        email_content += "</div></div>"
    
    return email_content

def send_email(subject, html_content, recipient_email=None):
    """Send an email with the formatted content"""
    sender_email = os.getenv('EMAIL_SENDER')
    recipient_email = recipient_email or os.getenv('EMAIL_RECIPIENT')
    password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    
    # Print debug info (without exposing full password)
    print(f"Email configuration:")
    print(f"- Sender: {sender_email}")
    print(f"- Recipient: {recipient_email}")
    print(f"- Password exists: {bool(password)}")
    print(f"- Password length: {len(password) if password else 0}")
    print(f"- SMTP Server: {smtp_server}")
    print(f"- SMTP Port: {smtp_port}")
    
    if not all([sender_email, recipient_email, password]):
        print("Error: Missing email configuration. Check environment variables.")
        return False
    
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)
    
    # Also add plain text alternative
    plain_text = "This is the Reddit digest - please view in HTML format"
    text_part = MIMEText(plain_text, "plain")
    message.attach(text_part)
    
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

def run_reddit_digest():
    """Main function to fetch posts and send email"""
    print(f"Running Reddit digest at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        reddit = connect_to_reddit()
        posts = fetch_top_posts(reddit)
        
        if not posts:
            print("No posts found")
            return
        
        email_content = format_email_content(posts)
        send_email(
            subject=f"Top r/cursor Posts - {datetime.now().strftime('%Y-%m-%d')}",
            html_content=email_content
        )
    except Exception as e:
        print(f"Error running reddit digest: {e}")

def schedule_job():
    """Set up scheduled job"""
    schedule_time = os.getenv('SCHEDULE_TIME', '09:00')
    schedule.every().day.at(schedule_time).do(run_reddit_digest)
    
    print(f"Scheduled daily digest to run at {schedule_time}")
    
    # Run once immediately on startup if INITIAL_RUN is set to true
    if os.getenv('INITIAL_RUN', 'false').lower() == 'true':
        run_reddit_digest()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Reddit Email Digest Service')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    
    # Check command line args first, then environment variables
    if args.run_once or os.getenv('RUN_ONCE', 'false').lower() == 'true':
        run_reddit_digest()
    else:
        schedule_job()
