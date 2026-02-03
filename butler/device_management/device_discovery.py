from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import zeroconf

logger = logging.getLogger(__name__)


class DiscoveryProtocol(Enum):
    MDNS = "mdns"
    UPNP = "upnp"
    MQTT = "mqtt"
    HTTP = "http"
    CUSTOM = "custom"


class DeviceCategory(Enum):
    LIGHTING = "lighting"
    CLIMATE = "climate"
    SECURITY = "security"
    ENTERTAINMENT = "entertainment"
    APPLIANCE = "appliance"
    CAMERA = "camera"
    SENSOR = "sensor"
    SWITCH = "switch"
    OTHER = "other"


@dataclass
class DiscoveredDevice:
    device_id: str
    name: str
    protocol: DiscoveryProtocol
    category: DeviceCategory
    ip_address: str
    port: int
    mac_address: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    services: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    is_available: bool = True

    def update_last_seen(self) -> None:
        self.last_seen = time.time()

    def age_seconds(self) -> float:
        return time.time() - self.last_seen

    def is_stale(self, max_age_seconds: float = 300.0) -> bool:
        return self.age_seconds() > max_age_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "protocol": self.protocol.value,
            "category": self.category.value,
            "ip_address": self.ip_address,
            "port": self.port,
            "mac_address": self.mac_address,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "capabilities": self.capabilities,
            "services": self.services,
            "metadata": self.metadata,
            "discovered_at": self.discovered_at,
            "last_seen": self.last_seen,
            "is_available": self.is_available,
            "age_seconds": self.age_seconds(),
        }


class DeviceDiscoveryListener(ABC):
    @abstractmethod
    async def on_device_discovered(self, device: DiscoveredDevice) -> None:
        pass

    @abstractmethod
    async def on_device_lost(self, device_id: str) -> None:
        pass

    @abstractmethod
    async def on_device_updated(self, device: DiscoveredDevice) -> None:
        pass


class DiscoveryScanner(ABC):
    def __init__(self, protocol: DiscoveryProtocol):
        self.protocol = protocol
        self._running = False
        self._listeners: List[DeviceDiscoveryListener] = []

    @abstractmethod
    async def scan(self, timeout: float = 30.0) -> List[DiscoveredDevice]:
        pass

    @abstractmethod
    async def start_continuous_scan(self, interval: float = 60.0) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    def add_listener(self, listener: DeviceDiscoveryListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: DeviceDiscoveryListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _notify_discovered(self, device: DiscoveredDevice) -> None:
        for listener in self._listeners:
            try:
                await listener.on_device_discovered(device)
            except Exception as e:
                logger.error(f"Error notifying listener of discovered device: {e}")

    async def _notify_lost(self, device_id: str) -> None:
        for listener in self._listeners:
            try:
                await listener.on_device_lost(device_id)
            except Exception as e:
                logger.error(f"Error notifying listener of lost device: {e}")

    async def _notify_updated(self, device: DiscoveredDevice) -> None:
        for listener in self._listeners:
            try:
                await listener.on_device_updated(device)
            except Exception as e:
                logger.error(f"Error notifying listener of updated device: {e}")


class MDNSScanner(DiscoveryScanner):
    def __init__(self):
        super().__init__(DiscoveryProtocol.MDNS)
        self.browser: Optional[zeroconf.ServiceBrowser] = None
        self.zeroconf: Optional[zeroconf.Zeroconf] = None
        self._discovered_devices: Dict[str, DiscoveredDevice] = {}

    async def scan(self, timeout: float = 30.0) -> List[DiscoveredDevice]:
        devices = []

        service_types = [
            "_hap._tcp.local.",
            "_http._tcp.local.",
            "_homeassistant._tcp.local.",
            "_esphomelib._tcp.local.",
            "_matter._tcp.local.",
            "_googlecast._tcp.local.",
            "_spotify-connect._tcp.local.",
            "_airplay._tcp.local.",
        ]

        for service_type in service_types:
            try:
                type_devices = await self._scan_service_type(service_type, timeout / len(service_types))
                devices.extend(type_devices)
            except Exception as e:
                logger.warning(f"Error scanning {service_type}: {e}")

        return devices

    async def _scan_service_type(self, service_type: str, timeout: float) -> List[DiscoveredDevice]:
        devices = []
        self._discovered_devices = {}

        def on_service_state_change(
            zeroconf: zeroconf.Zeroconf,
            service_type: str,
            name: str,
            state_change: zeroconf.ServiceStateChange
        ) -> None:
            if state_change is zeroconf.ServiceStateChange.Added:
                try:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        device = self._parse_service_info(info, service_type)
                        if device:
                            self._discovered_devices[device.device_id] = device
                except Exception as e:
                    logger.warning(f"Error parsing service info: {e}")

        self.zeroconf = zeroconf.Zeroconf()
        self.browser = zeroconf.ServiceBrowser(
            self.zeroconf,
            service_type,
            handlers=[on_service_state_change]
        )

        await asyncio.sleep(timeout)

        return list(self._discovered_devices.values())

    def _parse_service_info(
        self,
        info: zeroconf.ServiceInfo,
        service_type: str
    ) -> Optional[DiscoveredDevice]:
        addresses = info.parsed_scoped_addresses()
        if not addresses:
            return None

        ip_address = addresses[0]
        port = info.port
        name = info.name.replace(f".{service_type}", "")
        properties = {k.decode(): v.decode() for k, v in info.properties.items()}

        category = DeviceCategory.OTHER
        capabilities = []

        if "_hap._tcp" in service_type:
            category = DeviceCategory.LIGHTING
            capabilities.append("homekit")
        elif "_homeassistant._tcp" in service_type:
            category = DeviceCategory.OTHER
            capabilities.append("homeassistant")
        elif "_esphomelib._tcp" in service_type:
            category = DeviceCategory.SENSOR
            capabilities.append("esphome")
        elif "_googlecast._tcp" in service_type:
            category = DeviceCategory.ENTERTAINMENT
            capabilities.append("chromecast")
        elif "_spotify-connect._tcp" in service_type:
            category = DeviceCategory.ENTERTAINMENT
            capabilities.append("spotify")
        elif "_airplay._tcp" in service_type:
            category = DeviceCategory.ENTERTAINMENT
            capabilities.append("airplay")

        device_id = f"mdns_{name}_{ip_address}_{port}"

        return DiscoveredDevice(
            device_id=device_id,
            name=name,
            protocol=self.protocol,
            category=category,
            ip_address=ip_address,
            port=port,
            manufacturer=properties.get("md"),
            model=properties.get("model"),
            firmware_version=properties.get("fv"),
            capabilities=capabilities,
            services={"mdns": {"type": service_type, "properties": properties}},
        )

    async def start_continuous_scan(self, interval: float = 60.0) -> None:
        self._running = True

        while self._running:
            try:
                devices = await self.scan(timeout=10.0)
                for device in devices:
                    device.update_last_seen()
                    await self._notify_discovered(device)
            except Exception as e:
                logger.error(f"Error in continuous mDNS scan: {e}")

            await asyncio.sleep(interval)

    async def stop(self) -> None:
        self._running = False
        if self.browser:
            self.browser.cancel()
        if self.zeroconf:
            self.zeroconf.close()


class UPNPScanner(DiscoveryScanner):
    def __init__(self):
        super().__init__(DiscoveryProtocol.UPNP)
        self._discovered_devices: Dict[str, DiscoveredDevice] = {}

    async def scan(self, timeout: float = 30.0) -> List[DiscoveredDevice]:
        devices = []
        self._discovered_devices = {}

        try:
            search_address = ("239.255.255.250", 1900)

            message = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                "MAN: \"ssdp:discover\"\r\n"
                "MX: 3\r\n"
                "ST: ssdp:all\r\n"
                "\r\n"
            ).encode()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)

            sock.sendto(message, search_address)

            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode("utf-8", errors="ignore")
                    device = self._parse_upnp_response(response, addr)
                    if device:
                        devices.append(device)
                except socket.timeout:
                    break
                except Exception as e:
                    logger.warning(f"Error receiving UPnP response: {e}")

            sock.close()
        except Exception as e:
            logger.error(f"UPnP scan error: {e}")

        return devices

    def _parse_upnp_response(self, response: str, addr: tuple) -> Optional[DiscoveredDevice]:
        lines = response.split("\r\n")
        headers = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        location = headers.get("location")
        if not location:
            return None

        server = headers.get("server", "")
        usn = headers.get("usn", "")
        st = headers.get("st", "")

        category = DeviceCategory.OTHER
        capabilities = ["upnp"]

        if "light" in st.lower() or "light" in server.lower():
            category = DeviceCategory.LIGHTING
        elif "camera" in st.lower() or "camera" in server.lower():
            category = DeviceCategory.CAMERA
        elif "media" in st.lower() or "media" in server.lower():
            category = DeviceCategory.ENTERTAINMENT

        device_id = f"upnp_{usn.replace(':', '_')}"

        return DiscoveredDevice(
            device_id=device_id,
            name=st,
            protocol=self.protocol,
            category=category,
            ip_address=addr[0],
            port=0,
            capabilities=capabilities,
            services={
                "upnp": {
                    "location": location,
                    "server": server,
                    "usn": usn,
                    "st": st,
                }
            },
        )

    async def start_continuous_scan(self, interval: float = 60.0) -> None:
        self._running = True

        while self._running:
            try:
                devices = await self.scan(timeout=10.0)
                for device in devices:
                    device.update_last_seen()
                    await self._notify_discovered(device)
            except Exception as e:
                logger.error(f"Error in continuous UPnP scan: {e}")

            await asyncio.sleep(interval)

    async def stop(self) -> None:
        self._running = False


class HTTPScanner(DiscoveryScanner):
    def __init__(self, scan_range: Optional[str] = None):
        super().__init__(DiscoveryProtocol.HTTP)
        self.scan_range = scan_range or self._get_local_network()
        self._discovered_devices: Dict[str, DiscoveredDevice] = {}

    def _get_local_network(self) -> str:
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
            return str(network)
        except Exception:
            return "192.168.1.0/24"

    async def scan(self, timeout: float = 30.0) -> List[DiscoveredDevice]:
        devices = []

        try:
            network = ipaddress.IPv4Network(self.scan_range)
            tasks = []

            for ip in network.hosts():
                tasks.append(self._scan_host(str(ip), timeout / 256))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, DiscoveredDevice):
                    devices.append(result)

        except Exception as e:
            logger.error(f"HTTP scan error: {e}")

        return devices

    async def _scan_host(self, ip: str, timeout: float) -> Optional[DiscoveredDevice]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 80),
                timeout=timeout
            )

            request = "GET / HTTP/1.1\r\nHost: {}\r\n\r\n".format(ip).encode()
            writer.write(request)
            await writer.drain()

            response = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            writer.close()
            await writer.wait_closed()

            response_text = response.decode("utf-8", errors="ignore")

            if "server" in response_text.lower():
                category = DeviceCategory.OTHER
                capabilities = ["http"]

                if "homeassistant" in response_text.lower():
                    capabilities.append("homeassistant")
                elif "esphome" in response_text.lower():
                    category = DeviceCategory.SENSOR
                    capabilities.append("esphome")

                return DiscoveredDevice(
                    device_id=f"http_{ip}",
                    name=f"HTTP Device ({ip})",
                    protocol=self.protocol,
                    category=category,
                    ip_address=ip,
                    port=80,
                    capabilities=capabilities,
                )

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            pass

        return None

    async def start_continuous_scan(self, interval: float = 60.0) -> None:
        self._running = True

        while self._running:
            try:
                devices = await self.scan(timeout=10.0)
                for device in devices:
                    device.update_last_seen()
                    await self._notify_discovered(device)
            except Exception as e:
                logger.error(f"Error in continuous HTTP scan: {e}")

            await asyncio.sleep(interval)

    async def stop(self) -> None:
        self._running = False


class DeviceDiscoveryManager:
    def __init__(self):
        self.scanners: Dict[DiscoveryProtocol, DiscoveryScanner] = {}
        self._discovered_devices: Dict[str, DiscoveredDevice] = {}
        self._listeners: List[DeviceDiscoveryListener] = []
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

        self._init_default_scanners()

    def _init_default_scanners(self) -> None:
        self.scanners[DiscoveryProtocol.MDNS] = MDNSScanner()
        self.scanners[DiscoveryProtocol.UPNP] = UPNPScanner()
        self.scanners[DiscoveryProtocol.HTTP] = HTTPScanner()

        for scanner in self.scanners.values():
            scanner.add_listener(self)

    async def scan_all(self, timeout: float = 30.0) -> List[DiscoveredDevice]:
        all_devices = []

        for protocol, scanner in self.scanners.items():
            try:
                devices = await scanner.scan(timeout=timeout / len(self.scanners))
                for device in devices:
                    if device.device_id in self._discovered_devices:
                        self._discovered_devices[device.device_id].update_last_seen()
                    else:
                        self._discovered_devices[device.device_id] = device
                all_devices.extend(devices)
            except Exception as e:
                logger.error(f"Error scanning with {protocol.value}: {e}")

        await self._cleanup_stale_devices()

        return list(self._discovered_devices.values())

    async def start_continuous_discovery(self, interval: float = 60.0) -> None:
        if self._running:
            return

        self._running = True

        for scanner in self.scanners.values():
            asyncio.create_task(scanner.start_continuous_scan(interval))

        self._scan_task = asyncio.create_task(self._periodic_cleanup())

        logger.info("Started continuous device discovery")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        for scanner in self.scanners.values():
            await scanner.stop()

        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped device discovery")

    async def _periodic_cleanup(self) -> None:
        while self._running:
            await asyncio.sleep(300)
            await self._cleanup_stale_devices()

    async def _cleanup_stale_devices(self) -> None:
        stale_device_ids = []

        for device_id, device in self._discovered_devices.items():
            if device.is_stale(max_age_seconds=600):
                stale_device_ids.append(device_id)

        for device_id in stale_device_ids:
            device = self._discovered_devices.pop(device_id)
            device.is_available = False
            await self._notify_lost(device_id)

    def add_listener(self, listener: DeviceDiscoveryListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: DeviceDiscoveryListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def on_device_discovered(self, device: DiscoveredDevice) -> None:
        if device.device_id not in self._discovered_devices:
            self._discovered_devices[device.device_id] = device

        for listener in self._listeners:
            try:
                await listener.on_device_discovered(device)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")

    async def on_device_lost(self, device_id: str) -> None:
        for listener in self._listeners:
            try:
                await listener.on_device_lost(device_id)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")

    async def on_device_updated(self, device: DiscoveredDevice) -> None:
        for listener in self._listeners:
            try:
                await listener.on_device_updated(device)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")

    def get_discovered_devices(self) -> List[DiscoveredDevice]:
        return list(self._discovered_devices.values())

    def get_device(self, device_id: str) -> Optional[DiscoveredDevice]:
        return self._discovered_devices.get(device_id)

    def get_devices_by_protocol(self, protocol: DiscoveryProtocol) -> List[DiscoveredDevice]:
        return [d for d in self._discovered_devices.values() if d.protocol == protocol]

    def get_devices_by_category(self, category: DeviceCategory) -> List[DiscoveredDevice]:
        return [d for d in self._discovered_devices.values() if d.category == category]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": [device.to_dict() for device in self._discovered_devices.values()],
            "device_count": len(self._discovered_devices),
            "scanners": list(self.scanners.keys()),
        }
