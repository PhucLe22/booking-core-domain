from django.db import models

from core.constant import BookingStatus


class UserQuerySet(models.QuerySet):
    pass



class BookingQuerySet(models.QuerySet):
    def displayable(self):
        """Bookings shown on the calendar: not cancelled, rejected or expired."""
        return self.exclude(
            status__code__in=[
                BookingStatus.CANCELLED,
                BookingStatus.REJECTED,
                BookingStatus.EXPIRED,
            ]
        )
