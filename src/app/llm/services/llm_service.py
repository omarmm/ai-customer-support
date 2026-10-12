import asyncio
from collections.abc import Awaitable, Callable

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnexpectedError,
    LLMUnavailableError,
)
from app.llm.providers.base import LLMProvider
from app.llm.providers.exceptions import (
    LLMProviderAuthenticationError,
    LLMProviderConnectionError,
    LLMProviderError,
    LLMProviderHTTPError,
    LLMProviderInvalidRequestError,
    LLMProviderModelNotFoundError,
    LLMProviderRateLimitError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from app.llm.retry import RetryPolicy

# Ordered by specificity: provider HTTP subclasses must match before the
# generic LLMProviderHTTPError, and LLMProviderHTTPError before its base
# LLMProviderError. Unclassified provider failures map to the base LLMError.
_PROVIDER_ERROR_MAP: tuple[
    tuple[type[LLMProviderError], type[LLMError]], ...
] = (
    (LLMProviderTimeoutError, LLMTimeoutError),
    (LLMProviderConnectionError, LLMConnectionError),
    (LLMProviderRateLimitError, LLMRateLimitError),
    (LLMProviderAuthenticationError, LLMAuthenticationError),
    (LLMProviderInvalidRequestError, LLMInvalidRequestError),
    (LLMProviderModelNotFoundError, LLMModelNotFoundError),
    (LLMProviderUnavailableError, LLMUnavailableError),
    (LLMProviderResponseError, LLMResponseError),
    (LLMProviderHTTPError, LLMError),
    (LLMProviderError, LLMError),
)


class LLMService:

    def __init__(
        self,
        provider: LLMProvider,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        self.provider = provider
        self.retry_policy = (
            retry_policy if retry_policy is not None else RetryPolicy()
        )
        self._sleep = sleep if sleep is not None else asyncio.sleep

    async def generate(self, request: LLMRequest) -> LLMResponse:
        attempt = 0

        while True:
            try:
                response = await self.provider.generate(request)
            except LLMError:
                # Already an application-level error; pass it through
                # unchanged without retrying (it was not normalized here).
                raise
            except LLMProviderError as exc:
                error = self._normalize_provider_error(exc)
                cause = exc
            except Exception as exc:
                raise LLMUnexpectedError(
                    "Unexpected internal error during LLM generation."
                ) from exc
            else:
                response.metadata["retry_count"] = attempt
                return response

            if not error.retryable or attempt >= self.retry_policy.max_retries:
                error.retry_count = attempt
                raise error from cause

            await self._sleep(self.retry_policy.delay_for_attempt(attempt))
            attempt += 1

    def _normalize_provider_error(self, error: LLMProviderError) -> LLMError:
        for provider_error_type, application_error_type in _PROVIDER_ERROR_MAP:
            if isinstance(error, provider_error_type):
                return application_error_type(str(error))

        return LLMError(str(error))
