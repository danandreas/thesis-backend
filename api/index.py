import sys
import os

# Tambahkan root project ke sys.path agar import bisa menemukan module app, config, routes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()
