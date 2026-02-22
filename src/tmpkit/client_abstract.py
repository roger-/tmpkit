"""Abstract high-level router client interface used by tmpkit clients."""

from __future__ import annotations

from abc import ABC, abstractmethod

from tmpkit.deco.models import Connection, Device, Firmware, IPv4Status, Status


class AbstractRouterClient(ABC):
    @abstractmethod
    def supports(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def authorize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def logout(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_firmware(self) -> Firmware:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> Status:
        raise NotImplementedError

    @abstractmethod
    def get_ipv4_status(self) -> IPv4Status:
        raise NotImplementedError

    def get_devices(self) -> list[Device]:
        return list(self.get_status().devices)

    def reboot(self) -> None:
        raise NotImplementedError

    def set_wifi(self, wifi: Connection, enable: bool) -> None:
        _ = (wifi, enable)
        raise NotImplementedError

    def __enter__(self):
        self.authorize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.logout()
