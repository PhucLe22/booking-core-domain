from django.db import models

from core.constant import BookingStatus


class UserQuerySet(models.QuerySet):
    pass



class BookingQuerySet(models.QuerySet):
    def displayable(self):
        """Bookings that are shown on the calendar (not cancelled)."""
        return self.exclude(status__code=BookingStatus.CANCELLED)
