"""Whether the PC reaches the internet, and how fast, measured in background threads."""

import http.client
import socket
import sys
import threading
import time

# Two independent anycast services; reaching either one counts as online. IP
# addresses rather than names, so a broken DNS does not read as "offline".
PROBES = (("1.1.1.1", 443), ("8.8.8.8", 443))
PROBE_TIMEOUT = 2.0
SPEED_HOST = "speed.cloudflare.com"
# Cloudflare answers 403 to a /__down above ~25 MB, so a download is several of these.
DOWN_CHUNK_BYTES = 25_000_000
DOWN_SECONDS = 4.0
# Uploads grow until one takes UP_SECONDS, so slow lines send little and fast
# ones send enough for the TLS/request overhead not to dominate.
UP_SIZES = tuple(size * 1024 ** 2 for size in (1, 4, 16, 64))
UP_SECONDS = 1.0
READ_BYTES = 64 * 1024
HTTP_TIMEOUT = 10.0
# Not right at login, when the PC is busy enough to skew the figure.
FIRST_TEST_DELAY = 30.0
# A download below this shows as 0.0 Mbit/s: connected, but nothing gets through.
DEAD_RATE = 50_000
# After such a test, retry soon rather than show "offline" for a whole interval.
RETRY_SECONDS = 60.0


def probe():
    """TCP connect time in ms (about one round trip), or None when no probe answers."""
    for address in PROBES:
        start = time.monotonic()
        try:
            with socket.create_connection(address, timeout=PROBE_TIMEOUT):
                return (time.monotonic() - start) * 1000
        except OSError:
            continue
    return None


def upload_rate(connection):
    """Bits per second of the last (largest) upload to Cloudflare's speed test."""
    for size in UP_SIZES:
        start = time.monotonic()
        connection.request("POST", "/__up", body=bytes(size),
                           headers={"Content-Type": "application/octet-stream"})
        response = connection.getresponse()
        response.read()
        if response.status != 200:
            raise http.client.HTTPException(f"/__up answered {response.status}")
        elapsed = time.monotonic() - start
        if elapsed >= UP_SECONDS:
            break
    return 8 * size / elapsed


def download_rate(connection):
    """Bits per second downloaded from Cloudflare's speed test in DOWN_SECONDS."""
    received = 0
    start = time.monotonic()
    deadline = start + DOWN_SECONDS
    while time.monotonic() < deadline:
        connection.request("GET", f"/__down?bytes={DOWN_CHUNK_BYTES}")
        response = connection.getresponse()
        if response.status != 200:
            raise http.client.HTTPException(f"/__down answered {response.status}")
        while time.monotonic() < deadline:
            chunk = response.read(READ_BYTES)
            if not chunk:
                break
            received += len(chunk)
        else:
            # Cut off mid-response: the connection is unusable, and done with anyway.
            break
    return 8 * received / (time.monotonic() - start)


def speed_test():
    """(download, upload) in bits per second."""
    connection = http.client.HTTPSConnection(SPEED_HOST, timeout=HTTP_TIMEOUT)
    try:
        # Upload first: its responses are read in full, so the connection survives
        # for the download, which ends by abandoning a response.
        connection.connect()
        up = upload_rate(connection)
        return download_rate(connection), up
    finally:
        connection.close()


class Internet:
    """Probes connectivity and runs speed tests; the panel reads the attributes."""

    def __init__(self, check_seconds, speed_test_minutes):
        self.check_seconds = check_seconds
        self.speed_test_minutes = speed_test_minutes
        self.online = None      # None until the first probe is back
        self.latency = None     # ms, None while offline
        self.speed = None       # (down, up) bit/s of the last finished test
        self.speed_time = None  # time.time() of that test
        self.testing = False
        self.stalled = False    # the probe connects, but the last test got no data through

    def start(self):
        threading.Thread(target=self.watch, daemon=True).start()
        threading.Thread(target=self.measure, daemon=True).start()

    def watch(self):
        while True:
            latency = probe()
            self.online, self.latency = latency is not None, latency
            if not self.online:
                # Plainly offline; the test that runs once back online decides anew.
                self.stalled = False
            time.sleep(self.check_seconds)

    def measure(self):
        time.sleep(FIRST_TEST_DELAY)
        while True:
            if not self.online:
                time.sleep(self.check_seconds)
                continue
            time.sleep(self.run_test())

    def run_test(self):
        """One speed test; returns the seconds until the next one."""
        self.testing = True
        try:
            speed = speed_test()
        except OSError as error:
            # A timeout or dropped connection while the probe still connects.
            print(f"pc-monitor: speed test failed ({error})", file=sys.stderr)
            self.stalled = True
            return RETRY_SECONDS
        except http.client.HTTPException as error:
            # The server refused; says nothing about our connection.
            print(f"pc-monitor: speed test failed ({error})", file=sys.stderr)
            return self.speed_test_minutes * 60
        finally:
            self.testing = False
        self.stalled = speed[0] < DEAD_RATE
        if self.stalled:
            return RETRY_SECONDS
        self.speed, self.speed_time = speed, time.time()
        return self.speed_test_minutes * 60

    def state(self):
        return {"online": self.online, "latency": self.latency, "speed": self.speed,
                "stalled": self.stalled}
