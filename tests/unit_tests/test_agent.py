import json
from unittest.mock import MagicMock, patch

import pytest
from openai import BadRequestError, RateLimitError

from agent import ExcelAgent, LLMProvider


@pytest.fixture
def mock_openai_client():
    with patch("agent.OpenAI") as mock_openai_class:
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        yield mock_client_instance


@pytest.fixture
def agent(mock_openai_client):
    with patch("os.getenv", return_value="fake_key"):
        # We need to mock AVAILABLE_PROVIDERS so we have multiple providers to fall back to.
        mock_provider_1 = LLMProvider("Primary", mock_openai_client, "model-1")
        mock_provider_2 = LLMProvider("Secondary", mock_openai_client, "model-2")
        
        with patch("agent.AVAILABLE_PROVIDERS", [mock_provider_1, mock_provider_2]):
            agent_instance = ExcelAgent()
            yield agent_instance


def test_agent_happy_path(agent, mock_openai_client):
    """Test Path A: Agent returns a direct text response."""
    # 1. Setup Mock Response
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "There are 29 properties listed in Seattle."
    mock_message.tool_calls = None  # No tools requested
    mock_response.choices = [MagicMock(message=mock_message)]

    mock_openai_client.chat.completions.create.return_value = mock_response

    # Alias for readability in assertions
    mock_client = mock_openai_client

    # 2. Execute
    response_text = agent.chat("How many properties are listed in Seattle?")

    # 3. Assertions
    assert response_text == "There are 29 properties listed in Seattle."
    # Assert history contains the user message and the assistant's reply
    assert len(agent.history) == 2
    assert agent.history[0]["role"] == "user"
    assert agent.history[1]["role"] == "assistant"
    assert agent.history[1]["content"] == "There are 29 properties listed in Seattle."
    # Assert Groq API was called exactly once
    assert mock_openai_client.chat.completions.create.call_count == 1


@patch("agent.TOOL_FUNCTIONS")
def test_agent_react_loop(mock_tool_functions, agent, mock_openai_client):
    """Test Path B: Agent requests a tool, executes it, and returns a final response."""
    # 1. Setup Mock for Tool Functions
    mock_query_data = MagicMock(return_value={"total_matching": 1, "rows": [{"List Price": 500000}]})
    mock_tool_functions.__getitem__.return_value = mock_query_data

    # 2. Setup Mock Responses from Groq (Two turns)
    
    # Turn 1: LLM requests `query_data`
    mock_response_1 = MagicMock()
    mock_message_1 = MagicMock()
    mock_message_1.content = None
    
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "query_data"
    mock_tool_call.function.arguments = '{"dataset": "real_estate", "filters": {"City": "Seattle"}}'
    
    mock_message_1.tool_calls = [mock_tool_call]
    mock_response_1.choices = [MagicMock(message=mock_message_1)]

    # Turn 2: LLM provides final answer
    mock_response_2 = MagicMock()
    mock_message_2 = MagicMock()
    mock_message_2.content = "I found 1 listing in Seattle."
    mock_message_2.tool_calls = None
    mock_response_2.choices = [MagicMock(message=mock_message_2)]

    # Tell the mock client to return response 1 first, then response 2
    mock_openai_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

    # 3. Execute
    response_text = agent.chat("Find listings in Seattle")

    # 4. Assertions
    assert response_text == "I found 1 listing in Seattle."
    
    # Verify the tool was actually called with the correct arguments
    mock_tool_functions.__getitem__.assert_called_with("query_data")
    mock_query_data.assert_called_with(dataset="real_estate", filters={"City": "Seattle"})

    # Verify history length: User -> Assistant (Tool Call) -> Tool Result -> Assistant (Final)
    assert len(agent.history) == 4
    assert agent.history[0]["role"] == "user"
    assert agent.history[1]["role"] == "assistant"
    assert "tool_calls" in agent.history[1]
    assert agent.history[2]["role"] == "tool"
    assert "500000" in agent.history[2]["content"]  # The result was appended
    assert agent.history[3]["role"] == "assistant"

    # Verify API was called twice
    assert mock_openai_client.chat.completions.create.call_count == 2


@patch("time.sleep")
def test_agent_retry_logic_success(mock_sleep, agent, mock_openai_client):
    """Test that the agent retries on tool_use_failed errors and eventually succeeds."""
    
    # 1. Setup Mock Responses: Fail -> Fail -> Succeed
    error_response = MagicMock()
    error_response.json.return_value = {"error": {"message": "tool_use_failed details"}}
    bad_request_error = BadRequestError("Error: tool_use_failed", response=error_response, body={"error": {"code": "tool_use_failed"}})
    
    # Success response
    mock_response_success = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Success after retries!"
    mock_message.tool_calls = None
    mock_response_success.choices = [MagicMock(message=mock_message)]

    # Side effect: Error, Error, Success
    mock_openai_client.chat.completions.create.side_effect = [
        bad_request_error,
        bad_request_error,
        mock_response_success
    ]

    # 2. Execute
    response_text = agent.chat("Test retry")

    # 3. Assertions
    assert response_text == "Success after retries!"
    assert mock_openai_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2  # Should have slept twice before succeeding


@patch("time.sleep")
def test_agent_retry_logic_failure(mock_sleep, agent, mock_openai_client):
    """Test that the agent raises the exception if it fails 3 times."""
    
    # 1. Setup Mock Responses: Fail -> Fail -> Fail
    error_response = MagicMock()
    error_response.json.return_value = {"error": {"message": "tool_use_failed details"}}
    bad_request_error = BadRequestError("Error: tool_use_failed", response=error_response, body={"error": {"code": "tool_use_failed"}})
    
    mock_openai_client.chat.completions.create.side_effect = [
        bad_request_error,
        bad_request_error,
        bad_request_error
    ]

    # 2. Execute & Assert it raises
    with pytest.raises(BadRequestError):
        agent.chat("Test retry exhaust")

    # 3. Assertions
    assert mock_openai_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2  # Slept twice, failed on the third attempt


def test_agent_fallback_on_rate_limit(agent, mock_openai_client):
    """Test that the agent falls back to the next provider on RateLimitError."""
    # 1. Setup Mock Responses: RateLimitError -> Success
    error_response = MagicMock()
    error_response.status_code = 429
    rate_limit_error = RateLimitError("Rate limit exceeded", response=error_response, body=None)
    
    mock_response_success = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Success from backup!"
    mock_message.tool_calls = None
    mock_response_success.choices = [MagicMock(message=mock_message)]

    mock_openai_client.chat.completions.create.side_effect = [
        rate_limit_error,
        mock_response_success
    ]

    # Initial provider index should be 0
    assert agent.provider_idx == 0

    # 2. Execute
    response_text = agent.chat("Test fallback")

    # 3. Assertions
    assert response_text == "Success from backup!"
    assert mock_openai_client.chat.completions.create.call_count == 2
    # Provider index should have incremented to 1 (Secondary)
    assert agent.provider_idx == 1


def test_agent_fallback_exhaustion(agent, mock_openai_client):
    """Test that the agent raises RateLimitError if all providers are exhausted."""
    # 1. Setup Mock Responses: RateLimitError -> RateLimitError
    error_response = MagicMock()
    error_response.status_code = 429
    rate_limit_error = RateLimitError("Rate limit exceeded", response=error_response, body=None)
    
    mock_openai_client.chat.completions.create.side_effect = [
        rate_limit_error,
        rate_limit_error
    ]

    # Initial provider index should be 0
    assert agent.provider_idx == 0

    # 2. Execute & Assert it raises
    with pytest.raises(RateLimitError):
        agent.chat("Test fallback exhaust")

    # 3. Assertions
    assert mock_openai_client.chat.completions.create.call_count == 2
    # Provider index should have incremented to 1 (the last provider) before raising
    assert agent.provider_idx == 1
