#!/usr/bin/env python3
"""Helpers for loading runtime secrets from Bitwarden CLI / Secrets Manager CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path


def _run_cli(
    bin_name: str,
    args: list[str],
    env: dict[str, str],
    check: bool = True,
    input_text: str | None = None,
) -> str:
    exe = _resolve_cli(bin_name, env)
    proc = subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
    )
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise RuntimeError(f"Bitwarden CLI failed for '{bin_name} {' '.join(args)}': {detail}")
    return (proc.stdout or "").strip()


def _get_field(item: dict, name: str) -> str:
    fields = item.get("fields") or []
    for field in fields:
        if str(field.get("name") or "") == name:
            return str(field.get("value") or "").strip()
    return ""


def _parse_json(text: str, label: str) -> dict | list:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON from {label}.") from exc


def _resolve_cli(bin_name: str, env: dict[str, str]) -> str:
    found = shutil.which(bin_name)
    if found:
        return found
    if os.name == "nt" and bin_name.lower() == "bws":
        local = str(env.get("LOCALAPPDATA", "")).strip()
        if local:
            candidate = Path(local) / "bws" / "bws.exe"
            if candidate.exists():
                return str(candidate)
    return bin_name


def _require_bws(env: dict[str, str]) -> None:
    exe = _resolve_cli("bws", env)
    if shutil.which(exe) is not None:
        return
    if Path(exe).exists():
        return
    raise RuntimeError("Bitwarden Secrets Manager CLI (bws) is not installed or not in PATH.")


def inject_github_env_from_bw(item_name: str = "projects-factory/github") -> None:
    """Legacy: inject GITHUB_TOKEN/GITHUB_USERNAME from a personal-vault bw item."""
    if shutil.which("bw") is None:
        raise RuntimeError("Bitwarden CLI (bw) is not installed or not in PATH.")

    env = os.environ.copy()
    session = str(env.get("BW_SESSION", "")).strip()
    if not session:
        session = _run_cli("bw", ["unlock", "--raw"], env=env, check=True).strip()
        if not session:
            raise RuntimeError("Failed to unlock Bitwarden vault.")
        os.environ["BW_SESSION"] = session
        env["BW_SESSION"] = session

    item_json = _run_cli("bw", ["get", "item", "--session", session, item_name], env=env, check=True)
    if not item_json:
        raise RuntimeError(f"Bitwarden item not found: {item_name}")
    item = _parse_json(item_json, "bw get item")
    if not isinstance(item, dict):
        raise RuntimeError("Unexpected JSON shape from bw get item.")

    token = _get_field(item, "GITHUB_TOKEN") or str((item.get("login") or {}).get("password") or "").strip()
    username = _get_field(item, "GITHUB_USERNAME") or str((item.get("login") or {}).get("username") or "").strip()

    if not token:
        raise RuntimeError(
            f"GITHUB_TOKEN is empty in Bitwarden item '{item_name}'. "
            "Use custom field GITHUB_TOKEN or login password."
        )

    os.environ["GITHUB_TOKEN"] = token
    if username:
        os.environ["GITHUB_USERNAME"] = username


def _list_bws_secrets(env: dict[str, str], project_id: str | None = None) -> list[dict]:
    args = ["secret", "list"]
    if project_id:
        args.append(project_id)
    payload = _run_cli("bws", args, env=env, check=True)
    data = _parse_json(payload, "bws secret list")
    if not isinstance(data, list):
        raise RuntimeError("Unexpected JSON shape from bws secret list.")
    return [item for item in data if isinstance(item, dict)]


def _find_bws_secret_by_key(secrets: list[dict], key: str) -> dict | None:
    for secret in secrets:
        if str(secret.get("key") or "").strip() == key:
            return secret
    return None


def _get_bws_secret_value(env: dict[str, str], secret: dict) -> str:
    value = str(secret.get("value") or "").strip()
    if value:
        return value
    secret_id = str(secret.get("id") or "").strip()
    if not secret_id:
        return ""
    payload = _run_cli("bws", ["secret", "get", secret_id], env=env, check=True)
    data = _parse_json(payload, "bws secret get")
    if not isinstance(data, dict):
        return ""
    return str(data.get("value") or "").strip()


def inject_github_env_from_bws(
    project_id: str | None = None,
    token_key: str = "GITHUB_TOKEN",
    username_key: str = "GITHUB_USERNAME",
) -> None:
    """Inject GITHUB_* env vars from Bitwarden Secrets Manager (bws)."""
    env = os.environ.copy()
    _require_bws(env)
    access_token = str(env.get("BWS_ACCESS_TOKEN", "")).strip()
    if not access_token:
        raise RuntimeError("BWS_ACCESS_TOKEN is required for bws integration.")

    secrets = _list_bws_secrets(env=env, project_id=project_id)
    token_secret = _find_bws_secret_by_key(secrets, token_key)
    if not token_secret:
        scope_note = f" in project '{project_id}'" if project_id else ""
        raise RuntimeError(f"Secret '{token_key}' was not found{scope_note}.")

    token = _get_bws_secret_value(env, token_secret)
    if not token:
        raise RuntimeError(f"Secret '{token_key}' is empty.")
    os.environ["GITHUB_TOKEN"] = token

    username_secret = _find_bws_secret_by_key(secrets, username_key)
    if username_secret:
        username = _get_bws_secret_value(env, username_secret)
        if username:
            os.environ["GITHUB_USERNAME"] = username


def verify_bws_capabilities(require_write: bool = True, project_id: str | None = None) -> None:
    """Verify bws token has required capabilities; optionally probes create/edit/delete."""
    env = os.environ.copy()
    _require_bws(env)
    access_token = str(env.get("BWS_ACCESS_TOKEN", "")).strip()
    if not access_token:
        raise RuntimeError("BWS_ACCESS_TOKEN is required for bws integration.")

    _list_bws_secrets(env=env, project_id=project_id)
    if not require_write:
        return

    if not project_id:
        raise RuntimeError("BWS_REQUIRE_WRITE=1 requires BWS_PROJECT_ID to run CRUD permission probe.")

    probe_key = f"PF_CLI_PROBE_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    probe_value = f"created-{uuid.uuid4().hex[:8]}"
    probe_note = "Temporary write-permission probe from projects-factory."
    probe_id = ""
    try:
        created_text = _run_cli(
            "bws",
            ["secret", "create", probe_key, probe_value, project_id, "--note", probe_note],
            env=env,
            check=True,
        )
        created = _parse_json(created_text, "bws secret create")
        if not isinstance(created, dict):
            raise RuntimeError("Unexpected JSON shape from bws secret create.")
        probe_id = str(created.get("id") or "").strip()
        if not probe_id:
            raise RuntimeError("bws secret create did not return secret id.")

        edited_value = f"updated-{uuid.uuid4().hex[:8]}"
        _run_cli(
            "bws",
            ["secret", "edit", probe_id, "--value", edited_value],
            env=env,
            check=True,
        )
        _run_cli("bws", ["secret", "delete", probe_id], env=env, check=True)
    except Exception:
        if probe_id:
            try:
                _run_cli("bws", ["secret", "delete", probe_id], env=env, check=False)
            except Exception:
                pass
        raise


def inject_github_env_from_bitwarden(item_name: str = "projects-factory/github") -> None:
    """Backward-compatible alias for legacy bw mode."""
    inject_github_env_from_bw(item_name=item_name)
