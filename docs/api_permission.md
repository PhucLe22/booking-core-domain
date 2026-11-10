# API Permissions

Every API needs a permission code. A user can call the API when one of their active roles has that code. ADMIN can call every API.

```
users ──< user_roles >── roles ──< role_permissions >── permissions
```

## Permission code rule

```
CODE = <BASENAME>.<ACTION>      (in capitals)
```

- **BASENAME** comes from `router.register(..., basename="resource")` in each service's `apis/urls.py`.
- **ACTION** comes from the HTTP method and URL (standard actions), or from the Python method name (custom `@action`).

Example: `DELETE /api/v1/resources/{id}/` → basename `resource`, action `destroy` → `RESOURCE.DESTROY`.

The check is `ApiPermission` in [core/permissions/api_permission.py](core/permissions/api_permission.py).

## Standard actions

| What you do  | HTTP + URL            | Action           | Code                  |
| ------------ | --------------------- | ---------------- | --------------------- |
| View list    | `GET /items/`         | `list`           | `ITEM.LIST`           |
| View one     | `GET /items/{id}/`    | `retrieve`       | `ITEM.RETRIEVE`       |
| Create       | `POST /items/`        | `create`         | `ITEM.CREATE`         |
| Edit (full)  | `PUT /items/{id}/`    | `update`         | `ITEM.UPDATE`         |
| Edit (part)  | `PATCH /items/{id}/`  | `partial_update` | `ITEM.PARTIAL_UPDATE` |
| Delete       | `DELETE /items/{id}/` | `destroy`        | `ITEM.DESTROY`        |

A ViewSet can rename a code with `permission_codes`, for example `{"partial_update": "RESOURCE.UPDATE"}` makes PATCH use the same code as PUT.

## All APIs

All URLs start with `http://localhost:82/api/v1`.

**Status:** ✔ live means the permission check runs today. Planned means the service still uses the old role checks (`IsStaff` / `IsAdmin`) or only requires login.

### Resource: ✔ live

| API                         | Action  | Code                    |
| --------------------------- | ------- | ----------------------- |
| `GET /resources/`           | list    | `RESOURCE.LIST`         |
| `POST /resources/`          | create  | `RESOURCE.CREATE`       |
| `PUT /resources/{id}/`      | update  | `RESOURCE.UPDATE`       |
| `DELETE /resources/{id}/`   | destroy | `RESOURCE.DESTROY`      |
| `GET /resource_types/`      | list    | `RESOURCE_TYPE.LIST`    |
| `POST /resource_types/`     | create  | `RESOURCE_TYPE.CREATE`  |
| `PUT /resource_types/{id}/` | update  | `RESOURCE_TYPE.UPDATE`  |
| `DELETE /resource_types/{id}/` | destroy | `RESOURCE_TYPE.DESTROY` |

There is no `GET /resources/{id}/` yet, so there is no `RESOURCE.RETRIEVE`.

### Booking: planned

| API                      | Action   | Code               |
| ------------------------ | -------- | ------------------ |
| `GET /bookings/`         | list     | `BOOKING.LIST`     |
| `GET /bookings/{id}/`    | retrieve | `BOOKING.RETRIEVE` |
| `POST /bookings/`        | create   | `BOOKING.CREATE`   |
| `PUT /bookings/{id}/`    | update   | `BOOKING.UPDATE`   |
| `DELETE /bookings/{id}/` | destroy  | `BOOKING.DESTROY`  |
| `GET /bookings/me/`      | me       | `BOOKING.ME`       |
| `POST /bookings/staff/`  | staff    | `BOOKING.STAFF`    |
| `POST /bookings/guest/`  | guest    | public             |
| `GET /calendars/`        | list     | `CALENDAR.LIST`    |

### Master data: planned

| API                                           | Actions                                 | Code                |
| --------------------------------------------- | --------------------------------------- | ------------------- |
| `GET/POST/PUT/DELETE /enum_types/`            | list, retrieve, create, update, destroy | `ENUM_TYPE.*`       |
| `GET/POST/PUT/DELETE /enum_definitions/`      | list, retrieve, create, update, destroy | `ENUM_DEFINITION.*` |

### User: planned

| API                                  | Actions                                 | Code           |
| ------------------------------------ | --------------------------------------- | -------------- |
| `GET/POST/PUT/DELETE /users/`        | list, retrieve, create, update, destroy | `USER.*`       |
| `GET/POST/PUT/DELETE /roles/`        | list, retrieve, create, update, destroy | `ROLE.*`       |
| `GET/POST/PUT/DELETE /permissions/`  | list, create, update, destroy           | `PERMISSION.*` |
| `POST /auth/register/`               | create_user                             | public         |
| `POST /auth/login/`                  | login_user                              | public         |
| `POST /auth/logout/`                 | logout_user                             | any logged-in user |
| `GET /auth/me/`                      | me                                      | any logged-in user |
| `POST /auth/change_password/`        | change_password                         | any logged-in user |

### Storage: planned

| API                         | Actions                                 | Code               |
| --------------------------- | --------------------------------------- | ------------------ |
| `/storage_configs/`         | list, create, update, destroy           | `STORAGE_CONFIG.*` |
| `/folders/`                 | list, retrieve, create, update, destroy | `FOLDER.*`         |
| `/files/`                   | list, retrieve, create, update, destroy | `FILE.*`           |
| `GET /files/{id}/download/` | download                                | `FILE.DOWNLOAD`    |
| `/attachments/`             | list, create, destroy                   | `ATTACHMENT.*`     |

### Notification: planned

| API                                           | Action                    | Code                                     |
| --------------------------------------------- | ------------------------- | ---------------------------------------- |
| `GET /notifications/`                         | list                      | `NOTIFICATION.LIST`                      |
| `POST /notifications/`                        | create                    | `NOTIFICATION.CREATE`                    |
| `POST /notifications/mark_all_as_read/`       | mark_all_as_read          | `NOTIFICATION.MARK_ALL_AS_READ`          |
| `POST /notifications/{id}/mark_as_read/`      | mark_as_read              | `NOTIFICATION.MARK_AS_READ`              |
| `GET /notifications/unread_notification_count/` | unread_notification_count | `NOTIFICATION.UNREAD_NOTIFICATION_COUNT` |

## Seeded permissions

Migration [0005_seed_resource_permissions.py](core/migrations/0005_seed_resource_permissions.py) creates the 8 resource codes and gives them to the system roles:

| Role     | Permissions                                   |
| -------- | --------------------------------------------- |
| ADMIN    | none needed, passes every check               |
| STAFF    | all 8 `RESOURCE.*` and `RESOURCE_TYPE.*`      |
| CUSTOMER | `RESOURCE.LIST`, `RESOURCE_TYPE.LIST`         |

## Attach permissions to a role

Only ADMIN can call these APIs.

**Create a role**

```
POST /api/v1/roles/
Authorization: Bearer <admin access token>
```

```json
{
  "code": "A",
  "name": "Resource cleaner",
  "description": "Can view and delete resources",
  "configuration": {},
  "is_active": true,
  "permissions": ["RESOURCE.LIST", "RESOURCE.DESTROY"]
}
```

**Change a role's permissions**

```
PUT /api/v1/roles/{role_id}/
```

Send the same body. `permissions` **replaces** the role's whole list: leave a code out to remove it, or send `[]` to remove all. `code` and `name` are required on every PUT.

**Give the role to a user**

```
PUT /api/v1/users/{user_id}/
```

```json
{ "roles": ["A"] }
```

`roles` also replaces the user's whole list. Changes apply on the user's next request.

| Purpose                        | API                       |
| ------------------------------ | ------------------------- |
| Find a role id and its permissions | `GET /api/v1/roles/`  |
| List every permission code     | `GET /api/v1/permissions/` |

## Denied responses

| Case                        | Response |
| --------------------------- | -------- |
| No or invalid token         | `401` |
| Missing permission          | `403 {"status": false, "message": "You do not have the permission RESOURCE.LIST!"}` |
| Fixed role required by view | `403 {"status": false, "message": "Only ADMIN can use this API!"}` |

## Adding a new API

1. Add the endpoint to a ViewSet that has `permission_classes = [*LOGIN_REQUIRED, ApiPermission]`.
2. Its code is `<BASENAME>.<ACTION>`, eg a new `@action` `export` on bookings → `BOOKING.EXPORT`.
3. Add a data migration that creates the permission and gives it to the roles that need it.
4. Until a role has the code, only ADMIN can call the API.
