"""SSH tunnel transport helpers for TMP and TMP/AppV2 sessions."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

import paramiko

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover
    from tmpkit.lib.appv2 import TmpAppV2Session
    from tmpkit.lib.tmp import TmpSession


@dataclass(frozen=True, slots=True)
class SshTmpTarget:
    host: str
    port: int
    username: str
    password: str
    dest_host: str = "127.0.0.1"
    dest_port: int = 20002
    timeout_seconds: float = 8.0

    def connect_tmp(self, *, main_ver: int = 1, second_ver: int = 1):
        """Convenience method returning a context manager yielding a TmpSession."""
        return connect_tmp_over_ssh(self, main_ver=main_ver, second_ver=second_ver)

    def connect_appv2(
        self,
        *,
        main_ver: int = 1,
        second_ver: int = 1,
        business_type: int = 1,
        business_ver: int = 2,
        debug_raw: bool = False,
    ):
        """Convenience method returning a context manager yielding a TmpAppV2Session."""
        return connect_appv2_over_ssh(
            self,
            main_ver=main_ver,
            second_ver=second_ver,
            business_type=business_type,
            business_ver=business_ver,
            debug_raw=debug_raw,
        )


def _prefer_kex(existing: list[str], preferred_first: list[str]) -> list[str]:
    out = list(existing)
    for algo in reversed(preferred_first):
        try:
            out.remove(algo)
        except ValueError:
            pass
        out.insert(0, algo)
    return out


class TmpSshTunnel:
    def __init__(self, target: SshTmpTarget) -> None:
        self._target = target
        self._ssh_sock = None
        self._transport = None
        self._channel = None

    @property
    def channel(self):
        if self._channel is None:
            raise RuntimeError("tunnel not open")
        return self._channel

    def open(self) -> None:
        t = self._target
        logger.debug(
            "Opening SSH tunnel to %s:%s -> %s:%s",
            t.host,
            int(t.port),
            t.dest_host,
            int(t.dest_port),
        )

        try:
            ssh_sock = socket.create_connection(
                (t.host, int(t.port)),
                timeout=float(t.timeout_seconds),
            )
            transport = paramiko.Transport(ssh_sock)
            transport.banner_timeout = float(t.timeout_seconds)

            # Minimal Dropbear-compat tweak: prefer older DH KEX.
            sec = transport.get_security_options()
            try:
                sec.kex = _prefer_kex(
                    list(sec.kex),
                    ["diffie-hellman-group14-sha1", "diffie-hellman-group1-sha1"],
                )
            except Exception:
                pass

            # Paramiko 4.x can raise "No existing session" if auth is attempted
            # before the Transport has completed negotiation; Transport.connect()
            # performs negotiation + auth in a single call.
            try:
                transport.connect(username=t.username, password=t.password)
            except paramiko.ssh_exception.BadAuthenticationType as e:
                allowed = set(getattr(e, "allowed_types", []) or [])
                match "keyboard-interactive" in allowed:
                    case True:
                        pass
                    case False:
                        raise

            if not transport.is_authenticated():
                logger.debug(
                    "SSH server requires keyboard-interactive auth (host=%s user=%s)",
                    t.host,
                    t.username,
                )

                def handler(title, instructions, prompt_list):
                    _ = (title, instructions)
                    return [t.password for _prompt, _show in prompt_list]

                transport.auth_interactive(t.username, handler)

            if not transport.is_authenticated():
                raise RuntimeError("SSH authentication failed")

            logger.debug("SSH authenticated (host=%s user=%s)", t.host, t.username)

            channel = transport.open_channel(
                kind="direct-tcpip",
                dest_addr=(t.dest_host, int(t.dest_port)),
                src_addr=("127.0.0.1", 0),
                timeout=float(t.timeout_seconds),
            )
            channel.settimeout(float(t.timeout_seconds))

            self._ssh_sock = ssh_sock
            self._transport = transport
            self._channel = channel
        except Exception:
            logger.exception(
                "Failed to open SSH tunnel to %s:%s",
                t.host,
                int(t.port),
            )
            self.close()
            raise

    def close(self) -> None:
        logger.debug("Closing SSH tunnel")
        try:
            if self._channel is not None:
                self._channel.close()
        finally:
            self._channel = None
        try:
            if self._transport is not None:
                self._transport.close()
        finally:
            self._transport = None
        try:
            if self._ssh_sock is not None:
                self._ssh_sock.close()
        finally:
            self._ssh_sock = None

    def __enter__(self) -> "TmpSshTunnel":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def connect_tmp_over_ssh(
    target: SshTmpTarget, *, main_ver: int = 1, second_ver: int = 1
):
    """Open an SSH tunnel to a localhost TMP service and return a TmpSession.

    Usage:
        from tmpkit import SshTmpTarget, connect_tmp_over_ssh

        with connect_tmp_over_ssh(SshTmpTarget(...)) as session:
            session.assoc(send_client_hello=True)
    """

    from tmpkit.lib.tmp import TmpCodec, TmpSession

    logger.debug(
        "connect_tmp_over_ssh(host=%s port=%s dest_port=%s)",
        target.host,
        int(target.port),
        int(target.dest_port),
    )

    @contextmanager
    def _ctx() -> Iterator[TmpSession]:
        with TmpSshTunnel(target) as tunnel:
            session = TmpSession(
                tunnel.channel, codec=TmpCodec(main_ver=main_ver, second_ver=second_ver)
            )
            try:
                yield session
            finally:
                session.close()

    return _ctx()


def connect_appv2_over_ssh(
    target: SshTmpTarget,
    *,
    main_ver: int = 1,
    second_ver: int = 1,
    business_type: int = 1,
    business_ver: int = 2,
    debug_raw: bool = False,
):
    """Open an SSH tunnel to a localhost TMP service and return a TmpAppV2Session."""

    from tmpkit.lib.appv2 import TmpAppV2Codec, TmpAppV2Session

    logger.debug(
        "connect_appv2_over_ssh(host=%s port=%s dest_port=%s debug_raw=%s)",
        target.host,
        int(target.port),
        int(target.dest_port),
        bool(debug_raw),
    )

    @contextmanager
    def _ctx() -> Iterator[TmpAppV2Session]:
        with TmpSshTunnel(target) as tunnel:
            session = TmpAppV2Session(
                tunnel.channel,
                codec=TmpAppV2Codec(
                    main_ver=main_ver,
                    second_ver=second_ver,
                    business_type=business_type,
                    business_ver=business_ver,
                ),
                debug_raw=bool(debug_raw),
            )
            try:
                yield session
            finally:
                session.close()

    return _ctx()
