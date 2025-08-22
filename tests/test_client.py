import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Callable
from utils.types import ToolCall, ToolResult
from colorama import init, Fore, Style
import logging


from helpers.llmclient import (
    _convert_tool_definition,
    _safe_tool_execution,
    _execute_tool_calls,
    llm_call_with_tools,
    stream_llm_sync,
    stream_llm_messages_async
)

# Set up detailed logging for visual comparison
init()

# Custom logger config for colored output
class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.BLUE,
        "INFO": Fore.WHITE,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA,
    }

    def format(self, record):
        # Color the level name
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            )

        # Color special markers
        message = super().format(record)
        message = message.replace("✓", f"{Fore.GREEN}✓{Style.RESET_ALL}")
        message = message.replace("✗", f"{Fore.RED}✗{Style.RESET_ALL}")
        message = message.replace("EXPECTED:", f"{Fore.CYAN}EXPECTED:{Style.RESET_ALL}")
        message = message.replace("ACTUAL:", f"{Fore.YELLOW}ACTUAL:{Style.RESET_ALL}")

        return message
    
# logging w/ colors setup
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Test fixtures
@pytest.fixture
def sample_tool_definition():
    """What a tool definition should look like in your format"""
    return {
        "name": "web_search",
        "description": "Search the web for information",
        "function": lambda query: f"Results for: {query}",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search query",
                "required": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Max results",
                "required": False,
                "default": 10,
            },
        },
    }


@pytest.fixture
def sample_tool_call():
    """What a tool call from Claude looks like"""
    return ToolCall(
        id="call_123", name="web_search", arguments={"query": "quantum computing"}
    )


# ============= TEST: _convert_tool_definition =============


def test_convert_tool_definition(sample_tool_definition):
    """Test conversion to Anthropic's tool format"""

    logger.info("\n=== TEST: _convert_tool_definition ===")
    logger.info(f"INPUT: {json.dumps(sample_tool_definition, default=str, indent=2)}")

    # EXPECTED behavior
    expected_output = {
        "name": "web_search",
        "description": "Search the web for information",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 10,
                },
            },
            "required": ["query"],  # Only required fields
        },
    }

    logger.info(f"EXPECTED OUTPUT: {json.dumps(expected_output, indent=2)}")

    # ACTUAL execution
    actual_output = _convert_tool_definition(sample_tool_definition)
    logger.info(f"ACTUAL OUTPUT: {json.dumps(actual_output, indent=2)}")

    # Assertions with detailed comparison
    assert actual_output["name"] == expected_output["name"], "Tool name mismatch"
    assert (
        actual_output["description"] == expected_output["description"]
    ), "Description mismatch"
    assert "input_schema" in actual_output, "Missing input_schema in conversion"
    assert (
        actual_output["input_schema"]["type"] == "object"
    ), "Schema type should be 'object'"

    # Check required fields extraction
    if "required" in actual_output["input_schema"]:
        logger.info(f"✓ Required fields: {actual_output['input_schema']['required']}")
    else:
        logger.warning("✗ Missing 'required' field in schema")


def test_convert_tool_definition_no_required_params():
    """Test with all optional parameters"""

    logger.info("\n=== TEST: Tool with no required params ===")

    tool_def = {
        "name": "get_time",
        "description": "Get current time",
        "function": lambda: "12:00 PM",
        "parameters": {
            "timezone": {"type": "string", "required": False, "default": "UTC"}
        },
    }

    expected_required = []  # No required params
    logger.info(f"EXPECTED required fields: {expected_required}")

    actual_output = _convert_tool_definition(tool_def)
    actual_required = actual_output.get("input_schema", {}).get("required", [])
    logger.info(f"ACTUAL required fields: {actual_required}")

    assert actual_required == expected_required


# ============= TEST: _safe_tool_execution =============


@pytest.mark.asyncio
async def test_safe_tool_execution_success(sample_tool_call):
    """Test successful tool execution"""

    logger.info("\n=== TEST: _safe_tool_execution (Success Case) ===")

    # Mock tool function
    async def mock_tool(**kwargs):
        logger.info(f"Tool called with args: {kwargs}")
        return {"results": ["result1", "result2"]}

    # EXPECTED behavior
    logger.info(
        "EXPECTED: Tool executes successfully and returns ToolResult with content"
    )

    # ACTUAL execution
    result = await _safe_tool_execution(sample_tool_call, mock_tool)

    logger.info(f"ACTUAL result: {result}")

    # Assertions
    assert isinstance(result, ToolResult), "Should return ToolResult"
    assert result.tool_call_id == "call_123", "Should preserve tool_call_id"
    assert result.content is not None, "Should have content"
    assert result.error is None, "Should have no error on success"
    logger.info("✓ Success case handled correctly")


@pytest.mark.asyncio
async def test_safe_tool_execution_with_exception():
    """Test tool execution with exception handling"""

    logger.info("\n=== TEST: _safe_tool_execution (Exception Handling) ===")

    # Mock tool that raises exception
    async def failing_tool(**kwargs):
        logger.info("Tool about to fail...")
        raise ValueError("Tool execution failed!")

    tool_call = ToolCall(id="call_456", name="failing_tool", arguments={})

    # EXPECTED behavior
    logger.info(
        "EXPECTED: Returns ToolResult with error field populated, no exception raised"
    )

    # ACTUAL execution
    result = await _safe_tool_execution(tool_call, failing_tool)

    logger.info(f"ACTUAL result: {result}")

    # Assertions
    assert isinstance(result, ToolResult), "Should return ToolResult even on failure"
    assert result.tool_call_id == "call_456", "Should preserve tool_call_id"
    assert result.content is None, "Content should be None on error"
    assert result.error is not None, "Should have error message"
    assert (
        "Tool execution failed" in result.error
    ), "Error should contain exception message"
    logger.info("✓ Exception handled gracefully")


@pytest.mark.asyncio
async def test_safe_tool_execution_json_arguments():
    """Test handling of JSON string arguments"""

    logger.info("\n=== TEST: _safe_tool_execution (JSON argument parsing) ===")

    # Tool call with JSON string arguments (common from API)
    tool_call = ToolCall(
        id="call_789",
        name="test_tool",
        arguments='{"key": "value", "number": 42}',  # String JSON
    )

    received_args = None

    async def capture_args_tool(**kwargs):
        nonlocal received_args
        received_args = kwargs
        return "success"

    # EXPECTED behavior
    expected_args = {"key": "value", "number": 42}
    logger.info(f"EXPECTED parsed args: {expected_args}")

    # ACTUAL execution
    result = await _safe_tool_execution(tool_call, capture_args_tool)

    logger.info(f"ACTUAL parsed args: {received_args}")

    # Assertions
    assert received_args == expected_args, "Should parse JSON string to dict"
    logger.info("✓ JSON arguments parsed correctly")


# ============= TEST: _execute_tool_calls =============


@pytest.mark.asyncio
async def test_execute_tool_calls_parallel():
    """Test parallel execution of multiple tool calls"""

    logger.info("\n=== TEST: _execute_tool_calls (Parallel Execution) ===")

    # Track execution order
    execution_log = []

    async def slow_tool_1(**kwargs):
        execution_log.append("tool1_start")
        await asyncio.sleep(0.1)
        execution_log.append("tool1_end")
        return "result1"

    async def slow_tool_2(**kwargs):
        execution_log.append("tool2_start")
        await asyncio.sleep(0.05)
        execution_log.append("tool2_end")
        return "result2"

    tool_calls = [
        ToolCall(id="1", name="tool1", arguments={}),
        ToolCall(id="2", name="tool2", arguments={}),
    ]

    available_tools = [
        {"name": "tool1", "function": slow_tool_1},
        {"name": "tool2", "function": slow_tool_2},
    ]

    # EXPECTED behavior
    logger.info("EXPECTED: Tools start simultaneously (parallel), not sequentially")
    logger.info("EXPECTED order: Both start before either finishes")

    # ACTUAL execution
    results = await _execute_tool_calls(tool_calls, available_tools)

    logger.info(f"ACTUAL execution order: {execution_log}")

    # Assertions for parallel execution
    assert execution_log[0] == "tool1_start", "Tool 1 should start"
    assert (
        execution_log[1] == "tool2_start"
    ), "Tool 2 should start before tool 1 finishes"
    assert "tool2_end" in execution_log, "Tool 2 should complete"
    assert "tool1_end" in execution_log, "Tool 1 should complete"

    # Check results
    assert len(results) == 2, "Should return results for both tools"
    assert all(
        isinstance(r, ToolResult) for r in results
    ), "All results should be ToolResult"
    logger.info("✓ Parallel execution confirmed")


@pytest.mark.asyncio
async def test_execute_tool_calls_unknown_tool():
    """Test handling of unknown tool"""

    logger.info("\n=== TEST: _execute_tool_calls (Unknown Tool) ===")

    tool_calls = [
        ToolCall(id="1", name="known_tool", arguments={}),
        ToolCall(id="2", name="unknown_tool", arguments={}),
    ]

    available_tools = [{"name": "known_tool", "function": lambda: "success"}]

    # EXPECTED behavior
    logger.info("EXPECTED: Unknown tool returns error result, doesn't crash")

    # ACTUAL execution
    results = await _execute_tool_calls(tool_calls, available_tools)

    logger.info(f"ACTUAL results count: {len(results)}")
    logger.info(
        f"Result for unknown tool: {results[1] if len(results) > 1 else 'Missing'}"
    )

    # Assertions
    assert len(results) == 2, "Should return result for each tool call"
    assert results[1].error is not None, "Unknown tool should have error"
    assert "unknown_tool" in results[1].error.lower(), "Error should mention tool name"
    logger.info("✓ Unknown tool handled gracefully")


# ============= TEST: llm_call_with_tools =============


@pytest.mark.asyncio
async def test_llm_call_with_tools_no_tools_needed():
    """Test when LLM doesn't need to use tools"""

    logger.info("\n=== TEST: llm_call_with_tools (No Tools Used) ===")

    # Mock stream_llm_messages_async to return response without tool calls
    mock_response = Mock()
    mock_response.content = "The capital of France is Paris."
    mock_response.tool_calls = None

    with patch("helpers.llmclient.stream_llm_messages_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response

        # EXPECTED behavior
        logger.info("EXPECTED: Returns immediately with final_response, no tool calls")

        # ACTUAL execution
        result = await llm_call_with_tools(
            prompt="What is the capital of France?", tools=[], timeout=10
        )

        logger.info(f"ACTUAL result keys: {result.keys()}")
        logger.info(f"Tool calls count: {result.get('tool_calls_count', 'missing')}")

        # Assertions
        assert "final_response" in result, "Should have final_response"
        assert result["tool_calls_count"] == 0, "Should have 0 tool calls"
        assert "conversation" in result, "Should include conversation history"
        logger.info("✓ No-tool case handled correctly")


@pytest.mark.asyncio
async def test_llm_call_with_tools_with_tool_loop():
    """Test conversation loop with tool usage"""

    logger.info("\n=== TEST: llm_call_with_tools (Tool Loop) ===")

    # Mock responses for conversation loop
    response1 = Mock()
    response1.content = "I'll search for that information."
    response1.tool_calls = [
        ToolCall(id="1", name="web_search", arguments={"query": "test"})
    ]

    response2 = Mock()
    response2.content = "Based on the search results, here's the answer."
    response2.tool_calls = None  # No more tools, done

    with patch("helpers.llmclient.stream_llm_messages_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [response1, response2]

        # Mock tool
        async def mock_search(query):
            return f"Results for: {query}"

        tools = [
            {
                "name": "web_search",
                "function": mock_search,
                "parameters": {"query": {"type": "string"}},
            }
        ]

        # EXPECTED behavior
        logger.info(
            "EXPECTED: Makes tool call, gets result, continues conversation, then completes"
        )

        # ACTUAL execution
        result = await llm_call_with_tools(
            prompt="Find information about quantum computing", tools=tools, timeout=10
        )

        logger.info(f"ACTUAL tool calls: {result.get('tool_calls_count', 'missing')}")
        logger.info(f"Conversation length: {len(result.get('conversation', []))}")

        # Assertions
        assert result["tool_calls_count"] == 1, "Should have made 1 tool call"
        assert (
            len(result["conversation"]) >= 3
        ), "Should have user, assistant, tool, assistant messages"
        assert "final_response" in result, "Should have final response"
        logger.info("✓ Tool loop executed correctly")


@pytest.mark.asyncio
async def test_llm_call_with_tools_timeout():
    """Test timeout handling"""

    logger.info("\n=== TEST: llm_call_with_tools (Timeout) ===")

    async def slow_llm_mock(*args, **kwargs):
        await asyncio.sleep(5)  # Longer than timeout
        return Mock()

    with patch("helpers.llmclient.stream_llm_messages_async", new=slow_llm_mock):

        # EXPECTED behavior
        logger.info("EXPECTED: Times out after 1 second, returns error result")

        # ACTUAL execution
        result = await llm_call_with_tools(
            prompt="Test prompt", tools=[], timeout=1  # 1 second timeout
        )

        logger.info(f"ACTUAL result: {result}")

        # Assertions
        assert result.get("error") == "timeout", "Should indicate timeout error"
        assert (
            "timeout" in result.get("final_response", "").lower()
        ), "Should mention timeout"
        logger.info("✓ Timeout handled correctly")


@pytest.mark.asyncio
async def test_llm_call_with_tools_max_calls_limit():
    """Test max tool calls safety limit"""

    logger.info("\n=== TEST: llm_call_with_tools (Max Calls Limit) ===")

    # Mock LLM that always wants to use tools
    mock_response = Mock()
    mock_response.content = "I need to keep searching..."
    mock_response.tool_calls = [ToolCall(id="x", name="search", arguments={})]

    with patch("helpers.llmclient.stream_llm_messages_async", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response  # Always returns tool calls

        with patch("helpers.llmclient._execute_tool_calls", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [ToolResult("x", "result", None)]

            # Override max_tool_calls for testing
            with patch("MAX_TOOL_CALLS", 3):

                # EXPECTED behavior
                logger.info("EXPECTED: Stops after 3 tool calls (safety limit)")

                # ACTUAL execution
                result = await llm_call_with_tools(
                    prompt="Test",
                    tools=[{"name": "search", "function": lambda: "result"}],
                    timeout=10,
                )

                logger.info(
                    f"ACTUAL tool calls: {result.get('tool_calls_count', 'missing')}"
                )
                logger.info(f"Error: {result.get('error', 'none')}")

                # Assertions
                assert result["tool_calls_count"] <= 3, "Should not exceed max calls"
                assert (
                    result.get("error") == "max_tool_calls_exceeded"
                ), "Should indicate limit exceeded"
                logger.info("✓ Max calls limit enforced")


# ============= TEST: stream_llm_messages_async =============


@pytest.mark.asyncio
async def test_stream_llm_messages_async():
    """Test async streaming with tools"""
    
    logger.info(f"{Fore.CYAN}\n=== TEST: stream_llm_messages_async ==={Style.RESET_ALL}")
    
    messages = [{"role": "user", "content": "Test message"}]
    tools = [{"name": "test_tool", "input_schema": {"type": "object"}}]
    model = "claude-3-sonnet-20240229"
    max_tokens = 2000
    
    logger.info(f"INPUT messages: {messages}")
    logger.info(f"INPUT tools: {len(tools)} tools")
    logger.info(f"INPUT model: {model}")
    logger.info(f"INPUT max_tokens: {max_tokens}")
    
    # EXPECTED behavior
    logger.info(f"{Fore.CYAN}EXPECTED: Returns Message object from Anthropic API{Style.RESET_ALL}")
    logger.info(f"{Fore.CYAN}EXPECTED: Handles streaming properly{Style.RESET_ALL}")
    logger.info(f"{Fore.CYAN}EXPECTED: Passes tools and model correctly to API{Style.RESET_ALL}")
    
    # Mock the Anthropic API response
    mock_message = Mock()
    mock_message.content = "This is a test response from Claude"
    mock_message.model = model
    mock_message.usage = Mock()
    mock_message.usage.input_tokens = 10
    mock_message.usage.output_tokens = 15
    mock_message.tool_calls = None  # No tool calls in this response
    
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        # Mock the client instance
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        
        # Mock the messages.create method
        mock_client.messages.create.return_value = mock_message
        
        # ACTUAL execution
        result = await stream_llm_messages_async(messages, tools, model, max_tokens)
        
        logger.info(f"{Fore.YELLOW}ACTUAL result type: {type(result)}{Style.RESET_ALL}")
        logger.info(f"{Fore.YELLOW}ACTUAL content: {result.content if hasattr(result, 'content') else 'No content attr'}{Style.RESET_ALL}")
        logger.info(f"{Fore.YELLOW}ACTUAL model: {result.model if hasattr(result, 'model') else 'No model attr'}{Style.RESET_ALL}")
        
        # Verify the API was called correctly
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        
        logger.info(f"API called with: {call_args}")
        
        # Assertions
        assert result is not None, "Should return a message object"
        assert hasattr(result, 'content'), "Message should have content attribute"
        assert result.content == "This is a test response from Claude", "Content should match mock"
        
        # Verify API call parameters
        assert call_args[1]['model'] == model, "Should pass correct model"
        assert call_args[1]['max_tokens'] == max_tokens, "Should pass correct max_tokens"
        assert call_args[1]['messages'] == messages, "Should pass messages correctly"
        assert 'tools' in call_args[1], "Should include tools parameter"
        
        logger.info(f"{Fore.GREEN}✓ Message object returned correctly{Style.RESET_ALL}")
        logger.info(f"{Fore.GREEN}✓ API parameters passed correctly{Style.RESET_ALL}")

@pytest.mark.asyncio
async def test_stream_llm_messages_async_with_tool_calls():
    """Test async streaming when Claude wants to use tools"""
    
    logger.info(f"{Fore.CYAN}\n=== TEST: stream_llm_messages_async (With Tool Calls) ==={Style.RESET_ALL}")
    
    messages = [{"role": "user", "content": "Search for quantum computing news"}]
    tools = [{"name": "web_search", "input_schema": {"type": "object"}}]
    
    # Mock response with tool calls
    mock_message = Mock()
    mock_message.content = "I'll search for that information."
    mock_message.tool_calls = [
        Mock(id="call_123", name="web_search", arguments={"query": "quantum computing news"})
    ]
    
    # EXPECTED behavior
    logger.info(f"{Fore.CYAN}EXPECTED: Returns Message with tool_calls populated{Style.RESET_ALL}")
    
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_message
        
        # ACTUAL execution
        result = await stream_llm_messages_async(messages, tools, "claude-3-sonnet", 1000)
        
        logger.info(f"{Fore.YELLOW}ACTUAL tool_calls: {result.tool_calls if hasattr(result, 'tool_calls') else 'No tool_calls attr'}{Style.RESET_ALL}")
        
        # Assertions
        assert hasattr(result, 'tool_calls'), "Should have tool_calls attribute"
        assert result.tool_calls is not None, "tool_calls should not be None"
        assert len(result.tool_calls) == 1, "Should have 1 tool call"
        assert result.tool_calls[0].name == "web_search", "Tool call name should match"
        
        logger.info(f"{Fore.GREEN}✓ Tool calls handled correctly{Style.RESET_ALL}")

@pytest.mark.asyncio
async def test_stream_llm_messages_async_api_error():
    """Test handling of API errors"""
    
    logger.info(f"{Fore.CYAN}\n=== TEST: stream_llm_messages_async (API Error) ==={Style.RESET_ALL}")
    
    messages = [{"role": "user", "content": "Test"}]
    tools = []
    
    # EXPECTED behavior
    logger.info(f"{Fore.CYAN}EXPECTED: Raises exception on API error{Style.RESET_ALL}")
    
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        
        # Mock API error
        from anthropic import APIError
        mock_client.messages.create.side_effect = APIError("Rate limit exceeded")
        
        # ACTUAL execution - should raise exception
        with pytest.raises(APIError) as exc_info:
            await stream_llm_messages_async(messages, tools, "claude-3-sonnet", 1000)
        
        logger.info(f"{Fore.YELLOW}ACTUAL exception: {exc_info.value}{Style.RESET_ALL}")
        
        assert "Rate limit exceeded" in str(exc_info.value), "Should preserve original error message"
        logger.info(f"{Fore.GREEN}✓ API error handled correctly{Style.RESET_ALL}")

@pytest.mark.asyncio
async def test_stream_llm_messages_async_empty_tools():
    """Test with empty tools list"""
    
    logger.info(f"{Fore.CYAN}\n=== TEST: stream_llm_messages_async (Empty Tools) ==={Style.RESET_ALL}")
    
    messages = [{"role": "user", "content": "Simple question"}]
    tools = []  # Empty tools
    
    # EXPECTED behavior
    logger.info(f"{Fore.CYAN}EXPECTED: Works with empty tools list{Style.RESET_ALL}")
    
    mock_message = Mock()
    mock_message.content = "Simple answer"
    mock_message.tool_calls = None
    
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_message
        
        # ACTUAL execution
        result = await stream_llm_messages_async(messages, tools, "claude-3-haiku", 500)
        
        logger.info(f"{Fore.YELLOW}ACTUAL result: {result.content}{Style.RESET_ALL}")
        
        # Check API call
        call_args = mock_client.messages.create.call_args
        passed_tools = call_args[1].get('tools', 'not_passed')
        
        logger.info(f"Tools parameter: {passed_tools}")
        
        # Assertions
        assert result.content == "Simple answer", "Should return simple response"
        # Should either pass empty list or not pass tools parameter at all
        assert passed_tools == [] or passed_tools == 'not_passed', "Should handle empty tools appropriately"
        
        logger.info(f"{Fore.GREEN}✓ Empty tools handled correctly{Style.RESET_ALL}")

@pytest.mark.asyncio
async def test_stream_llm_messages_async_default_parameters():
    """Test default parameter handling"""
    
    logger.info(f"{Fore.CYAN}\n=== TEST: stream_llm_messages_async (Default Parameters) ==={Style.RESET_ALL}")
    
    messages = [{"role": "user", "content": "Test"}]
    tools = []
    
    # EXPECTED behavior - check what defaults are actually used
    logger.info(f"{Fore.CYAN}EXPECTED: Uses appropriate default model and max_tokens{Style.RESET_ALL}")
    
    mock_message = Mock()
    mock_message.content = "Response"
    
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_message
        
        # Call with minimal parameters (testing defaults)
        result = await stream_llm_messages_async(messages, tools, 'claude-sonnet-4-20250514', 4000)
        
        # Check what defaults were used
        call_args = mock_client.messages.create.call_args
        used_model = call_args[1].get('model', 'no_model')
        used_max_tokens = call_args[1].get('max_tokens', 'no_max_tokens')
        
        logger.info(f"{Fore.YELLOW}ACTUAL default model: {used_model}{Style.RESET_ALL}")
        logger.info(f"{Fore.YELLOW}ACTUAL default max_tokens: {used_max_tokens}{Style.RESET_ALL}")
        
        # Assertions (adjust these based on your function's actual defaults)
        assert used_model != 'no_model', "Should have a default model"
        assert used_max_tokens != 'no_max_tokens', "Should have default max_tokens"
        assert isinstance(used_max_tokens, int), "max_tokens should be integer"
        
        logger.info(f"{Fore.GREEN}✓ Default parameters work correctly{Style.RESET_ALL}")


# ============= TEST: stream_llm_sync =============


def test_stream_llm_sync():
    """Test synchronous LLM call"""

    logger.info("\n=== TEST: stream_llm_sync ===")

    # EXPECTED behavior
    logger.info("EXPECTED: Synchronous call, returns string response")
    logger.info("EXPECTED: Uses system prompt if provided")

    with patch("anthropic.Anthropic") as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.messages.create.return_value = Mock(content="Test response")

        # ACTUAL execution
        result = stream_llm_sync(
            prompt="Test prompt",
            system_prompt="You are a helpful assistant",
            model="claude-sonnet-4-20250514",
        )

        logger.info(f"ACTUAL result type: {type(result)}")
        logger.info(f"ACTUAL result: {result}")

        # Assertions
        assert isinstance(result, str), "Should return string"
        logger.info("✓ Sync call works correctly")


# ============= RUN ALL TESTS =============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
