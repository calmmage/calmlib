"""Simple image generation - just generate and return bytes."""
import base64
import litellm

from calmlib.llm.image_generation_utils import resolve_model


async def generate_image_gemini(prompt: str, model: str = "gemini/gemini-2.5-flash-image", size: str | None = None) -> bytes:
    """Generate image with Gemini, return bytes. Only supports 1024x1024."""
    if size and size != "1024x1024":
        raise ValueError(f"Gemini only supports size='1024x1024', got: {size}")
    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        modalities=["image", "text"]
    )
    data_uri = response.choices[0].message.images[0]['image_url']['url']
    base64_data = data_uri.split(',', 1)[1]
    return base64.b64decode(base64_data)


async def generate_image_openai(prompt: str, model: str = "openai/gpt-image-1", size: str | None = None, quality: str | None = None) -> bytes:
    """
    Generate image with OpenAI, return bytes.

    Size: "1024x1024", "1024x1536", "1536x1024", "auto"
    Quality: "low", "medium", "high", "auto"
    """
    kwargs = {"model": model, "prompt": prompt}
    if size:
        kwargs["size"] = size
    if quality:
        kwargs["quality"] = quality
    response = await litellm.aimage_generation(**kwargs)
    return base64.b64decode(response.data[0].b64_json)


async def generate_image(prompt: str, model: str = "gemini/gemini-2.5-flash-image", size: str | None = None, quality: str | None = None) -> bytes:
    """
    Generate image and return bytes.

    Args:
        prompt: Text description
        model: Full model name like "gemini/gemini-2.5-flash-image" or "openai/gpt-image-1"
        size: Image size (Gemini: only "1024x1024" | OpenAI: "1024x1024", "1024x1536", "1536x1024", "auto")
        quality: Image quality (OpenAI only: "low", "medium", "high", "auto")

    Returns:
        Image bytes ready to write to file
    """
    model = resolve_model(model)
    if model.startswith("gemini/"):
        return await generate_image_gemini(prompt, model, size)
    elif model.startswith("openai/"):
        return await generate_image_openai(prompt, model, size, quality)
    else:
        raise ValueError(f"Unknown model: {model}")
