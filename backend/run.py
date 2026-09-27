"""
Entry point for the Flask development server.

Usage:
    python backend/run.py
"""

import sys
import os
import signal

# Ensure project root is on the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.config import PORT

app = create_app()


def _graceful_shutdown(signum, frame):
    """Handle SIGTERM so atexit handlers (WAL checkpoint) actually run."""
    sys.exit(0)


def _phone_sync_enabled() -> bool:
    """Read the phone-sync setting so we know which interface to bind.
    Loopback-only unless the user has opted in via Settings."""
    try:
        return app.config['DB'].get_setting('phone_sync_enabled') == 'true'
    except Exception:
        return False


def _advertise_bonjour(port):
    """Advertise the sync service over Bonjour/mDNS so the phone can
    find the Mac without a typed IP. Optional: silently skipped if the
    zeroconf package is missing or the network refuses.

    Advertises ALL of the Mac's current IPv4 addresses — the phone may
    reach it over Wi-Fi, a Personal Hotspot, or USB tethering, each on
    its own address — and keeps the advertisement fresh as interfaces
    come and go (plugging the phone in AFTER launch creates a new
    interface that must join the advertisement)."""
    try:
        import socket
        import threading
        import time
        from zeroconf import ServiceInfo, Zeroconf, get_all_addresses

        def current_addresses():
            try:
                addrs = sorted(
                    a for a in get_all_addresses()
                    if a != '127.0.0.1' and not a.startswith('169.254.'))
                if addrs:
                    return addrs
            except Exception:
                pass
            return [socket.gethostbyname(socket.gethostname())]

        def make_info(addresses):
            return ServiceInfo(
                '_tarotjournal._tcp.local.',
                'Tarot Journal._tarotjournal._tcp.local.',
                addresses=[socket.inet_aton(a) for a in addresses],
                port=port,
                properties={'protocol': '1'},
            )

        zc = Zeroconf()
        addresses = current_addresses()
        zc.register_service(make_info(addresses))

        def refresh():
            nonlocal addresses
            while True:
                time.sleep(20)
                try:
                    now = current_addresses()
                    if now != addresses:
                        zc.update_service(make_info(now))
                        addresses = now
                except Exception:
                    pass  # transient network churn; retry next tick

        threading.Thread(target=refresh, daemon=True,
                         name='bonjour-refresh').start()
        return zc
    except Exception as exc:
        print(f"Bonjour advertisement unavailable: {exc}")
        return None


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    if _phone_sync_enabled():
        # 0.0.0.0 = listen on the LAN too. Safe because the app-wide
        # guard in backend/app.py restricts non-loopback callers to the
        # token-protected /api/sync/ routes.
        host = '0.0.0.0'
        _advertise_bonjour(PORT)
        print(f"Starting Tarot Journal API on http://localhost:{PORT} "
              f"(phone sync: listening on the local network)")
    else:
        host = '127.0.0.1'
        print(f"Starting Tarot Journal API on http://localhost:{PORT}")
    app.run(host=host, port=PORT, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
