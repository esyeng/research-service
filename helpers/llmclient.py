import os
import re
import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")


async def llm_call(
    prompt: str, system_prompt: str = "", model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Calls the model with the given prompt and returns the response.
    Args:
        prompt (str): The user prompt to send to the model.
        system_prompt (str, optional): The system_prompt to send to the model. Defaults to "".
        model (str, optional): The model to use for the call. Defaults to "claude-3-5-sonnet-20241022".
    Returns:
        str: The response from the language model.
    """
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": prompt}]
    async with client.messages.stream(
        model=model,
        max_tokens=64000,
        system=system_prompt,
        messages=messages,
        temperature=0.1,
    ) as stream:
        async for event in stream:
            if event.type == "text":
                print(event.text, end="", flush=True)
            elif event.type == "content_block_stop":
                print()
                print("\ncontent block finished accumulating:", event.content_block)
        print()

    # you can still get the accumulated final message outside of
    # the context manager, as long as the entire stream was consumed
    # inside of the context manager
    accumulated = await stream.get_final_message()
    print("accumulated message: ", accumulated.to_json())
    return accumulated.content[0].text


def extract_xml(text: str, tag: str) -> str:
    """
    Extracts the content of the specified XML tag from the given text. Used for parsing structured responses
    Args:
        text (str): The text containing the XML.
        tag (str): The XML tag to extract content from.
    Returns:
        str: The content of the specified XML tag, or an empty string if the tag is not found.
    """
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""
