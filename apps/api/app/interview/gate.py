"""Connection limits for the interview WebSocket (D42).

Two cheap guards that need no extra infrastructure:
- per client IP: one address can't open thousands of sockets (the real IP arrives via Caddy's headers);
- live interviews overall: Kokoro speech runs on a few CPUs, so past a measured number of simultaneous
  interviews everyone gets slower. Better to say "busy, try in a few minutes" than to degrade for all.
"""

from collections import Counter


class ConnectionGate:
    def __init__(self, per_ip: int):
        self._per_ip = per_ip
        self._open: Counter[str] = Counter()

    def enter(self, ip: str) -> bool:
        if self._open[ip] >= self._per_ip:
            return False
        self._open[ip] += 1
        return True

    def leave(self, ip: str) -> None:
        self._open[ip] -= 1
        if self._open[ip] <= 0:
            del self._open[ip]  # don't grow forever with one entry per address ever seen
