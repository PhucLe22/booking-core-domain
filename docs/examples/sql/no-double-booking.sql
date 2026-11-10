-- The database refuses overlapping active bookings on the same resource.
-- "during" is a tstzrange. The API turns the violation into SLOT_TAKEN.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings ADD CONSTRAINT no_overlap
  EXCLUDE USING gist (resource_id WITH =, during WITH &&)
  WHERE (status IN ('awaiting_payment', 'pending_approval', 'confirmed', 'checked_in'));
