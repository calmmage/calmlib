#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from calmlib.llm.image_generation import generate_image
from calmlib.utils import find_calmmage_env_key

os.environ["GEMINI_API_KEY"] = find_calmmage_env_key("GEMINI_API_KEY")
os.environ["OPENAI_API_KEY"] = find_calmmage_env_key("OPENAI_API_KEY")

OUTPUT_DIR = Path(__file__).parent / "test_images"
OUTPUT_DIR.mkdir(exist_ok=True)


async def test_gemini():
    image_data = await generate_image("A cute cartoon cat", model="gemini/gemini-2.5-flash-image")
    image_path = OUTPUT_DIR / "gemini_cat.png"
    image_path.write_bytes(image_data)
    print(f"open {image_path}")


async def test_openai():
    image_data = await generate_image("A cute cartoon cat", model="openai/gpt-image-1")
    image_path = OUTPUT_DIR / "openai_cat.png"
    image_path.write_bytes(image_data)
    print(f"open {image_path}")


async def main():
    await test_gemini()
    await test_openai()


if __name__ == "__main__":
    asyncio.run(main())
