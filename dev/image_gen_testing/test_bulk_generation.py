#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from calmlib.llm.bulk_image_generation import bulk_generate_images
from calmlib.utils import find_calmmage_env_key

os.environ["GEMINI_API_KEY"] = find_calmmage_env_key("GEMINI_API_KEY")

OUTPUT_DIR = Path(__file__).parent / "test_bulk"
OUTPUT_DIR.mkdir(exist_ok=True)


async def main():
    items = [
        {"prompt": "A red cat", "filename": "cat1.png"},
        {"prompt": "A blue cat", "filename": "cat2.png"},
        {"prompt": "A green cat", "filename": "cat3.png"},
    ]

    results = await bulk_generate_images(
        items=items,
        output_dir=OUTPUT_DIR,
        model="gemini",
        max_concurrent=2,
    )

    print(f"\nDone! {sum(r.success for r in results)}/{len(results)} succeeded")


if __name__ == "__main__":
    asyncio.run(main())
