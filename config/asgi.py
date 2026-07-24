"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# --- Production-safe LMS warmup using ASGI lifespan --------------------
from portal.services.allcloud_client import get_client

class LifespanWrapper:
    """Wraps the Django ASGI app to run async startup/shutdown hooks via lifespan protocol."""

    def __init__(self, app):
        self.app = app
        self._warmed = False

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Startup
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    if not self._warmed:
                        try:
                            client = get_client()
                            await client.auth.warmup()
                            print("✅ LMS connection warmed up successfully (production)")
                        except Exception as e:
                            # Non-fatal; first request will just be slower
                            print(f"⚠️ LMS warmup skipped: {e}")
                        self._warmed = True
                    await send({"type": "lifespan.startup.complete"})

                elif message["type"] == "lifespan.shutdown":
                    # Optional: close the HTTP client gracefully
                    try:
                        client = get_client()
                        await client.aclose()
                        print("✅ LMS client closed gracefully")
                    except Exception:
                        pass
                    await send({"type": "lifespan.shutdown.complete"})
                    return

        else:
            # Normal HTTP / WebSocket requests
            await self.app(scope, receive, send)

# Apply the wrapper
application = LifespanWrapper(get_asgi_application())
