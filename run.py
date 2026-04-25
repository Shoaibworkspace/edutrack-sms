#!/usr/bin/env python3
"""
EduTrack Student Management System - Startup Script
"""
import sys
import os

def check_dependencies():
    missing = []
    try: import flask
    except ImportError: missing.append('flask')
    try: from werkzeug.security import generate_password_hash
    except ImportError: missing.append('werkzeug')
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print("Install with: pip install flask werkzeug")
        sys.exit(1)

if __name__ == '__main__':
    check_dependencies()
    sys.path.insert(0, os.path.dirname(__file__))
    from app import app, init_db
    print("=" * 50)
    print("  EduTrack Student Management System")
    print("=" * 50)
    print("Initialising database...")
    init_db()
    print("Database ready.")
    print()
    print("  URL  : http://localhost:5000")
    print()
    print("  Admin   : admin@college.edu / admin123")
    print("  Student : arjun@student.edu / student123")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    app.run(debug=False, port=5000, host='0.0.0.0')
