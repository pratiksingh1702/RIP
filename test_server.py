"""Minimal script to test server imports and startup."""

from server.app import create_app

app = create_app()

print("✓ Server app created successfully!")
print("\nRegistered routes:")
for route in app.routes:
    if route.path.startswith("/docs") or route.path.startswith("/openapi") or route.path.startswith("/redoc"):
        continue
    print(f"  {route.methods} {route.path}")
