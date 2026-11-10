from rest_framework.settings import api_settings

# permission classes of an API that needs a logged in, active user with a valid token
# version: the DEFAULT_PERMISSION_CLASSES of settings (authenticate, active_account,
# check_token_version), so the list is written in one place only.
# Views without permission_classes already use them; LOGIN_REQUIRED is for views that
# add a class, eg permission_classes = [*LOGIN_REQUIRED, IsStaff], because
# permission_classes replaces the default list.
LOGIN_REQUIRED = list(api_settings.DEFAULT_PERMISSION_CLASSES)
