"""Validation utilities."""

import re
import requests
from typing import List
from urllib.parse import urlparse

from core.constants import Constants


class ImageValidator:
    """Utility class for image URL validation and extraction."""
    
    @staticmethod
    def detect_images_from_url(post_url: str, post_body: str = "") -> List[str]:
        """Extract image URLs from Reddit post URL and body."""
        images = []
        
        # Direct Reddit image posts (i.redd.it)
        if 'i.redd.it' in post_url:
            images.append(post_url)
        
        # Imgur direct links
        elif 'imgur.com' in post_url and not post_url.endswith('/'):
            normalized_url = ImageValidator.normalize_imgur_url(post_url)
            if normalized_url:
                images.append(normalized_url)
        
        # Extract image URLs from post body text
        if post_body:
            body_images = ImageValidator.extract_image_urls_from_text(post_body)
            images.extend(body_images)
        
        # Remove duplicates and limit to max images for cost control
        unique_images = list(dict.fromkeys(images))
        return unique_images[:Constants.MAX_IMAGES_PER_POST]
    
    @staticmethod
    def normalize_imgur_url(url: str) -> str:
        """Convert imgur.com/abc to i.imgur.com/abc.jpg"""
        try:
            if 'i.imgur.com' in url:
                return url
            if 'imgur.com/' in url:
                # Extract image ID from URL
                parts = url.split('/')
                if len(parts) > 3:
                    img_id = parts[-1].split('.')[0]  # Remove extension if present
                    return f"https://i.imgur.com/{img_id}.jpg"
        except Exception as e:
            print(f"Error normalizing imgur URL {url}: {e}")
        return None
    
    @staticmethod
    def extract_image_urls_from_text(text: str) -> List[str]:
        """Extract image URLs from text using regex."""
        image_urls = []
        
        # Common image URL patterns
        url_patterns = [
            r'https?://i\.redd\.it/[^\s]+',
            r'https?://i\.imgur\.com/[^\s]+\.(?:jpg|jpeg|png|gif|webp)',
            r'https?://imgur\.com/[^\s]+',
            r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)'
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            image_urls.extend(matches)
        
        # Normalize imgur URLs
        normalized_urls = []
        for url in image_urls:
            if 'imgur.com' in url and 'i.imgur.com' not in url:
                normalized = ImageValidator.normalize_imgur_url(url)
                if normalized:
                    normalized_urls.append(normalized)
            else:
                normalized_urls.append(url)
        
        return normalized_urls
    
    @staticmethod
    def validate_image_urls(image_urls: List[str], timeout: int = Constants.IMAGE_VALIDATION_TIMEOUT) -> List[str]:
        """Check if images are actually accessible."""
        valid_urls = []
        
        for url in image_urls:
            try:
                # Quick HEAD request to check if image exists
                response = requests.head(url, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'image' in content_type:
                        valid_urls.append(url)
                        print(f"Valid image found: {url}")
                    else:
                        print(f"URL not an image: {url} (content-type: {content_type})")
                else:
                    print(f"Image not accessible: {url} (status: {response.status_code})")
            except requests.RequestException as e:
                print(f"Error validating image {url}: {e}")
            except Exception as e:
                print(f"Unexpected error validating image {url}: {e}")
        
        return valid_urls


class WebSearchValidator:
    """Utility class for web search validation."""
    
    @staticmethod
    def extract_external_domains(url: str) -> List[str]:
        """Extract domains from URL that might indicate newsworthy content."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return [domain] if domain else []
        except Exception:
            return []
    
    @staticmethod
    def extract_product_mentions(text: str) -> List[str]:
        """Extract potential product/company names from text."""
        # Common tech product patterns
        patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:v\d|version|release|beta|alpha)\b',  # Version mentions
            r'\b[A-Z][a-zA-Z]*(?:AI|API|SDK|CLI|IDE|OS)\b',  # Tech acronyms
            r'\b(?:launched|released|announced)\s+([A-Z][a-zA-Z\s]+)',  # "launched ProductName"
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:just|now|today)\s+(?:launched|released)',  # "ProductName just launched"
        ]
        
        mentions = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Handle both string matches and tuple matches from capture groups
                for match in matches:
                    if isinstance(match, tuple):
                        mentions.extend([m for m in match if m])  # Add non-empty captures
                    else:
                        mentions.append(match)
        
        # Filter out common false positives
        false_positives = {'the', 'and', 'for', 'with', 'this', 'that', 'have', 'been', 'will', 'would', 'could', 'should'}
        return [mention.strip() for mention in mentions if mention.lower().strip() not in false_positives]