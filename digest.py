#!/usr/bin/env python3
"""
Reddit Digest - Entry point for the application.

This script provides the main entry point for the Reddit Email Digest application.
"""

import os
import sys

# Add the src directory to the Python path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Import and run the main function
from app import main

if __name__ == '__main__':
    exit(main())