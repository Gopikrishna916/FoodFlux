# 🔐 FoodFlux Admin Authentication - Quick Reference

## 📌 Environment Variables

```bash
# Required for admin account creation
ADMIN_MOBILE=9999999999          # 10-digit mobile number
ADMIN_PASSWORD=YourPassword@123  # Min 6 chars (use 12+ for production)
SECRET_KEY=random-key-here       # Flask session key
```

## 🚀 Local Development (Quick Start)

```bash
# 1. Create .env file
cp .env.example .env

# 2. Edit .env with your credentials
nano .env  # or use your editor

# 3. Run the app
python app.py

# 4. Admin login at http://localhost:5000/admin_login
#    Mobile: 9999999999
#    Password: (whatever you set in .env)
```

## ✅ Verify Setup

```bash
python test_admin_auth_setup.py
# or
python verify_admin_setup.py
```

## 🌐 Production Deployment (Render)

1. Go to Render Dashboard → Service Settings
2. Add Environment Variables:
   - `ADMIN_MOBILE`: Your 10-digit mobile
   - `ADMIN_PASSWORD`: Strong password
   - `SECRET_KEY`: Generated random key

```bash
# Generate SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"
```

3. Git push to deploy
4. Admin account auto-created on startup

## 📚 Documentation

| File | Purpose |
|------|---------|
| [.env.example](.env.example) | Configuration template |
| [ADMIN_AUTH_SETUP.md](ADMIN_AUTH_SETUP.md) | Full setup guide |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Feature overview |
| [test_admin_auth_setup.py](test_admin_auth_setup.py) | Security validation |
| [verify_admin_setup.py](verify_admin_setup.py) | Quick verification |

## 🔒 Security Checklist

- [ ] Never commit .env file (it's in .gitignore)
- [ ] Use strong passwords (12+ chars with symbols)
- [ ] Rotate credentials periodically
- [ ] Enable HTTPS in production
- [ ] Monitor admin login attempts
- [ ] Keep Flask updated

## 🆘 Troubleshooting

**Admin login not working?**
```bash
# Check environment variables
echo $ADMIN_MOBILE
echo $ADMIN_PASSWORD

# Verify admin account exists
python verify_admin_setup.py

# Check database
sqlite3 database.db "SELECT * FROM staff_users WHERE role='admin';"
```

**Generate new SECRET_KEY**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Reset admin password**
```bash
rm database.db
python app.py  # Creates new DB with new credentials from environment
```

## 📞 Admin Login Details

**URL:** `/admin_login`  
**Field 1:** 10-digit mobile number  
**Field 2:** Password  
**Database:** Uses `staff_users` table with role='admin'  
**Auth:** Mobile number + password (no email)  

## ⚡ Key Features

✓ Environment-based credentials  
✓ Auto-account creation on startup  
✓ Passwords hashed with Werkzeug  
✓ Mobile number authentication  
✓ No hardcoded secrets  
✓ .env protected in .gitignore  

---

**Status:** ✅ Production Ready  
**Last Updated:** May 1, 2026
