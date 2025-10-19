"""
Quick Draw dataset downloader.

Downloads and processes Google's Quick Draw dataset for use in projects.
Dataset: 50M drawings, 345 categories, Creative Commons Attribution 4.0
"""

import json
import subprocess
from pathlib import Path

from loguru import logger

# Categories suitable for baby/toddler flashcards
BABY_FRIENDLY_CATEGORIES = [
    # Animals
    "cat",
    "dog",
    "bird",
    "fish",
    "cow",
    "duck",
    "pig",
    "rabbit",
    "mouse",
    "bear",
    "horse",
    "sheep",
    "chicken",
    "lion",
    "tiger",
    "elephant",
    "giraffe",
    "monkey",
    "zebra",
    "frog",
    "butterfly",
    "snake",
    "turtle",
    "penguin",
    "owl",
    # Food
    "apple",
    "banana",
    "bread",
    "cookie",
    "cake",
    "pizza",
    "ice cream",
    "hot dog",
    "donut",
    "strawberry",
    "watermelon",
    "carrot",
    "broccoli",
    # Body parts
    "eye",
    "nose",
    "mouth",
    "hand",
    "foot",
    "ear",
    # Objects
    "ball",
    "cup",
    "shoe",
    "hat",
    "book",
    "chair",
    "table",
    "bed",
    "door",
    "car",
    "bicycle",
    "bus",
    "train",
    "airplane",
    "boat",
    "truck",
    # Nature
    "sun",
    "moon",
    "star",
    "cloud",
    "tree",
    "flower",
    "grass",
    "mountain",
    "ocean",
    "rain",
    "rainbow",
    "snowflake",
    # Shapes & Colors
    "circle",
    "square",
    "triangle",
    "hexagon",
    # Home/Family
    "house",
    "teddy bear",
    "clock",
    "telephone",
    "television",
]


class QuickDrawDownloader:
    """Download and process Google Quick Draw dataset."""

    BASE_URL = "https://storage.googleapis.com/quickdraw_dataset/full/simplified"

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_category(
        self, category: str, format: str = "simplified"
    ) -> Path | None:
        """
        Download a specific category.

        Args:
            category: Category name (e.g., 'cat', 'dog')
            format: Data format - 'simplified' (ndjson), 'raw', or 'numpy'

        Returns:
            Path to downloaded file or None if failed
        """
        # Clean category name
        category_clean = category.replace(" ", "%20")

        if format == "simplified":
            url = f"{self.BASE_URL}/{category_clean}.ndjson"
            filename = f"{category}.ndjson"
        else:
            logger.error(f"Format '{format}' not yet supported")
            return None

        output_file = self.output_dir / filename

        # Skip if already exists
        if output_file.exists():
            logger.info(f"Already exists: {output_file}")
            return output_file

        logger.info(f"Downloading {category} from {url}")

        try:
            # Use curl to download (faster than Python requests for large files)
            subprocess.run(
                ["curl", "-o", str(output_file), url], check=True, capture_output=True
            )
            logger.info(f"✓ Downloaded: {output_file}")
            return output_file

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed to download {category}: {e}")
            return None

    def download_baby_categories(self, limit: int | None = None) -> list[Path]:
        """
        Download all baby-friendly categories.

        Args:
            limit: Optional limit on number of categories to download

        Returns:
            List of paths to downloaded files
        """
        categories = (
            BABY_FRIENDLY_CATEGORIES[:limit] if limit else BABY_FRIENDLY_CATEGORIES
        )

        logger.info(f"Downloading {len(categories)} baby-friendly categories")

        downloaded = []
        for i, category in enumerate(categories, 1):
            logger.info(f"[{i}/{len(categories)}] {category}")
            result = self.download_category(category)
            if result:
                downloaded.append(result)

        logger.info(f"Downloaded {len(downloaded)}/{len(categories)} categories")
        return downloaded

    def extract_sample_images(
        self,
        category_file: Path,
        output_dir: Path,
        num_samples: int = 10,
        image_size: tuple[int, int] = (256, 256),
    ) -> list[Path]:
        """
        Extract sample drawings from a category file and save as PNG images.

        Args:
            category_file: Path to .ndjson category file
            output_dir: Directory to save PNG images
            num_samples: Number of samples to extract
            image_size: Size of output images (width, height)

        Returns:
            List of paths to saved images
        """
        import numpy as np
        from PIL import Image, ImageDraw

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        category_name = category_file.stem
        saved_images = []

        logger.info(f"Extracting {num_samples} samples from {category_name}")

        with open(category_file) as f:
            for i, line in enumerate(f):
                if i >= num_samples:
                    break

                # Parse drawing data
                data = json.loads(line)
                drawing = data["drawing"]

                # Create blank image
                img = Image.new("RGB", image_size, "white")
                draw = ImageDraw.Draw(img)

                # Draw strokes
                for stroke in drawing:
                    # stroke is [[x1, x2, ...], [y1, y2, ...]]
                    x_coords = stroke[0]
                    y_coords = stroke[1]

                    # Scale to image size
                    x_coords = np.array(x_coords) * (image_size[0] / 256)
                    y_coords = np.array(y_coords) * (image_size[1] / 256)

                    # Draw lines
                    points = list(zip(x_coords, y_coords, strict=False))
                    if len(points) > 1:
                        draw.line(points, fill="black", width=2)

                # Save image
                output_path = output_dir / f"{category_name}_{i:03d}.png"
                img.save(output_path)
                saved_images.append(output_path)

        logger.info(f"✓ Saved {len(saved_images)} images to {output_dir}")
        return saved_images


# Convenience function
def download_quickdraw_categories(
    categories: list[str] | None = None,
    output_dir: Path = Path("./quickdraw_data"),
    baby_friendly_only: bool = True,
) -> list[Path]:
    """
    Download Quick Draw categories.

    Args:
        categories: Specific categories to download, or None for baby-friendly defaults
        output_dir: Where to save files
        baby_friendly_only: If True, only download baby-friendly categories

    Returns:
        List of downloaded file paths
    """
    downloader = QuickDrawDownloader(output_dir)

    if baby_friendly_only and not categories:
        return downloader.download_baby_categories()
    elif categories:
        return [downloader.download_category(cat) for cat in categories]
    else:
        logger.error("Must specify categories or use baby_friendly_only=True")
        return []


# Example usage
if __name__ == "__main__":
    # Download baby-friendly categories
    output_dir = Path("./quickdraw_baby_images")

    downloader = QuickDrawDownloader(output_dir / "data")

    # Download first 5 categories
    files = downloader.download_baby_categories(limit=5)

    # Extract sample images from first file
    if files:
        samples = downloader.extract_sample_images(
            files[0], output_dir / "samples", num_samples=5, image_size=(512, 512)
        )
        print(f"Extracted samples: {samples}")
