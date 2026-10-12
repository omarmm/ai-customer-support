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

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            return await self.provider.generate(request)
        except LLMError:
            raise
        except LLMProviderError as exc:
            raise self._normalize_provider_error(exc) from exc
        except Exception as exc:
            raise LLMUnexpectedError(
                "Unexpected internal error during LLM generation."
            ) from exc

    def _normalize_provider_error(self, error: LLMProviderError) -> LLMError:
        for provider_error_type, application_error_type in _PROVIDER_ERROR_MAP:
            if isinstance(error, provider_error_type):
                return application_error_type(str(error))

        return LLMError(str(error))
