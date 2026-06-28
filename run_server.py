
import sys
import uvicorn
from server.app import app


def main():
    print("Starting server...")
    sys.stdout.flush()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")


if __name__ == "__main__":
    main()
