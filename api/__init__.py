"""
API package for Lexsy AI Assistant
"""

# Import routers with error handling
try:
    from .auth import router as auth_router
except ImportError as e:
    print(f"Failed to import auth router: {e}")
    auth_router = None

try:
    from .clients import router as clients_router
except ImportError as e:
    print(f"Failed to import clients router: {e}")
    clients_router = None

try:
    from .documents import router as documents_router
except ImportError as e:
    print(f"Failed to import documents router: {e}")
    documents_router = None

try:
    from .emails import router as emails_router
except ImportError as e:
    print(f"Failed to import emails router: {e}")
    emails_router = None

try:
    from .chat import router as chat_router
except ImportError as e:
    print(f"Failed to import chat router: {e}")
    chat_router = None

# Export available routers
__all__ = []
if auth_router:
    __all__.append("auth_router")
if clients_router:
    __all__.append("clients_router")
if documents_router:
    __all__.append("documents_router")
if emails_router:
    __all__.append("emails_router")
if chat_router:
    __all__.append("chat_router")
