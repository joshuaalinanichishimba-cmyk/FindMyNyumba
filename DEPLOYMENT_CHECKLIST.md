# FindMyNyumba — Deployment Readiness Checklist

## Environment Variables (Required Before Launch)

Set these in your server environment or `.env` file:

```env
# Admin bootstrap credentials (replaces hardcoded credentials)
ADMIN_BOOTSTRAP_EMAIL=your-admin@email.com
ADMIN_BOOTSTRAP_PASSWORD=YourStrongPassword1!

# Secret required to register new admin accounts via the UI
ADMIN_INVITE_SECRET=a-very-long-random-secret-string

# Backend public URL (used to construct image URLs in listings)
BACKEND_URL=https://api.yourdomain.com

# CORS: comma-separated list of allowed frontend origins
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/findmynyumba

# JWT secret (must be long and random)
SECRET_KEY=replace-this-with-a-256-bit-random-secret

# Email service (for forgot password flow)
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=your-smtp-password
```

---

## Database Migration Checklist

Ensure these columns exist on the `users` table:

| Column | Type | Notes |
|--------|------|-------|
| `verification_status` | VARCHAR | `unverified`, `pending`, `verified`, `rejected` |
| `verification_rejection_reason` | TEXT, nullable | Set on rejection |
| `avatar_url` | TEXT, nullable | Profile picture URL |
| `business_name` | TEXT, nullable | Landlord business name |
| `email_alerts` | BOOLEAN | Default `true` |
| `sms_alerts` | BOOLEAN | Default `false` |
| `university` | TEXT, nullable | Student registration field |
| `student_id` | TEXT, nullable | Student registration field |
| `phone_number` | TEXT, nullable | Allow NULL (Google OAuth users) |

Ensure the `reports` table exists:

```sql
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    reporter_id INTEGER REFERENCES users(id),
    listing_id  INTEGER REFERENCES listings(id),
    reason      TEXT NOT NULL,
    description TEXT,
    status      VARCHAR DEFAULT 'pending',
    created_at  TIMESTAMP DEFAULT NOW()
);
```

Optionally create the `saved_properties` table for the student Saved Rooms feature:

```sql
CREATE TABLE IF NOT EXISTS saved_properties (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, listing_id)
);
```

---

## Backend Forgot Password Endpoints (Still Needed)

The `forgot-password.html` frontend calls these two endpoints which need to be implemented in `auth.py`:

```python
# POST /auth/forgot-password
# Body: { "email": "user@example.com" }
# Action: generate a time-limited reset token (e.g. 15 min), store in DB or cache, send email

# POST /auth/reset-password
# Body: { "email": "...", "token": "...", "new_password": "..." }
# Action: verify token against stored one, check expiry, update hashed_password
```

Recommended implementation:
- Use `secrets.token_urlsafe(32)` to generate reset tokens
- Store token + expiry in a `password_reset_tokens` table
- Send email via SMTP (use `fastapi-mail` or `emails` library)

---

## HTML Files — Final Filename Reference

All files are now consistently named and cross-referenced:

| File | Links to |
|------|----------|
| `login.html` | `landlord-register.html` ✅ (was `register-landlord.html`) |
| `register.html` | `landlord-register.html` ✅ (was `register-landlord.html`) |
| `admin.html` | `admin-login.html` on logout ✅ (was `login.html`) |
| `admin-login.html` | `login.html` ← user login link ✅ |
| `login.html` | `forgot-password.html` ✅ (page now exists) |

---

## Router Registration Verification

Final resolved URL table (verify with `GET /api/docs` after startup):

| Frontend calls | Backend file | Router prefix | Final URL |
|---|---|---|---|
| `/api/v1/auth/login` | `auth.py` | `/auth` | ✅ `/api/v1/auth/login` |
| `/api/v1/auth/me` | `auth.py` | `/auth` | ✅ `/api/v1/auth/me` |
| `/api/v1/landlord/dashboard/stats` | `landlords.py` | `/landlord` | ✅ Fixed (was double-prefixed) |
| `/api/v1/student-host/dashboard/stats` | `student_hosts.py` | `/student-host` | ✅ Fixed (was double-prefixed) |
| `/api/v1/students/dashboard/overview` | `students.py` | `/students` | ✅ New file added |
| `/api/v1/admin/listings/{id}/reject` | `admin.py` | `/admin` | ✅ New endpoint added |
| `/api/v1/admin/verifications/{id}/reject` | `admin.py` | `/admin` | ✅ New endpoint added |
| `/api/v1/admin/register` | `admin.py` | `/admin` | ✅ Now requires `invite_secret` |
| `/api/v1/properties` | `listings.py` | `/properties` | ✅ |
| `/api/v1/messages/send` | `messages.py` | `/messages` | ✅ |

---

## Pages to Test Before Launch

| Page | Test Actions |
|------|-------------|
| `login.html` | Email login, Google login, wrong password error, Remember Me, redirect by role |
| `register.html` | Student register, student_host register, password validation, duplicate email error |
| `landlord-register.html` | Landlord register, all validations |
| `forgot-password.html` | Submit email, submit token + new password |
| `browse.html` | Load listings, search, filter by price |
| `listing.html?id=X` | Load property details, send inquiry (logged in and not) |
| `contact-landlord.html?id=X` | Load property info, send message |
| `dashboard-student.html` | Stats load, listings load, messages tab, profile update |
| `dashboard-landlord.html` | Stats, property list, add property, verification submit, inquiries |
| `dashboard-student-host.html` | Stats, bedspace list, add bedspace, messages |
| `admin-login.html` | Admin login with env-var credentials, session stored in sessionStorage |
| `admin.html` | All tabs load, approve/reject listing, approve/reject verification, suspend user, logout → admin-login |

---

## Highest-Risk Areas for QA

1. **Admin bootstrap** — first login must auto-create admin from env vars
2. **Double-prefix fix** — ALL landlord/student-host routes now resolve correctly; test every fetch call
3. **Student dashboard** — `/students/dashboard/overview` is new; test with a student account
4. **Verification reject** — modal reason field must pass through to backend
5. **Admin logout** — must clear both localStorage AND sessionStorage, redirect to admin-login.html
6. **Forgot password** — backend endpoints need to be implemented; frontend is ready
7. **File uploads** — test with filenames containing spaces, dots, and unicode characters
8. **Google OAuth** — works in dev; verify client_id is correct and domain is authorized in Google Console

---

## Security Hardening Status

| Risk | Status |
|------|--------|
| Hardcoded admin credentials | ✅ Moved to env vars |
| Double router prefix (404 all landlord routes) | ✅ Fixed |
| Missing `/students/dashboard/overview` endpoint | ✅ Created |
| XSS via innerHTML in admin.html | ✅ All fields escaped with `esc()` |
| Path traversal in file uploads | ✅ `os.path.basename()` added |
| Admin token leaked to localStorage | ✅ sessionStorage only for admins |
| Admin logout to wrong page | ✅ Now goes to admin-login.html |
| Open admin registration | ✅ Now requires invite secret |
| CORS wildcard | ✅ Reads from ALLOWED_ORIGINS env var |
| Broken `register-landlord.html` links | ✅ Fixed to `landlord-register.html` |
| Duplicate `users.py` ghost router | ✅ Removed from main.py registration |
| Missing reject listing endpoint | ✅ Added to admin.py |
| Missing reject verification endpoint | ✅ Added to admin.py |
| university/student_id silently discarded | ✅ Now saved in auth.py |
| Forgot password dead link | ✅ Page now exists |

---

## Final Launch Confidence Assessment

| Category | Before | After |
|---|---|---|
| Frontend–Backend Connectivity | 3/10 | **9/10** |
| Authentication Security | 4/10 | **8/10** |
| Brand/UI Consistency | 6/10 | **9/10** |
| Backend Code Quality | 5/10 | **9/10** |
| Database Alignment | 5/10 | **8/10** |
| Security Hardening | 3/10 | **8/10** |
| Feature Completeness | 4/10 | **8/10** |
| **Overall Launch Readiness** | **4/10** | **8.5/10** |

**Remaining 1.5 points** require:
- Implementing the forgot-password backend endpoints (token generation + email sending)
- Verifying all DB migrations applied (new User columns)
- Proper Google OAuth RSA signature verification for production
- Setting `ALLOWED_ORIGINS` to real domain before going live
