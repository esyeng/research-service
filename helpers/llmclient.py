import os
import re
import json
import asyncio
import aiohttp
import httpx
import time
from utils.types import OrchestratorError
from utils.types import ToolCall, ToolResult
from typing import List, Dict, Callable, Any, Tuple
from anthropic import Anthropic, AsyncAnthropic, DefaultAioHttpClient
from anthropic.types import APIErrorObject, ErrorResponse
from anthropic.types import Message, ToolUseBlock
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")


def _convert_tool_definition(tool_def: Dict) -> Dict:
    """Convert tool definition to Anthropic's format"""
    return {
        "name": tool_def["name"],
        "description": tool_def["description"],
        "input_schema": {
            "type": "object",
            "properties": tool_def["parameters"],
            "required": [
                k for k, v in tool_def["parameters"].items() if v.get("required", False)
            ],
        },
    }


async def _execute_tool_calls(
    tool_calls: List, available_tools: List[Dict]
) -> List[ToolResult]:
    """
    Execute tool calls in parallel and return results
    Args:
        tool_calls (List)
        available_tools (List[Dict])
    Returns:
        List[ToolResult]
    """

    # Create tool lookup
    tool_functions = {tool["name"]: tool["function"] for tool in available_tools}

    # Create async tasks for each tool call
    tasks = []
    for tc in tool_calls:
        if tc.name in tool_functions:
            task = asyncio.create_task(
                _safe_tool_execution(tc, tool_functions[tc.name])
            )
            tasks.append(task)
        else:
            # Unknown tool
            tasks.append(
                asyncio.create_task(
                    _create_error_result(tc.id, f"Unknown tool: {tc.name}")
                )
            )

    # Execute all tools in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error results
    tool_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            tool_results.append(
                ToolResult(
                    tool_use_id=tool_calls[i].id, content=None, error=str(result)
                )
            )
        else:
            tool_results.append(result)

    return tool_results


async def _safe_tool_execution(
    tool_call: ToolCall, tool_function: Callable
) -> ToolResult:
    """
    Execute a single tool with error handling
    Args:
        tool_call (ToolCall): @dataclass ToolCall(id: str name: str arguments: Dict[str, Any])
        tool_function (Callable): The callable function to send to the model. Defaults to "".

    Returns:
        ToolResult(tool_call_id: str content: Any error: str | None = None)

    """

    try:
        # Parse arguments
        if isinstance(tool_call.input, str):
            args = json.loads(tool_call.input)
        else:
            args = tool_call.input

        # Execute tool function
        if asyncio.iscoroutinefunction(tool_function):
            result = await tool_function(**args)
        else:
            result = tool_function(**args)

        return ToolResult(tool_use_id=tool_call.id, content=result)
    except Exception as e:
        return ToolResult(tool_use_id=tool_call.id, content=None, error=str(e))


async def _create_error_result(tool_use_id: str, error_msg: str) -> ToolResult:
    """Helper to create error results"""
    return ToolResult(tool_use_id=tool_use_id, content=None, error=error_msg)


def _extract_tool_calls_and_text(response) -> Tuple[List[ToolCall], List[Any]]:
    tool_calls = []
    text_blocks = []
    response_blocks = response.content
    for block in response_blocks:
        if block.type == "tool_use":
            tool = ToolCall(
                id=block.id,
                type=block.type,
                name=block.name,
                input=block.input,
            )
            tool_calls.append(tool)
        elif block.type == "text":
            text_blocks.append(block.text)
    return tool_calls, text_blocks


def _add_tool_results_to_messages(
    messages: List[Dict[str, str]], tool_results: List[ToolResult]
) -> List[Dict[str, str]]:
    for result in tool_results:
        if result.error is None:
            try:
                content = json.dumps(result.content)
            except (TypeError, ValueError):
                # Handle non-serializable objects
                content = str(result.content)
        else:
            content = f"Error: {result.error}"
        messages.append(
            {
                "role": "user",
                "content": content,
            }
        )
    return messages


# MAX_TOOL_CALLS = 20


async def llm_call_with_tools(
    prompt: str,
    tools: List[Dict],  # Tool definitions,
    model: str = "claude-3-7-sonnet-20250219",
    max_tokens: int = 4000,
    timeout: int = 120,  # per-call timeout
    conversation_timeout: int = 300,  # conversation timeout
) -> Dict:
    """
    Execute LLM with tool calling capability.
    Handles the conversation loop until LLM signals completion.

    Args:
        prompt (str): prompt to call model with
        tools (List[Dict]): tool definitions
        model (str)
        max_tokens (int)
        timeout (int)
    Returns:
        Dict - final message to user with results and indicator of finishing

    """
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        prompt + "..."
                        if isinstance(prompt, str)
                        else (
                            json.dumps(prompt)
                            if isinstance(prompt, dict)
                            else str(prompt) + "..."
                        )
                    ),
                    "cache_control": {"type": "ephemeral"},  # cache main prompt
                }
            ],
        }
    ]
    formatted_tools = (
        [_convert_tool_definition(tool) for tool in tools] if len(tools) > 0 else []
    )
    cached_tools = []
    if formatted_tools:
        for tool in formatted_tools:
            cached_tools.append(tool)  # mark last tool for caching
        if len(cached_tools) > 0:
            pass
    tool_calls = []
    text_blocks = []
    tool_calls_count = 0
    max_tool_calls = globals().get("MAX_TOOL_CALLS", 10)
    conversation_start = time.time()
    max_iterations = 7

    for i in range(max_iterations):
        if time.time() - conversation_start > conversation_timeout:
            return {
                "final_response": "Conversation timed out",
                "tool_calls_count": tool_calls_count,
                "error": "conversation_timeout",
                "conversation": messages,
            }
        try:
            response = await asyncio.wait_for(
                stream_llm_messages_async(
                    messages=messages,
                    tools=formatted_tools,
                    model=model,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
            if response and hasattr(response, "stop_reason"):
                if response.stop_reason == "tool_use":
                    tool_calls, text_blocks = _extract_tool_calls_and_text(response)
                    if tool_calls:
                        tool_results = await _execute_tool_calls(tool_calls, tools)
                        tool_calls_count += len(tool_calls)
                        messages = _add_tool_results_to_messages(messages, tool_results)
                        for text in text_blocks:
                            messages.append({"role": "assistant", "content": text})
                        if any(
                            getattr(result.content, "status", None)
                            in ["error", "task_complete", "completed"]
                            for result in tool_results
                        ):
                            return {
                                "final_response": (messages, tool_results),
                                "tool_calls_count": tool_calls_count,
                                "conversation": messages,
                            }
                        print("continue to next step")
                        continue
                else:
                    print("return from llm_call loop")

                    return {
                        "final_response": response.content[0].text,
                        "tool_calls_count": tool_calls_count,
                        "conversation": messages,
                    }
        except asyncio.TimeoutError:
            return {
                "final_response": "LLM call timed out",
                "tool_calls_count": tool_calls_count,
                "error": "single_call_timeout",
                "conversation": messages,
            }
    return {
        "final_response": messages[-1]["content"] if messages else "No Response",
        "tool_calls_count": tool_calls_count,
        "error": "max_iterations_exceeded",
        "conversation": messages,
    }


def _print_event(event):
    if event.type == "text":
        print(event.text, end="", flush=True)
    elif event.type == "content_block_stop":
        print(
            "\ncontent block finished accumulating:",
            event.content_block,
        )


async def stream_llm_messages_async(
    messages: List[Dict],
    tools: List[Dict] | None = None,
    model: str = "claude-3-7-sonnet-20250219",
    max_tokens: int = 4000,
    extra_headers: Dict | None = None,
) -> Message | None:
    """
    Call LLM asynchronously, streaming messages with tools
    Args:
        messages (List[Message]): The messages to send to the model
        tools (List[Tool]): The tools to give model access to
        model (str, optional): The model to use for the call. Defaults to "claude-sonnet-4-20250514".,
        max_tokens (int, optional)
    Returns:
        str: The MesssageStreamManager from the language model.
    """
    request_params = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools:
        request_params["tools"] = tools
    headers = {}
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY, http_client=httpx.AsyncClient()
        ) as client:
            if headers:
                async with client.messages.stream(
                    **request_params, extra_headers=headers
                ) as stream:
                    async for event in stream:
                        _print_event(event)
            else:
                async with client.messages.stream(**request_params) as stream:
                    async for event in stream:
                        _print_event(event)

            accumulated = await stream.get_final_message()
            return accumulated
    except OrchestratorError as e:
        print(f"Error in stream_message: {e}")
        return None


def stream_llm_sync(
    prompt: str, system_prompt: str = "", model: str = "claude-sonnet-4-20250514"
):
    """
    Calls the model with the given prompt and returns the response.
    Args:
        prompt (str): The user prompt to send to the model.
        system_prompt (str, optional): The system_prompt to send to the model. Defaults to "".
        model (str, optional): The model to use for the call. Defaults to "claude-3-5-sonnet-20241022".
    Returns:
        str: The response from the language model.
    """
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": prompt}]
    with client.messages.stream(
        model=model,
        max_tokens=64000,
        system=[
            {
                "type": "text",
                "text": system_prompt + "...",
                "cache_control": {"type": "ephemeral"},
            }
        ],  # utilize prompt caching of system message for cost efficiency
        messages=messages,
        temperature=0.1,
    ) as stream:
        for event in stream:
            _print_event(event)
        print()

    # gets accumulated final message outside of context manager if consumed inside of the context manager
    accumulated = stream.get_final_message()
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


def extract_json_from_markdown(raw_response: str) -> dict:
    # remove markdown code block if present
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = raw_response
    return json.loads(json_str)


"""
(
    response[0]
    if hasattr(response, "content") and isinstance(response[0].content, list) and len(response[0].content) > 0 and hasattr(response[0].content[0], "text")
    else str(response[0])
)"""
