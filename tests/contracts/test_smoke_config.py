from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from smoke.lib.config import (
    DEFAULT_TARGETS,
    TARGET_REQUIRED_ENV,
    SmokeConfig,
)


def _settings(**overrides):
    values = {
        "model": "deepseek/deepseek-chat",
        "model_opus": None,
        "model_sonnet": None,
        "model_haiku": None,
        "nvidia_nim_api_key": "",
        "open_router_api_key": "",
        "deepseek_api_key": "deepseek-key",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _smoke_config(**overrides) -> SmokeConfig:
    values = {
        "root": Path("."),
        "results_dir": Path(".smoke-results"),
        "live": False,
        "interactive": False,
        "targets": DEFAULT_TARGETS,
        "provider_matrix": frozenset(),
        "timeout_s": 45.0,
        "prompt": "Reply with exactly: FCC_SMOKE_PONG",
        "claude_bin": "claude",
        "worker_id": "main",
        "settings": _settings(),
    }
    values.update(overrides)
    return SmokeConfig(**values)


def test_deepseek_is_default_smoke_target() -> None:
    assert "providers" in DEFAULT_TARGETS
    assert "providers" in TARGET_REQUIRED_ENV


def test_deepseek_provider_configuration_uses_api_key() -> None:
    config = _smoke_config()

    assert config.has_provider_configuration("deepseek")
    assert config.provider_models()[0].full_model == "deepseek/deepseek-chat"


def test_deepseek_provider_matrix_filters_models() -> None:
    config = _smoke_config(provider_matrix=frozenset({"deepseek"}))

    assert [model.provider for model in config.provider_models()] == ["deepseek"]


def test_provider_smoke_models_cover_configured_providers_independent_of_model_mapping(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FCC_SMOKE_MODEL_NVIDIA_NIM", "1")
    config = _smoke_config(
        settings=_settings(
            model="open_router/test",
            deepseek_api_key="",
            open_router_api_key="",
            nvidia_nim_api_key="nim-key",
        )
    )

    models = config.provider_smoke_models()

    assert [model.provider for model in models] == ["nvidia_nim"]
    assert models[0].full_model == "nvidia_nim/1"
    assert models[0].source == "FCC_SMOKE_MODEL_NVIDIA_NIM"


def test_provider_smoke_model_override_accepts_model_name_without_prefix(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FCC_SMOKE_MODEL_DEEPSEEK", "deepseek-reasoner")
    config = _smoke_config(
        settings=_settings(
            deepseek_api_key="deepseek-key",
        ),
        provider_matrix=frozenset({"deepseek"}),
    )

    models = config.provider_smoke_models()

    assert models[0].full_model == "deepseek/deepseek-reasoner"
    assert models[0].source == "FCC_SMOKE_MODEL_DEEPSEEK"


def test_provider_smoke_model_override_accepts_owner_model_name(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FCC_SMOKE_MODEL_NVIDIA_NIM", "z-ai/glm-5.1")
    config = _smoke_config(
        settings=_settings(
            model="deepseek/deepseek-chat",
            deepseek_api_key="",
            nvidia_nim_api_key="nim-key",
        ),
        provider_matrix=frozenset({"nvidia_nim"}),
    )

    models = config.provider_smoke_models()

    assert models[0].full_model == "nvidia_nim/z-ai/glm-5.1"
    assert models[0].source == "FCC_SMOKE_MODEL_NVIDIA_NIM"


def test_provider_smoke_model_override_rejects_wrong_provider_prefix(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FCC_SMOKE_MODEL_DEEPSEEK", "open_router/llama3.1")
    config = _smoke_config(
        settings=_settings(
            deepseek_api_key="deepseek-key",
        ),
        provider_matrix=frozenset({"deepseek"}),
    )

    try:
        config.provider_smoke_models()
    except ValueError as exc:
        assert "FCC_SMOKE_MODEL_DEEPSEEK" in str(exc)
    else:
        raise AssertionError("expected wrong provider prefix to fail")


def test_provider_smoke_matrix_filters_provider_catalog(monkeypatch) -> None:
    monkeypatch.delenv("FCC_SMOKE_MODEL_DEEPSEEK", raising=False)
    config = _smoke_config(
        settings=_settings(
            deepseek_api_key="deepseek-key",
            nvidia_nim_api_key="nim-key",
        ),
        provider_matrix=frozenset({"nvidia_nim"}),
    )

    assert [model.provider for model in config.provider_smoke_models()] == [
        "nvidia_nim"
    ]


def test_provider_smoke_does_not_include_unmapped_cloud_when_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FCC_SMOKE_MODEL_NVIDIA_NIM", raising=False)
    config = _smoke_config(
        settings=_settings(
            model="deepseek/test", nvidia_nim_api_key="", deepseek_api_key=""
        )
    )

    assert config.provider_smoke_models() == []
