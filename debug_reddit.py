#!/usr/bin/env python3
import praw
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to Reddit API
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent='testing_script'
)

# Test all subreddits
subreddits = ['cursor', 'windsurf', 'vibecoding', 'Anthropic', 'AI_Agents', 'Linear']

for subreddit_name in subreddits:
    print(f"\nTesting r/{subreddit_name}:")
    try:
        subreddit = reddit.subreddit(subreddit_name)
        print(f"Subreddit exists: {subreddit.display_name}, {subreddit.title}")
        
        posts = list(subreddit.hot(limit=3))
        print(f"Found {len(posts)} posts")
        
        for i, post in enumerate(posts, 1):
            print(f"{i}. '{post.title[:50]}...' by u/{post.author.name if post.author else '[deleted]'}")
            
    except Exception as e:
        print(f"Error: {e}")
        
print("\nDebug complete")
