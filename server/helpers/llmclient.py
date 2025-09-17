import os
import json
import asyncio
import httpx
from typing import List, Dict, Any, AsyncGenerator
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


ANTHROPIC_API_KEY = require_env("ANTHROPIC_API_KEY")


class LLMClient:
    def __init__(self):
        self._async = AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            http_client=httpx.AsyncClient(),
            timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=10.0),
        )

    async def stream_text(
        self,
        prompt: str,
        system: str = "You are a helpful assistant",
        model: str = "claude-3-7-sonnet-20250219",
        max_tokens: int = 6000,
    ) -> AsyncGenerator[str, None]:
        """
        Asynchronous text streaming without tool usage.
        Yields text chunks as they are generated.
        """
        try:
            async with self._async.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                system=system,
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield event.text
                    elif event.type == "content_block_delta" and hasattr(
                        event.delta, "text"
                    ):
                        yield event.delta.text
        except Exception as e:
            yield f"Error: {str(e)}"

    async def stream_with_tools(
        self,
        prompt: str,
        system: str,
        tools: List[Dict],
        model: str = "claude-3-7-sonnet-20250219",
        max_tokens: int = 7000,
    ) -> AsyncGenerator[str, None]:
        """
        Simplified streaming with sequential tool execution.
        Yields text chunks and handles tool calls one at a time.
        """
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        formatted_tools = (
            [self._convert_tool_definition(t) for t in tools] if tools else []
        )

        max_iterations = 5
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1

            try:
                async with self._async.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    messages=messages,
                    system=system,
                    tools=formatted_tools if formatted_tools else None,
                ) as stream:
                    # Stream text responses
                    async for event in stream:
                        if event.type == "text":
                            yield event.text
                        elif event.type == "content_block_delta" and hasattr(
                            event.delta, "text"
                        ):
                            yield event.delta.text

                    # Get final message to check for tool calls
                    final_message = await stream.get_final_message()

                    # Check if we need to execute tools
                    tool_calls = self._extract_tool_calls(final_message)
                    if not tool_calls:
                        # No tools to execute, conversation complete
                        return

                    # Execute tools sequentially (one at a time)
                    for tool_call in tool_calls:
                        tool_result = await self._execute_single_tool(tool_call)

                        # Add tool call and result to conversation
                        messages.append(
                            {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "id": tool_call["id"],
                                        "name": tool_call["name"],
                                        "input": tool_call["input"],
                                    }
                                ],
                            }
                        )

                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_call["id"],
                                        "content": tool_result,
                                    }
                                ],
                            }
                        )

            except Exception as e:
                yield f"Error: {str(e)}"
                return

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

    def _extract_tool_calls(self, message) -> List[Dict]:
        """Extract tool calls from LLM response"""
        tool_calls = []
        for block in getattr(message, "content", []):
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}),
                    }
                )
        return tool_calls

    async def _execute_single_tool(self, tool_call: Dict) -> str:
        """Execute a single tool call with proper error handling"""
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]

        # Map tool names to functions (simplified - you'd import actual functions)
        tool_functions = {
            "web_search": self._dummy_web_search,
            "web_fetch": self._dummy_web_fetch,
            "complete_task": self._dummy_complete_task,
        }

        if tool_name not in tool_functions:
            return f"Error: Unknown tool {tool_name}"

        try:
            result = await tool_functions[tool_name](tool_input)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    # Placeholder tool implementations - replace with actual imports
    async def _dummy_web_search(self, input_data: Dict) -> str:
        """Placeholder for web search tool"""
        return f"Search results for: {input_data.get('query', '')}"

    async def _dummy_web_fetch(self, input_data: Dict) -> str:
        """Placeholder for web fetch tool"""
        return f"Fetched content from: {input_data.get('url', '')}"

    async def _dummy_complete_task(self, input_data: Dict) -> str:
        """Placeholder for complete task tool"""
        return "Task completed successfully"

    # Synchronous version for final essay generation
    def generate_text(
        self,
        prompt: str,
        system: str = "You are a helpful assistant",
        model: str = "claude-3-7-sonnet-20250219",
        max_tokens: int = 8000,
    ) -> str:
        """Synchronous text generation for final outputs"""
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )

        return response.content[0].text if response.content else ""
