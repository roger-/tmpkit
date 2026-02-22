from __future__ import annotations

import argparse
from getpass import getpass
from hashlib import sha1
from pathlib import Path
from typing import Any

import yaml

from tmpkit.deco.client import DecoSshClient, DecoSshConfig
from tmpkit.lib.ssh import SshTmpTarget


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email", default=None, help="TP-Link ID email")
    parser.add_argument(
        "--login-yaml",
        default=None,
        help=(
            "Path to YAML file with credentials (keys: user/email and password). "
            "If omitted, tries login.yaml, ../login.yaml, then /login.yaml."
        ),
    )


def _read_login_config(args: argparse.Namespace) -> dict[str, Any]:
    cached = getattr(args, "_login_config_cache", None)
    if isinstance(cached, dict):
        return cached

    candidates: list[Path] = []
    raw = getattr(args, "login_yaml", None)
    if isinstance(raw, str) and raw.strip():
        candidates.append(Path(raw.strip()))
    else:
        candidates.extend((Path("login.yaml"), Path("../login.yaml"), Path("/login.yaml")))

    loaded: dict[str, Any] = {}
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        if isinstance(parsed, dict):
            loaded = parsed
            break

    setattr(args, "_login_config_cache", loaded)
    return loaded


def get_email(args: argparse.Namespace) -> str:
    if args.email is not None:
        email = str(args.email).strip()
        if email:
            return email

    cfg = _read_login_config(args)
    for key in ("user", "email", "username"):
        raw = cfg.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text

    raise ValueError("No email provided (use --email or a login.yaml with user/email)")


def read_password(args: argparse.Namespace) -> str:
    if args.ssh_pass is not None:
        return str(args.ssh_pass)

    cfg = _read_login_config(args)
    for key in ("password", "ssh_pass"):
        raw = cfg.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text

    return getpass("SSH password: ")


def make_client(
    *,
    host: str,
    email: str,
    ssh_password: str,
    timeout_seconds: float,
    debug_raw: bool = False,
    all_nodes: bool = False,
) -> DecoSshClient:
    return DecoSshClient(
        DecoSshConfig(
            host=str(host),
            email=str(email),
            ssh_password=str(ssh_password),
            timeout_seconds=float(timeout_seconds),
            debug_raw=bool(debug_raw),
        ),
        all_nodes=bool(all_nodes),
    )


def make_target(
    *,
    host: str,
    email: str,
    ssh_password: str,
    timeout_seconds: float,
    ssh_port: int = 20001,
    dest_host: str = "127.0.0.1",
    dest_port: int = 20002,
) -> SshTmpTarget:
    return SshTmpTarget(
        host=str(host),
        port=int(ssh_port),
        username=sha1(str(email).encode()).hexdigest(),
        password=str(ssh_password),
        dest_host=str(dest_host),
        dest_port=int(dest_port),
        timeout_seconds=float(timeout_seconds),
    )
