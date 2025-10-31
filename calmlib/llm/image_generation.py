"""Simple image generation - just generate and return bytes."""
import base64
import litellm


async def generate_image_gemini(prompt: str, model: str = "gemini/gemini-2.5-flash-image") -> bytes:
    """Generate image with Gemini, return bytes."""
    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        modalities=["image", "text"]
    )
    data_uri = response.choices[0].message.images[0]['image_url']['url']
    base64_data = data_uri.split(',', 1)[1]
    return base64.b64decode(base64_data)


async def generate_image_openai(prompt: str, model: str = "openai/gpt-image-1") -> bytes:
    """Generate image with OpenAI, return bytes."""
    response = await litellm.aimage_generation(model=model, prompt=prompt)
    return base64.b64decode(response.data[0].b64_json)


async def generate_image(prompt: str, model: str = "gemini/gemini-2.5-flash-image") -> bytes:
    """
    Generate image and return bytes.

    Args:
        prompt: Text description
        model: Full model name like "gemini/gemini-2.5-flash-image" or "openai/gpt-image-1"

    Returns:
        Image bytes ready to write to file
    """
    if model.startswith("gemini/"):
        return await generate_image_gemini(prompt, model)
    elif model.startswith("openai/"):
        return await generate_image_openai(prompt, model)
    else:
        raise ValueError(f"Unknown model: {model}")
