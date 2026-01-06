#!/usr/bin/env python3
"""
PDF AI Assistant - Web Interface Launcher
"""
import subprocess
import sys
import os
import webbrowser
import time

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_web.txt"])

def start_server():
    """Start the FastAPI server"""
    print("Starting PDF AI Assistant...")
    print("Server will be available at: http://localhost:8000")
    
    # Start the server
    subprocess.Popen([
        sys.executable, "-m", "uvicorn", 
        "web_backend:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ])
    
    # Wait a moment then open browser
    time.sleep(3)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    try:
        # Check if dependencies need to be installed
        if not os.path.exists("__pycache__") or "--install" in sys.argv:
            install_dependencies()
        
        start_server()
        
        print("\n" + "="*50)
        print("PDF AI Assistant is running!")
        print("URL: http://localhost:8000")
        print("Press Ctrl+C to stop the server")
        print("="*50)
        
        # Keep the script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)