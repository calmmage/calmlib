"""
Bulk image generation utilities for calmlib.

Provides utilities for:
- Bulk generation with progress tracking
- Cost estimation
- MongoDB progress tracking for recovery
- Batch processing with retries
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .image_generation import generate_image, resolve_model


@dataclass
class BulkGenerationConfig:
    """Configuration for bulk image generation."""

    model: str | None = None  # Auto-select if None
    size: str = "1024x1024"
    quality: str | None = None  # Only for models that support it (OpenAI)
    max_concurrent: int = 5  # Max concurrent requests
    max_retries: int = 3
    output_dir: Path | None = None
    save_images: bool = True
    track_in_mongodb: bool = False


@dataclass
class GenerationResult:
    """Result of a single image generation."""

    success: bool
    prompt: str
    output_path: Path | None = None
    error: str | None = None
    cost: float = 0.0
    duration: float = 0.0


class BulkImageGenerator:
    """Handle bulk image generation with progress tracking and recovery."""

    def __init__(self, config: BulkGenerationConfig):
        self.config = config
        self.results: list[GenerationResult] = []

        # Cost per image by model (approximate)
        self.cost_map = {
            "dalle-3": 0.040,  # $0.040 per 1024x1024
            "dalle-2": 0.020,  # $0.020 per 1024x1024
            "gpt-image-1": 0.040,  # Similar to DALL-E 3
            "imagen-4": 0.020,  # Gemini pricing
            "nano-banana": 0.015,  # Gemini Flash pricing
        }

    def estimate_cost(self, num_images: int, model: str | None = None) -> float:
        """Estimate total cost for generating images."""
        model_name = model or self.config.model
        resolved = resolve_model(model_name)

        # Extract base model name for cost lookup
        for key in self.cost_map:
            if key in resolved:
                return num_images * self.cost_map[key]

        # Default estimate if model not in map
        logger.warning(f"No cost estimate for {resolved}, using default $0.03")
        return num_images * 0.03

    async def generate_one(
        self, prompt: str, output_filename: str | None = None, retry_count: int = 0
    ) -> GenerationResult:
        """Generate a single image with retry logic."""
        start_time = time.time()

        try:
            # Generate image
            kwargs = {
                "prompt": prompt,
                "model": self.config.model,
                "size": self.config.size,
            }

            # Only pass quality for models that support it (not Gemini)
            if self.config.quality is not None:
                resolved = resolve_model(self.config.model)
                # Skip quality for Gemini models
                if "gemini" not in resolved.lower():
                    kwargs["quality"] = self.config.quality

            image_bytes = await generate_image(**kwargs)

            duration = time.time() - start_time

            # Save image if configured
            output_path = None
            if self.config.save_images and output_filename:
                output_path = self.config.output_dir / output_filename
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(image_bytes)
                logger.info(f"Saved image to {output_path}")

            # Calculate cost
            cost = self.estimate_cost(1, self.config.model)

            return GenerationResult(
                success=True,
                prompt=prompt,
                output_path=output_path,
                cost=cost,
                duration=duration,
            )

        except Exception as e:
            # Retry logic
            if retry_count < self.config.max_retries:
                logger.warning(
                    f"Generation failed, retrying ({retry_count + 1}/{self.config.max_retries}): {e}"
                )
                await asyncio.sleep(2**retry_count)  # Exponential backoff
                return await self.generate_one(prompt, output_filename, retry_count + 1)

            # Final failure
            duration = time.time() - start_time
            logger.error(
                f"Generation failed after {self.config.max_retries} retries: {e}"
            )

            return GenerationResult(
                success=False, prompt=prompt, error=str(e), duration=duration
            )

    async def generate_batch(
        self,
        prompts: list[tuple[str, str]],  # List of (prompt, output_filename)
        progress_callback: Callable[[int, int, GenerationResult], None] | None = None,
    ) -> list[GenerationResult]:
        """
        Generate multiple images in batch with concurrent requests.

        Args:
            prompts: List of (prompt, output_filename) tuples
            progress_callback: Optional callback(current, total, result) for progress updates

        Returns:
            List of GenerationResult objects
        """
        total = len(prompts)

        logger.info(f"Starting batch generation: {total} images")
        logger.info(f"Max concurrent: {self.config.max_concurrent}")
        logger.info(f"Estimated cost: ${self.estimate_cost(total):.2f}")

        # Semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Counter for progress
        completed = 0

        async def generate_with_limit(
            prompt: str, filename: str
        ) -> GenerationResult:
            nonlocal completed
            async with semaphore:
                result = await self.generate_one(prompt, filename)
                completed += 1

                # Progress callback
                if progress_callback:
                    progress_callback(completed, total, result)

                return result

        # Create all tasks
        tasks = [
            generate_with_limit(prompt, filename)
            for i, (prompt, filename) in enumerate(prompts)
        ]

        # Run concurrently with tqdm if available
        try:
            from tqdm.asyncio import tqdm

            results = await tqdm.gather(*tasks, desc="Generating images")
        except ImportError:
            # Fallback without tqdm
            logger.warning("tqdm not installed, progress bar disabled")
            results = await asyncio.gather(*tasks)

        # Summary
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        total_cost = sum(r.cost for r in results)
        total_time = sum(r.duration for r in results)

        logger.info(f"Batch complete: {successful} succeeded, {failed} failed")
        logger.info(f"Total cost: ${total_cost:.2f}, Total time: {total_time:.1f}s")

        self.results.extend(results)
        return results


# Convenience function for simple batch generation
async def bulk_generate_images(
    items: list[dict[str, str]],  # List of {"prompt": ..., "filename": ...}
    output_dir: Path,
    model: str | None = None,
    size: str = "1024x1024",
    max_concurrent: int = 5,
) -> list[GenerationResult]:
    """
    Simple bulk image generation with concurrent requests.

    Args:
        items: List of dicts with 'prompt' and 'filename' keys
        output_dir: Directory to save images
        model: Model to use (auto-selects if None)
        size: Image size (default 1024x1024)
        max_concurrent: Max concurrent requests (default 5)

    Returns:
        List of GenerationResult objects
    """
    config = BulkGenerationConfig(
        model=model,
        size=size,
        max_concurrent=max_concurrent,
        output_dir=output_dir,
        save_images=True,
    )

    generator = BulkImageGenerator(config)

    # Convert items to prompt tuples
    prompts = [(item["prompt"], item["filename"]) for item in items]

    # Simple progress callback
    def progress(current: int, total: int, result: GenerationResult):
        status = "✓" if result.success else "✗"
        print(f"{status} [{current}/{total}] {result.output_path or result.error}")

    return await generator.generate_batch(prompts, progress_callback=progress)


# Example usage
async def example_usage():
    """Example of how to use the bulk generator."""

    # Define what to generate
    items = [
        {"prompt": "A cute cartoon cat, simple drawing style", "filename": "cat.png"},
        {
            "prompt": "A friendly cartoon dog, simple drawing style",
            "filename": "dog.png",
        },
        {
            "prompt": "A colorful cartoon bird, simple drawing style",
            "filename": "bird.png",
        },
    ]

    # Generate
    results = await bulk_generate_images(
        items=items,
        output_dir=Path("./generated_images"),
        model="nano-banana",  # or None to auto-select
        size="1024x1024",
        max_concurrent=5,
    )

    # Check results
    for result in results:
        if result.success:
            print(f"✓ Generated: {result.output_path}")
        else:
            print(f"✗ Failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(example_usage())
