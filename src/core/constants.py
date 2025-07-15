"""Constants used throughout the application."""


class Constants:
    """Application constants."""
    
    # Post filtering
    MIN_POST_SCORE = 10
    DEFAULT_POSTS_PER_SUBREDDIT = 3
    DEFAULT_COMMENT_LIMIT = 3
    
    # Image analysis
    MAX_IMAGES_PER_POST = 2
    IMAGE_ANALYSIS_MIN_SCORE = 25
    
    # Token estimation
    TOKEN_ESTIMATION_RATIO = 4  # Characters per token approximation
    MAX_POST_TOKENS = 700
    MAX_COMMENT_TOKENS = 250
    
    # Web search
    WEB_SEARCH_SCORE_THRESHOLD = 30
    WEB_SEARCH_MIN_SCORE = 15
    
    # Email styling
    REDDIT_ORANGE = "#FF4500"
    REDDIT_BLUE = "#0079D3"
    REDDIT_TEXT_COLOR = "#1A1A1B"
    REDDIT_LIGHT_TEXT = "#7C7C7C"
    REDDIT_BACKGROUND = "#F8F9FA"
    REDDIT_CARD_BACKGROUND = "#FFFFFF"
    REDDIT_DIVIDER = "#EDEFF1"
    REDDIT_HIGHLIGHT = "#f0f7ff"
    REDDIT_SHADOW = "rgba(0, 0, 0, 0.1)"
    REDDIT_RADIUS = "10px"
    
    # Cost calculation (GPT-4o pricing as of 2025)
    GPT4O_PROMPT_COST_PER_1K = 0.005
    GPT4O_COMPLETION_COST_PER_1K = 0.015
    GPT4O_IMAGE_COST = 0.00765  # Per image cost for low detail
    
    # Timeouts
    IMAGE_VALIDATION_TIMEOUT = 5  # seconds
    SMTP_TIMEOUT = 10  # seconds
    
    # File names
    LAST_EMAIL_CONTENT_FILE = "last_email_content.html"
    SUBREDDIT_DATA_FILE = "subreddit_data.txt"
    WEB_SEARCH_USAGE_FILE = "web_search_usage.json"
    WEB_SEARCH_CIRCUIT_STATE_FILE = "web_search_circuit_state.json"