"""High-level Deco SSH client API and configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from hashlib import sha1

from tmpkit.client_abstract import AbstractRouterClient
from tmpkit.deco.models import Firmware, IPv4Status, Status
from tmpkit.deco.opcodes import DecoAppV2Opcode
from tmpkit.deco.status_adapter import (
    deco_get_firmware,
    deco_get_ipv4_status,
    deco_get_status,
)
from tmpkit.lib.appv2 import TmpAppV2Codec, TmpAppV2Session
from tmpkit.lib.ssh import SshTmpTarget, TmpSshTunnel

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DecoSshConfig:
    host: str
    email: str
    ssh_password: str
    ssh_port: int = 20001
    dest_host: str = "127.0.0.1"
    dest_port: int = 20002
    timeout_seconds: float = 60.0
    debug_raw: bool = False
    ssh_username: str | None = None

    @property
    def effective_ssh_username(self) -> str:
        if self.ssh_username and str(self.ssh_username).strip():
            return str(self.ssh_username).strip()
        return sha1(str(self.email).encode()).hexdigest()


class DecoSshClient(AbstractRouterClient):
    def __init__(self, config: DecoSshConfig, *, all_nodes: bool = False) -> None:
        self._config = config
        self._all_nodes = bool(all_nodes)
        self._tunnel: TmpSshTunnel | None = None
        self._session: TmpAppV2Session | None = None

    def _bootstrap(self) -> None:
        session = self._require_session()
        timeout = float(self._config.timeout_seconds)
        session.assoc(timeout_seconds=timeout, send_client_hello=True)
        session.request_appv2(
            op_code=DecoAppV2Opcode.TMP_APPV2_OP_TOKEN_ALLOC,
            payload=b"",
            timeout_seconds=timeout,
        )
        session.request_appv2(
            op_code=DecoAppV2Opcode.TMP_APPV2_OP_COMP_NEGOTIATE,
            payload=b"",
            timeout_seconds=timeout,
        )

    def _require_session(self) -> TmpAppV2Session:
        if self._session is None:
            raise RuntimeError("client is not authorized; call authorize() first")
        return self._session

    def supports(self) -> bool:
        try:
            self.authorize()
            return True
        except Exception:
            return False
        finally:
            self.logout()

    def authorize(self) -> None:
        if self._session is not None:
            return

        cfg = self._config
        target = SshTmpTarget(
            host=cfg.host,
            port=int(cfg.ssh_port),
            username=cfg.effective_ssh_username,
            password=str(cfg.ssh_password),
            dest_host=str(cfg.dest_host),
            dest_port=int(cfg.dest_port),
            timeout_seconds=float(cfg.timeout_seconds),
        )

        tunnel = TmpSshTunnel(target)
        tunnel.open()
        session = TmpAppV2Session(
            tunnel.channel,
            codec=TmpAppV2Codec(),
            debug_raw=bool(cfg.debug_raw),
        )

        try:
            self._tunnel = tunnel
            self._session = session
            self._bootstrap()
        except Exception:
            self.logout()
            raise

    def logout(self) -> None:
        session = self._session
        tunnel = self._tunnel
        self._session = None
        self._tunnel = None

        if session is not None:
            try:
                session.close()
            except Exception:
                pass

        if tunnel is not None:
            tunnel.close()

    def get_firmware(self) -> Firmware:
        return deco_get_firmware(
            self._require_session(), timeout_seconds=float(self._config.timeout_seconds)
        )

    def get_status(self) -> Status:
        return deco_get_status(
            self._require_session(),
            timeout_seconds=float(self._config.timeout_seconds),
            include_nodes=bool(self._all_nodes),
        )

    def get_ipv4_status(self) -> IPv4Status:
        return deco_get_ipv4_status(
            self._require_session(), timeout_seconds=float(self._config.timeout_seconds)
        )
