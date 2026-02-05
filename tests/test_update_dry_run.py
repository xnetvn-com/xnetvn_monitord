import re
import subprocess
import sys
from pathlib import Path


def test_update_dry_run(tmp_path):
    # Prepare a sandbox install directory with a fake installed package
    install_dir = tmp_path / "install"
    pkg_dir = install_dir / "xnetvn_monitord"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text('__version__ = "0.0.1"\n')

    # Use the real update script but inject a test release payload via environment variable to avoid
    # network calls and fragile file edits. This keeps the script logic unchanged while making tests deterministic.
    repo_root = Path(__file__).resolve().parents[1]
    orig = repo_root / "scripts" / "update.sh"

    test_release = "v9.9.9\nhttps://example.com/dummy.tar.gz\nhttps://example.com/release"

    env = dict(**{**{k: v for k, v in __import__('os').environ.items()}, 'XNETVN_MONITORD_TEST_LATEST_RELEASE': test_release})

    # Execute the script in dry-run mode with injected environment
    proc = subprocess.run(["bash", str(orig), "--install-dir", str(install_dir), "--dry-run"], capture_output=True, text=True, env=env)

    # Debug output on failure
    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)

    assert proc.returncode == 0
    assert "Dry-run: would create backup directory" in proc.stdout
    assert "Dry-run: would download release tarball" in proc.stdout
    assert "Update applied successfully" in proc.stdout
