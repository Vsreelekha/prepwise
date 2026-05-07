"""
Auth router alias module.

This file re-exports the auth/user router so `main.py` can import
`routers.auth` consistently.
"""

from .users import router

