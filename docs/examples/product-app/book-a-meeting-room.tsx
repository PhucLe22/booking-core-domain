// A product screen: core hooks and components, product wording and layout.
import { useAvailability, useCreateBooking } from "@booking-core/api-client";
import { AvailabilityPicker } from "@booking-core/booking-ui";
import { MemberLayout } from "../layouts/member-layout";
import { RoomCard } from "../components/room-card";

export function BookAMeetingRoom({ siteId }: { siteId: string }) {
  const availability = useAvailability({ siteId, resourceType: "meeting_room" });
  const createBooking = useCreateBooking();

  return (
    <MemberLayout title="Book a meeting room">
      <AvailabilityPicker
        slots={availability.data}
        onSelect={(slot) =>
          createBooking.mutate({ resourceId: slot.resourceId, start: slot.start, end: slot.end })
        }
        renderResource={(room) => <RoomCard room={room} />}
      />
    </MemberLayout>
  );
}
