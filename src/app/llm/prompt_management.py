
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Mapping


class PromptManagementError(Exception):
    """Base exception for prompt management errors."""


class UnknownPromptError(PromptManagementError):
    """Raised when a prompt identifier is unknown."""


class MissingPromptVariablesError(PromptManagementError):
    """Raised when required prompt variables are missing."""


class UnexpectedPromptVariablesError(PromptManagementError):
    """Raised when unexpected prompt variables are supplied."""


class InvalidPromptVariableValueError(PromptManagementError):
    """Raised when a prompt variable has an invalid value."""


class InvalidPromptTemplateError(PromptManagementError):
    """Raised when a prompt template is missing or invalid."""


@dataclass(frozen=True)
class PromptDefinition:
    template_file: str
    required_variables: frozenset[str]


PROMPT_DEFINITIONS: dict[str, PromptDefinition] = {
    "support_message_analysis": PromptDefinition(
        template_file="support_message_analysis.txt",
        required_variables=frozenset({"customer_message"}),
    ),
}


class PromptRegistry:
    def __init__(
        self,
        prompts_dir: Path | None = None,
        definitions: Mapping[str, PromptDefinition] | None = None,
    ) -> None:
        self._prompts_dir = (
            prompts_dir
            if prompts_dir is not None
            else Path(__file__).parent / "prompts"
        )
        self._definitions = (
            definitions
            if definitions is not None
            else PROMPT_DEFINITIONS
        )

    def get_template(self, prompt_id: str) -> tuple[Template, frozenset[str]]:
        definition = self._definitions.get(prompt_id)

        if definition is None:
            raise UnknownPromptError(
                f"Unknown prompt identifier: {prompt_id}"
            )

        filename = Path(definition.template_file)

        if filename.is_absolute() or ".." in filename.parts:
            raise InvalidPromptTemplateError(
                f"Invalid template path for prompt: {prompt_id}"
            )

        template_path = (self._prompts_dir / filename).resolve()

        try:
            template_path.relative_to(self._prompts_dir.resolve())
        except ValueError as exc:
            raise InvalidPromptTemplateError(
                f"Invalid template path for prompt: {prompt_id}"
            ) from exc

        try:
            content = template_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InvalidPromptTemplateError(
                f"Unable to load template for prompt: {prompt_id}"
            ) from exc

        template = Template(content)

        if not template.is_valid():
            raise InvalidPromptTemplateError(
                f"Invalid template syntax for prompt: {prompt_id}"
            )

        actual_variables = set(template.get_identifiers())
        expected_variables = set(definition.required_variables)

        if actual_variables != expected_variables:
            raise InvalidPromptTemplateError(
                f"Template variables do not match the definition "
                f"for prompt: {prompt_id}"
            )

        return template, definition.required_variables


class PromptRenderer:
    def __init__(self, registry: PromptRegistry) -> None:
        self._registry = registry


    def render(
        self,
        prompt_id: str,
        variables: Mapping[str, str],
    ) -> str:
        template, required_variables = (
            self._registry.get_template(prompt_id)
        )

        # Validate names and values before comparing variable sets.
        for name, value in variables.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise InvalidPromptVariableValueError(
                    "Prompt variable names and values must be strings."
                )

        supplied_variables = set(variables)

        missing = required_variables - supplied_variables
        if missing:
            raise MissingPromptVariablesError(
                f"Missing required variables: {sorted(missing)}"
            )

        unexpected = supplied_variables - required_variables
        if unexpected:
            raise UnexpectedPromptVariablesError(
                f"Unexpected variables: {sorted(unexpected)}"
            )

        try:
            return template.substitute(variables)
        except (KeyError, ValueError) as exc:
            raise InvalidPromptTemplateError(
                "Unable to render the prompt template."
            ) from exc

