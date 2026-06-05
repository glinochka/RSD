"""Sanitization service for Website Builder content.

Provides HTML and CSS sanitization to prevent XSS and CSS injection attacks.
"""

import re
import html
from typing import List, Set, Optional
import bleach
from bleach.css_sanitizer import CSSSanitizer


# Allowed HTML tags for user content (block-level editing)
ALLOWED_TAGS: Set[str] = {
    'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 'strike', 'del', 's',
    'a', 'img',
    'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'hr',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
}

# Extended tags for fullpage AI-generated HTML (includes interactive elements)
FULLPAGE_ALLOWED_TAGS: Set[str] = {
    # Standard content
    'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 'strike', 'del', 's',
    'a', 'img',
    'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'hr',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
    # Semantic structure
    'header', 'nav', 'main', 'section', 'article', 'aside', 'footer',
    'figure', 'figcaption', 'details', 'summary',
    # Forms (for contact forms)
    'form', 'input', 'textarea', 'button', 'label', 'select', 'option',
    # Interactive elements
    'script', 'style', 'svg', 'path', 'circle', 'rect', 'line', 'polyline',
    'polygon', 'ellipse', 'g', 'defs', 'use', 'text', 'tspan',
    # Media
    'video', 'audio', 'source', 'track',
    # Other
    'iframe', 'embed', 'object', 'param',
    'canvas', 'progress', 'meter',
}

# Allowed HTML attributes
ALLOWED_ATTRIBUTES: dict = {
    '*': ['class', 'id', 'style'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading'],
    'table': ['border', 'cellpadding', 'cellspacing'],
}

# Allowed CSS properties (inline styles)
ALLOWED_CSS_PROPERTIES: Set[str] = {
    # Text
    'color', 'font-size', 'font-family', 'font-weight', 'font-style',
    'text-align', 'text-decoration', 'text-transform', 'line-height',
    'letter-spacing', 'word-spacing',
    # Spacing
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    # Layout
    'display', 'width', 'height', 'max-width', 'max-height', 'min-width', 'min-height',
    'border', 'border-top', 'border-right', 'border-bottom', 'border-left',
    'border-radius', 'border-collapse',
    'background', 'background-color', 'background-image', 'background-size',
    'position', 'top', 'right', 'bottom', 'left', 'z-index',
    'float', 'clear', 'overflow', 'overflow-x', 'overflow-y',
    'visibility', 'opacity',
    # Flexbox/Grid
    'flex', 'flex-direction', 'flex-wrap', 'flex-flow', 'justify-content',
    'align-items', 'align-content', 'order', 'flex-grow', 'flex-shrink', 'flex-basis',
    'align-self', 'gap', 'column-gap', 'row-gap',
    'grid', 'grid-template', 'grid-template-columns', 'grid-template-rows',
    'grid-column', 'grid-row', 'grid-area',
    # Other
    'cursor', 'pointer-events', 'user-select',
    'box-shadow', 'text-shadow',
    'transition', 'transform',
    'list-style', 'list-style-type', 'list-style-position',
}

# Dangerous CSS properties that should never be allowed
FORBIDDEN_CSS_PROPERTIES: Set[str] = {
    'behavior',  # IE expression
    'binding',   # Mozilla XBL
    '-moz-binding',
}

# Dangerous CSS values patterns
DANGEROUS_CSS_PATTERNS: List[str] = [
    r'expression\s*\(',  # CSS expressions (IE)
    r'javascript:',      # JavaScript URLs
    r'vbscript:',        # VBScript URLs
    r'data:text/html',   # Data URIs with HTML
    r'data:application/x-javascript',
    r'@import',          # External imports
    r'url\s*\(\s*["\']?\s*javascript:',  # JavaScript in url()
]

# Dangerous HTML event handlers
DANGEROUS_ATTRS_PATTERN = re.compile(
    r'^(on|xmlns|xlink:href|formaction|lowsrc|dynsrc)',
    re.IGNORECASE
)

# URL protocols that are allowed
ALLOWED_URL_PROTOCOLS: Set[str] = {'http', 'https', 'mailto', 'tel'}

# Dangerous URL schemes
DANGEROUS_URL_SCHEMES: Set[str] = {
    'javascript', 'vbscript', 'data', 'file', 'about', 'chrome', 'resource',
}


class WebsiteSanitizationService:
    """Service for sanitizing user-generated content for websites."""
    
    def __init__(self):
        """Initialize the sanitization service."""
        # Create CSS sanitizer with allowed properties
        self.css_sanitizer = CSSSanitizer(
            allowed_css_properties=list(ALLOWED_CSS_PROPERTIES)
        )
    
    def sanitize_html(
        self,
        content: str,
        allowed_tags: Optional[Set[str]] = None,
        allowed_attrs: Optional[dict] = None,
        strip_disallowed: bool = True,
    ) -> str:
        """Sanitize HTML content.
        
        Removes dangerous tags and attributes while preserving safe content.
        
        Args:
            content: Raw HTML content
            allowed_tags: Override default allowed tags
            allowed_attrs: Override default allowed attributes
            strip_disallowed: If True, remove disallowed tags; if False, escape them
            
        Returns:
            Sanitized HTML string
        """
        if not content:
            return ""
        
        tags = allowed_tags or ALLOWED_TAGS
        attrs = allowed_attrs or ALLOWED_ATTRIBUTES
        
        # First pass: Use bleach for basic sanitization
        sanitized = bleach.clean(
            content,
            tags=list(tags),
            attributes=attrs,
            strip=strip_disallowed,
            css_sanitizer=self.css_sanitizer,
        )
        
        # Second pass: Additional cleaning for edge cases
        sanitized = self._clean_remaining_dangers(sanitized)
        
        return sanitized

    def sanitize_fullpage_html(
        self,
        content: str,
        strip_disallowed: bool = True,
    ) -> str:
        """Sanitize AI-generated fullpage HTML content.
        
        Allows more tags including script and style for interactive elements,
        but removes dangerous patterns like event handlers and javascript: URLs.
        
        Args:
            content: Raw HTML content from AI generation
            strip_disallowed: If True, remove disallowed tags; if False, escape them
            
        Returns:
            Sanitized HTML string safe for rendering in iframe
        """
        if not content:
            return ""
        
        # Extended attributes for fullpage content
        fullpage_attrs = {
            **ALLOWED_ATTRIBUTES,
            'script': ['src', 'type', 'async', 'defer'],
            'style': ['type', 'media', 'scoped'],
            'svg': ['viewBox', 'fill', 'stroke', 'stroke-width', 'xmlns'],
            'path': ['d', 'fill', 'stroke', 'stroke-width'],
            'input': ['type', 'name', 'placeholder', 'value', 'required', 'disabled', 'readonly', 'maxlength'],
            'textarea': ['name', 'placeholder', 'rows', 'cols', 'required', 'disabled', 'readonly', 'maxlength'],
            'button': ['type', 'disabled'],
            'form': ['action', 'method', 'enctype'],
            'video': ['src', 'controls', 'autoplay', 'loop', 'muted', 'poster', 'width', 'height'],
            'audio': ['src', 'controls', 'autoplay', 'loop', 'muted'],
            'source': ['src', 'type'],
            'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen'],
        }
        
        # First pass: Use bleach with extended tags
        sanitized = bleach.clean(
            content,
            tags=list(FULLPAGE_ALLOWED_TAGS),
            attributes=fullpage_attrs,
            strip=strip_disallowed,
            css_sanitizer=self.css_sanitizer,
        )
        
        # Second pass: Clean dangerous patterns (event handlers, JS URLs)
        sanitized = self._clean_fullpage_dangers(sanitized)
        
        return sanitized

    def _clean_fullpage_dangers(self, html: str) -> str:
        """Clean dangerous patterns from fullpage HTML while preserving safe scripts."""
        if not html:
            return html
        
        # Remove event handlers (onclick, onload, onerror, etc.)
        # Use regex to match on* attributes
        html = re.sub(
            r'\s+on\w+\s*=\s*(["\'][^"\']*["\']|[^\s>]+)',
            '',
            html,
            flags=re.IGNORECASE
        )
        
        # Remove javascript: URLs in href/src
        html = re.sub(
            r'\s(href|src|action)\s*=\s*["\']\s*javascript:[^"\']*["\']',
            r' \1="#"',
            html,
            flags=re.IGNORECASE
        )
        
        # Remove vbscript: URLs
        html = re.sub(
            r'\s(href|src|action)\s*=\s*["\']\s*vbscript:[^"\']*["\']',
            r' \1="#"',
            html,
            flags=re.IGNORECASE
        )
        
        # Remove data:text/html URLs
        html = re.sub(
            r'\s(href|src|action)\s*=\s*["\']\s*data:text/html[^"\']*["\']',
            r' \1="#"',
            html,
            flags=re.IGNORECASE
        )
        
        # Check for dangerous script patterns
        # Block document.write, eval, and dynamic script injection
        dangerous_js_patterns = [
            r'document\.write\s*\(',
            r'document\.writeln\s*\(',
            r'eval\s*\(',
            r'Function\s*\(\s*["\']',
            r'setTimeout\s*\(\s*["\']',
            r'setInterval\s*\(\s*["\']',
            r'new\s+Function\s*\(',
            r'importScripts\s*\(',
            r'XMLHttpRequest',
            r'fetch\s*\(',
            r'WebSocket',
        ]
        
        # If dangerous patterns found in inline scripts, escape the script content
        def escape_dangerous_scripts(match):
            script_content = match.group(1)
            for pattern in dangerous_js_patterns:
                if re.search(pattern, script_content, re.IGNORECASE):
                    # Escape the entire script tag
                    return f'<!-- Script blocked due to dangerous pattern: {match.group(0)[:100]}... -->'
            return match.group(0)
        
        # Check script tags for dangerous patterns
        html = re.sub(
            r'<script[^>]*>(.*?)</script>',
            escape_dangerous_scripts,
            html,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        return html
    
    def sanitize_css(self, css: str) -> str:
        """Sanitize CSS content.
        
        Removes dangerous CSS rules and properties.
        
        Args:
            css: Raw CSS content
            
        Returns:
            Sanitized CSS string
        """
        if not css:
            return ""
        
        # Remove comments
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        
        # Check for dangerous patterns
        for pattern in DANGEROUS_CSS_PATTERNS:
            css = re.sub(pattern, '', css, flags=re.IGNORECASE)
        
        # Remove @import, @keyframes, @font-face
        css = re.sub(r'@\s*(import|keyframes|font-face|charset|namespace)[^;]*;', '', css, flags=re.IGNORECASE)
        css = re.sub(r'@\s*(media|supports|document)[^{]*\{[^}]*\}', '', css, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove forbidden properties
        for prop in FORBIDDEN_CSS_PROPERTIES:
            pattern = r'[;\s]' + re.escape(prop) + r'\s*:'
            css = re.sub(pattern, ':', css, flags=re.IGNORECASE)
        
        return css.strip()
    
    def sanitize_url(self, url: str) -> Optional[str]:
        """Sanitize URL to prevent JavaScript injection.
        
        Args:
            url: URL string to sanitize
            
        Returns:
            Sanitized URL or None if dangerous
        """
        if not url:
            return None
        
        url = url.strip()
        
        # Check for dangerous URL schemes
        lower_url = url.lower()
        for scheme in DANGEROUS_URL_SCHEMES:
            if lower_url.startswith(f'{scheme}:'):
                return None
        
        # Check for other dangerous patterns
        if re.search(r'[<>"\']', url):
            return None
        
        # Allow relative URLs
        if url.startswith('/') or url.startswith('./') or url.startswith('../'):
            return url
        
        # Check protocol
        protocol_match = re.match(r'^([a-z][a-z0-9+.-]*):', lower_url)
        if protocol_match:
            protocol = protocol_match.group(1)
            if protocol not in ALLOWED_URL_PROTOCOLS:
                return None
        
        return url
    
    def sanitize_json_content(self, content: dict) -> dict:
        """Recursively sanitize JSON content.
        
        Sanitizes all string values in a JSON object.
        
        Args:
            content: Dictionary with content to sanitize
            
        Returns:
            Sanitized dictionary
        """
        if isinstance(content, dict):
            return {
                key: self.sanitize_json_content(value)
                for key, value in content.items()
            }
        elif isinstance(content, list):
            return [self.sanitize_json_content(item) for item in content]
        elif isinstance(content, str):
            # Check if it looks like HTML
            if '<' in content and '>' in content:
                return self.sanitize_html(content)
            return content
        else:
            return content
    
    def validate_block_content(self, content: dict) -> tuple[bool, list]:
        """Validate website block content for security issues.
        
        Args:
            content: Block content dictionary
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        def check_value(value, path=""):
            if isinstance(value, str):
                # Check for suspicious patterns
                lower_value = value.lower()
                
                # Check for script tags
                if re.search(r'<script[^>]*>', lower_value):
                    issues.append(f"Script tag detected at {path}")
                
                # Check for event handlers
                if re.search(r'\s(on\w+)\s*=', lower_value):
                    issues.append(f"Event handler detected at {path}")
                
                # Check for JavaScript URLs
                if 'javascript:' in lower_value:
                    issues.append(f"JavaScript URL detected at {path}")
                
                # Check for iframe
                if re.search(r'<iframe[^>]*>', lower_value):
                    issues.append(f"Iframe detected at {path}")
                
                # Check for object/embed
                if re.search(r'<(object|embed|applet)[^>]*>', lower_value):
                    issues.append(f"Object/embed/applet detected at {path}")
                
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_value(v, f"{path}.{k}" if path else k)
                    
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    check_value(v, f"{path}[{i}]")
        
        check_value(content)
        
        return len(issues) == 0, issues
    
    def _clean_remaining_dangers(self, html: str) -> str:
        """Additional cleaning for edge cases bleach might miss."""
        # Remove any remaining dangerous attributes
        # This regex matches on* attributes
        html = re.sub(
            r'\s+on\w+\s*=\s*(["\'][^"\']*["\']|[^\s>]+)',
            '',
            html,
            flags=re.IGNORECASE
        )
        
        # Remove xmlns attributes
        html = re.sub(
            r'\s+xmlns\w*\s*=\s*["\'][^"\']*["\']',
            '',
            html,
            flags=re.IGNORECASE
        )
        
        # Remove javascript: URLs that might remain
        html = re.sub(
            r'javascript:\s*[^"\'>\s]*',
            '',
            html,
            flags=re.IGNORECASE
        )
        
        return html


# Singleton instance
_sanitization_service: Optional[WebsiteSanitizationService] = None


def get_website_sanitization_service() -> WebsiteSanitizationService:
    """Get or create singleton instance of sanitization service."""
    global _sanitization_service
    if _sanitization_service is None:
        _sanitization_service = WebsiteSanitizationService()
    return _sanitization_service


def sanitize_user_content(content: str) -> str:
    """Convenience function to sanitize user content."""
    service = get_website_sanitization_service()
    return service.sanitize_html(content)


def sanitize_css_content(css: str) -> str:
    """Convenience function to sanitize CSS content."""
    service = get_website_sanitization_service()
    return service.sanitize_css(css)
