"""SEO service for Website Builder - favicon conversion and OG image generation."""

import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageDraw, ImageFont


# Favicon sizes to generate
FAVICON_SIZES = [16, 32, 48, 64, 128, 180, 192, 256]

# OG Image dimensions (OpenGraph standard)
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630


@dataclass
class FaviconResult:
    """Result of favicon conversion."""

    success: bool
    files: dict[str, bytes]  # size -> image bytes
    error_message: str | None = None


@dataclass
class OGImageResult:
    """Result of OG image generation."""

    success: bool
    image_bytes: bytes | None = None
    content_type: str = "image/png"
    error_message: str | None = None


class WebsiteSEOService:
    """Service for handling SEO-related image operations."""

    def __init__(self, storage_path: str | None = None):
        """Initialize SEO service.

        Args:
            storage_path: Base path for storing generated images
        """
        self.storage_path = storage_path or os.getenv(
            "WEBSITE_ASSETS_PATH", "/tmp/website_assets"
        )
        self.favicon_path = os.path.join(self.storage_path, "favicons")
        self.og_image_path = os.path.join(self.storage_path, "og_images")

        # Ensure directories exist
        Path(self.favicon_path).mkdir(parents=True, exist_ok=True)
        Path(self.og_image_path).mkdir(parents=True, exist_ok=True)

    def _get_storage_path(self, website_id: int, filename: str) -> str:
        """Get full storage path for a file."""
        website_dir = os.path.join(self.storage_path, str(website_id))
        Path(website_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(website_dir, filename)

    def convert_favicon(
        self,
        image_data: BinaryIO,
        original_filename: str,
        website_id: int,
    ) -> FaviconResult:
        """Convert uploaded image to multiple favicon sizes.

        Args:
            image_data: Binary image data
            original_filename: Original filename for extension detection
            website_id: Website ID for storage organization

        Returns:
            FaviconResult with generated files
        """
        try:
            # Open image
            img = Image.open(image_data)

            # Convert to RGBA if necessary
            if img.mode not in ("RGBA", "RGB", "P"):
                img = img.convert("RGBA")

            # Generate favicons for different sizes
            files = {}

            # Generate individual PNG files
            for size in FAVICON_SIZES:
                resized = self._resize_for_favicon(img, size)
                output = io.BytesIO()
                resized.save(output, format="PNG", optimize=True)
                files[f"{size}x{size}"] = output.getvalue()

            # Generate ICO file (16, 32, 48 sizes combined)
            ico_sizes = [16, 32, 48]
            ico_images = [self._resize_for_favicon(img, s) for s in ico_sizes]
            ico_output = io.BytesIO()
            ico_images[0].save(
                ico_output,
                format="ICO",
                sizes=[(s, s) for s in ico_sizes],
                append_images=ico_images[1:],
            )
            files["favicon.ico"] = ico_output.getvalue()

            # Save files to storage
            saved_files = {}
            favicon_id = str(uuid.uuid4())[:8]

            for size_name, data in files.items():
                if size_name == "favicon.ico":
                    filename = f"favicon-{favicon_id}.ico"
                else:
                    filename = f"favicon-{favicon_id}-{size_name}.png"

                filepath = self._get_storage_path(website_id, filename)
                with open(filepath, "wb") as f:
                    f.write(data)

                saved_files[size_name] = filepath

            return FaviconResult(success=True, files=saved_files)

        except Exception as e:
            return FaviconResult(
                success=False,
                files={},
                error_message=f"Favicon conversion failed: {str(e)}"
            )

    def _resize_for_favicon(self, img: Image.Image, size: int) -> Image.Image:
        """Resize image for favicon, maintaining aspect ratio with transparency."""
        # Create transparent background
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))

        # Calculate resize dimensions maintaining aspect ratio
        img_ratio = img.width / img.height
        if img_ratio > 1:
            new_width = size
            new_height = int(size / img_ratio)
        else:
            new_height = size
            new_width = int(size * img_ratio)

        # Resize with high quality
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Center the image
        x_offset = (size - new_width) // 2
        y_offset = (size - new_height) // 2

        # Paste with alpha if available
        if resized.mode == "RGBA":
            result.paste(resized, (x_offset, y_offset), resized)
        else:
            result.paste(resized, (x_offset, y_offset))

        return result

    def generate_og_image(
        self,
        title: str,
        description: str | None,
        website_id: int,
        background_color: str = "#3B82F6",
        text_color: str = "#FFFFFF",
        logo_path: str | None = None,
    ) -> OGImageResult:
        """Generate OpenGraph image for social sharing.

        Args:
            title: Page/site title
            description: Optional description/subtitle
            website_id: Website ID for storage
            background_color: Background color (hex)
            text_color: Text color (hex)
            logo_path: Optional path to logo image

        Returns:
            OGImageResult with generated image
        """
        try:
            # Create base image
            img = Image.new(
                "RGB",
                (OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT),
                self._hex_to_rgb(background_color)
            )
            draw = ImageDraw.Draw(img)

            # Try to load fonts
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
                desc_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            except:
                # Fallback to default font
                title_font = ImageFont.load_default()
                desc_font = title_font

            # Add logo if provided
            y_position = 100
            if logo_path and os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    logo_size = 120
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    logo_x = (OG_IMAGE_WIDTH - logo_size) // 2
                    img.paste(logo, (logo_x, y_position), logo if logo.mode == 'RGBA' else None)
                    y_position += logo_size + 40
                except Exception:
                    pass  # Continue without logo

            # Draw title (wrapped)
            text_rgb = self._hex_to_rgb(text_color)
            max_width = OG_IMAGE_WIDTH - 160

            # Wrap title text
            wrapped_title = self._wrap_text(title, title_font, max_width, draw)
            title_y = y_position + 50

            for line in wrapped_title[:3]:  # Max 3 lines
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                text_x = (OG_IMAGE_WIDTH - text_width) // 2
                draw.text((text_x, title_y), line, font=title_font, fill=text_rgb)
                title_y += 80

            # Draw description if provided
            if description:
                desc_y = title_y + 30
                wrapped_desc = self._wrap_text(description, desc_font, max_width, draw)

                for line in wrapped_desc[:2]:  # Max 2 lines
                    bbox = draw.textbbox((0, 0), line, font=desc_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (OG_IMAGE_WIDTH - text_width) // 2
                    draw.text((text_x, desc_y), line, font=desc_font, fill=text_rgb)
                    desc_y += 45

            # Add decorative element
            self._add_decorative_element(draw, background_color)

            # Save to bytes
            output = io.BytesIO()
            img.save(output, format="PNG", optimize=True)
            image_bytes = output.getvalue()

            # Save to storage
            og_id = str(uuid.uuid4())[:8]
            filename = f"og-image-{website_id}-{og_id}.png"
            filepath = self._get_storage_path(website_id, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            return OGImageResult(
                success=True,
                image_bytes=image_bytes,
                content_type="image/png"
            )

        except Exception as e:
            return OGImageResult(
                success=False,
                error_message=f"OG image generation failed: {str(e)}"
            )

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        draw: ImageDraw.ImageDraw
    ) -> list[str]:
        """Wrap text to fit within max_width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text]

    def _add_decorative_element(
        self,
        draw: ImageDraw.ImageDraw,
        background_color: str
    ) -> None:
        """Add decorative gradient/pattern to OG image."""
        # Add subtle gradient overlay at bottom
        overlay_color = (255, 255, 255, 30)
        draw.rectangle(
            [(0, OG_IMAGE_HEIGHT - 100), (OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT)],
            fill=overlay_color
        )

    def get_favicon_url(self, website_id: int, favicon_id: str) -> str | None:
        """Get URL path for favicon files."""
        ico_path = self._get_storage_path(website_id, f"favicon-{favicon_id}.ico")
        if os.path.exists(ico_path):
            return f"/assets/websites/{website_id}/favicon-{favicon_id}.ico"
        return None

    def get_og_image_url(self, website_id: int, og_id: str) -> str | None:
        """Get URL path for OG image."""
        path = self._get_storage_path(website_id, f"og-image-{website_id}-{og_id}.png")
        if os.path.exists(path):
            return f"/assets/websites/{website_id}/og-image-{website_id}-{og_id}.png"
        return None


# Singleton instance
_seo_service_instance: WebsiteSEOService | None = None


def get_website_seo_service() -> WebsiteSEOService:
    """Get or create singleton instance of WebsiteSEOService."""
    global _seo_service_instance
    if _seo_service_instance is None:
        _seo_service_instance = WebsiteSEOService()
    return _seo_service_instance
