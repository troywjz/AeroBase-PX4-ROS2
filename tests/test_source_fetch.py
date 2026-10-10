import importlib.util
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_sources.py"
SPEC = importlib.util.spec_from_file_location("aerobase_fetch_sources", SCRIPT)
fetch_sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_sources)


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def source(path: Path) -> str:
    path.mkdir()
    git("init", str(path))
    git("-C", str(path), "config", "user.email", "test@example.invalid")
    git("-C", str(path), "config", "user.name", "Test")
    (path / ".gitignore").write_text("build/\nlog/\n")
    (path / "source.txt").write_text("fixture")
    git("-C", str(path), "add", ".")
    git("-C", str(path), "commit", "-m", "fixture")
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def test_clean_source_with_ignored_runtime_files_is_accepted(tmp_path, capsys):
    checkout = tmp_path / "source path with spaces"
    commit = source(checkout)
    (checkout / "build").mkdir()
    (checkout / "build/output.log").write_text("ignored")
    fetch_sources.fetch({"commit": commit}, checkout)
    assert "Verified" in capsys.readouterr().out


def test_new_clone_can_be_checked_out_at_locked_sha(tmp_path):
    origin = tmp_path / "local origin"
    locked_commit = source(origin)
    git("-C", str(origin), "branch", "-M", "main")
    (origin / "source.txt").write_text("later revision")
    git("-C", str(origin), "commit", "-am", "later")
    destination = tmp_path / "new runtime" / "checkout with spaces"
    fetch_sources.fetch({"url": str(origin), "ref": "main", "commit": locked_commit}, destination)
    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
    assert actual == locked_commit


def test_dirty_existing_source_fails_without_resetting_user_file(tmp_path):
    checkout = tmp_path / "source"
    commit = source(checkout)
    user_file = checkout / "user-change.txt"
    user_file.write_text("keep me")
    with pytest.raises(SystemExit, match="left unchanged"):
        fetch_sources.fetch({"commit": commit}, checkout)
    assert user_file.read_text() == "keep me"


def test_clean_existing_wrong_sha_fails_without_fetch_or_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "existing source"
    current_commit = source(checkout)
    expected_commit = "a" * 40
    calls = []
    real_run = fetch_sources.subprocess.run

    def record_run(command, **kwargs):
        calls.append(command)
        return real_run(command, **kwargs)

    monkeypatch.setattr(fetch_sources.subprocess, "run", record_run)
    with pytest.raises(SystemExit, match="does not match the locked commit"):
        fetch_sources.fetch({"commit": expected_commit}, checkout)
    actual_commit = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    assert actual_commit == current_commit
    assert not any(command[3] in {"fetch", "checkout"} for command in calls if len(command) > 3 and command[1] == "-C")


def test_network_failure_retries_once_with_single_operation_proxy(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode, stderr=""):
            self.returncode = returncode
            self.stdout = ""
            self.stderr = stderr

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result(1, "Could not resolve host") if len(calls) == 1 else Result(0)

    monkeypatch.setattr(fetch_sources.subprocess, "run", fake_run)
    fetch_sources.git_operation(["git", "clone", "remote", "destination"], network=True,
                                proxy="http://user:private-token@example.invalid:1234")
    assert len(calls) == 2
    assert calls[1][1:3] == ["-c", "http.proxy=http://user:private-token@example.invalid:1234"]


def test_non_network_failure_does_not_retry_proxy(monkeypatch):
    calls = []

    class Result:
        returncode = 1
        stdout = ""
        stderr = "fatal: invalid refspec"

    monkeypatch.setattr(fetch_sources.subprocess, "run", lambda command, **kwargs: calls.append(command) or Result())
    with pytest.raises(SystemExit, match="detailed output is suppressed"):
        fetch_sources.git_operation(["git", "fetch", "origin", "bad"], network=True, proxy="http://proxy.invalid")
    assert len(calls) == 1
