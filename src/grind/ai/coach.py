"""AI Coach - unified interface for Copilot and OpenRouter."""

from typing import AsyncIterator, Literal

from openai import AsyncOpenAI

from grind.config import Settings


class Coach:
    """AI coaching interface with streaming support."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = self._create_client()
        self._conversation: list[dict[str, str]] = []

    def _create_client(self) -> AsyncOpenAI:
        """Create the appropriate OpenAI client based on provider."""
        if self.settings.provider == "copilot":
            return AsyncOpenAI(
                base_url=f"{self.settings.copilot_relay_url}/v1",
                api_key="copilot",  # Relay handles auth
            )
        else:  # openrouter
            return AsyncOpenAI(
                base_url=self.settings.openrouter_base_url,
                api_key=self.settings.openrouter_api_key or "",
            )

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation = []

    def set_problem_context(self, problem_title: str, problem_description: str) -> None:
        """Set the current problem context for the coach."""
        self._conversation = [
            {
                "role": "user",
                "content": f"I'm working on this problem:\n\n# {problem_title}\n\n{problem_description}",
            },
            {
                "role": "assistant",
                "content": "I see the problem. Let me know when you're ready to discuss your approach or if you need any hints!",
            },
        ]

    async def chat(self, message: str) -> str:
        """Send a message and get a complete response."""
        chunks = []
        async for chunk in self.stream(message):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream(self, message: str) -> AsyncIterator[str]:
        """Send a message and stream the response."""
        self._conversation.append({"role": "user", "content": message})

        messages = [
            {"role": "system", "content": self.settings.agent.system_prompt},
            *self._conversation,
        ]

        response = await self._client.chat.completions.create(
            model=self.settings.agent.model,
            messages=messages,  # type: ignore
            temperature=self.settings.agent.temperature,
            stream=True,
        )

        full_response = []
        async for chunk in response:  # type: ignore[union-attr]
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response.append(content)
                yield content

        self._conversation.append({"role": "assistant", "content": "".join(full_response)})

    async def get_hint(self, code: str, hint_level: Literal["gentle", "medium", "strong"]) -> str:
        """Get a hint based on current code and desired hint strength."""
        prompts = {
            "gentle": "Give me a very subtle hint about the direction I should think in, without revealing the approach.",
            "medium": "Give me a hint about what pattern or technique might be useful here.",
            "strong": "I'm stuck. Give me a clear hint about the approach, but don't write the code.",
        }

        message = f"Here's my current code:\n\n```\n{code}\n```\n\n{prompts[hint_level]}"
        return await self.chat(message)

    async def review_code(self, code: str, language: str) -> str:
        """Review submitted code and provide feedback."""
        message = f"""Review my {language} solution:

```{language}
{code}
```

Analyze:
1. Time and space complexity
2. Edge cases handled/missed
3. Code style and readability
4. Potential optimizations
5. Pattern recognition (what technique did I use?)"""
        return await self.chat(message)

    async def explain_approach(self, approach: str) -> str:
        """Explain a specific algorithmic approach."""
        message = f"Explain the {approach} approach/pattern and how it applies to this problem."
        return await self.chat(message)
