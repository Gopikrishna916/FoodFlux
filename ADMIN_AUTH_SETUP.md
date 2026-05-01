# 🔐 FoodFlux Admin Authentication Setup Guide

## Overview

FoodFlux uses **secure, environment-based authentication** for admin accounts. The admin account is automatically created during application startup using credentials provided via environment variables.

### Key Features

✅ **Secure by Design**
- Credentials stored in environment variables, never hardcoded
- Passwords automatically hashed using Werkzeug's `generate_password_hash`
- No plain-text credentials in source code, logs, or frontend

✅ **Mobile Number Based**
- Admin logs in using mobile number + password (not email)
- Consistent with staff (manager, delivery partner) authentication

✅ **Automatic Account Creation**
- Admin account is created on application startup if it doesn't exist
- Uses credentials from `ADMIN_MOBILE` and `ADMIN_PASSWORD` environment variables
- Does NOT overwrite existing admin accounts

---

## Configuration

### Environment Variables

Create a `.env` file in your project root with the following required variables:

```bash
# Admin credentials (10-digit mobile + password)
ADMIN_MOBILE=9999999999
ADMIN_PASSWORD=SecureAdminPassword@123

# Other required variables
SECRET_KEY=your-secret-key-here
```

### Deployment Platforms

#### **Local Development**

1. Create `.env` file in project root:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
ADMIN_MOBILE=9999999999
ADMIN_PASSWORD=MySecurePassword@123
SECRET_KEY=dev-secret-key
```

3. Run the application:
```bash
python app.py
```

The admin account will be automatically created with your credentials.

#### **Render.com Deployment**

1. Go to your Render service dashboard
2. Click **"Environment"** tab
3. Add environment variables:
   - `ADMIN_MOBILE`: Your 10-digit mobile number
   - `ADMIN_PASSWORD`: Strong password (min 6 chars, recommended 12+)
   - `SECRET_KEY`: Random key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)

4. Deploy the application
5. Admin account will be created automatically on first startup

#### **Other Platforms (Heroku, AWS, etc.)**

Use the platform's environment variable configuration:
- Set `ADMIN_MOBILE`, `ADMIN_PASSWORD`, `SECRET_KEY` as environment variables
- The app will automatically create the admin account on startup

---

## Admin Login

### Step-by-Step Login Process

1. **Navigate to Admin Login**
   - Go to `/admin_login` route
   - Click "Admin" button on navbar

2. **Enter Credentials**
   - Mobile Number: Enter your 10-digit admin mobile number
   - Password: Enter your admin password

3. **Submit**
   - Click "Login" button
   - Redirect to admin dashboard on success

### Admin Dashboard Features

Once logged in, the admin can:
- 👥 Manage staff (managers, delivery partners)
- 🍔 Add/edit/delete food items
- 📋 View all orders
- 📊 Monitor operations
- 🚚 Manage delivery personnel

---

## Security Requirements

### ✅ DO (Best Practices)

- ✅ Use **strong passwords**: minimum 12 characters with uppercase, lowercase, numbers, and symbols
- ✅ Store credentials in **environment variables only**
- ✅ Use `.env` file locally, never commit to git
- ✅ Rotate admin credentials periodically
- ✅ Monitor admin login attempts
- ✅ Use HTTPS in production

### 🚫 DO NOT (Security Risks)

- 🚫 Hardcode credentials in source code
- 🚫 Commit `.env` file to git
- 🚫 Share admin credentials via email or chat
- 🚫 Use weak passwords (like "admin123")
- 🚫 Display credentials in logs or console
- 🚫 Allow public admin account creation UI

---

## Troubleshooting

### Issue: Admin Login Not Working

**Check 1:** Verify environment variables are set
```bash
# On Linux/Mac
echo $ADMIN_MOBILE
echo $ADMIN_PASSWORD

# On Windows (PowerShell)
$env:ADMIN_MOBILE
$env:ADMIN_PASSWORD
```

**Check 2:** Verify credentials are correct
- Mobile number must be exactly 10 digits
- Password is case-sensitive
- No leading/trailing spaces

**Check 3:** Check database for admin account
```bash
# In Python shell
from app import query_db
admin = query_db("SELECT * FROM staff_users WHERE role = 'admin'", one=True)
print(admin)
```

### Issue: Admin Account Not Created

**Solution:** Run database initialization
```bash
python -c "from app import get_db, init_db; db = get_db(); init_db()"
```

### Issue: Password Not Working After Setting Environment Variable

**Solution:** Restart the application
- Changes to environment variables require application restart
- Development server must be restarted (Ctrl+C, then `python app.py`)

---

## Development Credentials (Local Testing)

**Default fallback values** (used only if environment variables not set):

```
Mobile Number: 9999999999
Password: admin@123
```

⚠️ These are **fallback values for development only**. Always use environment variables in production.

---

## Production Checklist

Before deploying to production:

- [ ] Set strong, unique `ADMIN_MOBILE` and `ADMIN_PASSWORD`
- [ ] Generate random `SECRET_KEY` using: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Configure environment variables in deployment platform
- [ ] Test admin login on staging environment
- [ ] Verify no credentials in logs
- [ ] Enable HTTPS for all admin connections
- [ ] Set up admin login monitoring/alerts
- [ ] Document credentials in secure location (password manager)
- [ ] Plan credential rotation schedule

---

## Code Reference

### Database Schema

```sql
-- Admin account stored in staff_users table
CREATE TABLE staff_users(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mobile_number TEXT UNIQUE,
    password TEXT NOT NULL,  -- Hashed password
    role TEXT NOT NULL,      -- "admin", "manager", "delivery_partner"
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Environment Variable Reading

```python
# In app.py
ADMIN_MOBILE = os.environ.get("ADMIN_MOBILE") or "9999999999"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "admin@123"

# During startup (seed_staff_users)
if admin_mobile not in existing_mobiles:
    db.execute(
        "INSERT INTO staff_users (...) VALUES (...)",
        ("FoodFlux Admin", admin_email, admin_mobile, 
         generate_password_hash(ADMIN_PASSWORD), "admin")
    )
```

### Login Authentication

```python
@app.route("/admin_login", methods=["POST"])
def admin_login():
    mobile_number = normalize_mobile(request.form.get("mobile_number"))
    password = request.form.get("password")
    
    staff = query_db(
        "SELECT ... FROM staff_users WHERE mobile_number = ? AND role = 'admin'",
        (mobile_number,), one=True
    )
    
    if staff and check_password_hash(staff["password"], password):
        # Set session variables
        session["staff_role"] = "admin"
        return redirect(url_for("admin_dashboard"))
    
    return "Invalid credentials"
```

---

## Support & Questions

For issues or questions about admin authentication:
1. Check this guide's troubleshooting section
2. Verify environment variables are correctly set
3. Review app.py `admin_login()` function for implementation details
4. Check database for admin account existence

---

**Last Updated:** May 1, 2026
**Version:** 1.0
**Security Level:** Production Ready ✅
