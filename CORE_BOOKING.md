# Core Booking

The booking system is split into 6 services. Each service owns its own tables.

## Services

1. **User**: users and login
   - Tables: `users`
   - Port: 9001
2. **Resource**: what can be booked
   - Tables: `resource_types`, `resources`, `resource_groups`
   - Port: 9014
3. **Booking**: bookings and their status
   - Tables: `bookings`, `booking_events`
   - Port: planned
4. **Scheduling**: when a resource is free
   - Tables: `schedules`, `time_slots`, `schedule_locks`, `availability`
   - Port: planned
5. **Booking Rule**: who can book, and the limits
   - Tables: `booking_policies`, `booking_eligibilities`
   - Port: planned
6. **Notification**: sends messages to users
   - Tables: `notifications`
   - Port: 9012

**Rule:** a service only writes to its own tables. To use another service's
data, call its API.

> `apschedule` (port 9013) only runs background jobs. It is not the Scheduling
> service.

## Resource

- A **resource type** is a kind of thing, e.g. `MEETING_ROOM`.
- A **resource** is one real thing of that type, e.g. `MR-A-01`.
- A **resource group** groups resources, e.g. by floor (planned).

A resource type defines which fields its resources must have:

```json
{
  "fields": {
    "capacity": { "type": "integer", "required": true },
    "location": { "type": "string", "required": true }
  }
}
```

Field types: `string`, `integer`, `number`, `boolean`, `object`, `array`.

Resource status: `1` Active, `2` Inactive, `3` Maintenance. Only active
resources can be booked.

API docs: http://localhost:9014/api/v1/docs/

## Booking status

| Status | Meaning |
|---|---|
| `2` Pending | Waiting for approval |
| `1` Confirmed | The slot is reserved |
| `3` Cancelled | Cancelled, the slot is free again |
| `4` Completed | The booking time has passed |

```
Pending ──► Confirmed ──► Completed
   │            │
   └────────────┴──► Cancelled
```

## How a booking is created

1. **Resource** checks the resource exists and is active.
2. **Booking Rule** checks the user is allowed to book it.
3. **Scheduling** checks the time is free and locks it.
4. **Booking** saves the booking.
5. **Notification** tells the user.

If any step fails, nothing is saved and the API returns an error.

## API response

Every API returns the same format.

Success:

```json
{ "status": true, "data": { }, "message": "Resource created successfully!" }
```

Error:

```json
{
  "status": false,
  "data": { "code": ["Resource type code 'MEETING_ROOM' already exists!"] },
  "message": "Resource type code 'MEETING_ROOM' already exists!"
}
```

List APIs also return `pagination` and accept `page` and `page_size`.

## Add a new service

1. Copy `services/resource` to `services/<name>`.
2. Add it to `docker-compose.yml` with a new port.
3. Add its models to `core/models.py` and run
   `python manage.py makemigrations core --name <name>`.
