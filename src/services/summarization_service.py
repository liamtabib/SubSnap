"""AI summarization engine."""

import openai
import traceback
from typing import Optional, Dict, Any, List

from core.config import Config
from models.reddit_models import RedditPost
from core.constants import Constants
from models.ai_models import PostSummary, UsageStats
from services.image_analysis_service import ImageAnalysisService
from services.web_search_service import WebSearchService


class SummarizationService:
    """Main AI summarization engine with fallback chain."""
    
    def __init__(self, config: Config):
        """Initialize AI summarizer."""
        self.config = config
        self.openai_client = None
        
        # Initialize OpenAI client
        if config.openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=config.openai_api_key)
                print("OpenAI client initialized successfully")
            except Exception as e:
                print(f"Error initializing OpenAI client: {e}")
                self.openai_client = None
        else:
            print("WARNING: OpenAI API key not available - summaries will be skipped")
        
        # Initialize components
        self.image_analyzer = ImageAnalysisService(config.image_analysis)
        self.web_search_manager = WebSearchService(config.web_search)
    
    def count_tokens(self, text: str) -> int:
        """Count the approximate number of tokens in a text string."""
        # Simple approximation: 1 token ≈ 4 characters for English text
        return len(text) // Constants.TOKEN_ESTIMATION_RATIO
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximately the specified number of tokens."""
        if self.count_tokens(text) <= max_tokens:
            return text
        
        # Approximate truncation (rough estimate)
        char_limit = max_tokens * Constants.TOKEN_ESTIMATION_RATIO - 10
        return text[:char_limit] + "... [truncated]"
    
    def create_multimodal_system_prompt(self, subreddit_name: str, has_images: bool) -> str:
        """Create system prompt optimized for multimodal content."""
        base_prompt = f"You are summarizing a Reddit post from r/{subreddit_name}. "
        
        if has_images:
            base_prompt += """
The post includes both text and images. When analyzing images:
- For screenshots: Describe key UI elements, code, or technical details shown
- For diagrams: Explain the concepts or architecture illustrated  
- For product demos: Describe what's being showcased
- For code/terminal screenshots: Mention key technical details visible
- Integrate visual and text information into a cohesive summary

IMPORTANT: Keep image descriptions concise and relevant to the post's main point.
"""
        
        base_prompt += """
IMPORTANT CURRENT KNOWLEDGE (2025):
- Claude Code: Anthropic's official CLI tool for Claude, enables terminal-based AI coding assistance with file editing and command execution
- Vibe Coding: A development approach centered on using AI-driven workflows and tools for coding efficiency
- MCP (Model Context Protocol): A protocol that allows AI models to interface with external tools and systems
- o3: An OpenAI large language model similar to GPT-4o but with specific tooling optimizations
- RAG: Retrieval Augmented Generation, a technique for enhancing AI responses with retrieved context
- Claude 4: Anthropic's flagship large language model released in 2024-2025
- AI Agents: Autonomous systems that can perform tasks, make decisions, and interact with APIs/tools
- SideProject: Term for personal projects developers build in their spare time, often to solve problems or learn new technologies
- Linear: A project management and issue tracking tool popular with development teams
- Anthropic: AI safety company that created Claude, focused on developing helpful, harmless, and honest AI systems

Use casual, conversational language. Keep summaries proportional to content complexity.
DO NOT use emojis. DO NOT address the reader directly. Give a concise, brief summary of what the post actually says.
"""
        
        return base_prompt
    
    def create_web_search_system_prompt(self, subreddit_name: str, has_images: bool) -> str:
        """Create system prompt for web search enabled summarization."""
        base_prompt = self.create_multimodal_system_prompt(subreddit_name, has_images)
        
        # Add web search specific instructions
        web_search_instructions = """

WEB SEARCH CAPABILITIES:
You have access to web search to enhance summaries with current information.

CRITICAL: Keep summaries concise (2-3 sentences max). Web search should add VALUE, not LENGTH.

When web search provides useful context:
- Add 1-2 brief sentences with current info (e.g., "The app is available on Google Play as 'AppName'" or "Recent updates show pricing at $X/month")
- Only mention information that directly relates to the post
- Do NOT include detailed feature lists, competitor analysis, or lengthy explanations
- Focus on: current availability, recent changes, or factual corrections only

ALWAYS prioritize brevity over completeness. A short, accurate summary is better than a long, detailed one.
"""
        
        return base_prompt + web_search_instructions
    
    def summarize_post_content_with_web_search(self, post: RedditPost) -> Optional[Dict[str, Any]]:
        """Enhanced post summarization using OpenAI Responses API with web search."""
        print(f"Attempting web search summarization: {post.title[:30]}...")
        
        if not self.openai_client:
            print("OpenAI API key not available. Skipping post summarization.")
            return None
        
        # Check if we can and should perform web search
        can_search, reason = self.web_search_manager.can_perform_search(post)
        if not can_search:
            if self.config.web_search.test_mode:
                print(f"Cannot perform web search: {reason}")
            return None
        
        # Detect and validate images
        valid_images = self.image_analyzer.detect_images(post)
        has_images = len(valid_images) > 0
        
        try:
            # Prepare content for API call
            content_array = []
            
            # Add text content
            title = post.title
            body = self.truncate_to_tokens(post.body, Constants.MAX_POST_TOKENS)
            search_guidance = self.web_search_manager.create_search_guidance_context(post)
            
            text_content = f"Title: {title}\n\nContent: {body}"
            if search_guidance:
                text_content += f"\n\nSearch guidance: {search_guidance}"
            
            content_array.append({"type": "text", "text": text_content})
            
            # Add images if we have them
            if has_images:
                max_images = min(len(valid_images), self.config.image_analysis.max_images_per_post)
                for img_url in valid_images[:max_images]:
                    content_array.append({
                        "type": "image_url",
                        "image_url": {"url": img_url, "detail": "low"}
                    })
            
            # Prepare input for Responses API
            system_prompt = self.create_web_search_system_prompt(post.subreddit, has_images)
            
            # Use correct Responses API format
            if has_images and len(valid_images) > 0:
                input_content = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": f"{system_prompt}\n\nAnalyze this Reddit post: {text_content}"
                            }
                        ] + [
                            {
                                "type": "input_image",
                                "image_url": img_url
                            } for img_url in valid_images[:max_images]
                        ]
                    }
                ]
            else:
                input_content = f"{system_prompt}\n\nAnalyze this Reddit post: {text_content}"
            
            # API call with web search tool using Responses API
            response = self.openai_client.responses.create(
                model="gpt-4o",
                input=input_content,
                tools=[{"type": "web_search"}]
            )
            
            # Record successful search
            self.web_search_manager.circuit_breaker.record_success()
            
            # Extract summary and usage
            summary = self._extract_summary_from_response(response)
            web_search_used = self._check_web_search_usage(response)
            usage_stats = self._extract_usage_stats(response, valid_images, web_search_used)
            
            # Update cost tracking
            if web_search_used:
                self.web_search_manager.cost_tracker.record_search(
                    post.title,
                    actual_cost=usage_stats.web_search_cost,
                    success=True
                )
            
            if self.config.web_search.test_mode:
                print(f"Web search summary completed: web_search_used={web_search_used}, cost=${usage_stats.estimated_cost:.4f}")
            
            return {"summary": summary, "usage": usage_stats}
            
        except Exception as e:
            print(f"ERROR in web search summarization: {e}")
            
            # Record failure for circuit breaker
            self.web_search_manager.circuit_breaker.record_failure()
            
            if self.config.web_search.test_mode:
                print(f"Web search failed: {e}")
                print(f"Traceback: {traceback.format_exc()}")
            
            return None
    
    def summarize_post_content_multimodal(self, post: RedditPost) -> Optional[Dict[str, Any]]:
        """Enhanced post summarization with optional image analysis."""
        print(f"Attempting multimodal summarization: {post.title[:30]}...")
        
        if not self.openai_client:
            print("OpenAI API key not available. Skipping post summarization.")
            return None
        
        # Detect and validate images
        valid_images = self.image_analyzer.detect_images(post)
        has_images = len(valid_images) > 0
        
        if has_images:
            print(f"Processing {len(valid_images)} images with text content")
        
        try:
            # Prepare content for API call
            if has_images:
                content_array = []
                
                # Add text content
                title = post.title
                body = self.truncate_to_tokens(post.body, Constants.MAX_POST_TOKENS)
                text_content = f"Title: {title}\n\nContent: {body}"
                content_array.append({"type": "text", "text": text_content})
                
                # Add images
                max_images = self.config.image_analysis.max_images_per_post
                for img_url in valid_images[:max_images]:
                    content_array.append({
                        "type": "image_url",
                        "image_url": {"url": img_url, "detail": "low"}
                    })
            else:
                # Text-only content
                title = post.title
                body = self.truncate_to_tokens(post.body, Constants.MAX_POST_TOKENS)
                content_array = f"Title: {title}\n\nContent: {body}"
            
            # Create system message
            system_message = {
                "role": "system",
                "content": self.create_multimodal_system_prompt(post.subreddit, has_images)
            }
            
            # Create message array
            messages = [
                system_message,
                {"role": "user", "content": content_array}
            ]
            
            # API call with potential image support
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=200 if has_images else 150,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            usage_stats = UsageStats(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                images_processed=len(valid_images[:max_images]) if has_images else 0,
                estimated_cost=self.image_analyzer.calculate_multimodal_cost(
                    response.usage.__dict__, 
                    len(valid_images[:max_images]) if has_images else 0
                )
            )
            
            if has_images:
                print(f"Multimodal summary generated with {len(valid_images[:max_images])} images (cost: ${usage_stats.estimated_cost:.4f})")
            else:
                print("Text-only summary generated")
            
            return {"summary": summary, "usage": usage_stats}
            
        except Exception as e:
            print(f"ERROR generating multimodal summary: {e}")
            # Fallback to text-only if multimodal fails
            if has_images:
                print("Falling back to text-only summary...")
                return self.summarize_post_content_text_only(post)
            return None
    
    def summarize_post_content_text_only(self, post: RedditPost) -> Optional[Dict[str, Any]]:
        """Basic text-only summarization (fallback)."""
        print(f"Attempting text-only summarization: {post.title[:30]}...")
        
        if not self.openai_client:
            print("OpenAI API key not available. Skipping post summarization.")
            return None
        
        try:
            # Prepare content
            title = post.title
            body = self.truncate_to_tokens(post.body, Constants.MAX_POST_TOKENS)
            post_content = f"Title: {title}\n\nContent: {body}"
            
            # Create system message
            system_message = {
                "role": "system",
                "content": self.create_multimodal_system_prompt(post.subreddit, False)
            }
            
            # Create message array
            messages = [
                system_message,
                {"role": "user", "content": post_content}
            ]
            
            # API call
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=150,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            usage_stats = UsageStats(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            
            return {"summary": summary, "usage": usage_stats}
            
        except Exception as e:
            print(f"ERROR generating text-only summary: {e}")
            return None
    
    def summarize_post_content(self, post: RedditPost) -> Optional[Dict[str, Any]]:
        """Main entry point for post summarization with fallback chain."""
        
        # Try web search enhanced summarization first (if enabled and applicable)
        if self.config.web_search.enabled:
            try:
                result = self.summarize_post_content_with_web_search(post)
                if result is not None:
                    if self.config.web_search.test_mode:
                        print("✓ Used web search enhanced summarization")
                    return result
            except Exception as e:
                if self.config.web_search.test_mode:
                    print(f"✗ Web search summarization failed: {e}")
        
        # Fallback to multimodal summarization
        try:
            result = self.summarize_post_content_multimodal(post)
            if result is not None:
                if self.config.web_search.test_mode:
                    print("✓ Used multimodal summarization (fallback)")
                return result
        except Exception as e:
            if self.config.web_search.test_mode:
                print(f"✗ Multimodal summarization failed: {e}")
        
        # Final fallback to text-only summarization
        try:
            result = self.summarize_post_content_text_only(post)
            if result is not None:
                if self.config.web_search.test_mode:
                    print("✓ Used text-only summarization (final fallback)")
                return result
        except Exception as e:
            if self.config.web_search.test_mode:
                print(f"✗ Text-only summarization failed: {e}")
        
        # All methods failed
        print(f"ERROR: All summarization methods failed for post: {post.title[:50]}...")
        return None
    
    def summarize_comments(self, post: RedditPost) -> Optional[Dict[str, Any]]:
        """Generate a summary of the post comments."""
        if not self.openai_client:
            print("WARNING: OpenAI client not available, skipping comment summary generation")
            return None
        
        # Check if there are comments to summarize
        if not post.comments:
            return {
                "summary": "No comments to summarize.",
                "usage": UsageStats()
            }
        
        try:
            # Prepare comments content
            comments_content = f"Post Title: {post.title}\n\nComments:\n"
            remaining_tokens = Constants.MAX_COMMENT_TOKENS
            tokens_per_comment = remaining_tokens // len(post.comments) if len(post.comments) > 0 else remaining_tokens
            
            for i, comment in enumerate(post.comments, 1):
                truncated_comment = self.truncate_to_tokens(comment.body, tokens_per_comment)
                comments_content += f"{i}. By u/{comment.author}: {truncated_comment}\n"
            
            # Create system message
            system_message = {
                "role": "system",
                "content": f"You are summarizing comments on a Reddit post from r/{post.subreddit}. "
                           "Give a concise, factual summary of the comments. Use casual, conversational language. "
                           "DO NOT use emojis or usernames. Use phrases like 'one user said', 'another person mentioned'."
            }
            
            messages = [
                system_message,
                {"role": "user", "content": comments_content}
            ]
            
            # API call
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=100,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            usage_stats = UsageStats(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            
            print("Comments summary generated successfully")
            return {"summary": summary, "usage": usage_stats}
            
        except Exception as e:
            print(f"Error generating comments summary: {e}")
            return None
    
    def summarize_post(self, post: RedditPost) -> PostSummary:
        """Generate separate summaries for the post content and its comments."""
        # Generate post content summary
        post_summary_data = self.summarize_post_content(post)
        post_summary = None
        post_usage = None
        
        if post_summary_data:
            post_summary = post_summary_data.get('summary')
            usage_data = post_summary_data.get('usage')
            if isinstance(usage_data, UsageStats):
                post_usage = usage_data
            elif isinstance(usage_data, dict):
                post_usage = UsageStats(**usage_data)
        
        # Generate comments summary
        comments_summary_data = self.summarize_comments(post)
        comments_summary = None
        comments_usage = None
        
        if comments_summary_data:
            comments_summary = comments_summary_data.get('summary')
            usage_data = comments_summary_data.get('usage')
            if isinstance(usage_data, UsageStats):
                comments_usage = usage_data
            elif isinstance(usage_data, dict):
                comments_usage = UsageStats(**usage_data)
        
        return PostSummary(
            post_summary=post_summary,
            comments_summary=comments_summary,
            post_usage=post_usage,
            comments_usage=comments_usage
        )
    
    def _extract_summary_from_response(self, response) -> str:
        """Extract summary from OpenAI response."""
        if hasattr(response, 'choices') and response.choices:
            return response.choices[0].message.content.strip()
        elif hasattr(response, 'output') and response.output:
            for output_item in response.output:
                if hasattr(output_item, 'type') and output_item.type == 'message':
                    if hasattr(output_item, 'content') and output_item.content:
                        for content_item in output_item.content:
                            if hasattr(content_item, 'text'):
                                return content_item.text.strip()
        return str(response).strip()
    
    def _check_web_search_usage(self, response) -> bool:
        """Check if web search was actually used in the response."""
        # Check for standard tool calls
        if hasattr(response, 'choices') and response.choices:
            for choice in response.choices:
                if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        if hasattr(tool_call, 'type') and 'web_search' in str(tool_call.type):
                            return True
        
        # Check for Responses API format
        if hasattr(response, 'output') and hasattr(response.output, 'tool_calls'):
            for tool_call in response.output.tool_calls:
                if tool_call.type == 'web_search_call':
                    return True
        
        return False
    
    def _extract_usage_stats(self, response, valid_images: List[str], web_search_used: bool) -> UsageStats:
        """Extract usage statistics from OpenAI response."""
        try:
            if hasattr(response.usage, 'input_tokens'):
                # Responses API format
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
            else:
                # Chat Completions API format
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
            
            web_search_cost = self.config.web_search.cost_per_search if web_search_used else 0
            estimated_cost = self.image_analyzer.calculate_multimodal_cost(
                {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens},
                len(valid_images)
            ) + web_search_cost
            
            return UsageStats(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                images_processed=len(valid_images),
                web_search_used=web_search_used,
                web_search_cost=web_search_cost,
                estimated_cost=estimated_cost
            )
            
        except AttributeError:
            # Fallback if usage structure is unexpected
            return UsageStats(
                web_search_used=web_search_used,
                web_search_cost=web_search_cost,
                estimated_cost=web_search_cost
            )