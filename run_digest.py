#!/usr/bin/env python3
"""
Simple runner script for the refactored Reddit Email Digest.

This script provides a simple way to run the modular version of the application
while maintaining backwards compatibility with the existing workflow.
"""

import os
import sys

# Add the src directory to the Python path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Import and run the main function
from main import main

if __name__ == '__main__':
    exit(main())