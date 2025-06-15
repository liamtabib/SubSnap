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

# Initialize OpenAI API client
openai_api_key = os.getenv('OPENAI_API_KEY')
print(f"OpenAI API key available: {bool(openai_api_key)}") 
print(f"OpenAI API key length: {len(openai_api_key) if openai_api_key else 0}")

# More robust OpenAI client version detection
is_openai_modern = False

# First detection method: try accessing a modern client attribute
try:
    # This will only exist in modern openai>=1.0.0
    openai_version = openai.__version__
    if openai_version and int(openai_version.split('.')[0]) >= 1:
        is_openai_modern = True
        print(f"Detected modern OpenAI client version: {openai_version}")
    else:
        print(f"Detected legacy OpenAI client version: {openai_version}")
except (AttributeError, ValueError, IndexError):
    # Second detection method: try importing legacy module
    try:
        import openai.api_resources
        is_openai_modern = False
        print("Detected legacy OpenAI client based on module structure")
    except ImportError:
        # If this import fails too, we're likely on a modern client
        is_openai_modern = True
        print("Detected modern OpenAI client based on module structure")

# Initialize the client based on detected version
if openai_api_key:
    try:
        if is_openai_modern:
            # Modern client initialization (>=1.0.0)
            client = openai.OpenAI(api_key=openai_api_key)
            openai_client = client
            print("OpenAI client initialized with modern configuration")
            
            # Verify it's correctly initialized by accessing a property
            # that only exists in the modern client
            if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                print("Verified modern OpenAI client configuration")
            else:
                # Fallback if the modern initialization didn't work as expected
                print("Warning: Modern client initialization may not be correct, forcing legacy mode")
                is_openai_modern = False
                openai.api_key = openai_api_key
                openai_client = openai
        else:
            # Legacy client initialization (<1.0.0)
            openai.api_key = openai_api_key
            openai_client = openai
            print("OpenAI client initialized with legacy configuration")
        
        print(f"OpenAI client initialized successfully: True")
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        openai_client = None
else:
    openai_client = None
    print("WARNING: OpenAI client not initialized - summaries will be skipped")

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
    global is_openai_modern
    print(f"Attempting to summarize post: {post_data['title'][:30]}...")
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
                       "- Cursor: An AI-powered code editor with GPT-4o integration and code generation capabilities. "
                       "- Windsurf: A competing AI IDE, owned by OpenAI as of 2024, with advanced coding assistance and code editing features. "
                       "- Vibe Coding: A development approach centered on using AI-driven workflows and tools for coding efficiency. "
                       "- MCP (Model Context Protocol): A protocol that allows AI models to interface with external tools and systems, defining how models interact with API endpoints. "
                       "- o3: An OpenAI large language model similar to GPT-4o but with specific tooling optimizations. "
                       "- RAG: Retrieval Augmented Generation, a technique for enhancing AI responses with retrieved context. "
                       "- Claude 4: Anthropic's flagship large language model released in 2024-2025. "
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
        
        # Try to use the correct client approach, with fallback mechanisms
        try:
            if is_openai_modern:
                # Modern client approach (>=1.0.0)
                print("Using modern OpenAI client API for post summary")
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=150,
                    temperature=0.5
                )
                # Access via object attributes
                summary = response.choices[0].message.content.strip()
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            else:
                # Legacy client approach (<1.0.0)
                print("Using legacy OpenAI client API for post summary")
                response = openai_client.ChatCompletion.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=150,
                    temperature=0.5
                )
                # Access via dictionary indexing
                summary = response["choices"][0]["message"]["content"].strip()
                usage = {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"]
                }
        except Exception as api_error:
            # If we get an error indicating we're using the wrong API version,
            # try the other approach as a fallback
            error_str = str(api_error)
            print(f"Initial API call error: {error_str}")
            
            if "no longer supported in openai>=1.0.0" in error_str:
                # We incorrectly detected legacy client but we have modern
                print("Fallback to modern OpenAI client API")
                is_openai_modern = True  # Update the global flag
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
            elif "AttributeError" in error_str and "object has no attribute 'chat'" in error_str:
                # We incorrectly detected modern client but we have legacy
                print("Fallback to legacy OpenAI client API")
                is_openai_modern = False  # Update the global flag
                response = openai_client.ChatCompletion.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=150,
                    temperature=0.5
                )
                summary = response["choices"][0]["message"]["content"].strip()
                usage = {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"]
                }
            else:
                # Some other error occurred, re-raise
                raise
            
        print("OpenAI API call succeeded!")
        
        print(f"Generated post summary for: {post_data['title'][:30]}...")
        return {"summary": summary, "usage": usage}
        
    except Exception as e:
        print(f"ERROR generating post summary with OpenAI API: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None


def summarize_comments(post_data, subreddit_name):
    """Generate a summary of the post comments using OpenAI API"""
    global is_openai_modern
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
        
        # Try to use the correct client approach, with fallback mechanisms
        try:
            if is_openai_modern:
                # Modern client approach (>=1.0.0)
                print("Using modern OpenAI client API for comment summary")
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
            else:
                # Legacy client approach (<1.0.0)
                print("Using legacy OpenAI client API for comment summary")
                response = openai_client.ChatCompletion.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=100,
                    temperature=0.5
                )
                # Access via dictionary indexing
                summary = response["choices"][0]["message"]["content"].strip()
                usage = {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"]
                }
        except Exception as api_error:
            # If we get an error indicating we're using the wrong API version,
            # try the other approach as a fallback
            error_str = str(api_error)
            print(f"Initial API call error for comments summary: {error_str}")
            
            if "no longer supported in openai>=1.0.0" in error_str:
                # We incorrectly detected legacy client but we have modern
                print("Fallback to modern OpenAI client API for comments")
                is_openai_modern = True  # Update the global flag
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=100,
                    temperature=0.5
                )
                summary = response.choices[0].message.content.strip()
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            elif "AttributeError" in error_str and "object has no attribute 'chat'" in error_str:
                # We incorrectly detected modern client but we have legacy
                print("Fallback to legacy OpenAI client API for comments")
                is_openai_modern = False  # Update the global flag
                response = openai_client.ChatCompletion.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=100,
                    temperature=0.5
                )
                summary = response["choices"][0]["message"]["content"].strip()
                usage = {
                    "prompt_tokens": response["usage"]["prompt_tokens"],
                    "completion_tokens": response["usage"]["completion_tokens"],
                    "total_tokens": response["usage"]["total_tokens"]
                }
            else:
                # Some other error occurred, re-raise
                raise
            
        print(f"Generated comments summary for: {post_data['title'][:30]}...")
        return {"summary": summary, "usage": usage}
        
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
                padding: 20px; 
                line-height: 1.6; 
                background-color: var(--background);
                color: var(--text-color);
            }}
            
            h1 {{ 
                color: var(--primary-color); 
                font-size: 28px;
                font-weight: 600;
                margin-bottom: 8px;
            }}
            
            h2 {{ 
                color: var(--secondary-color); 
                font-size: 22px;
                font-weight: 500;
                padding: 12px 20px;
                margin: 30px 0 20px 0; 
                border-radius: var(--radius);
                background: linear-gradient(90deg, var(--secondary-color), #2A95E9);
                color: white;
                box-shadow: 0 2px 10px var(--shadow);
            }}
            
            h3 {{ 
                color: var(--secondary-color); 
                font-size: 18px;
                font-weight: 500;
                margin: 15px 0 5px 0;
            }}

            a {{ 
                color: var(--secondary-color); 
                text-decoration: none; 
            }}

            a:hover {{ 
                text-decoration: underline; 
            }}

            p {{ 
                margin: 10px 0; 
            }}

            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}

            .header {{
                text-align: center;
                padding: 20px 0;
                border-bottom: 1px solid var(--divider);
                margin-bottom: 20px;
            }}

            .date {{
                color: var(--light-text);
                font-size: 16px;
                margin-bottom: 20px;
            }}

            .token-usage {{ 
                background-color: var(--highlight); 
                padding: 15px;
                border-radius: var(--radius);
                margin-bottom: 30px; 
                box-shadow: 0 1px 5px var(--shadow);
                display: flex;
                flex-wrap: wrap;
                justify-content: space-around;
                align-items: center;
            }}

            .token-usage h3 {{
                width: 100%;
                text-align: center;
                margin: 0 0 15px 0;
            }}

            .token-item {{
                display: inline-block;
                padding: 8px 15px;
                border-radius: 20px;
                background: white;
                margin: 5px;
                font-size: 14px;
                box-shadow: 0 1px 3px var(--shadow);
            }}

            .post {{ 
                margin-bottom: 30px; 
                padding: 20px;
                background-color: var(--card-background);
                border-radius: var(--radius);
                box-shadow: 0 2px 10px var(--shadow);
            }}

            .post-title {{ 
                font-size: 20px; 
                font-weight: bold; 
                color: var(--text-color); 
                line-height: 1.4;
            }}

            .post-title a {{
                color: inherit;
            }}

            .post-meta {{ 
                color: var(--light-text); 
                font-size: 14px; 
                margin: 10px 0;
                display: flex;
                align-items: center;
                flex-wrap: wrap;
            }}

            .meta-item {{
                margin-right: 12px;
                display: flex;
                align-items: center;
            }}

            .upvotes {{
                color: var(--primary-color);
                font-weight: 600;
                background-color: rgba(255, 69, 0, 0.1);
                padding: 3px 10px;
                border-radius: 15px;
                margin-right: 10px;
            }}

            .comments-count {{
                color: var(--secondary-color);
                background-color: rgba(0, 121, 211, 0.1);
                padding: 3px 10px;
                border-radius: 15px;
            }}

            .summary {{ 
                background-color: #FFFFFF; 
                padding: 15px;
                border-radius: var(--radius); 
                margin: 15px 0;
                box-shadow: 0 1px 3px var(--shadow);
                border-left: 4px solid var(--primary-color);
            }}

            .comments-summary {{ 
                border-left: 4px solid var(--secondary-color); 
                padding: 15px;
                margin: 15px 0; 
                background-color: #FFFFFF;
                border-radius: var(--radius);
                box-shadow: 0 1px 3px var(--shadow);
            }}

            .comment {{ 
                margin: 15px 0; 
                padding: 10px 15px;
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
                <div class="post-title">
                    <span class="upvotes">{post['score']}</span>
                    <a href="{post['url']}" target="_blank">{post['title']}</a>
                </div>
                <div class="post-meta">
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
        
        # Generate summaries for all posts
        print("Generating summaries for all posts...")
        for subreddit, posts in all_subreddit_posts.items():
            print(f"Summarizing posts from r/{subreddit}...")
            for post in posts:
                # Generate summaries for this post
                summaries = summarize_post(post, subreddit)
                # Store summaries in the post data
                post['summaries'] = summaries
                
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
