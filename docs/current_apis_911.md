# Booking Core BE – Danh sách API hiện có

Tài liệu tổng hợp từ code hiện tại (`services/*/apis/urls.py`, `views.py`, `core/serializers`, `core/filters.py`,
`core/permissions`). Đây là API **đang chạy thật**, khác với `WEB_API_SPEC.md` (API web cần có).

## 1. Kiến trúc & routing

Mỗi service là một Django app riêng, dùng chung `app/` (settings, root urls) và `core/` (models, serializers,
filters, permission). Nginx gom tất cả về một gốc `http://<host>/api/v1/...`.

| Service | Port (host) | Prefix path qua nginx |
|---|---|---|
| user | 9001 | `/api/v1/auth`, `/users`, `/roles`, `/permissions` |
| notification | 9012 | `/api/v1/notifications` |
| resource | 9014 | `/api/v1/resources`, `/resource_types` |
| booking | 9015 | `/api/v1/bookings`, `/calendars` |
| storage | 9016 | `/api/v1/storage_configs`, `/folders`, `/files`, `/attachments`, `/media/*` |
| master-data | 9017 | `/api/v1/enum_types`, `/enum_definitions` |
| nodejs-socket | 9000 | `/socket.io/` (Socket.IO + gRPC server) |
| apschedule, celery | – | Không có REST API nghiệp vụ |

Mỗi Django service còn có: `GET /api/v1/schema/` (OpenAPI), `GET /api/v1/docs/` (Swagger UI), `/admin/`,
`/__debug__/`. Các path này **không** được nginx proxy, chỉ gọi trực tiếp theo port service.

## 2. Quy ước chung

| Mục | Giá trị |
|---|---|
| Auth | `Authorization: Bearer <access_token>` (SimpleJWT, HS256). Access 60 phút, refresh 15 ngày, refresh có rotate + blacklist |
| Đăng nhập bắt buộc | Mặc định mọi API (`LOGIN_REQUIRED` = đã đăng nhập + tài khoản `status=true` + `token_version` khớp). Ngoại lệ ghi rõ ở từng API |
| Trailing slash | Bắt buộc, vd `/api/v1/bookings/` |
| Update | Chỉ hỗ trợ `PUT` (gửi đủ field bắt buộc). `PATCH` trả **405** vì không viewset nào có `partial_update` |
| ID | UUID cho resource/booking/storage/enum; **số nguyên** cho user, role, permission, notification |
| Field naming | snake_case |
| Phân trang | Query `page`, `page_size` (mặc định 5, tối đa 100) |

### Response thành công

```json
{ "status": true, "data": { ... }, "message": "Booking created successfully!" }
```

Danh sách có phân trang:

```json
{
  "status": true,
  "data": [ ... ],
  "message": "Resources retrieved successfully!",
  "pagination": {
    "total_items": 12, "page_size": 5, "current_page": 1, "total_pages": 3,
    "next_page": "http://.../api/v1/resources/?page=2", "previous_page": null
  }
}
```

### Response lỗi

| HTTP | Body |
|---|---|
| 400 (validate) | `{ "status": false, "data": { "<field>": ["..."] }, "message": "<lỗi đầu tiên>" }` |
| 401 | `{ "status": false, "message": "Authentication credentials were not provided." }` |
| 403 | `{ "status": false, "message": "<lý do>" }` (vd `You do not have the permission RESOURCE.DESTROY!`) |
| 404 | `{ "status": false, "message": "The requested resource could not be found." }` |

Login sai trả **401** với body dạng 400: `{ "status": false, "data": { "username": [...] }, "message": ... }`.

### Phân quyền

| Ký hiệu | Ý nghĩa |
|---|---|
| Public | Không cần token |
| Login | Mọi user đã đăng nhập |
| Staff | Role `ADMIN` hoặc `STAFF` |
| Admin | Role `ADMIN` |
| Perm `X.Y` | Role của user phải có permission code `X.Y` (bảng `role_permissions`). `ADMIN` luôn qua |

Permission đã seed (`core/migrations/0005`): `RESOURCE.{LIST,CREATE,UPDATE,DESTROY}`,
`RESOURCE_TYPE.{LIST,CREATE,UPDATE,DESTROY}`. STAFF có cả 8, CUSTOMER có `RESOURCE.LIST`, `RESOURCE_TYPE.LIST`.

## 3. Tổng quan (72 endpoint, storage gộp theo nhóm)

| # | Method | Path | Quyền | Service |
|---|---|---|---|---|
| 1 | POST | `/auth/register/` | Public | user |
| 2 | POST | `/auth/login/` | Public | user |
| 3 | POST | `/auth/refresh/` | Public | user |
| 4 | POST | `/auth/logout/` | Login | user |
| 5 | GET | `/auth/me/` | Login | user |
| 6 | PUT | `/auth/me/` | Login | user |
| 7 | POST | `/auth/change_password/` | Login | user |
| 8 | GET | `/users/` | Staff | user |
| 9 | GET | `/users/{id}/` | Staff | user |
| 10 | POST | `/users/` | Admin | user |
| 11 | PUT | `/users/{id}/` | Admin | user |
| 12 | DELETE | `/users/{id}/` | Admin | user |
| 13 | GET | `/roles/` | Admin | user |
| 14 | GET | `/roles/{id}/` | Admin | user |
| 15 | POST | `/roles/` | Admin | user |
| 16 | PUT | `/roles/{id}/` | Admin | user |
| 17 | DELETE | `/roles/{id}/` | Admin | user |
| 18 | GET | `/permissions/` | Admin | user |
| 19 | POST | `/permissions/` | Admin | user |
| 20 | PUT | `/permissions/{id}/` | Admin | user |
| 21 | DELETE | `/permissions/{id}/` | Admin | user |
| 22 | GET | `/resource_types/` | Perm `RESOURCE_TYPE.LIST` | resource |
| 23 | POST | `/resource_types/` | Perm `RESOURCE_TYPE.CREATE` | resource |
| 24 | PUT | `/resource_types/{id}/` | Perm `RESOURCE_TYPE.UPDATE` | resource |
| 25 | DELETE | `/resource_types/{id}/` | Perm `RESOURCE_TYPE.DESTROY` | resource |
| 26 | GET | `/resources/` | Perm `RESOURCE.LIST` | resource |
| 27 | POST | `/resources/` | Perm `RESOURCE.CREATE` | resource |
| 28 | PUT | `/resources/{id}/` | Perm `RESOURCE.UPDATE` | resource |
| 29 | DELETE | `/resources/{id}/` | Perm `RESOURCE.DESTROY` | resource |
| 30 | GET | `/bookings/` | Login | booking |
| 31 | GET | `/bookings/me/` | Login | booking |
| 32 | GET | `/bookings/{id}/` | Login (chủ booking hoặc Staff) | booking |
| 33 | POST | `/bookings/` | Login | booking |
| 34 | POST | `/bookings/guest/` | Public | booking |
| 35 | POST | `/bookings/staff/` | Staff | booking |
| 36 | PUT | `/bookings/{id}/` | Login (chủ booking hoặc Staff) | booking |
| 37 | DELETE | `/bookings/{id}/` | Login (chủ booking hoặc Staff) | booking |
| 38 | GET | `/calendars/` | Login | booking |
| 39 | GET | `/enum_types/` | Login | master-data |
| 40 | GET | `/enum_types/{id}/` | Login | master-data |
| 41 | POST | `/enum_types/` | Admin | master-data |
| 42 | PUT | `/enum_types/{id}/` | Admin | master-data |
| 43 | DELETE | `/enum_types/{id}/` | Admin | master-data |
| 44 | GET | `/enum_definitions/` | Login | master-data |
| 45 | GET | `/enum_definitions/{id}/` | Login | master-data |
| 46 | POST | `/enum_definitions/` | Admin | master-data |
| 47 | PUT | `/enum_definitions/{id}/` | Admin | master-data |
| 48 | DELETE | `/enum_definitions/{id}/` | Admin | master-data |
| 49 | GET/POST/PUT/DELETE | `/storage_configs/[{id}/]` (4 API) | Admin | storage |
| 50 | GET/POST/PUT/DELETE + GET `{id}` | `/folders/[{id}/]` (5 API) | Login (chủ sở hữu hoặc Staff) | storage |
| 51 | GET/POST/PUT/DELETE + GET `{id}` | `/files/[{id}/]` (5 API) | Login (chủ sở hữu hoặc Staff) | storage |
| 52 | GET | `/files/{id}/download/` | Login (chủ sở hữu hoặc Staff) | storage |
| 53 | GET/POST/DELETE | `/attachments/[{id}/]` (3 API) | Login (chủ file hoặc Staff) | storage |
| 54 | GET | `/media/{path}` | Public | storage |
| 55 | GET | `/notifications/` | Login | notification |
| 56 | POST | `/notifications/` | Login | notification |
| 57 | POST | `/notifications/mark_all_as_read/` | Login | notification |
| 58 | POST | `/notifications/{id}/mark_as_read/` | Login | notification |
| 59 | GET | `/notifications/unread_notification_count/` | Login | notification |

(Tất cả path có tiền tố `/api/v1`.)

---

## 4. User service

### Auth

| API | Body | Response `data` |
|---|---|---|
| `POST /auth/register/` | `username`, `password` (≥8 ký tự, có chữ hoa, số, ký tự đặc biệt), `first_name`, `last_name` | User (role mặc định `CUSTOMER`). 201 |
| `POST /auth/login/` | `username`, `password` | User + `access_token`, `refresh_token`. Sai → 401 |
| `POST /auth/refresh/` | `refresh_token` | User + `access_token`, `refresh_token` mới (token cũ bị blacklist) |
| `POST /auth/logout/` | `refresh_token` | `{}` — blacklist refresh token và tăng `token_version` (mọi phiên khác bị đăng xuất) |
| `GET /auth/me/` | – | User hiện tại |
| `PUT /auth/me/` | `first_name`, `last_name` | User sau cập nhật |
| `POST /auth/change_password/` | `old_password`, `new_password` (phải khác mật khẩu cũ) | User + token mới; các phiên khác bị đăng xuất |

User object:

```json
{
  "id": 1, "username": "admin@finepro.net", "first_name": "Admin", "last_name": "System",
  "full_name": "Admin System", "roles": ["ADMIN"], "avatar": null, "status": true
}
```

### Users (`/users/`)

- **List** – filter: `username` (icontains), `name` (first/last name icontains), `role` (role code), `status` (bool). Có phân trang.
- **Create** – `username`, `password`, `first_name`, `last_name`, `roles` (list role code, ≥1), `status` (tuỳ chọn).
- **Update** – như create nhưng **không** được gửi `password`, không đổi `username`. Admin không tự bỏ role ADMIN / tự khoá tài khoản. Sau update `token_version` tăng → user phải đăng nhập lại.
- **Delete** – soft delete; không tự xoá chính mình.

### Roles (`/roles/`)

Body: `code` (tự upper), `name`, `description`, `configuration` (JSON), `is_active`, `permissions` (list permission code).
Response có thêm `id`, `is_system`. Role hệ thống không đổi code/không tắt/không xoá; role còn gán cho user không xoá được.
List không phân trang.

### Permissions (`/permissions/`)

Body: `code` (tự upper, unique), `name`, `description`, `configuration`. List không phân trang.
Không xoá được nếu đang được status transition tham chiếu (`ProtectedError`).

---

## 5. Resource service

### Resource types (`/resource_types/`)

- **List** – filter `code`, `code__icontains`, `name`, `name__icontains`. Có phân trang. Trả mọi field model:
  `id, code, name, description, configuration, is_active`.
- **Create / Update** – `code` (unique), `name`, `configuration`, `status_mapping` (chỉ update, write-only).

`configuration`:

```json
{
  "status_enum_type": "RESOURCE_STATUS",
  "fields": {
    "capacity": { "type": "integer", "required": true, "min": 1, "max": 200, "default": 4 },
    "floor": { "type": "string", "max_length": 10, "pattern": "^[0-9]+F$" },
    "payment": { "type": "string", "enum_type": "PAYMENT_METHOD" },
    "languages": { "type": "array", "item_type": "string", "choices": ["vi", "en"], "unique": true }
  }
}
```

- `status_enum_type`: enum type cung cấp danh sách trạng thái cho resource của type này (mặc định `RESOURCE_STATUS`).
- `fields`: định nghĩa custom field, kiểm tra bởi `core/configuration_rules.py`.
- `status_mapping` `{ "<code cũ>": "<code mới>" | "" }`: khi đổi `status_enum_type`, chuyển trạng thái resource cũ sang list mới (`""` = bỏ trạng thái). Code trùng tên được map tự động.

### Resources (`/resources/`)

- **List** – filter `resource_type` (UUID), `resource_type_code`, `status` (code, iexact), `code`, `code__icontains`, `name`, `name__icontains`. Có phân trang.
- **Create / Update** – `resource_type` (UUID), `code` (unique trong type), `name`, `status` (code trong list của type; `""`/`null` = không trạng thái; bỏ qua khi tạo → `ACTIVE`), `configuration` (giá trị theo `fields` của type, field thiếu được điền `default`).

```json
{
  "id": "0192...", "resource_type": "0192...", "resource_type_code": "ROOM",
  "code": "R101", "name": "Phòng 101", "status": "ACTIVE",
  "configuration": { "capacity": 4 }, "created_at": "...", "updated_at": "..."
}
```

Chưa có `GET /resources/{id}/` và `GET /resource_types/{id}/` (trả 405).

---

## 6. Booking service

### Bookings (`/bookings/`)

| API | Ghi chú |
|---|---|
| `GET /bookings/` | Tất cả booking. Filter: `resource`, `resource_type` (UUID), `resource_type_code`, `user` (id), `status` (code), `title__icontains`, `from_time`, `to_time` (booking giao với khoảng). Sắp theo `start_at`, có phân trang |
| `GET /bookings/me/` | Như trên nhưng chỉ booking của user hiện tại |
| `GET /bookings/{id}/` | User thường chỉ thấy booking của mình (khác → 404); Staff thấy tất cả |
| `POST /bookings/` | Body: `resource`, `start_at`, `end_at`, `status?`, `title?`, `description?`, `configuration?`. `user` lấy từ token |
| `POST /bookings/guest/` | Public. Như trên + `guest_name`, `guest_email` (bắt buộc), `guest_phone?` |
| `POST /bookings/staff/` | Staff đặt hộ: chọn `user` (id) **hoặc** nhập `guest_name` + `guest_email`, không được cả hai |
| `PUT /bookings/{id}/` | Body như create; dùng để đổi giờ/đổi trạng thái (confirm, cancel, complete) |
| `DELETE /bookings/{id}/` | Xoá booking |

Quy tắc nghiệp vụ (`EditBookingSerializer`):

- `end_at > start_at`.
- Resource phải bookable: trạng thái `ACTIVE` hoặc enum value có `configuration.bookable = true`.
- Booking mới chỉ được `PENDING` hoặc `CONFIRMED` (mặc định `CONFIRMED`).
- Booking `PENDING`/`CONFIRMED` không được trùng giờ trên cùng resource (khoá row resource bằng `select_for_update`). Trùng → 400 `{"start_at": ["Resource is already booked for this time!"]}`.
- Chuyển trạng thái:

| Hiện tại | Được chuyển sang |
|---|---|
| PENDING | CONFIRMED, CANCELLED |
| CONFIRMED | CANCELLED, COMPLETED |
| CANCELLED, COMPLETED | – (không sửa được nữa) |

Booking object:

```json
{
  "id": "0192...", "resource": "0192...", "user": 5,
  "guest_name": null, "guest_email": null, "guest_phone": null,
  "start_at": "2026-12-15T09:00:00+07:00", "end_at": "2026-12-15T10:00:00+07:00",
  "status": "CONFIRMED", "status_name": "Confirmed",
  "title": "Họp team", "description": null, "configuration": {}, "created_at": "..."
}
```

### Calendar (`GET /calendars/`)

Query: `start_date`, `end_date` (bắt buộc, `YYYY-MM-DD`, tối đa 31 ngày), `resource`, `resource_type`, `resource_type_code`.
Trả về mọi resource (lọc theo query), mỗi resource có lịch từng ngày; booking `CANCELLED` bị ẩn, booking dài nhiều
ngày xuất hiện ở mỗi ngày nó phủ. Không phân trang, không có thông tin liên hệ guest.

```json
[
  {
    "id": "0192...", "code": "R101", "name": "Phòng 101", "status": "<status id>",
    "resource_type": "0192...", "resource_type_code": "ROOM",
    "calendar": [
      { "date": "2026-12-15", "bookings": [
        { "id": "...", "user": 5, "title": "Họp team", "start_at": "...", "end_at": "...",
          "status": "CONFIRMED", "status_name": "Confirmed" } ] }
    ]
  }
]
```

---

## 7. Master-data service

### Enum types (`/enum_types/`)

Body: `code` (tự upper), `name`, `description?`. Response thêm `id`, `is_system`, `definitions_count`. List không phân trang.
Enum type hệ thống (`RESOURCE_STATUS`, `BOOKING_STATUS`, `NOTIFICATION_TYPE`) không đổi code, không xoá.
Chỉ xoá được khi không còn value.

### Enum definitions (`/enum_definitions/`)

- **List** – filter `enum_type` (code), `code`, `is_active`. Trả về **theo nhóm** enum type, không phân trang:

```json
[
  {
    "enum_type": "RESOURCE_STATUS", "name": "Resource status", "description": "", "is_system": true,
    "definitions": [
      { "id": "...", "code": "ACTIVE", "name": "Active", "value": 1, "position": 0,
        "configuration": {}, "is_system": true, "is_active": true }
    ]
  }
]
```

- **Retrieve / Create / Update** – body: `enum_type` (code), `code` (unique trong type), `name`, `value?` (int, unique trong type), `position?` (≥0), `configuration?`, `is_active?`.
  Value hệ thống không đổi type/code, không tắt, không xoá. Value đang được dùng không xoá được (gợi ý đặt `is_active=false`).

---

## 8. Storage service

Quyền chung: Admin/Staff thấy mọi folder/file/attachment; user khác chỉ thấy của mình (khác → 404).

### Storage configs (`/storage_configs/`) – Admin

Body: `code` (upper, unique), `name`, `provider` (`LOCAL` | `S3` | `MINIO`), `configuration`, `max_file_size_bytes`,
`allowed_extensions` (list), `is_default`, `is_active`.

- `configuration` không được chứa key giống credential (`secret`, `password`, `access_key`, `token`, `credential`).
- LOCAL: `configuration.path` (mặc định = code, chỉ `a-z0-9_-/`, không trùng storage khác, không đổi khi đã có file);
  `configuration.purposes` (list purpose dùng storage này, mỗi purpose thuộc 1 storage).
- Chỉ một storage `is_default`; đặt default mới sẽ bỏ default cũ. Không xoá được khi còn file.

### Folders (`/folders/`)

- **List** – filter `parent` (UUID), `is_root` (bool), `name` (icontains). Có phân trang.
- **Create / Update** – `name`, `parent?`, `configuration?`. Tên không trùng trong cùng folder cha của cùng owner; không di chuyển vào chính nó/con của nó.
- **Delete** – xoá cả folder con; file bên trong được giữ và chuyển ra root.
- Response: `id, name, parent, created_by, configuration, children_count, files_count, created_at, updated_at`.

### Files (`/files/`)

| API | Ghi chú |
|---|---|
| `GET /files/` | Filter `folder`, `is_root`, `name` (icontains), `extension`. Mới nhất trước, có phân trang |
| `GET /files/{id}/` | Chi tiết file |
| `POST /files/` | `multipart/form-data`: `file`, `folder?`, `storage_config?` (code), `object_type?`, `object_id?`, `purpose?`. Có `object_type` + `object_id` thì gắn attachment luôn (response có thêm `attachment`) |
| `PUT /files/{id}/` | `original_name`, `folder?`, `configuration?` (đổi tên / di chuyển) |
| `DELETE /files/{id}/` | Xoá file + attachment; nội dung bị xoá khỏi storage sau khi commit |
| `GET /files/{id}/download/` | Trả file nhị phân (`Content-Disposition: attachment`) |

Chọn storage khi upload: `storage_config` → storage có `purpose` tương ứng → storage default. Kiểm tra
`allowed_extensions` và `max_file_size_bytes`.

```json
{
  "id": "0192...", "original_name": "avatar.png", "extension": "png", "mime_type": "image/png",
  "size_bytes": 10240, "checksum": "...", "folder": null, "uploaded_by": 5,
  "storage_config": "0192...", "storage_config_code": "AVATARS", "configuration": {},
  "url": "http://<BE_DOMAIN>/api/v1/media/avatars/2026/11/<uuid>.png",
  "download_url": "/api/v1/files/<id>/download/", "created_at": "...", "updated_at": "..."
}
```

`url` chỉ có với storage `LOCAL` (S3/MinIO trả `null`).

### Attachments (`/attachments/`)

- **List** – filter `object_type`, `object_id`, `file` (UUID), `purpose`. Có phân trang.
- **Create** – `file` (UUID), `object_type` (`booking` | `resource` | `resource_type` | `comment` | `user`), `object_id`, `purpose?`, `configuration?`. Không gắn trùng (file + object + purpose).
- **Delete** – chỉ gỡ liên kết, file vẫn giữ.
- Response: `id, file, file_detail (File object), content_type, object_id, purpose, configuration, created_at`.

### Media (`GET /media/{path}`)

Public, không cần token, phục vụ file trong `STORAGE_ROOT` (link `url` của file LOCAL). Không liệt kê thư mục.

---

## 9. Notification service

| API | Ghi chú |
|---|---|
| `GET /notifications/` | Thông báo của user hiện tại. Filter `is_read`. Có phân trang |
| `POST /notifications/` | Body `{ "user_ids": [1, 2], "notify_type": <id enum NOTIFICATION_TYPE>, "data": {...} }` → tạo hàng loạt, 201 |
| `POST /notifications/mark_all_as_read/` | Đánh dấu tất cả của user đã đọc |
| `POST /notifications/{id}/mark_as_read/` | Đánh dấu 1 thông báo đã đọc |
| `GET /notifications/unread_notification_count/` | `data` = số chưa đọc |

Response tạo/list: `{ "status": true, "data": [ { "id", "user": {User}, "notify_type", "data", "is_read", "created_at", "updated_at", ... } ] }`.
Các API mark/count trả `data` là chuỗi hoặc số, không có `message`.

---

## 10. Socket service (nodejs-socket)

- Kết nối: Socket.IO tại `/socket.io/`, `auth: { token: "<access_token>" }` (verify bằng `JWT_ACCESS_TOKEN_SECRET`). Thiếu token → `401 Unauthorized`, sai → `403 Forbidden`.
- Khi kết nối, socket join room `user:<user_id>`.
- Client → server: `globalNotify` `{ data: { message } }` – tạo notification hệ thống cho mọi user khác và broadcast.
- Server → client: `myNotification` `{ data: { change: 1 } }` – báo client tải lại thông báo / số chưa đọc.
- gRPC `NotificationService.EmitNotification({ users: [int] })` – Django gọi để emit `myNotification` tới các room user.

---

## 11. Điểm cần lưu ý (từ code hiện tại)

- `GET /bookings/` cho **mọi user đã đăng nhập** xem tất cả booking, gồm `guest_email`/`guest_phone` – có thể cần giới hạn cho Staff.
- `POST /notifications/` cho mọi user đăng nhập tạo thông báo cho user bất kỳ; thiếu `user_ids` sẽ lỗi 500.
- `POST /notifications/{id}/mark_as_read/` không kiểm tra thông báo có thuộc user hiện tại không.
- Notification và các API mark/count không dùng format `response_success` chuẩn (thiếu `message`).
- Resource / resource type chưa có API chi tiết (`GET {id}`), và mọi resource dùng `ApiPermission` thay vì role cố định.
- `PATCH` không hỗ trợ ở mọi service; `permission_codes = {"partial_update": ...}` trong resource views hiện chưa có tác dụng.
- Calendar trả `status` của resource là **id** của enum value, không phải code như `GET /resources/`.
