"""CSS Isolation service for Website Builder.

Provides CSS scoping to prevent styles from one website affecting others.
Uses class prefixing technique: .site-{website_id} selector prefixing.
"""

import re
import hashlib
from typing import Optional
from dataclasses import dataclass


@dataclass
class ScopedCSSResult:
    """Result of CSS scoping operation."""
    css: str
    scope_class: str
    original_hash: str


class WebsiteCSSIsolationService:
    """Service for isolating CSS between different websites.
    
    This service adds scope prefixes to all CSS selectors to ensure
    styles from one website don't leak to others on the same page.
    
    Example:
        Input:  `.header { color: red; }`
        Output: `.site-123 .header { color: red; }`
    """
    
    # CSS at-rules that contain selectors
    SELECTOR_AT_RULES = {'media', 'supports', 'container', 'layer'}
    
    # CSS at-rules that don't contain selectors
    NON_SELECTOR_AT_RULES = {'import', 'charset', 'namespace', 'font-face', 'keyframes', 'property'}
    
    def __init__(self):
        """Initialize CSS isolation service."""
        # Regex to match CSS selectors (simplified, handles most common cases)
        # Matches rule sets: selector { properties }
        self.rule_pattern = re.compile(
            r'([^{}@]+)\{([^}]*)\}',
            re.DOTALL
        )
        
        # Regex to match at-rules
        self.atrule_pattern = re.compile(
            r'@(\w+)\s+([^{;]+)(?:\{([^}]*)\})?',
            re.DOTALL
        )
        
        # Pattern to match :host and :root selectors
        self.host_root_pattern = re.compile(r':(host|root)\b')
    
    def generate_scope_class(self, website_id: int) -> str:
        """Generate scope class name for a website.
        
        Args:
            website_id: Website ID
            
        Returns:
            Scope class name like 'site-123'
        """
        return f"site-{website_id}"
    
    def generate_unique_id(self, website_id: int, salt: str = "") -> str:
        """Generate unique identifier for CSS class names.
        
        Creates short hash for use with CSS-in-JS style class names.
        
        Args:
            website_id: Website ID
            salt: Additional salt for uniqueness
            
        Returns:
            Short unique identifier
        """
        hash_input = f"{website_id}:{salt}"
        hash_bytes = hashlib.md5(hash_input.encode()).digest()
        # Use base36 for shorter representation
        return self._bytes_to_base36(hash_bytes[:4])
    
    def _bytes_to_base36(self, data: bytes) -> str:
        """Convert bytes to base36 string."""
        num = int.from_bytes(data, 'big')
        alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
        if num == 0:
            return '0'
        result = ''
        while num > 0:
            num, rem = divmod(num, 36)
            result = alphabet[rem] + result
        return result[:6]  # Limit to 6 chars
    
    def scope_css(self, css: str, website_id: int) -> ScopedCSSResult:
        """Add scope prefix to all CSS selectors.
        
        Wraps all selectors with the website scope class to isolate styles.
        
        Args:
            css: Original CSS content
            website_id: Website ID for scope generation
            
        Returns:
            ScopedCSSResult with transformed CSS
        """
        if not css or not css.strip():
            return ScopedCSSResult(css="", scope_class=self.generate_scope_class(website_id), original_hash="")
        
        scope_class = self.generate_scope_class(website_id)
        
        # Calculate hash of original CSS for cache busting
        original_hash = hashlib.md5(css.encode()).hexdigest()[:8]
        
        # Process CSS
        scoped_css = self._scope_css_content(css, scope_class)
        
        return ScopedCSSResult(
            css=scoped_css,
            scope_class=scope_class,
            original_hash=original_hash,
        )
    
    def _scope_css_content(self, css: str, scope_class: str) -> str:
        """Process CSS content and add scope prefixes."""
        result = []
        i = 0
        
        while i < len(css):
            # Skip whitespace
            while i < len(css) and css[i] in ' \t\n\r':
                result.append(css[i])
                i += 1
            
            if i >= len(css):
                break
            
            # Check for at-rules
            if css[i] == '@':
                at_rule_result, new_i = self._process_at_rule(css, i, scope_class)
                result.append(at_rule_result)
                i = new_i
            # Check for comments
            elif css[i:i+2] == '/*':
                comment_end = css.find('*/', i + 2)
                if comment_end == -1:
                    comment_end = len(css)
                else:
                    comment_end += 2
                result.append(css[i:comment_end])
                i = comment_end
            # Regular rule
            elif css[i] != '}':
                rule_result, new_i = self._process_rule(css, i, scope_class)
                result.append(rule_result)
                i = new_i
            else:
                i += 1
        
        return ''.join(result)
    
    def _process_at_rule(self, css: str, start: int, scope_class: str) -> tuple[str, int]:
        """Process an at-rule (like @media, @keyframes)."""
        # Find the at-rule name
        match = re.match(r'@(\w+)', css[start:])
        if not match:
            # Not a valid at-rule, return as-is
            return css[start], start + 1
        
        rule_name = match.group(1).lower()
        
        # Handle non-selector at-rules (import, charset, etc.)
        if rule_name in self.NON_SELECTOR_AT_RULES:
            # Find the end of the rule (semicolon or block)
            if rule_name in {'font-face', 'keyframes', 'property'}:
                # Block-based
                block_start = css.find('{', start)
                if block_start == -1:
                    return css[start:], len(css)
                
                block_end = self._find_matching_brace(css, block_start)
                if rule_name == 'keyframes':
                    # Don't scope keyframes content, but scope from outside
                    return css[start:block_end+1], block_end + 1
                else:
                    return css[start:block_end+1], block_end + 1
            else:
                # Semicolon-based
                end = css.find(';', start)
                if end == -1:
                    return css[start:], len(css)
                return css[start:end+1], end + 1
        
        # Handle selector-containing at-rules (media, supports, container, layer)
        if rule_name in self.SELECTOR_AT_RULES:
            # Find the block
            block_start = css.find('{', start)
            if block_start == -1:
                return css[start:], len(css)
            
            at_rule_prefix = css[start:block_start+1]
            
            # Find matching closing brace
            block_end = self._find_matching_brace(css, block_start)
            
            # Process content inside the block
            inner_content = css[block_start+1:block_end]
            scoped_inner = self._scope_css_content(inner_content, scope_class)
            
            return f"{at_rule_prefix}{scoped_inner}}}", block_end + 1
        
        # Unknown at-rule, return as-is
        block_start = css.find('{', start)
        if block_start == -1:
            return css[start:], len(css)
        block_end = self._find_matching_brace(css, block_start)
        return css[start:block_end+1], block_end + 1
    
    def _process_rule(self, css: str, start: int, scope_class: str) -> tuple[str, int]:
        """Process a CSS rule (selectors + declaration block)."""
        # Find the opening brace
        brace_start = css.find('{', start)
        if brace_start == -1:
            return css[start:], len(css)
        
        # Extract selectors
        selectors_str = css[start:brace_start].strip()
        
        # Find matching closing brace
        brace_end = self._find_matching_brace(css, brace_start)
        
        # Extract declarations
        declarations = css[brace_start+1:brace_end].strip()
        
        # Scope the selectors
        scoped_selectors = self._scope_selectors(selectors_str, scope_class)
        
        # Build scoped rule
        scoped_rule = f"{scoped_selectors} {{{declarations}}}"
        
        return scoped_rule, brace_end + 1
    
    def _scope_selectors(self, selectors_str: str, scope_class: str) -> str:
        """Add scope prefix to selectors."""
        if not selectors_str:
            return selectors_str
        
        # Split by comma (multiple selectors)
        selectors = [s.strip() for s in selectors_str.split(',')]
        scoped_selectors = []
        
        for selector in selectors:
            if not selector:
                continue
            
            # Skip :root and :host - don't scope them
            if self.host_root_pattern.match(selector):
                scoped_selectors.append(selector)
            # Skip @ rules inside selectors (shouldn't happen but safety)
            elif selector.startswith('@'):
                scoped_selectors.append(selector)
            # Universal selector
            elif selector == '*':
                scoped_selectors.append(f".{scope_class} *")
            # Regular selector
            else:
                # Add scope prefix
                # Handle complex selectors like .class:hover > .child
                scoped = self._add_scope_to_complex_selector(selector, scope_class)
                scoped_selectors.append(scoped)
        
        return ', '.join(scoped_selectors)
    
    def _add_scope_to_complex_selector(self, selector: str, scope_class: str) -> str:
        """Add scope to a potentially complex selector."""
        # Handle combinators: > + ~ (space)
        # Split by combinators while preserving them
        parts = re.split(r'(\s*[>+~]\s*|\s+)', selector)
        
        # First part gets the scope
        if parts:
            parts[0] = f".{scope_class} {parts[0]}"
        
        return ''.join(parts)
    
    def _find_matching_brace(self, text: str, open_brace_pos: int) -> int:
        """Find the position of the matching closing brace."""
        depth = 1
        i = open_brace_pos + 1
        
        while i < len(text) and depth > 0:
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
            i += 1
        
        return i - 1
    
    def generate_scoped_html_class(self, website_id: int, original_class: str) -> str:
        """Generate a scoped CSS class name for use in HTML.
        
        This creates unique class names that won't conflict with other websites.
        
        Args:
            website_id: Website ID
            original_class: Original class name
            
        Returns:
            Scoped class name
        """
        unique_id = self.generate_unique_id(website_id, original_class)
        return f"wb-{website_id}-{unique_id}"
    
    def wrap_html_with_scope(self, html: str, website_id: int) -> str:
        """Wrap HTML content with a scope container.
        
        Args:
            html: HTML content
            website_id: Website ID
            
        Returns:
            HTML wrapped in scope container
        """
        scope_class = self.generate_scope_class(website_id)
        return f'<div class="{scope_class}">{html}</div>'


# Singleton instance
_css_isolation_service: Optional[WebsiteCSSIsolationService] = None


def get_website_css_isolation_service() -> WebsiteCSSIsolationService:
    """Get or create singleton instance of CSS isolation service."""
    global _css_isolation_service
    if _css_isolation_service is None:
        _css_isolation_service = WebsiteCSSIsolationService()
    return _css_isolation_service


def scope_css_for_website(css: str, website_id: int) -> str:
    """Convenience function to scope CSS for a website."""
    service = get_website_css_isolation_service()
    result = service.scope_css(css, website_id)
    return result.css
