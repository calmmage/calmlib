#!/usr/bin/env python3
import asyncio
import base64
import os
from pathlib import Path
import litellm
from calmlib.utils import find_calmmage_env_key

os.environ["GEMINI_API_KEY"] = find_calmmage_env_key("GEMINI_API_KEY")
os.environ["OPENAI_API_KEY"] = find_calmmage_env_key("OPENAI_API_KEY")

OUTPUT_DIR = Path(__file__).parent / "test_images"
OUTPUT_DIR.mkdir(exist_ok=True)


def save_image(data_uri: str, filepath: Path) -> None:
    open(filepath, 'wb').write(base64.b64decode(data_uri.split(',', 1)[1]))


async def test_gemini():
    response = await litellm.acompletion(model="gemini/gemini-2.5-flash-image", messages=[{"role": "user", "content": "Generate an image of a cute cartoon cat"}], modalities=["image", "text"])
    filepath = OUTPUT_DIR / "gemini_cat.png"
    save_image(response.choices[0].message.images[0]['image_url']['url'], filepath)
    print(f"open {filepath}")


async def test_openai():
    response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A cute cartoon cat")
    filepath = OUTPUT_DIR / "openai_cat.png"
    save_image(f"data:image/png;base64,{response.data[0].b64_json}", filepath)
    print(f"open {filepath}")


async def main():
    await test_gemini()
    await test_openai()


if __name__ == "__main__":
    asyncio.run(main())
