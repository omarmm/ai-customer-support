
from pathlib import Path

import pytest

from app.llm.prompt_management import (
    InvalidPromptTemplateError,
    InvalidPromptVariableValueError,
    MissingPromptVariablesError,
    PromptDefinition,
    PromptRegistry,
    PromptRenderer,
    UnexpectedPromptVariablesError,
    UnknownPromptError,
)


@pytest.fixture
def prompt_setup(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "welcome.txt").write_text(
        "Hello $name. Your order is $order_id.",
        encoding="utf-8",
    )

    definitions = {
        "welcome": PromptDefinition(
            template_file="welcome.txt",
            required_variables=frozenset({"name", "order_id"}),
        )
    }

    registry = PromptRegistry(
        prompts_dir=prompts_dir,
        definitions=definitions,
    )

    return registry, PromptRenderer(registry)


def test_render_prompt_with_multiple_variables(prompt_setup):
    _, renderer = prompt_setup

    result = renderer.render(
        "welcome",
        {"name": "Omar", "order_id": "123"},
    )

    assert result == "Hello Omar. Your order is 123."


def test_missing_variable_is_rejected(prompt_setup):
    _, renderer = prompt_setup

    with pytest.raises(MissingPromptVariablesError):
        renderer.render("welcome", {"name": "Omar"})


def test_unexpected_variable_is_rejected(prompt_setup):
    _, renderer = prompt_setup

    with pytest.raises(UnexpectedPromptVariablesError):
        renderer.render(
            "welcome",
            {
                "name": "Omar",
                "order_id": "123",
                "extra": "unexpected",
            },
        )


def test_unknown_prompt_is_rejected(prompt_setup):
    _, renderer = prompt_setup

    with pytest.raises(UnknownPromptError):
        renderer.render("unknown", {})


def test_non_string_value_is_rejected(prompt_setup):
    _, renderer = prompt_setup

    with pytest.raises(InvalidPromptVariableValueError):
        renderer.render(
            "welcome",
            {"name": "Omar", "order_id": 123},
        )


def test_empty_values_are_allowed(prompt_setup):
    _, renderer = prompt_setup

    result = renderer.render(
        "welcome",
        {"name": "", "order_id": ""},
    )

    assert result == "Hello . Your order is ."


def test_rendering_is_deterministic(prompt_setup):
    _, renderer = prompt_setup
    variables = {"name": "Omar", "order_id": "123"}

    assert renderer.render("welcome", variables) == renderer.render(
        "welcome", variables
    )


def test_template_content_is_not_modified(prompt_setup):
    registry, renderer = prompt_setup
    template_path = registry._prompts_dir / "welcome.txt"
    original = template_path.read_text(encoding="utf-8")

    renderer.render(
        "welcome",
        {"name": "Omar", "order_id": "123"},
    )

    assert template_path.read_text(encoding="utf-8") == original


def test_invalid_template_syntax_is_rejected(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "broken.txt").write_text(
        "Hello $",
        encoding="utf-8",
    )

    registry = PromptRegistry(
        prompts_dir=prompts_dir,
        definitions={
            "broken": PromptDefinition(
                template_file="broken.txt",
                required_variables=frozenset(),
            )
        },
    )

    with pytest.raises(InvalidPromptTemplateError):
        PromptRenderer(registry).render("broken", {})


def test_template_variable_mismatch_is_rejected(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "welcome.txt").write_text(
        "Hello $name",
        encoding="utf-8",
    )

    registry = PromptRegistry(
        prompts_dir=prompts_dir,
        definitions={
            "welcome": PromptDefinition(
                template_file="welcome.txt",
                required_variables=frozenset({"customer_name"}),
            )
        },
    )

    with pytest.raises(InvalidPromptTemplateError):
        PromptRenderer(registry).render("welcome", {"customer_name": "Omar"})


def test_variable_values_are_not_evaluated_as_templates(prompt_setup):
    _, renderer = prompt_setup

    result = renderer.render(
        "welcome",
        {
            "name": "$order_id",
            "order_id": "123",
        },
    )

    assert result == "Hello $order_id. Your order is 123."



def test_path_traversal_is_rejected(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("Sensitive content", encoding="utf-8")

    registry = PromptRegistry(
        prompts_dir=prompts_dir,
        definitions={
            "outside": PromptDefinition(
                template_file="../outside.txt",
                required_variables=frozenset(),
            )
        },
    )

    with pytest.raises(InvalidPromptTemplateError):
        PromptRenderer(registry).render("outside", {})


def test_non_string_variable_name_is_rejected(prompt_setup):
    _, renderer = prompt_setup

    with pytest.raises(InvalidPromptVariableValueError):
        renderer.render(
            "welcome",
            {"name": "Omar", "order_id": "123", 42: "invalid"},
        )
