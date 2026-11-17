import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_client(monkeypatch, config):
    monkeypatch.setitem(sys.modules, "config", config)
    spec = importlib.util.spec_from_file_location("client_under_test", ROOT / "src/parsers/hh_api_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HHApiClient()


def test_no_config_no_authorization(monkeypatch):
    monkeypatch.delenv("HH_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("USER_AGENT_EMAIL", raising=False)
    client = load_client(monkeypatch, None)
    assert "Authorization" not in client.headers


def test_environment_overrides_local_config(monkeypatch):
    monkeypatch.setenv("HH_ACCESS_TOKEN", "test-environment-token")
    monkeypatch.setenv("USER_AGENT_EMAIL", "test@example.invalid")
    client = load_client(monkeypatch, SimpleNamespace(HH_ACCESS_TOKEN="test-local-token", USER_AGENT_EMAIL="local@example.invalid"))
    assert client.headers["Authorization"] == "Bearer test-environment-token"
    assert "test@example.invalid" in client.headers["User-Agent"]


def test_empty_environment_disables_local_token(monkeypatch):
    monkeypatch.setenv("HH_ACCESS_TOKEN", "")
    monkeypatch.setenv("USER_AGENT_EMAIL", "")
    client = load_client(monkeypatch, SimpleNamespace(HH_ACCESS_TOKEN="test-local-token"))
    assert "Authorization" not in client.headers


@pytest.mark.parametrize("error", [FileNotFoundError(), PermissionError()])
def test_command_line_file_errors(monkeypatch, capsys, error):
    import runpy
    import pandas as pd
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(pd, "read_csv", fail)
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
    assert result.value.code == 1
    assert "файл" in capsys.readouterr().out.lower()
