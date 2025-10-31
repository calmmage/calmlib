#!/usr/bin/env python3
"""Test which params actually work with each API."""
import asyncio
import base64
import os
from pathlib import Path
import litellm
from calmlib.utils import find_calmmage_env_key

os.environ["OPENAI_API_KEY"] = find_calmmage_env_key("OPENAI_API_KEY")

OUTPUT_DIR = Path(__file__).parent / "test_images"
OUTPUT_DIR.mkdir(exist_ok=True)


async def test_openai_1024x1024():
    print("OpenAI 1024x1024: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A red cat", size="1024x1024")
        (OUTPUT_DIR / "openai_1024x1024.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_1536x1024():
    print("OpenAI 1536x1024: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A blue cat", size="1536x1024")
        (OUTPUT_DIR / "openai_1536x1024.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_1024x1536():
    print("OpenAI 1024x1536: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A green cat", size="1024x1536")
        (OUTPUT_DIR / "openai_1024x1536.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_quality_low():
    print("OpenAI quality=low: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A yellow cat", quality="low")
        (OUTPUT_DIR / "openai_quality_low.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_quality_medium():
    print("OpenAI quality=medium: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A purple cat", quality="medium")
        (OUTPUT_DIR / "openai_quality_medium.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_quality_high():
    print("OpenAI quality=high: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A pink cat", quality="high")
        (OUTPUT_DIR / "openai_quality_high.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def test_openai_size_quality():
    print("OpenAI 1536x1024 + quality=high: ", end="")
    try:
        response = await litellm.aimage_generation(model="openai/gpt-image-1", prompt="A orange cat", size="1536x1024", quality="high")
        (OUTPUT_DIR / "openai_1536x1024_high.png").write_bytes(base64.b64decode(response.data[0].b64_json))
        print("✓")
    except Exception as e:
        print(f"✗ {e}")


async def main():
    await test_openai_1024x1024()
    await test_openai_1536x1024()
    await test_openai_1024x1536()
    await test_openai_quality_low()
    await test_openai_quality_medium()
    await test_openai_quality_high()
    await test_openai_size_quality()


if __name__ == "__main__":
    asyncio.run(main())
