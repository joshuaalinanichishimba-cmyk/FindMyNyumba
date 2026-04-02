from slowapi import Limiter
from slowapi.util import get_remote_address

# This tracks unique IP addresses to prevent abuse
limiter = Limiter(key_func=get_remote_address)
