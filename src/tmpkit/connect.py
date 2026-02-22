"""Convenience constructors for low-level TMP and TMP/AppV2 SSH sessions."""

from __future__ import annotations

import logging

from tmpkit.lib.ssh import SshTmpTarget

logger = logging.getLogger(__name__)


def connect_tmp(
    *,
    host: str,
    username: str,
    password: str,
    port: int = 22,
    dest_host: str = "127.0.0.1",
    dest_port: int = 20002,
    timeout_seconds: float = 8.0,
    main_ver: int = 1,
    second_ver: int = 1,
):
    """Convenience helper to get a TMP session over SSH.

    Returns a context manager yielding a `TmpSession`.

    Example:
        from tmpkit import connect_tmp

        with connect_tmp(host="192.168.0.29", port=20001, username="...", password="...") as session:
            session.assoc(send_client_hello=True)
    """

    logger.debug(
        "connect_tmp(host=%s port=%s dest_port=%s timeout=%ss)",
        host,
        int(port),
        int(dest_port),
        float(timeout_seconds),
    )

    target = SshTmpTarget(
        host=host,
        port=int(port),
        username=username,
        password=password,
        dest_host=dest_host,
        dest_port=int(dest_port),
        timeout_seconds=float(timeout_seconds),
    )
    return target.connect_tmp(main_ver=main_ver, second_ver=second_ver)


def connect_appv2(
    *,
    host: str,
    username: str,
    password: str,
    port: int = 22,
    dest_host: str = "127.0.0.1",
    dest_port: int = 20002,
    timeout_seconds: float = 8.0,
    main_ver: int = 1,
    second_ver: int = 1,
    business_type: int = 1,
    business_ver: int = 2,
):
    """Convenience helper to get a TMP/AppV2 session over SSH.

    Returns a context manager yielding a `TmpAppV2Session`.
    """

    logger.debug(
        "connect_appv2(host=%s port=%s dest_port=%s timeout=%ss)",
        host,
        int(port),
        int(dest_port),
        float(timeout_seconds),
    )

    target = SshTmpTarget(
        host=host,
        port=int(port),
        username=username,
        password=password,
        dest_host=dest_host,
        dest_port=int(dest_port),
        timeout_seconds=float(timeout_seconds),
    )
    return target.connect_appv2(
        main_ver=main_ver,
        second_ver=second_ver,
        business_type=business_type,
        business_ver=business_ver,
    )
