from core.middlewares.active_account import ActiveAccountMiddleware
from core.middlewares.authenticate import AuthenticateMiddleware
from core.middlewares.check_token_version import TokenVersionMiddleware

# permission classes for APIs that require a logged in, active user with a
# valid token version (auth is disabled globally in settings)
LOGIN_REQUIRED = [
    AuthenticateMiddleware,
    ActiveAccountMiddleware,
    TokenVersionMiddleware,
]
