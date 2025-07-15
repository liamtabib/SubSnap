#!/usr/bin/env python3
"""
Test runner for SubSnap test suite.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.append('../src')
from core.reporter import SubSnapReporter


def run_test_file(test_file: str, format_type: str = 'console') -> bool:
    """Run a single test file and return success status."""
    try:
        cmd = [sys.executable, test_file]
        if format_type != 'console':
            cmd.extend(['--format', format_type])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def main():
    """Run all tests in the test suite."""
    parser = argparse.ArgumentParser(description='SubSnap Test Suite Runner')
    parser.add_argument('--format', choices=['console', 'json', 'quiet'], 
                       default='console', help='Output format')
    parser.add_argument('--output', help='Output file for JSON format')
    parser.add_argument('--test', help='Run specific test file')
    args = parser.parse_args()
    
    # Change to tests directory
    os.chdir(Path(__file__).parent)
    
    # Available test files
    test_files = [
        'test_web_search.py',
        'test_full_integration.py',
        'test_edge_cases.py',
        'test_image_detection.py',
        'test_multimodal.py',
        'validate_scoring.py'
    ]
    
    # Filter to specific test if requested
    if args.test:
        test_files = [f for f in test_files if args.test in f]
        if not test_files:
            print(f"No test files found matching: {args.test}")
            return 1
    
    # Initialize reporter
    reporter = SubSnapReporter(args.format)
    reporter.start_suite("SubSnap Test Suite")
    
    # Run tests
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"Running {test_file}...")
            success = run_test_file(test_file, 'quiet')  # Run tests quietly
            status = 'pass' if success else 'fail'
            reporter.add_result(test_file, status)
        else:
            reporter.add_result(test_file, 'skip', 'File not found')
    
    # Output results
    reporter.end_suite()
    reporter.output(args.output)
    
    return 0


if __name__ == '__main__':
    exit(main())