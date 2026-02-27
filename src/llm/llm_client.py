"""LLM client using LiteLLM for Bedrock/Ollama integration."""

import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

try:
    from litellm import completion
except ImportError as err:
    raise ImportError("litellm is not installed. Please install it with: uv add litellm") from err

load_dotenv()


class LLMClient:
    """
    LLM client using LiteLLM for unified access to Bedrock and Ollama.

    Supports:
    - AWS Bedrock: Claude, Titan, Llama models
    - Ollama: Local models (llama2, mistral, etc.)
    - OpenAI: GPT models (if needed)
    """

    def __init__(
        self,
        model: str = "ollama/llama2",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        api_base: str | None = None,
    ):
        """
        Initialize LLM client.

        Args:
            model: Model identifier. Examples:
                - Bedrock: "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
                - Ollama: "ollama/llama2" or "ollama/mistral"
                - OpenAI: "gpt-4" or "gpt-3.5-turbo"
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            api_base: Optional API base URL for Ollama (default: http://localhost:11434)
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_base = api_base or os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

        # Validate Bedrock credentials if using Bedrock
        if model.startswith("bedrock/"):
            self._validate_bedrock_credentials()

        logger.info("LLM Client initialized: %s", model)

    def _validate_bedrock_credentials(self):
        """Check if AWS credentials are configured for Bedrock."""
        required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            logger.warning(
                "Missing AWS credentials: %s. Set these in .env file or environment "
                "variables for Bedrock access.",
                ", ".join(missing),
            )

    def _build_kwargs(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict:
        """Build the keyword arguments dict for litellm.completion()."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        if stream:
            kwargs["stream"] = True
        if self.model.startswith("ollama/"):
            kwargs["api_base"] = self.api_base
        return kwargs

    def generate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str:
        """
        Generate completion using LiteLLM.

        Args:
            messages: List of message dicts with "role" and "content"
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            stream: Whether to stream the response

        Returns:
            Generated text response
        """
        kwargs = self._build_kwargs(messages, temperature, max_tokens, stream=stream)

        try:
            if stream:
                return self._stream_completion(kwargs)

            response = completion(**kwargs)
            return response.choices[0].message.content

        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg and self.model.startswith("ollama/"):
                raise RuntimeError(
                    f"Cannot connect to Ollama at {self.api_base}. "
                    "Make sure Ollama is running: ollama serve"
                ) from e
            raise

    def generate_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        Yield text chunks from a streaming LLM completion.

        Same arguments as generate(), but yields str chunks instead of
        returning the full text.  Intended for use with st.write_stream().
        """
        kwargs = self._build_kwargs(messages, temperature, max_tokens, stream=True)

        for chunk in completion(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _stream_completion(self, kwargs: dict) -> str:
        """Stream completion and return full response."""
        kwargs["stream"] = True
        response_text = ""

        for chunk in completion(**kwargs):
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                response_text += content

        print()  # New line after streaming
        return response_text

    def chat(
        self,
        user_message: str,
        system_message: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Simple chat interface for single-turn conversations.

        Args:
            user_message: User's message
            system_message: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Model's response
        """
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": user_message})

        return self.generate(messages, temperature=temperature, max_tokens=max_tokens)

    @classmethod
    def from_env(cls, model_env_var: str = "LLM_MODEL") -> "LLMClient":
        """
        Create LLM client from environment variables.

        Environment variables:
            LLM_MODEL: Model identifier (default: ollama/llama2)
            LLM_TEMPERATURE: Temperature (default: 0.0)
            LLM_MAX_TOKENS: Max tokens (default: 2048)
            OLLAMA_API_BASE: Ollama API base URL

        For Bedrock:
            AWS_ACCESS_KEY_ID
            AWS_SECRET_ACCESS_KEY
            AWS_REGION_NAME
        """
        model = os.getenv(model_env_var, "ollama/llama2")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
        api_base = os.getenv("OLLAMA_API_BASE")

        return cls(model=model, temperature=temperature, max_tokens=max_tokens, api_base=api_base)


# Example usage
if __name__ == "__main__":
    # Test with Ollama
    client = LLMClient(model="ollama/llama2")
    response = client.chat(
        user_message="What is steel manufacturing?",
        system_message="You are a helpful assistant that answers questions about metallurgy.",
    )
    print(response)
