"""Clean reporting system for SubSnap test results and analytics."""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    status: str  # 'pass', 'fail', 'skip'
    details: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class TestSuite:
    """Represents a collection of test results."""
    name: str
    results: List[TestResult]
    summary: Dict[str, Any]
    timestamp: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SubSnapReporter:
    """Clean reporting system for SubSnap tests and analytics."""
    
    def __init__(self, format_type: str = 'console'):
        """Initialize reporter with output format."""
        self.format_type = format_type
        self.test_suites: List[TestSuite] = []
        self.current_suite: Optional[TestSuite] = None
    
    def start_suite(self, name: str):
        """Start a new test suite."""
        self.current_suite = TestSuite(
            name=name,
            results=[],
            summary={},
            timestamp=datetime.now().isoformat()
        )
    
    def add_result(self, name: str, status: str, details: Optional[str] = None):
        """Add a test result to the current suite."""
        if not self.current_suite:
            self.start_suite("Default")
        
        result = TestResult(
            name=name,
            status=status,
            details=details
        )
        self.current_suite.results.append(result)
    
    def end_suite(self, summary: Optional[Dict[str, Any]] = None):
        """End the current test suite."""
        if not self.current_suite:
            return
        
        # Calculate summary if not provided
        if summary is None:
            summary = self._calculate_summary(self.current_suite.results)
        
        self.current_suite.summary = summary
        self.test_suites.append(self.current_suite)
        self.current_suite = None
    
    def _calculate_summary(self, results: List[TestResult]) -> Dict[str, Any]:
        """Calculate summary statistics for test results."""
        total = len(results)
        passed = sum(1 for r in results if r.status == 'pass')
        failed = sum(1 for r in results if r.status == 'fail')
        skipped = sum(1 for r in results if r.status == 'skip')
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'success_rate': (passed / total * 100) if total > 0 else 0
        }
    
    def output(self, file_path: Optional[str] = None):
        """Output the results in the specified format."""
        if self.format_type == 'json':
            self._output_json(file_path)
        elif self.format_type == 'console':
            self._output_console()
        elif self.format_type == 'quiet':
            self._output_quiet()
    
    def _output_console(self):
        """Output results to console with nice formatting."""
        for suite in self.test_suites:
            print(f"\n📧 {suite.name}")
            print("=" * 50)
            
            for result in suite.results:
                icon = self._get_status_icon(result.status)
                print(f"{icon} {result.name}")
                if result.details and self.format_type == 'console':
                    print(f"   {result.details}")
            
            # Print summary
            summary = suite.summary
            print(f"\n📊 Summary: {summary['passed']}/{summary['total']} passed")
            if summary['failed'] > 0:
                print(f"   ❌ {summary['failed']} failed")
            if summary['skipped'] > 0:
                print(f"   ⏭️  {summary['skipped']} skipped")
            print(f"   ✅ Success rate: {summary['success_rate']:.1f}%")
    
    def _output_json(self, file_path: Optional[str] = None):
        """Output results as JSON."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'suites': [asdict(suite) for suite in self.test_suites]
        }
        
        json_output = json.dumps(data, indent=2)
        
        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_output)
            print(f"📄 Results saved to {file_path}")
        else:
            print(json_output)
    
    def _output_quiet(self):
        """Output minimal results."""
        total_passed = sum(suite.summary['passed'] for suite in self.test_suites)
        total_tests = sum(suite.summary['total'] for suite in self.test_suites)
        
        if total_tests == total_passed:
            print("✅ All tests passed")
        else:
            print(f"❌ {total_tests - total_passed} tests failed")
            sys.exit(1)
    
    def _get_status_icon(self, status: str) -> str:
        """Get emoji icon for status."""
        return {
            'pass': '✅',
            'fail': '❌',
            'skip': '⏭️'
        }.get(status, '❓')


class WebSearchReporter(SubSnapReporter):
    """Specialized reporter for web search analytics."""
    
    def __init__(self, format_type: str = 'console'):
        super().__init__(format_type)
        self.web_search_stats = {
            'enabled': False,
            'posts_enhanced': 0,
            'posts_candidates': 0,
            'daily_usage': {},
            'circuit_breaker_state': 'closed',
            'enhanced_posts': []
        }
    
    def set_web_search_stats(self, stats: Dict[str, Any]):
        """Set web search statistics."""
        self.web_search_stats.update(stats)
    
    def _output_console(self):
        """Output with web search analytics."""
        super()._output_console()
        
        if self.web_search_stats['enabled']:
            print(f"\n🌐 Web Search Analytics")
            print("=" * 50)
            print(f"Posts enhanced: {self.web_search_stats['posts_enhanced']}")
            print(f"Posts candidates: {self.web_search_stats['posts_candidates']}")
            print(f"Daily usage: {self.web_search_stats.get('daily_usage', {})}")
            print(f"Circuit breaker: {self.web_search_stats['circuit_breaker_state']}")
            
            if self.web_search_stats['enhanced_posts']:
                print("\n🔍 Enhanced Posts:")
                for post in self.web_search_stats['enhanced_posts']:
                    print(f"  - {post}")


def create_reporter(format_type: str = 'console') -> SubSnapReporter:
    """Factory function to create appropriate reporter."""
    return SubSnapReporter(format_type)


# CLI Integration
def add_reporter_args(parser):
    """Add reporter arguments to CLI parser."""
    parser.add_argument(
        '--format', 
        choices=['console', 'json', 'quiet'], 
        default='console',
        help='Output format (default: console)'
    )
    parser.add_argument(
        '--output', 
        help='Output file path (for json format)'
    )


def get_reporter_from_args(args) -> SubSnapReporter:
    """Create reporter from CLI arguments."""
    return create_reporter(args.format)