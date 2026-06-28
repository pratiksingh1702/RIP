
print("Testing import...")
try:
    from server.app import app
    print("Import successful!")
    print(f"App: {app}")
    print("Routers:", app.routes)
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
