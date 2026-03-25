import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_restore_quarantine_script_restores_manifest(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "restore_quarantine.sh"
    install_dir = tmp_path / "install"
    package_dir = install_dir / "xnetvn_monitord"
    source_package_dir = repo_root / "src" / "xnetvn_monitord"
    shutil.copytree(source_package_dir, package_dir)

    quarantine_dir = install_dir / ".local" / "quarantine"
    manifest_dir = quarantine_dir / "manifests"
    items_dir = quarantine_dir / "items" / "run-restore"
    manifest_dir.mkdir(parents=True)
    items_dir.mkdir(parents=True)

    original_path = tmp_path / "restore-target" / "candidate.log"
    quarantine_path = items_dir / "000001_candidate.log"
    quarantine_path.write_text("payload", encoding="utf-8")

    manifest_path = manifest_dir / "run-restore.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run-restore",
                "generated_at": 1_000_000,
                "items": [
                    {
                        "original_path": str(original_path),
                        "quarantine_path": str(quarantine_path),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "bash",
            str(script_path),
            "--install-dir",
            str(install_dir),
            "--manifest",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)

    assert proc.returncode == 0
    assert original_path.read_text(encoding="utf-8") == "payload"
    assert quarantine_path.exists() is False
    assert manifest_path.exists() is False


def test_restore_quarantine_script_fails_for_missing_manifest(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "restore_quarantine.sh"
    install_dir = tmp_path / "install"
    package_dir = install_dir / "xnetvn_monitord"
    source_package_dir = repo_root / "src" / "xnetvn_monitord"
    shutil.copytree(source_package_dir, package_dir)

    missing_manifest = tmp_path / "missing.json"
    proc = subprocess.run(
        [
            "bash",
            str(script_path),
            "--install-dir",
            str(install_dir),
            "--manifest",
            str(missing_manifest),
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "Manifest file not found" in proc.stderr
