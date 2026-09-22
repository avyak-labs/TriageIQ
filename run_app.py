"""
TriageIQ - Unified Runner Script
Launches both the FastAPI REST backend and the Vite React frontend concurrently.
Usage:
    python run_app.py
"""
import os
import sys
import subprocess
import time
import signal

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
VENV_PYTHON = os.path.join(ROOT_DIR, "venv", "Scripts", "python.exe")

if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable


def main():
    print("=" * 60)
    print("🚀 Launching TriageIQ Full-Stack Application")
    print("   • Backend  (FastAPI): http://127.0.0.1:8001")
    print("   • Frontend (React/Vite): http://localhost:5173")
    print("=" * 60)

    # 1. Start FastAPI backend on port 8001
    backend_cmd = [
        VENV_PYTHON,
        "-m",
        "uvicorn",
        "server:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8001",
        "--reload",
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=ROOT_DIR)

    # 2. Start Vite dev server on port 5173
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=FRONTEND_DIR)

    def shutdown(sig, frame):
        print("\n🛑 Stopping TriageIQ services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
            frontend_proc.wait(timeout=3)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
        print("Done. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("❌ Backend stopped unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("❌ Frontend stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
