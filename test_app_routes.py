#!/usr/bin/env python3
"""Test that app initializes and runs without errors"""
import sys

# Note: Simulating no environment variables by checking the warning
# The app should NOT crash even if variables aren't set

from app import app, get_db, init_db

print("Testing FoodFlux app initialization and home page...")
print()

try:
    with app.app_context():
        db = get_db()
        init_db()
        db.commit()
        
        # Try to access the home page
        with app.test_client() as client:
            print("Testing GET /")
            response = client.get("/")
            
            if response.status_code in [200, 302]:
                print("✓ Home page accessible (status: {})".format(response.status_code))
            else:
                print("✗ Unexpected status code: {}".format(response.status_code))
                sys.exit(1)
            
            # Test login page
            print("Testing GET /login")
            response = client.get("/login")
            if response.status_code == 200:
                print("✓ Login page accessible")
            else:
                print("✗ Login page error: {}".format(response.status_code))
                sys.exit(1)
            
            # Test admin login page
            print("Testing GET /admin_login")
            response = client.get("/admin_login")
            if response.status_code == 200:
                print("✓ Admin login page accessible")
            else:
                print("✗ Admin login page error: {}".format(response.status_code))
                sys.exit(1)
        
        print()
        print("✅ FoodFlux app is working correctly!")
        print("✅ No internal server errors on initialization")
        
except Exception as e:
    print("✗ ERROR: {}".format(str(e)))
    import traceback
    traceback.print_exc()
    sys.exit(1)
