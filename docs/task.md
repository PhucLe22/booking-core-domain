# Booking Core BE – Danh sách task đưa BE về khớp Web spec

Tài liệu tham chiếu:
- API hiện có: `docs/current_apis_911.md`
- API web cần: `docs/web_api_spec.md`

Cách dùng: mỗi phiên làm việc chỉ làm **một task**, ví dụ "Làm task 2.13 trong docs/task.md".
Làm theo thứ tự phase; trong một phase, làm theo thứ tự số. Xong task thì đánh dấu `[x]`.

## Quyết định đã chốt

- [x] **Giữ snake_case** cho query, body và response (không dùng camelCase như spec web). Tên field theo spec được
      viết lại dạng snake_case, vd `customFieldValues` → `custom_field_values`, `resourceTypeId` → `resource_type_id`.
- [x] **Giữ cấu hình URL hiện tại**: có `/` ở cuối, path snake_case (`/resource_types/`), không sửa `urls.py` và
      `nginx/default.conf`. Action mới cũng theo kiểu này (vd `/bookings/{id}/check_in/`, `/bookings/{id}/no_show/`).
- [x] **Giữ envelope** `{ status, data, message }` qua `response_success` có sẵn trong `core/utils.py` cho response
      thành công.
- [x] **Giữ phân trang `CustomPaginator`** (`page`, `page_size`) có sẵn trong `core/paginators.py`, không làm cursor.
- [x] **Mọi response (thành công và lỗi) cùng format** `{status, data, message}`:
  - thành công: `response_success` → `{"status": true, "data": ..., "message": "..."}`
  - lỗi: `{"status": false, "data": {<field>: [<lỗi>]} hoặc {}, "message": "<lỗi đầu tiên>"}` – giống
    `response_errors`, không có `code`; web phân biệt loại lỗi bằng HTTP status:
    401, 403, 404, 405, 409 (trùng slot, sai trạng thái, sai version), 422 (dữ liệu sai).
  - chỉ áp cho resource và booking (qua `WebApiMixin`); các service khác giữ handler cũ `core/exceptions.py`.
- [x] **Dùng lại file có sẵn trong `core/`, không tạo file trùng chức năng trong service.** Sửa thẳng:
  - `core/models.py` + `core/migrations/` – field/model
  - `core/serializers/*.py` – serializer theo spec (sửa class có sẵn, vd `ResourceTypeSerializer`); trước khi sửa
    kiểm tra class đó có service nào khác dùng không
  - `core/filters.py` – filter theo spec
  - `core/utils.py` – helper chung: `response_success`, `WebApiMixin` + `web_api_exception_handler` (format lỗi),
    `success_response` / `error_responses` (Swagger)
  - `core/configuration_rules.py` – kiểu custom field
  - Service chỉ giữ `views.py`, `urls.py`, `documents.py`. Không sửa `app/settings.py`.
- [x] Lỗi nghiệp vụ trong serializer dùng `serializers.ValidationError(..., code="slot_taken")` của DRF;
      `web_api_exception_handler` trong `core/utils.py` đọc `code` để chọn HTTP 409/422 (`ERROR_CODE_STATUS`).
- [x] **Giữ** `PUT /bookings/{id}/`, `POST /bookings/guest/`, `POST /bookings/staff/`. Khi đổi trạng thái phải đi qua
      `Booking.change_status()` (task 2.10) để có `history`.

### Điểm lệch so với spec web (phía web cần cập nhật `contracts/openapi.yaml`)

| Spec web | BE |
|---|---|
| camelCase (`customFieldValues`) | snake_case (`custom_field_values`) |
| `/resource-types`, `/bookings/{id}/check-in`, không `/` cuối | `/resource_types/`, `/bookings/{id}/check_in/` |
| Trả object trực tiếp | Envelope `{ status, data, message }` |
| `limit` / `cursor` → `{ data, nextCursor }` | `page` / `page_size` → `{ status, data, message, pagination }` |

## Còn cần chốt

- [ ] "Giờ mở cửa" của Availability lưu ở đâu (spec nhắc nhưng chưa có schema)? → trước task 3.3.
- [ ] Timer (3.5): logic chuyển trạng thái nằm trong `core/` (task 2.10) nên chạy được từ container `apschedule`
      (có mount `core/`) → đề xuất command trong `core/management/commands/` + job trong
      `services/apschedule/apis/schedulers.py`. Chốt trước task 3.5.

## Kiểm tra

Máy local chưa cài Django trong `.venv` → chạy kiểm tra trong container
(`docker compose up -d resource_service booking_service`, gọi qua nginx hoặc port 9014/9015).

---

## Phase 0 – Chuẩn bị

- [ ] **0.1** Tạo `CLAUDE.md`: cấu trúc `core/` + `services/*/apis`, cách chạy, quy ước response/lỗi/quyền,
      nguyên tắc "code mới trong service, core chỉ tái sử dụng", trỏ tới `docs/`.
  - `CLAUDE.md` (mới)

## Phase 1 – Format lỗi cho resource và booking

> Mỗi task sửa **cả hai** service. View nào thêm `WebApiMixin` (đặt trước `viewsets.ViewSet`) thì trả lỗi theo format chung.
> Các task 1.1, 1.2, 1.3, 1.5, 1.6 cũ (camelCase, bỏ envelope, cursor, đổi URL) đã bỏ theo "Quyết định đã chốt".

- [x] **1.4** Format lỗi `{status: false, data, message}` với HTTP status đúng loại lỗi
      (ban đầu làm problem+json, sau đổi sang format chung – xem "Quyết định đã chốt"):
  - `WebApiMixin` + `web_api_exception_handler` trong `core/utils.py`, bật bằng `WebApiMixin.get_exception_handler()`
    (không đụng `core/exceptions.py`)
  - 401 chưa đăng nhập / token hỏng, 403, 404 (kể cả UUID sai trong URL), 405, 422 lỗi dữ liệu (kể cả JSON hỏng);
    lỗi có code `slot_taken` / `invalid_transition` / `stale_version` → 409, `booking_denied` → 422
  - cho `ResourceViewSet`, `ResourceTypeViewSet`, `BookingViewSet`, `CalendarViewSet` kế thừa mixin;
    view raise `ValidationError` thay cho `response_errors`
  - Files: `core/utils.py`, `services/{resource,booking}/apis/views.py`
  - Ghi chú: serializer trong core chưa gắn code nghiệp vụ, nên trùng slot / sai trạng thái hiện vẫn trả
    422; thành 409 sau task 2.10 (`invalid_transition`) và 2.11 (`slot_taken`).
- [x] **1.7** Cập nhật mô tả Swagger: envelope `response_success` + `pagination` và lỗi `{status, data, message}`
      (dùng `OpenApiExample`, `OpenApiResponse`).
  - helper trong `core/utils.py`: `success_response(Serializer, "object" | "list" | "page")`,
    `error_responses(*AUTH_ERRORS, "NOT_FOUND", ...)` (ví dụ lỗi trong `ERROR_EXAMPLES`)
  - `services/{resource,booking}/apis/documents.py`
  - Ghi chú: task sau khi thêm lỗi mới (`SLOT_TAKEN`, `INVALID_TRANSITION`, `STALE_VERSION`, `BOOKING_DENIED`)
    phải thêm loại lỗi đó vào `error_responses(...)` của API tương ứng.

## Phase 2 – Sửa resource và booking theo spec

### Resource type

- [x] **2.1** Thêm `version`, `created_at`, `updated_at` vào model.
  - `core/models.py` (`ResourceType`), `core/migrations/0006_resource_type_version_timestamps.py`
  - Ghi chú: `version` mặc định 1, chưa tự tăng – việc tăng version khi update làm ở task 2.5.
- [x] **2.2** Serializer theo spec: `key` ← `code`, `label` ← `name`, `fields` dạng mảng (DB vẫn lưu object trong
      `configuration["fields"]`, thứ tự trong `configuration["field_order"]` vì jsonb không giữ thứ tự key),
      `status_enum_type`. `key` và key của field phải khớp `^[a-z][a-z0-9_]*$` (key cũ như `MEETING_ROOM`
      gửi lại y nguyên vẫn được).
  - `core/serializers/resource_serializers.py` (`ResourceTypeSerializer`, `EditResourceTypeSerializer`)
  - `services/resource/apis/{views,documents}.py`
- [x] **2.3** Bổ sung kiểu field của spec (`text`, `long_text`, `select`, `multi_select`, `phone`, `reference`,
      `file`, `multi_file`; thuộc tính `scope`, `options`, `validation`) vào bảng `RULES` có sẵn.
  - `core/configuration_rules.py`
  - Rule mới: `options`, `multiple_of`, `target_resource_type_id`, `max_size_bytes`, `allowed_mime_types`.
    Rule có thể đặt phẳng trong field (format cũ) hoặc trong `validation` (format spec), không được đặt cả hai.
  - `select`/`multi_select` cần `options` (hoặc `enum_type`), `reference` cần `target_resource_type_id`.
  - `check_configuration(..., scope="resource")` chỉ kiểm field của scope đó; field `scope: booking` dùng ở task 2.11.
  - Kiểu cũ (`string`, `array`, `object`, `time`…) vẫn giữ cho dữ liệu đang có.
- [x] **2.4** Thêm `GET /resource_types/{id}/` + seed quyền `RESOURCE_TYPE.RETRIEVE` (STAFF, CUSTOMER).
  - `services/resource/apis/views.py`, `services/resource/apis/documents.py`
  - `core/migrations/0007_seed_resource_type_retrieve_permission.py`
  - Ghi chú: `ResourceTypeViewSet` hiện không dùng `ApiPermission` nên quyền này chưa có tác dụng.
- [x] **2.5** Đổi `update` → `partial_update` (`PATCH`) với `base_version`; sai version → lỗi code `stale_version` (409).
  - `PUT /resource_types/{id}/` bỏ (405). PATCH chỉ sửa field được gửi, `base_version` bắt buộc, lưu xong `version` + 1;
    view khóa dòng (`select_for_update`) để 2 request cùng version không cùng qua.
  - `services/resource/apis/views.py`, `core/serializers/resource_serializers.py`

### Resource

- [x] **2.6** Serializer theo spec (sửa `EditResourceSerializer`/`ResourceSerializer`): `label` ← `name`,
      `custom_field_values` ← `configuration`, `resource_type_id`; `code` không bắt buộc.
  - `core/serializers/resource_serializers.py`
  - Response: `id, resource_type_id, resource_type_key, code, label, status, custom_field_values, created_at, updated_at`.
  - Không gửi `code` khi tạo → sinh từ label (`Phone Booth 1` → `PHONE_BOOTH_1`, trùng thì `_2`, `_3`…);
    khi cập nhật không gửi thì giữ code cũ.
- [x] **2.7** Thêm `GET /resources/{id}/` + quyền `RESOURCE.RETRIEVE`; filter theo spec.
  - `services/resource/apis/{views,documents}.py`, `core/filters.py` (`ResourceFilter`)
  - `core/migrations/0008_seed_resource_retrieve_permission.py` (STAFF, CUSTOMER)
  - Filter: `resource_type_id`, `resource_type_key`, `status`, `code`, `label`, `label__icontains`
    (thay `resource_type`, `resource_type_code`, `name`).
  - Ghi chú: `ResourceViewSet` hiện không dùng `ApiPermission` nên quyền này chưa có tác dụng.

### Booking

- [x] **2.8** Thêm `updated_at`, `applied_config` vào `Booking`; tạo model `BookingHistory`
      (`from_status`, `to_status`, `occurred_at`, `actor_type`, `actor_id`, `reason`).
  - `core/models.py` (`Booking`, `BookingHistory` – bảng `booking_histories`, `booking.history`),
    `core/constant.py` (`BookingActorType`: `user` / `system`)
  - `core/migrations/0009_booking_history_applied_config.py`: booking có sẵn được điền `updated_at = created_at`
    và 1 dòng history ban đầu (trạng thái hiện tại, actor là user đặt, booking guest thì `system`).
  - Chưa ghi history khi tạo/đổi trạng thái booking – làm ở 2.10 (`Booking.change_status`) và 2.11.
- [x] **2.9** Mở rộng lên 9 trạng thái: migration seed thêm vào enum `BOOKING_STATUS`, chuyển dữ liệu
      `PENDING` → `PENDING_APPROVAL`.
  - `core/migrations/0010_seed_booking_statuses.py`: đổi code dòng `PENDING` thành `PENDING_APPROVAL` (giữ id nên
    booking và history vẫn trỏ đúng), thêm `AWAITING_PAYMENT`, `CHECKED_IN`, `EXPIRED`, `REJECTED`, `NO_SHOW`
    (value 5–9, thứ tự theo spec). Rollback xóa giá trị mới chưa dùng, đổi lại `PENDING`.
  - `core/constant.py` (`BookingStatus` đủ 9 code; `BOOKING_TRANSITIONS` chỉ đổi tên `PENDING` – bảng đầy đủ ở 2.10)
  - `core/serializers/booking_serializers.py`: giữ slot khi `AWAITING_PAYMENT`, `PENDING_APPROVAL`, `CONFIRMED`,
    `CHECKED_IN`; booking mới chỉ được `PENDING_APPROVAL` hoặc `CONFIRMED`.
  - `core/querysets.py`: calendar ẩn `CANCELLED`, `REJECTED`, `EXPIRED`.
  - Ghi chú: client gửi `status: "pending"` giờ nhận 422 – phải gửi `pending_approval`.
- [x] **2.10** Logic chuyển trạng thái theo spec, dùng chung cho API và timer.
  - `core/constant.py`: `BOOKING_TRANSITIONS` đủ 9 trạng thái (5 trạng thái kết thúc = danh sách rỗng).
    `CONFIRMED → COMPLETED` tạm giữ cho resource type không check-in, tách theo `flow_config` ở 3.2.
  - `core/models.py` (`Booking`): `transition_error(current, target)`, `change_status(to_status, actor=None,
    reason=None)` (đổi trạng thái + ghi `BookingHistory`; sai → lỗi code `invalid_transition` = 409),
    `add_history(...)`. Không có actor = `system` (timer).
  - `core/serializers/booking_serializers.py`: kiểm tra bằng `Booking.transition_error`; tạo booking ghi history
    đầu tiên; `PUT` đổi status đi qua `change_status`. Booking ở trạng thái kết thúc không sửa được (409).
  - `services/booking/apis/views.py`: `serializer.save(actor=request.user)` (guest: actor `system`).
- [ ] **2.11** Serializer theo spec (sửa `EditBookingSerializer`, giữ kiểm tra giờ/trùng slot; chuyển
      `validate_status_change` sang `BOOKING_TRANSITIONS` mới): `resource_id`, `start`/`end`, `member_id`, `resource_type_id`,
      `custom_field_values`, `status` viết thường, `history`, `applied_config`; trùng giờ → code `slot_taken` (409).
  - `core/serializers/booking_serializers.py`
- [ ] **2.12** Filter theo spec (sửa `BookingFilter`): `from`/`to`, `member_id`, `resource_type_id`, `resource_id`,
      `status`; mới nhất trước.
  - `core/filters.py`
- [ ] **2.13** Thêm action `check_in`, `complete`, `no_show`, `cancel`, `approve`, `reject` (`reject` có `reason`),
      path dạng `/bookings/{id}/<action>/`, gọi `Booking.change_status()` (`PUT` đã đi qua hàm này từ 2.10).
  - `services/booking/apis/{views,documents}.py`
- [ ] **2.14** Đồng bộ các API giữ lại với spec (sửa `GuestBookingSerializer`/`StaffBookingSerializer`):
      `guest` (`guest_name`, `guest_email`, `guest_phone`), `staff` (`member_id` thay `user`), trả object `Booking` như spec.
  - `core/serializers/booking_serializers.py`
- [ ] **2.15** Header `Idempotency-Key` cho `POST /bookings/` (Django cache trên Redis có sẵn).
  - `services/booking/apis/views.py`

## Phase 3 – Module mới

- [ ] **3.1** Site: model (`label`, `timezone_offset`) + FK `Resource.site`; API `GET /sites/{id}/`;
      filter `site_id` cho resource và booking.
  - `core/models.py`, migration mới
  - `core/serializers/resource_serializers.py` (`SiteSerializer`), `core/filters.py`
  - `services/resource/apis/{views,urls,documents}.py`
  - `nginx/default.conf`
- [ ] **3.2** `flow_config` / `availability_config`: validate khi lưu resource type; chụp `applied_config` khi tạo
      booking; áp dụng cửa sổ check-in và hạn hủy.
  - `core/serializers/resource_serializers.py`
  - `core/models.py` (`Booking.change_status`)
- [ ] **3.3** Availability: `GET /availability/` (slot, buffer, ngày blackout).
  - logic tính slot: chưa có file phù hợp trong `core/` → chốt vị trí khi làm task (vd `core/utils.py` nếu ngắn)
  - `services/booking/apis/{views,urls,documents}.py`
  - `nginx/default.conf`
- [ ] **3.4** Rules: model `Rule` (dùng lại hoặc thay `BookingPolicy` có sẵn) + `rule_set_version`; bộ đánh giá
      JSONLogic; CRUD + `preview`; gọi khi tạo booking (`deny` → lỗi code `booking_denied` (422),
      `require_approval` → `pending_approval`).
  - `core/models.py`, migration mới
  - bộ đánh giá rule: chưa có file phù hợp trong `core/` → chốt vị trí khi làm task; thêm thư viện JSONLogic
    vào pyproject của booking + gốc
  - `core/serializers/` (serializer của Rule), `services/booking/apis/{views,urls,documents}.py`
  - `nginx/default.conf`
- [ ] **3.5** Timer chạy mỗi phút: `no_show`, `complete`, `expired` (actor `system`) – vị trí chạy xem mục "Còn cần chốt".
  - `core/management/commands/booking_timers.py` (mới, cạnh `example_cron_job.py` có sẵn)
  - `services/apschedule/apis/schedulers.py`

- [ ] **3.6** Thời gian trả về có múi giờ theo spec (`2026-12-15T09:00:00+07:00`). Hiện `USE_TZ = False` nên API trả
      giờ không có offset (`2026-11-10T09:21:25.969270`).
  - Hướng nhỏ: serializer của resource và booking format datetime kèm offset của site (sau 3.1) / `Asia/Ho_Chi_Minh`,
    không đổi DB.
  - Hướng đầy đủ: bật `USE_TZ = True` trong `app/settings.py` (ảnh hưởng mọi service), chuyển dữ liệu datetime đang lưu
    dạng naive, kiểm tra lại các filter `from`/`to`, calendar.
  - Chốt hướng trước khi làm; nên làm cùng/sau 3.1 (Site có `timezone_offset`).

## Phase 4 – Làm sau (cần quyết định trước)

- [ ] **4.1** Multi-tenant (`X-Tenant-Id`): middleware + cột `tenant` trên mọi bảng (thay đổi lớn nhất).
- [ ] **4.2** UUIDv7: thay `uuid.uuid4` trong `core/models.py`.
- [ ] **4.3** Cập nhật `docs/current_apis_911.md` sau mỗi phase.
- [ ] **4.4** Áp format lỗi chung cho auth, user, storage, master-data, notification: thêm `WebApiMixin`
      (`core/utils.py`) vào view, sửa client socket nếu nó đọc lỗi
      (`services/nodejs-socket/src/apis/{authApi,userApi,notificationApi}.js`).
