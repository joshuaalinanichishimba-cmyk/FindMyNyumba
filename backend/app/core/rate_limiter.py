"""
app/core/rate_limiter.py
Shared rate limiter for FindMyNyumba.

WHY THIS EXISTS
---------------
slowapi was already in requirements.txt and a Limiter was defined here, but
setup_rate_limiting() was never called from main.py and no endpoint had a
limit. That meant /auth/login could be brute-forced at full speed. This file
now exposes a single shared `limiter` plus named limit strings so every
sensitive endpoint uses the same, easy-to-audit values.

USAGE
-----
1. In main.py:
       from app.core.rate_limiter import setup_rate_limiting
       setup_rate_limiting(app)        # call once, after `app = FastAPI(...)`

2. On any endpoint that should be limited, the path-operation function MUST
   accept a `request: Request` parameter (slowapi reads the client IP from it):

       from fastapi import Request
       from app.core.rate_limiter import limiter, LOGIN_LIMIT

       @router.post("/login")
       @limiter.limit(LOGIN_LIMIT)
       def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
           ...

Limits are per-client-IP per the window shown. Tune the numbers below in one
place rather than scattering magic strings across the codebase.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import FastAPI

# Single shared limiter. Importing `limiter` from here everywhere guarantees
# all decorators register against the same instance held on app.state.
limiter = Limiter(key_func=get_remote_address)

# Named limits — change the policy here, not at each call site.
LOGIN_LIMIT          = "5/minute"     # password login attempts
REGISTER_LIMIT       = "5/hour"       # new account creation
FORGOT_PASSWORD_LIMIT = "3/hour"      # reset-link requests (anti email-bomb)
RESET_PASSWORD_LIMIT  = "5/hour"      # reset token submissions
MESSAGE_SEND_LIMIT    = "30/minute"   # outbound chat messages (anti-spam)
REPORT_LIMIT          = "10/hour"     # abuse/scam reports


def setup_rate_limiting(app: FastAPI) -> None:
    """Attach the shared limiter to the app and register the 429 handler."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
