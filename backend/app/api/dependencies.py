
"""

app/auth/dependencies.py

Backward-compatibility shim.

All routers that previously imported from here now point to the same

canonical dependency in app.api.deps.

"""

from app.api.deps import get_current_user  # noqa: F401 — re-exported for legacy imports

