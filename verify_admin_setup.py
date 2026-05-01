#!/usr/bin/env python3
"""Quick verification that admin setup works with environment variables"""
import os
os.environ["ADMIN_MOBILE"] = "9999999999"
os.environ["ADMIN_PASSWORD"] = "SecurePassword@123"
os.environ["SECRET_KEY"] = "test-secret"

from app import app, get_db, init_db, query_db

with app.app_context():
    db = get_db()
    init_db()
    db.commit()
    
    admin = query_db(
        'SELECT id, name, mobile_number, role FROM staff_users WHERE role = "admin"',
        one=True
    )
    
    if admin:
        print("✓ Admin Account Created Successfully:")
        print(f"  ID: {admin[0]}")
        print(f"  Name: {admin[1]}")
        print(f"  Mobile: {admin[2]}")
        print(f"  Role: {admin[3]}")
        print("\n✓ FoodFlux Admin Authentication Ready!")
    else:
        print("✗ Admin account not found")
