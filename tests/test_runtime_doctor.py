import importlib.util
import json
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doctor.py"
SPEC = importlib.util.spec_from_file_location("aerobase_doctor", SCRIPT)
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def checkout(path: Path, content="source") -> str:
    path.mkdir(parents=True)
    git("init", str(path))
    git("-C", str(path), "config", "user.email", "test@example.invalid")
    git("-C", str(path), "config", "user.name", "Test")
    (path / ".gitignore").write_text("build/\nlog/\n")
    (path / "source.txt").write_text(content)
    git("-C", str(path), "add", ".")
    git("-C", str(path), "commit", "-m", "fixture")
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def fixture(tmp_path):
    repo = tmp_path / "project with spaces"
    runtime = tmp_path / "runtime path with spaces"
    (repo / "config").mkdir(parents=True)
    (repo / "ros2_ws/src/aerobase_monitor").mkdir(parents=True)
    runtime.mkdir()
    names = {
        "px4": "PX4-Autopilot",
        "px4_msgs": "ros2_ws/src/px4_msgs",
        "agent": "Micro-XRCE-DDS-Agent",
        "agent_logger": "spdlog",
    }
    locks = {}
    for key, relative in names.items():
        commit = checkout(runtime / relative)
        locks[key] = {"commit": commit}
    (repo / "config/stack.lock.json").write_text(json.dumps({
        "px4": locks["px4"], "px4_msgs": locks["px4_msgs"],
        "agent": locks["agent"], "agent_logger": locks["agent_logger"],
    }))
    for relative in (
        "PX4-Autopilot/build/px4_sitl_default/bin/px4",
        "agent-install/bin/MicroXRCEAgent",
        "agent-install/lib/libagent.so",
        "ros2_ws/install/setup.bash",
        "px4-venv/bin/python",
    ):
        file = runtime / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("fixture")
        if relative.endswith("/px4") or relative.endswith("/MicroXRCEAgent") or relative.endswith("/bin/python"):
            file.chmod(0o755)
    (runtime / "ros2_ws/src").mkdir(parents=True, exist_ok=True)
    (runtime / "ros2_ws/src/aerobase_monitor").symlink_to(repo / "ros2_ws/src/aerobase_monitor", target_is_directory=True)
    (runtime / "PX4-Autopilot/build/log").mkdir(parents=True)
    (runtime / "PX4-Autopilot/build/log/build.log").write_text("ignored build output")
    release = tmp_path / "os-release"
    release.write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
    return repo, runtime, release, locks


def run_doctor(repo, runtime, release):
    return doctor.diagnose(repo, runtime, env={"ROS_DISTRO": "jazzy"}, release_file=release,
                           ros_setup=runtime / "ros2_ws/install/setup.bash",
                           system="Linux", machine="x86_64")


def test_clean_locked_runtime_and_ignored_build_logs_pass(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    assert report["overall"] == "pass"
    assert all(item["status"] == "pass" for item in report["checks"])
    assert "runtime path with spaces" not in json.dumps(report)


def test_missing_source_is_reported_as_fetch_build_next_step(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    (runtime / "spdlog").rename(runtime / "spdlog.saved")
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    source_check = next(item for item in report["checks"] if item["name"] == "source.spdlog")
    assert source_check["status"] == "warn"
    assert "build_runtime.sh" in source_check["detail"]


def test_locked_commit_mismatch_fails_without_exposing_checkout_path(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    # Add a commit to the PX4 checkout while preserving its working tree.
    px4 = runtime / "PX4-Autopilot"
    (px4 / "source.txt").write_text("different revision")
    git("-C", str(px4), "add", "source.txt")
    git("-C", str(px4), "commit", "-m", "mismatch")
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    source_check = next(item for item in report["checks"] if item["name"] == "source.px4")
    assert source_check["status"] == "fail"
    assert str(runtime) not in json.dumps(report)


def test_package_link_mismatch_preserves_migration_guidance(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    link = runtime / "ros2_ws/src/aerobase_monitor"
    link.unlink()
    old_package = tmp_path / "old package"
    old_package.mkdir()
    link.symlink_to(old_package, target_is_directory=True)
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    item = next(item for item in report["checks"] if item["name"] == "runtime.package_link")
    assert item["status"] == "fail"
    assert "new runtime directory" in item["detail"]
    assert link.resolve() == old_package.resolve()


def test_arm_is_warned_without_claiming_accepted_architecture(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = doctor.diagnose(repo, runtime, env={"ROS_DISTRO": "jazzy"}, release_file=release,
                            ros_setup=runtime / "ros2_ws/install/setup.bash",
                            system="Linux", machine="aarch64")
    architecture = next(item for item in report["checks"] if item["name"] == "architecture")
    assert architecture["status"] == "warn"
    assert "not yet accepted" in architecture["detail"]
    assert report["host_architecture"] == "arm64"


def test_malformed_lock_is_a_failure_check_instead_of_an_exception(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    (repo / "config/stack.lock.json").write_text(json.dumps({"px4": {"commit": "a" * 40}}))
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    lock_check = next(item for item in report["checks"] if item["name"] == "source.lock")
    assert lock_check["status"] == "fail"
    assert "malformed" in lock_check["detail"]


def test_non_executable_build_binary_is_reported_as_missing(tmp_path, monkeypatch):
    repo, runtime, release, _ = fixture(tmp_path)
    (runtime / "PX4-Autopilot/build/px4_sitl_default/bin/px4").chmod(0o644)
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/fixture")
    report = run_doctor(repo, runtime, release)
    px4_check = next(item for item in report["checks"] if item["name"] == "runtime.px4")
    assert px4_check["status"] == "warn"
    assert "not executable" in px4_check["detail"]


def test_strict_cli_returns_nonzero_for_warning_while_default_does_not(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "diagnose", lambda *_: {"overall": "warn", "checks": []})
    monkeypatch.setattr(doctor.sys, "argv", [str(SCRIPT), "--json"])
    assert doctor.main() == 0
    json.loads(capsys.readouterr().out)
    monkeypatch.setattr(doctor.sys, "argv", [str(SCRIPT), "--json", "--strict"])
    assert doctor.main() == 1
    json.loads(capsys.readouterr().out)
