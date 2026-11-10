# Booking Core – Danh sách API cần có cho Web

Nguồn: `booking-core/web` (apps `console` + `member`). Client được sinh tự động (orval) từ
`booking-core/contracts/openapi.yaml`, nên đó là contract chuẩn. Ví dụ đánh dấu *(spec)* lấy nguyên
từ `examples` trong OpenAPI; các ví dụ còn lại được dựng theo schema.

## Quy ước chung

| Mục | Giá trị |
|---|---|
| Base URL | `/api/v1` |
| Auth | `Authorization: Bearer <JWT>` |
| Tenant | Header **bắt buộc** `X-Tenant-Id: <uuid>` trên mọi request |
| ID | UUIDv7 string |
| Thời gian | ISO 8601 có offset của site, vd `2026-12-15T09:00:00+07:00` (offset lấy từ `GET /sites/{id}`) |
| Phân trang | Query `limit` (1–100, mặc định 50), `cursor`; response `{ "data": [...], "nextCursor": string \| null }` |
| Content-Type lỗi | `application/problem+json` (RFC 9457 + field `code`) |
| Field naming | camelCase |

### Định dạng lỗi

```json
{
  "type": "https://errors.bookingcore.dev/not-found",
  "title": "Not found",
  "status": 404,
  "code": "NOT_FOUND",
  "detail": "No booking with that id in this tenant."
}
```

`code` ∈ `VALIDATION_FAILED | BOOKING_DENIED | SLOT_TAKEN | INVALID_TRANSITION | STALE_VERSION | UNAUTHENTICATED | FORBIDDEN | NOT_FOUND`.
Web đọc `body.code` để hiển thị lỗi, nên **bắt buộc** trả `code`.

| HTTP | code | Khi nào |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Thiếu/sai/hết hạn token |
| 403 | `FORBIDDEN` | Không có quyền trong tenant |
| 404 | `NOT_FOUND` | Không có bản ghi trong tenant |
| 409 | `SLOT_TAKEN` | Slot đã có người giữ (create booking) |
| 409 | `INVALID_TRANSITION` | Chuyển trạng thái booking không hợp lệ |
| 409 | `STALE_VERSION` | `baseVersion` cũ (update resource type / rule) |
| 422 | `VALIDATION_FAILED` | Body sai, kèm `errors[]` |
| 422 | `BOOKING_DENIED` | Rule chặn booking, kèm `reasons[]` |

```json
// 422 VALIDATION_FAILED
{
  "type": "https://errors.bookingcore.dev/validation-failed",
  "title": "Validation failed",
  "status": 422,
  "code": "VALIDATION_FAILED",
  "errors": [{ "field": "key", "message": "Must match ^[a-z][a-z0-9_]*$" }]
}
```

## Tổng quan (23 API)

| # | Method | Path | operationId | Dùng ở |
|---|---|---|---|---|
| 1 | GET | `/resource-types` | listResourceTypes | console, member |
| 2 | POST | `/resource-types` | createResourceType | console |
| 3 | GET | `/resource-types/{resourceTypeId}` | getResourceType | console, member |
| 4 | PATCH | `/resource-types/{resourceTypeId}` | updateResourceType | console |
| 5 | GET | `/sites/{siteId}` | getSite | console, member |
| 6 | GET | `/resources` | listResources | console, member |
| 7 | POST | `/resources` | createResource | console |
| 8 | GET | `/resources/{resourceId}` | getResource | (có trong contract) |
| 9 | GET | `/availability` | searchAvailability | (có trong contract, mock) |
| 10 | GET | `/bookings` | listBookings | console, member |
| 11 | POST | `/bookings` | createBooking | console, member |
| 12 | GET | `/bookings/{bookingId}` | getBooking | member |
| 13 | POST | `/bookings/{bookingId}/check-in` | checkInBooking | console, member |
| 14 | POST | `/bookings/{bookingId}/complete` | completeBooking | console |
| 15 | POST | `/bookings/{bookingId}/no-show` | markBookingNoShow | console |
| 16 | POST | `/bookings/{bookingId}/cancel` | cancelBooking | console, member |
| 17 | POST | `/bookings/{bookingId}/approve` | approveBooking | console (Approvals) |
| 18 | POST | `/bookings/{bookingId}/reject` | rejectBooking | console (Approvals) |
| 19 | GET | `/rules` | listRules | console |
| 20 | POST | `/rules` | createRule | console |
| 21 | PATCH | `/rules/{ruleId}` | updateRule | console |
| 22 | DELETE | `/rules/{ruleId}` | deleteRule | console |
| 23 | POST | `/rules/preview` | previewRule | console (rules-editor) |

> Chưa có API auth/login/me trong contract — web hiện dùng token `null` và tenant cố định
> `0193f4c1-0000-7000-8000-000000000001` (`apps/*/src/auth.ts`).

---

## 1. Resource Types

### 1.1 `GET /resource-types` – Danh sách loại tài nguyên
Query: `limit`, `cursor`. Sắp xếp mới nhất trước.

**Output 200** *(spec)*
```json
{
  "data": [
    {
      "id": "0193f4c2-7a3b-7c3e-8e2a-1f9b6c5d4e3a",
      "key": "phone_booth",
      "label": "Phone booth",
      "version": 1,
      "fields": [
        { "key": "has_phone_charger", "label": "Has phone charger", "type": "boolean", "required": true }
      ],
      "flowConfig": {
        "confirmation": "instant",
        "checkIn": { "required": true, "opensMinutesBefore": 15, "noShowAfterMinutes": 15 },
        "cancellation": { "allowedUntilMinutesBefore": 60 }
      },
      "availabilityConfig": { "slotMinutes": 15 },
      "createdAt": "2026-10-28T09:00:00+07:00",
      "updatedAt": "2026-10-28T09:00:00+07:00"
    }
  ],
  "nextCursor": null
}
```

### 1.2 `POST /resource-types` – Tạo loại tài nguyên
Bắt buộc: `key` (`^[a-z][a-z0-9_]*$`), `label`, `flowConfig`, `availabilityConfig`. `fields` mặc định `[]`.

**Input** *(spec)*
```json
{
  "key": "phone_booth",
  "label": "Phone booth",
  "fields": [
    { "key": "has_phone_charger", "label": "Has phone charger", "type": "boolean", "required": true }
  ],
  "flowConfig": {
    "confirmation": "instant",
    "checkIn": { "required": true, "opensMinutesBefore": 15, "noShowAfterMinutes": 15 },
    "cancellation": { "allowedUntilMinutesBefore": 60 }
  },
  "availabilityConfig": { "slotMinutes": 15 }
}
```
**Output 201**: object `ResourceType` (như 1 phần tử trong 1.1, `version: 1`). Lỗi: 422.

Chi tiết schema con:
- `FieldDefinition`: `key`, `label`, `type` (`text|long_text|integer|number|boolean|date|datetime|select|multi_select|email|url|phone|reference|file|multi_file`), `scope` (`resource` mặc định | `booking`), `required` (false), `help`, `options[] {value,label}` (bắt buộc với select/multi_select), `validation` (`minLength, maxLength, pattern, min, max, multipleOf, minItems, maxItems, maxSizeBytes, allowedMimeTypes[], targetResourceTypeId` – bắt buộc cho `reference`).
- `flowConfig.confirmation`: `instant | approval`.
- `flowConfig.checkIn`: `required`, `selfCheckInAllowed` (mặc định true), `opensMinutesBefore`, `noShowAfterMinutes`.
- `availabilityConfig`: `slotMinutes` (bắt buộc), `bufferMinutes` (0), `blackoutDates[] {label, startDate, endDate}`.

### 1.3 `GET /resource-types/{resourceTypeId}`
**Output 200**: `ResourceType` (giống 1.2). Lỗi: 404.

### 1.4 `PATCH /resource-types/{resourceTypeId}` – Sửa flow/availability config
Có optimistic locking qua `baseVersion`. Booking đã tạo giữ nguyên `appliedConfig` cũ.

**Input**
```json
{
  "baseVersion": 1,
  "flowConfig": {
    "confirmation": "approval",
    "checkIn": { "required": true, "selfCheckInAllowed": false, "opensMinutesBefore": 10, "noShowAfterMinutes": 20 },
    "cancellation": { "allowedUntilMinutesBefore": 120 }
  },
  "availabilityConfig": {
    "slotMinutes": 30,
    "bufferMinutes": 15,
    "blackoutDates": [{ "label": "Christmas Day", "startDate": "2026-12-25", "endDate": "2026-12-25" }]
  }
}
```
**Output 200**: `ResourceType` với `version: 2` và config mới. Lỗi: 404, 409 `STALE_VERSION`, 422.

---

## 2. Sites

### 2.1 `GET /sites/{siteId}`
Web dùng `timezoneOffset` để hiển thị/gửi mọi thời gian.

**Output 200** *(spec)*
```json
{ "id": "0193f4c2-8b4c-7d4f-9f3b-2a0c7d6e5f4b", "label": "Demo site", "timezoneOffset": "+07:00" }
```

---

## 3. Resources

### 3.1 `GET /resources`
Query: `limit`, `cursor`, `resourceTypeId?`, `siteId?`.

**Output 200**
```json
{
  "data": [
    {
      "id": "0193f4c2-9c5d-7e5a-af4c-3b1d8e7f6a5c",
      "resourceTypeId": "0193f4c2-7a3b-7c3e-8e2a-1f9b6c5d4e3a",
      "siteId": "0193f4c2-8b4c-7d4f-9f3b-2a0c7d6e5f4b",
      "label": "Phone Booth 1",
      "customFieldValues": { "has_phone_charger": true },
      "createdAt": "2026-10-28T09:05:00+07:00",
      "updatedAt": "2026-10-28T09:05:00+07:00"
    }
  ],
  "nextCursor": null
}
```

### 3.2 `POST /resources`
Bắt buộc: `resourceTypeId`, `siteId`, `label`. `customFieldValues` theo key của các field scope `resource`.

**Input** *(spec)*
```json
{
  "resourceTypeId": "0193f4c2-7a3b-7c3e-8e2a-1f9b6c5d4e3a",
  "siteId": "0193f4c2-8b4c-7d4f-9f3b-2a0c7d6e5f4b",
  "label": "Phone Booth 1",
  "customFieldValues": { "has_phone_charger": true }
}
```
**Output 201**: `Resource` (như phần tử trong 3.1). Lỗi: 404 (type/site không tồn tại), 422.

### 3.3 `GET /resources/{resourceId}`
**Output 200**: `Resource`. Lỗi: 404.

---

## 4. Availability

### 4.1 `GET /availability` – Tìm slot trống
Query bắt buộc: `siteId`, `resourceTypeId`, `date` (YYYY-MM-DD theo giờ site); tuỳ chọn `resourceId`.
Áp dụng giờ mở, `slotMinutes`, `bufferMinutes`, `blackoutDates`.

**Input**: `GET /api/v1/availability?siteId=0193f4c2-8b4c-...&resourceTypeId=0193f4c4-2d6e-...&date=2026-12-15`

**Output 200** *(spec)*
```json
{
  "siteId": "0193f4c2-8b4c-7d4f-9f3b-2a0c7d6e5f4b",
  "resourceTypeId": "0193f4c4-2d6e-7f6b-ba5d-4c2e9f8a7b6c",
  "date": "2026-12-15",
  "slotMinutes": 30,
  "slots": [
    { "start": "2026-12-15T09:00:00+07:00", "end": "2026-12-15T09:30:00+07:00", "resourceIds": ["0193f4c4-3e7f-7a7c-ab6e-5d3f0a9b8c7d"] },
    { "start": "2026-12-15T09:30:00+07:00", "end": "2026-12-15T10:00:00+07:00", "resourceIds": [] }
  ]
}
```
Nếu `date` rơi vào blackout: thêm `"blackoutLabel": "Christmas Day"` và mọi slot có `resourceIds: []`.

---

## 5. Bookings

### Trạng thái & chuyển đổi

`awaiting_payment | pending_approval | confirmed | checked_in | completed | expired | rejected | cancelled | no_show`

| Action | Từ | Sang |
|---|---|---|
| create | – | `confirmed` (instant) / `pending_approval` (approval hoặc rule `require_approval`) |
| check-in | `confirmed` (trong cửa sổ check-in) | `checked_in` |
| complete | `checked_in` | `completed` |
| no-show | `confirmed` | `no_show` |
| cancel | `awaiting_payment`, `pending_approval`, `confirmed` (theo cancellation policy) | `cancelled` |
| approve | `pending_approval` | `confirmed` |
| reject | `pending_approval` | `rejected` |

Sai trạng thái → 409 `INVALID_TRANSITION`. Mỗi lần chuyển phải thêm 1 phần tử vào `history`.

### Object `Booking` *(spec)*
```json
{
  "id": "0193f4c6-5a91-7c9e-cd80-7f5b2c1d0e9f",
  "resourceId": "0193f4c4-3e7f-7a7c-ab6e-5d3f0a9b8c7d",
  "resourceTypeId": "0193f4c4-2d6e-7f6b-ba5d-4c2e9f8a7b6c",
  "siteId": "0193f4c2-8b4c-7d4f-9f3b-2a0c7d6e5f4b",
  "memberId": "0193f4c5-4f80-7b8d-bc7f-6e4a1b0c9d8e",
  "start": "2026-12-15T09:00:00+07:00",
  "end": "2026-12-15T09:30:00+07:00",
  "status": "confirmed",
  "customFieldValues": {},
  "appliedConfig": {
    "flowConfigVersion": 1,
    "ruleSetVersion": 1,
    "confirmation": "instant",
    "checkIn": { "required": true, "opensMinutesBefore": 15, "noShowAfterMinutes": 15 },
    "cancellation": { "allowedUntilMinutesBefore": 60 }
  },
  "history": [
    {
      "toStatus": "confirmed",
      "occurredAt": "2026-12-15T07:02:11+07:00",
      "actor": { "type": "user", "id": "0193f4c5-4f80-7b8d-bc7f-6e4a1b0c9d8e" }
    }
  ],
  "createdAt": "2026-12-15T07:02:11+07:00",
  "updatedAt": "2026-12-15T07:02:11+07:00"
}
```
`history[]`: `fromStatus?` (không có ở entry đầu), `toStatus`, `occurredAt`, `actor {type: user|system, id?}`, `reason?`.

### 5.1 `GET /bookings`
Query: `limit`, `cursor`, `resourceId?`, `resourceTypeId?`, `siteId?`, `memberId?`, `status?`,
`from?`, `to?` (date-time; lọc booking **giao nhau** với khoảng). Mới nhất trước.

Ví dụ web gọi: `GET /bookings?status=pending_approval` (Approvals), `GET /bookings?siteId=...&from=2026-12-14T00:00:00+07:00&to=2026-12-21T00:00:00+07:00` (Calendar).

**Output 200**
```json
{ "data": [ /* Booking */ ], "nextCursor": "eyJpZCI6IjAxOTMuLi4ifQ" }
```

### 5.2 `POST /bookings` – Tạo booking
Header bắt buộc thêm: `Idempotency-Key: <string>` (gửi lại cùng key → trả kết quả cũ, không tạo trùng).
Bắt buộc: `resourceId`, `start`, `end`. `memberId` mặc định là user đăng nhập (admin có thể đặt hộ).
`customFieldValues` theo field scope `booking`.

**Input** *(spec)*
```json
{
  "resourceId": "0193f4c4-3e7f-7a7c-ab6e-5d3f0a9b8c7d",
  "start": "2026-12-15T09:00:00+07:00",
  "end": "2026-12-15T09:30:00+07:00",
  "customFieldValues": {}
}
```
**Output 201**: `Booking` (như trên).

**Lỗi**
- 404: resource không tồn tại
- 409 `SLOT_TAKEN`
- 422 `VALIDATION_FAILED` hoặc `BOOKING_DENIED`:
```json
{
  "type": "https://errors.bookingcore.dev/booking-denied",
  "title": "Booking not allowed",
  "status": 422,
  "code": "BOOKING_DENIED",
  "reasons": [{ "ruleId": "guests-max-2h", "message": "Guests can book at most 2 hours" }]
}
```

### 5.3 `GET /bookings/{bookingId}`
**Output 200**: `Booking` kèm `appliedConfig` + `history`. Lỗi: 404.

### 5.4 – 5.7 Các action không body
`POST /bookings/{id}/check-in`, `/complete`, `/no-show`, `/cancel`

**Input**: không có body (chỉ path `bookingId` + headers).

**Output 200**: `Booking` đã cập nhật, vd sau check-in:
```json
{
  "id": "0193f4c6-5a91-7c9e-cd80-7f5b2c1d0e9f",
  "status": "checked_in",
  "history": [
    { "toStatus": "confirmed", "occurredAt": "2026-12-15T07:02:11+07:00", "actor": { "type": "user", "id": "0193f4c5-4f80-7b8d-bc7f-6e4a1b0c9d8e" } },
    { "fromStatus": "confirmed", "toStatus": "checked_in", "occurredAt": "2026-12-15T08:50:00+07:00", "actor": { "type": "user", "id": "0193f4c5-4f80-7b8d-bc7f-6e4a1b0c9d8e" } }
  ],
  "updatedAt": "2026-12-15T08:50:00+07:00"
  /* ...các field còn lại của Booking */
}
```
Lỗi: 404, 409 `INVALID_TRANSITION`:
```json
{
  "type": "https://errors.bookingcore.dev/invalid-transition",
  "title": "Invalid transition",
  "status": 409,
  "code": "INVALID_TRANSITION",
  "detail": "Cannot check in a booking in status cancelled."
}
```
Ghi chú: `complete` và `no-show` bình thường do timer hệ thống chạy (actor `system`); API cho admin thao tác tay.

### 5.8 `POST /bookings/{bookingId}/approve`
**Input**: không body. **Output 200**: `Booking` với `status: "confirmed"`.

### 5.9 `POST /bookings/{bookingId}/reject`
**Input**
```json
{ "reason": "Room is reserved for the board meeting." }
```
**Output 200**: `Booking` với `status: "rejected"`, entry history cuối có `"reason": "Room is reserved for the board meeting."`.
Lỗi: 404, 409, 422 (thiếu/rỗng `reason`).

---

## 6. Rules

`when` là **JSONLogic** trên context cố định (`booking`, `resource`, `user`, `user.groups`, `time`, `usage`); `null` = luôn áp dụng.
`scope`: `{}` = toàn tenant, hoặc đúng **một** trong `siteId` / `resourceTypeId` / `resourceId`.
`consequence`: `deny | require_approval`. Mỗi lần create/update/delete phải tăng `ruleSetVersion` của tenant.

### 6.1 `GET /rules`
Query: `limit`, `cursor`, `siteId?`, `resourceTypeId?`, `resourceId?` (lọc đúng scope đó), `consequence?`. Sắp xếp `priority` giảm dần.

**Output 200**
```json
{
  "data": [
    {
      "id": "0193f4c8-7cb3-7eaf-8f91-9a7d4e3f2c1b",
      "label": "Guests book at most 2 hours",
      "scope": { "resourceTypeId": "0193f4c4-2d6e-7f6b-ba5d-4c2e9f8a7b6c" },
      "consequence": "deny",
      "priority": 10,
      "when": { "and": [ { "in": ["guest", { "var": "user.groups" }] }, { ">": [{ "var": "booking.durationMinutes" }, 120] } ] },
      "enabled": true,
      "version": 1,
      "createdAt": "2026-12-15T07:00:00+07:00",
      "updatedAt": "2026-12-15T07:00:00+07:00"
    }
  ],
  "nextCursor": null
}
```

### 6.2 `POST /rules`
Bắt buộc: `label`, `scope`, `consequence`, `priority` (0). `enabled` mặc định true.

**Input** *(spec)*
```json
{
  "label": "Guests book at most 2 hours",
  "scope": { "resourceTypeId": "0193f4c4-2d6e-7f6b-ba5d-4c2e9f8a7b6c" },
  "consequence": "deny",
  "priority": 10,
  "when": { "and": [ { "in": ["guest", { "var": "user.groups" }] }, { ">": [{ "var": "booking.durationMinutes" }, 120] } ] }
}
```
**Output 201**: `Rule` (như phần tử trong 6.1). Lỗi: 422.

### 6.3 `PATCH /rules/{ruleId}`
Chỉ sửa được `label`, `priority`, `when`, `enabled` (scope & consequence cố định). Bắt buộc `baseVersion`, `label`, `priority`, `enabled`.

**Input**
```json
{
  "baseVersion": 1,
  "label": "Guests book at most 3 hours",
  "priority": 20,
  "when": { "and": [ { "in": ["guest", { "var": "user.groups" }] }, { ">": [{ "var": "booking.durationMinutes" }, 180] } ] },
  "enabled": false
}
```
**Output 200**: `Rule` với `version: 2`. Lỗi: 404, 409 `STALE_VERSION`, 422.

### 6.4 `DELETE /rules/{ruleId}`
**Output 204**: không body. Lỗi: 404.

### 6.5 `POST /rules/preview` – Thử rule nháp
Phải dùng **cùng evaluator** với pipeline booking.

**Input**
```json
{
  "consequence": "deny",
  "when": { "and": [ { "in": ["guest", { "var": "user.groups" }] }, { ">": [{ "var": "booking.durationMinutes" }, 120] } ] },
  "context": {
    "userGroups": ["guest"],
    "durationMinutes": 180,
    "startsInMinutes": 1440,
    "activeBookingsForMember": 0
  }
}
```
(`context` mặc định: `userGroups: []`, `durationMinutes: 60`, `startsInMinutes: 1440`, `activeBookingsForMember: 0`.)

**Output 200**
```json
{
  "matched": true,
  "decision": "deny",
  "reasons": [{ "ruleId": "preview", "message": "Guests book at most 2 hours" }]
}
```
Không khớp → `{ "matched": false, "decision": "allow", "reasons": [] }`. `decision` ∈ `allow | deny | require_approval`.
