"""OSC клиенты (Resolume + monitor) и send_osc."""
from pythonosc import udp_client

import config


class OscOutput:
    """Два клиента: основной (Resolume) + монитор (Protokol/Chataigne).
    Сокеты non-blocking — не крешится если получатель не слушает."""

    def __init__(self):
        self.client = udp_client.SimpleUDPClient(config.OSC_IP, config.OSC_PORT)
        self.monitor = (
            udp_client.SimpleUDPClient(config.MONITOR_OSC_IP, config.MONITOR_OSC_PORT)
            if config.SEND_TO_MONITOR else None
        )
        self.client._sock.setblocking(False)
        if self.monitor is not None:
            self.monitor._sock.setblocking(False)

    def send(self, address, value):
        try:
            self.client.send_message(address, value)
        except (BlockingIOError, OSError):
            pass
        if self.monitor is not None:
            try:
                self.monitor.send_message(address, value)
            except (BlockingIOError, OSError):
                pass
