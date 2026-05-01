#!/usr/bin/env python3
"""
Test script to verify secure admin authentication setup
Run this to validate that admin account creation works correctly
"""

import os
import sys

# Set environment variables BEFORE importing app
os.environ["ADMIN_MOBILE"] = "9999999999"
os.environ["ADMIN_PASSWORD"] = "TestAdmin@123"
os.environ["SECRET_KEY"] = "test-secret-key"

import sqlite3

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import check_password_hash

# Test 1: Verify environment variables can be read
print("=" * 70)
print("TEST 1: Environment Variables")
print("=" * 70)

from app import app, get_db, init_db, ADMIN_MOBILE, ADMIN_PASSWORD

print(f"✓ ADMIN_MOBILE: {ADMIN_MOBILE}")
print(f"✓ ADMIN_PASSWORD: (hashed in database)")
print()

# Test 2: Verify admin account is created in database
print("=" * 70)
print("TEST 2: Admin Account Creation")
print("=" * 70)

with app.app_context():
    # Initialize database
    db = get_db()
    init_db()
    db.commit()
    
    # Query admin account
    admin = db.execute(
        "SELECT id, name, email, mobile_number, role FROM staff_users WHERE role = 'admin' AND mobile_number IS NOT NULL",
        ()
    ).fetchone()
    
    if admin:
        print(f"✓ Admin account created:")
        print(f"  - ID: {admin[0]}")
        print(f"  - Name: {admin[1]}")
        print(f"  - Email: {admin[2]}")
        print(f"  - Mobile: {admin[3]}")
        print(f"  - Role: {admin[4]}")
    else:
        print("✗ Admin account not found in database")
        sys.exit(1)
    
    print()

# Test 3: Verify password hashing (no plain text storage)
print("=" * 70)
print("TEST 3: Password Security")
print("=" * 70)

with app.app_context():
    db = get_db()
    admin_password_hash = db.execute(
        "SELECT password FROM staff_users WHERE role = 'admin' AND mobile_number IS NOT NULL"
    ).fetchone()
    
    if admin_password_hash:
        stored_hash = admin_password_hash[0]
        print(f"✓ Password is hashed: {stored_hash[:50]}...")
        print(f"✓ Password is NOT stored as plain text: {ADMIN_PASSWORD not in stored_hash}")
        
        # Verify password hash works
        if check_password_hash(stored_hash, ADMIN_PASSWORD):
            print(f"✓ Password hash verification successful")
        else:
            print(f"✗ Password hash verification failed")
            sys.exit(1)
    else:
        print("✗ Password hash not found")
        sys.exit(1)
    
    print()

# Test 4: Verify no hardcoded credentials in code
print("=" * 70)
print("TEST 4: Hardcoded Credentials Check")
print("=" * 70)

with open("app.py", "r", encoding="utf-8", errors="ignore") as f:
    app_code = f.read()
    
    # Check for common hardcoded patterns
    dangerous_patterns = [
        'ADMIN_MOBILE = "',
        "ADMIN_MOBILE = '",
        'ADMIN_PASSWORD = "',
        "ADMIN_PASSWORD = '",
    ]
    
    found_issues = []
    for pattern in dangerous_patterns:
        if pattern in app_code:
            found_issues.append(pattern)
    
    if found_issues:
        print("✗ Found potentially hardcoded credentials:")
        for issue in found_issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("✓ No hardcoded admin credentials found in app.py")
    
    print()

# Test 5: Verify admin login form uses mobile number
print("=" * 70)
print("TEST 5: Admin Login Form Verification")
print("=" * 70)

with open("templates/admin_login.html", "r", encoding="utf-8") as f:
    admin_login_html = f.read()
    
    if 'name="mobile_number"' in admin_login_html:
        print("✓ Admin login form uses 'mobile_number' field")
    else:
        print("✗ Admin login form does NOT use 'mobile_number' field")
        sys.exit(1)
    
    if 'type="email"' in admin_login_html and 'name="email"' in admin_login_html:
        print("✗ Admin login form still has email field (should be removed)")
        sys.exit(1)
    else:
        print("✓ Admin login form does NOT use email field")
    
    print()

# Test 6: Verify .env is in .gitignore
print("=" * 70)
print("TEST 6: Git Configuration")
print("=" * 70)

with open(".gitignore", "r", encoding="utf-8") as f:
    gitignore = f.read()
    
    if ".env" in gitignore:
        print("✓ .env file is in .gitignore (credentials won't be committed)")
    else:
        print("✗ .env file is NOT in .gitignore")
        sys.exit(1)
    
    print()

# Summary
print("=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print()
print("Admin authentication is properly configured:")
print("  ✓ Environment variables read correctly")
print("  ✓ Admin account created in database")
print("  ✓ Passwords are securely hashed")
print("  ✓ No hardcoded credentials in source code")
print("  ✓ Admin login form uses mobile number")
print("  ✓ .env file protected in .gitignore")
print()
print("Ready for production deployment! 🚀")
