import os
import re
import json
import asyncio
import aiohttp
import httpx
from utils.types import OrchestratorError
from utils.types import ToolCall, ToolResult
from typing import List, Dict, Callable
from anthropic import Anthropic, AsyncAnthropic, DefaultAioHttpClient
from anthropic.types import APIErrorObject, ErrorResponse
from anthropic.types import Message
from dotenv import load_dotenv

load_dotenv()

# m = Message(

# )
# s = StopReason(

# )
# t = ToolUseBlock(

# )
# b = ToolResultBlockParam(


# )
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
                    tool_call_id=tool_calls[i].id, content=None, error=str(result)
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
        if isinstance(tool_call.arguments, str):
            args = json.loads(tool_call.arguments)
        else:
            args = tool_call.arguments

        # Execute tool function
        if asyncio.iscoroutinefunction(tool_function):
            result = await tool_function(**args)
        else:
            result = tool_function(**args)

        return ToolResult(tool_call_id=tool_call.id, content=result)
    except Exception as e:
        return ToolResult(tool_call_id=tool_call.id, content=None, error=str(e))


async def _create_error_result(tool_call_id: str, error_msg: str) -> ToolResult:
    """Helper to create error results"""
    return ToolResult(tool_call_id=tool_call_id, content=None, error=error_msg)


async def stream_llm_messages_async(messages, tools, model, max_tokens) -> Message:
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
    try:
        async with AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY, http_client=httpx.AsyncClient()
        ) as client:
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                tools=tools,
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        print(event.text, end="", flush=True)
                    elif event.type == "content_block_stop":
                        print("\ncontent block finished accumulating:", event.content_block)
            
            accumulated = await stream.get_final_message()
            return accumulated
    except OrchestratorError as e:
        print(f"Error in stream_message: {e}")
        return None
        
    # return await client.messages.create(
    #     model=model,
    #     max_tokens=max_tokens,
    #     messages=messages,
    #     tools=tools,
    # )


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
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],  # utilize prompt caching of system message for cost efficiency
        messages=messages,
        temperature=0.1,
    ) as stream:
        for event in stream:
            if event.type == "text":
                print(event.text, end="", flush=True)
            elif event.type == "content_block_stop":
                print()
                print("\ncontent block finished accumulating:", event.content_block)
        print()

    # gets accumulated final message outside of context manager if consumed inside of the context manager
    accumulated = stream.get_final_message()
    print("accumulated message: ", accumulated.to_json())
    return accumulated.content[0].text

MAX_TOOL_CALLS = 20

async def llm_call_with_tools(
    prompt: str,
    tools: List[Dict],  # Tool definitions
    model: str = "claude-3-sonnet-20240229",
    max_tokens: int = 4000,
    timeout: int = 120,
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
    final = {}
    messages = [{"role": "user", "content": prompt}]
    tool_calls_count = 0
    max_tool_calls = MAX_TOOL_CALLS

    # Convert tool definitions to Anthropic format
    formatted_tools = [_convert_tool_definition(tool) for tool in tools]

    while tool_calls_count < max_tool_calls:
        try:
            # Call API with formatted tool definitions
            response = await asyncio.wait_for(
                stream_llm_messages_async(messages, formatted_tools, model, max_tokens),
                timeout=timeout,
            )
            # print(f"response object, llmclient.py line 199: {response}")
            print(f"OBJ TYPE, llmclient.py line ~259: {type(response)}")
            tool_calls_count += 1
            if response:
                if (
                    hasattr(response, "content")
                    and isinstance(response.content, list)
                    and len(response.content) > 0
                ):
                    assistant_content = response.content[0].text

                    messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_content,
                        }
                    )
                    if (
                        response.stop_reason == "tool_use"
                        or response.content[0].type == "tool_use"
                    ):
                        tool_calls = response.content

                        # if not tool_calls:
                        #     final = {
                        #         "final_response": response.content,
                        #         "tool_calls_count": tool_calls_count,
                        #         "conversation": messages,
                        #     }
                        if isinstance(tool_calls, list):
                            # execute tool calls in parallel
                            tool_results = await _execute_tool_calls(tool_calls, tools)
                            tool_calls_count += len(tool_calls)

                            # add tool results back to conversation
                            for result in tool_results:
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": result.tool_call_id,
                                        "content": (
                                            json.dumps(result.content)
                                            if result.error is None
                                            else f"Error: {result.error}"
                                        ),
                                    }
                                )

        except asyncio.TimeoutError:
            return {
                "final_response": "Tool execution timed out",
                "tool_calls_count": tool_calls_count,
                "error": "timeout",
                "conversation": messages,
            }
        except Exception as e:
            return {
                "final_response": f"Error during execution: {str(e)}",
                "tool_calls_count": tool_calls_count,
                "error": str(e),
                "conversation": messages,
            }
    final = {
        "final_response": "Reached maximum tool call limit",
        "tool_calls_count": tool_calls_count,
        "error": "max_tool_calls_exceeded",
        "conversation": messages,
    }
    print(f"\n\n\n\nhit final message llmclient line 269: {final}\n\n\n\n")
    # Hit tool call limit
    return final


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
