"""Cost tracking utilities."""

import json
import os
from datetime import datetime
from typing import Dict, Any

from core.constants import Constants


class CostTracker:
    """Base class for cost tracking."""
    
    def __init__(self, usage_file: str):
        """Initialize cost tracker."""
        self.usage_file = usage_file
        self.usage_data = self.load_usage_data()
    
    def load_usage_data(self) -> Dict[str, Any]:
        """Load daily usage data from file."""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    # Clean old data (keep only today's data)
                    today = datetime.now().strftime('%Y-%m-%d')
                    if data.get('date') == today:
                        return data
            
            # Return fresh data for today
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'searches_count': 0,
                'total_cost': 0.0,
                'searches': []
            }
        except Exception as e:
            print(f"Error loading usage data from {self.usage_file}: {e}")
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'searches_count': 0,
                'total_cost': 0.0,
                'searches': []
            }
    
    def save_usage_data(self) -> None:
        """Save usage data to file."""
        try:
            # Ensure output directory exists
            os.makedirs(Constants.OUTPUT_DIR, exist_ok=True)
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            print(f"Error saving usage data to {self.usage_file}: {e}")
    
    def record_usage(self, description: str, cost: float, success: bool = True) -> None:
        """Record a usage event."""
        record = {
            'timestamp': datetime.now().isoformat(),
            'description': description[:50] + '...' if len(description) > 50 else description,
            'cost': cost,
            'success': success
        }
        
        self.usage_data['searches_count'] += 1
        self.usage_data['total_cost'] += cost
        self.usage_data['searches'].append(record)
        
        self.save_usage_data()
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get summary of today's usage."""
        return {
            'date': self.usage_data['date'],
            'searches_count': self.usage_data['searches_count'],
            'total_cost': self.usage_data['total_cost'],
            'searches': self.usage_data['searches']
        }


class WebSearchCostTracker(CostTracker):
    """Tracks daily web search usage and costs."""
    
    def __init__(self, daily_limit: int, cost_limit: float):
        """Initialize web search cost tracker."""
        super().__init__(Constants.WEB_SEARCH_USAGE_FILE)
        self.daily_limit = daily_limit
        self.cost_limit = cost_limit
    
    def can_search(self) -> bool:
        """Check if we're within daily limits."""
        # Check count limit
        if self.usage_data['searches_count'] >= self.daily_limit:
            return False
        
        # Check cost limit
        estimated_new_cost = self.usage_data['total_cost'] + 0.03  # Default cost per search
        if estimated_new_cost > self.cost_limit:
            return False
        
        return True
    
    def record_search(self, post_title: str, actual_cost: float = None, success: bool = True) -> None:
        """Record a web search usage."""
        cost = actual_cost if actual_cost is not None else 0.03
        self.record_usage(post_title, cost, success)
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get summary of today's web search usage."""
        base_summary = super().get_daily_summary()
        base_summary.update({
            'remaining_searches': max(0, self.daily_limit - self.usage_data['searches_count']),
            'remaining_budget': max(0, self.cost_limit - self.usage_data['total_cost'])
        })
        return base_summary