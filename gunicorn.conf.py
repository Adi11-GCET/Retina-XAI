"""
RETINA-XAI Gunicorn Configuration for Render Free Deployment
-------------------------------------------------------------
Target Environment: Render Free Web Service (0.1 CPU, 512 MB RAM)

Rules applied:
1. workers = 1: Crucial for 512MB RAM. Running multiple workers duplicates Python,
   PyTorch, and model memory in RAM, immediately triggering OOM SIGKILL.
2. threads = 1: Single-thread prevents CPU context-switching thrash on 0.1 vCPU.
3. timeout = 120: Prevents premature WORKER TIMEOUT on constrained CPU.
4. max_requests = 100: Cleanly reclaims C++ memory arenas and OpenCV/PyTorch fragmentation.
5. Dynamic port binding via $PORT environment variable.
"""

import os

# Dynamic binding for Render (Render injects $PORT)
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Concurrency & Worker Model (Single worker for 512MB RAM)
workers = 1
threads = 1
worker_class = "sync"

# Timeouts (Expanded for 0.1 CPU inference)
timeout = 180
graceful_timeout = 30
keepalive = 5

# Memory Leak / Fragmentation Prevention
max_requests = 100
max_requests_jitter = 10

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
