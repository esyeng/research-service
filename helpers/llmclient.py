import os
import re
import json
import asyncio
import httpx
import time
import traceback
from utils.types import OrchestratorError
from utils.types import ToolCall
from helpers.tools import web_search, web_fetch, complete_task
from typing import List, Dict, Callable, Any, Tuple
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")


class LLMClient:
    MAX_TOOL_RESULT_LENGTH = 4000  # max chars per tool result snippet
    MAX_CONVERSATION_HISTORY = 10  
    def __init__(self):
        self._sync = Anthropic(api_key=ANTHROPIC_API_KEY)
        self._async = AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            http_client=httpx.AsyncClient(),
            timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=2.0),
        )
        self.functions = {
            "web_fetch": web_fetch,
            "web_search": web_search,
            "complete_task": complete_task,
        }

    def stream_synchronous(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Calls the synchronous model with the given prompt and returns the response.
        Args:
            prompt (str): The user prompt to send to the model.
            system_prompt (str, optional): The system_prompt to send to the model. Defaults to "".
            model (str, optional): The model to use for the call. Defaults to "claude-3-5-sonnet-20241022".
        Returns:
            str: The response from the language model.
        """

        messages = [{"role": "user", "content": prompt}]
        with self._sync.messages.stream(
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
                self._print_event(event)
            print()

        # gets accumulated final message outside of context manager if consumed inside of the context manager
        accumulated = stream.get_final_message()
        return accumulated.content[0].text

    async def stream_asynchronous(
        self,
        messages: List[Dict],
        system: str,
        tools: List[Dict] | None = None,
        model: str = "claude-3-7-sonnet-20250219",
        max_tokens: int = 8000,
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
            "system": [
                {
                    "type": "text",
                    "text": system + "...",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
        if tools:
            request_params["tools"] = tools
        headers = {}
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with AsyncAnthropic(
                api_key=ANTHROPIC_API_KEY,
                http_client=httpx.AsyncClient(),
                timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=2.0),
            ) as client:
                if headers:
                    async with client.messages.stream(
                        **request_params, extra_headers=headers
                    ) as stream:
                        async for event in stream:
                            self._print_event(event)
                else:
                    async with client.messages.stream(**request_params) as stream:
                        async for event in stream:
                            self._print_event(event)

                accumulated = await stream.get_final_message()
                return accumulated
        except OrchestratorError as e:
            print(f"Error in stream_message: {e}")
            return None

    async def call_llm_with_tools(
        self,
        prompt: str,
        system: str,
        tools: List[Dict],
        model: str = "claude-3-7-sonnet-20250219",
        max_tokens: int = 4000,
        timeout: int = 240,
        conversation_timeout: int = 700,
    ) -> Dict:
        """
        Execute LLM with tool calling capability in a conversation loop.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            prompt if isinstance(prompt, str) else json.dumps(prompt)
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]

        formatted_tools: List[Dict[str, Any]] = (
            [self._convert_tool_definition(t) for t in tools] if tools else []
        )

        tool_calls_count = 0
        conversation_start = time.time()
        max_iterations = 4
        runs = 0

        while runs < max_iterations:
            runs += 1
            if time.time() - conversation_start > conversation_timeout:
                return {
                    "final_response": "Conversation timed out",
                    "tool_calls_count": tool_calls_count,
                    "error": "conversation_timeout",
                    "conversation": messages,
                }

            try:
                response = await asyncio.wait_for(
                    self.stream_asynchronous(
                        messages=messages,
                        system=system,
                        tools=formatted_tools,
                        model=model,
                        max_tokens=max_tokens,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                return {
                    "final_response": "LLM call timed out",
                    "tool_calls_count": tool_calls_count,
                    "error": "single_call_timeout",
                    "conversation": messages,
                }

            if not response or not hasattr(response, "stop_reason"):
                continue

            stop_reason = getattr(response, "stop_reason", None)

            if stop_reason == "tool_use":
                tool_calls, text_blocks = self._extract_tool_calls_and_text(response)
                if tool_calls:
                    try:
                        tool_results = await self._execute_tool_calls(
                            tool_calls, formatted_tools
                        )
                        tool_calls_count += len(tool_calls)

                        # append results to conversation
                        messages = self._add_tool_results_to_messages(
                            messages, tool_calls, tool_results
                        )

                        # append any text blocks
                        for text in text_blocks:
                            block = (
                                {"type": "text", "text": text + '.'}
                                if isinstance(text, str)
                                else {
                                    "type": "text",
                                    "text": json.dumps(text, default=str) + '.',
                                }
                            )
                            messages.append({"role": "assistant", "content": [block]})

                        # check if any tool result signals completion/error
                        if any(
                            isinstance(res, dict)
                            and res.get("status")
                            in ["completed", "task_complete", "error"]
                            for res in tool_results
                        ):
                            return {
                                "final_response": messages,
                                "tool_calls_count": tool_calls_count,
                                "conversation": messages,
                            }

                    except Exception as e:
                        raise OrchestratorError(
                            message=f"Error during tool execution: {e}",
                            task_id=None,
                        )

            else:
                # LLM finished response without tool calls
                final_text = (
                    response.content[0].text if response.content else "No response"
                )
                return {
                    "final_response": final_text,
                    "tool_calls_count": tool_calls_count,
                    "conversation": messages,
                }

        # fallback if max iterations reached
        return {
            "final_response": messages[-1]["content"] if messages else "No Response",
            "tool_calls_count": tool_calls_count,
            "error": "max_iterations_exceeded",
            "conversation": messages,
        }

    async def _create_error_result(
        self, tool_use_id: str, error_msg: str
    ) -> Dict[str, Any]:
        """Return a tool_result block shaped for Anthropic messages."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {error_msg}",
                }
            ],
            "is_error": True,
        }

    def _convert_tool_definition(self, tool_def: Dict) -> Dict:
        """Convert tool definition to Anthropic's format"""
        return {
            "name": tool_def["name"],
            "description": tool_def["description"],
            "input_schema": {
                "type": "object",
                "properties": tool_def["parameters"],
                "required": [
                    k
                    for k, v in tool_def["parameters"].items()
                    if v.get("required", False)
                ],
            },
        }

    async def _execute_tool_calls(
        self, tool_calls: List[ToolCall], available_tools: List[Dict[str, Any]]
    ) -> List[dict]:
        """
        Execute multiple tool calls in parallel and return normalized dict results.

        Args:
            tool_calls: List[ToolCall] objects
            available_tools: List of tool definitions (dicts with 'name' and 'function')

        Returns:
            List[dict]: Each dict contains tool_use_id, content, is_error, and optionally error
        """

        # Build lookup from tool name -> function
        print(f"\n\navail toools: {available_tools}\n\n")
        tool_functions: Dict[str, Callable] = self.functions

        async def run_single(tc: ToolCall) -> dict:
            func = tool_functions.get(tc.name)
            if not callable(func):
                return {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": f"ERROR: Unknown tool {tc.name}",
                }
            try:
                result = await self._safe_tool_execution(tc, func)
                return {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,  # should be a string or JSON-serializable
                }
            except asyncio.TimeoutError:
                return {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": f"ERROR: Timeout executing tool {tc.name}",
                }
            except Exception as e:
                return {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": f"ERROR: Exception in tool {tc.name}: {e}",
                }

        # Run all tools concurrently
        results = await asyncio.gather(*[run_single(tc) for tc in tool_calls])
        return [{"role": "user", "content": results}]

    async def _safe_tool_execution(
        self, tool_call: ToolCall, tool_function: Callable
    ) -> dict:
        """
        Execute a single tool call safely with error handling.

        Returns:
            dict with keys: type, tool_use_id, content, is_error, error (optional)
        """
        try:
            # Parse input arguments
            args = tool_call.input
            if isinstance(args, str):
                args = json.loads(args)

            # Call tool function (sync or async)
            if asyncio.iscoroutinefunction(tool_function):
                result = await tool_function(**args)
            else:
                result = tool_function(**args)

            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": [result],
                "is_error": False,
            }

        except Exception as e:
            return {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": None,
                "is_error": True,
                "error": str(e),
            }

    def _extract_tool_calls_and_text(
        self, response
    ) -> Tuple[List[ToolCall], List[str]]:
        tool_calls: List[ToolCall] = []
        text_blocks: List[str] = []

        for block in response.content:
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

        print(f"\n\nTOOL CALLS EXTRACTED → {tool_calls}")
        print(f"\n\nTEXT BLOCKS EXTRACTED → {text_blocks}")
        return tool_calls, text_blocks

    def _add_tool_results_to_messages(
        self,
        messages: List[Dict[str, Any]],
        tool_calls: List[ToolCall],
        tool_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Append tool calls and their results to the conversation messages in a format
        compatible with the LLM tool-calling system.
        """
        for i, result in enumerate(tool_results):
            call = tool_calls[i]

            # Append the assistant message describing the tool call
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": (
                                call.input
                                if isinstance(call.input, dict)
                                else str(call.input)
                            ),
                        }
                    ],
                }
            )

            # Append the tool's returned result (API-compliant)
            content = result.get("content")
            raw_content = result.get("content")
            print(f"\n\n\RAWWWWWWWW)))))))))) ----> {raw_content}")
            if isinstance(raw_content, str):
                snippet = raw_content[:self.MAX_TOOL_RESULT_LENGTH]
            elif isinstance(raw_content, list):
                snippet = [str(x)[:self.MAX_TOOL_RESULT_LENGTH] for x in raw_content]
            else:
                snippet = str(raw_content)[:self.MAX_TOOL_RESULT_LENGTH]

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": [
                                {
                                    "type": "text",  
                                    "text": (
                                        snippet
                                        if isinstance(snippet, str)
                                        else str(snippet)
                                    ),
                                }
                            ],
                        }
                    ],
                }
            )

        return messages

    def _print_event(self, event):
        if event.type == "text":
            print(event.text, end="", flush=True)
        elif event.type == "content_block_stop":
            print(
                "\ncontent block finished accumulating:",
                event.content_block,
            )


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
