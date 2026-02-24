import os
import subprocess
import sys
from pathlib import Path


def _make_env(**overrides):
    env = dict(os.environ)
    env.update(overrides)
    return env


def test_install_dry_run():
    # Use the real install script but inject a test release payload via environment variable
    # to avoid network calls. This keeps the script logic unchanged while making tests deterministic.
    repo_root = Path(__file__).resolve().parents[1]
    orig = repo_root / "scripts" / "install.sh"

    test_release = "v9.9.9\nhttps://example.com/dummy.tar.gz\nhttps://example.com/release"
    env = _make_env(XNETVN_MONITORD_TEST_LATEST_RELEASE=test_release)

    # Execute the script in dry-run mode with injected release metadata
    proc = subprocess.run(
        ["bash", str(orig), "--dry-run", "--install-dir", "/tmp/xnetvn_monitord_test_install"],
        capture_output=True,
        text=True,
        env=env,
    )

    # Debug output on failure
    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)

    assert proc.returncode == 0
    assert "Dry-run: would download release tarball from: https://example.com/dummy.tar.gz" in proc.stdout
    assert "Dry-run: would copy source code" in proc.stdout
    assert "Installation completed successfully! (v9.9.9)" in proc.stdout


def test_install_dry_run_specific_version():
    repo_root = Path(__file__).resolve().parents[1]
    orig = repo_root / "scripts" / "install.sh"

    test_release = "v1.2.3\nhttps://example.com/v1.2.3.tar.gz\nhttps://example.com/release/v1.2.3"
    env = _make_env(XNETVN_MONITORD_TEST_LATEST_RELEASE=test_release)

    proc = subprocess.run(
        [
            "bash",
            str(orig),
            "--dry-run",
            "--version",
            "v1.2.3",
            "--install-dir",
            "/tmp/xnetvn_monitord_test_install",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)

    assert proc.returncode == 0
    assert "v1.2.3" in proc.stdout
    assert "Installation completed successfully!" in proc.stdout


def test_install_requires_release_metadata():
    """install.sh must exit non-zero when no release metadata is available."""
    repo_root = Path(__file__).resolve().parents[1]
    orig = repo_root / "scripts" / "install.sh"

    # Simulate failure by providing an empty release payload
    env = _make_env(XNETVN_MONITORD_TEST_LATEST_RELEASE="\n\n")

    proc = subprocess.run(
        ["bash", str(orig), "--dry-run", "--install-dir", "/tmp/xnetvn_monitord_test_install"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode != 0
    assert "Unable to fetch release metadata" in proc.stderr or "Unable to fetch release metadata" in proc.stdout
