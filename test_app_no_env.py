#!/usr/bin/env python3
"""Test that app initializes correctly even WITHOUT environment variables"""
import os
import sys

# Clear environment variables to simulate production without credentials
os.environ.pop("ADMIN_MOBILE", None)
os.environ.pop("ADMIN_PASSWORD", None)
os.environ["SECRET_KEY"] = "test-secret"

from app import app, get_db, init_db

print("Testing app initialization without environment variables...")
print()

try:
    with app.app_context():
        db = get_db()
        init_db()
        db.commit()
        
        # Try to access the home page without errors
        with app.test_client() as client:
            response = client.get("/")
            
            if response.status_code in [200, 302]:
                print("✓ App initialized successfully without environment variables")
                print("✓ Home page accessible (status code: {})".format(response.status_code))
            else:
                print("✗ Home page returned error: {}".format(response.status_code))
                sys.exit(1)
        
        print()
        print("✓ FoodFlux works without admin credentials!")
        print("✓ Fix verified - No 500 errors on initialization")
        
except Exception as e:
    print("✗ Error during initialization: {}".format(str(e)))
    import traceback
    traceback.print_exc()
    sys.exit(1)
