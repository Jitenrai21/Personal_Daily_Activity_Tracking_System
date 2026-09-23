from planner.models import ScheduleBlock, WeeklyRoutine
from users.models import UserProfile


def generate_blocks_for_date(user, date):
    routines = WeeklyRoutine.objects.filter(
        user=user, weekday=date.weekday(), is_active=True
    ).select_related("activity")

    profile = UserProfile.objects.filter(user=user).first()

    created = []
    for routine in routines:
        if profile and profile.wake_time and routine.start_time < profile.wake_time:
            continue
        if profile and profile.sleep_time and routine.end_time > profile.sleep_time:
            continue

        overlaps = ScheduleBlock.objects.filter(
            user=user,
            date=date,
            start_time__lt=routine.end_time,
            end_time__gt=routine.start_time,
        ).exists()

        if overlaps:
            continue

        block = ScheduleBlock.objects.create(
            user=user,
            activity=routine.activity,
            date=date,
            start_time=routine.start_time,
            end_time=routine.end_time,
            timezone=routine.timezone,
            source=ScheduleBlock.SOURCE_ROUTINE,
            is_recurring=True,
            notes=routine.notes,
        )
        created.append(block)

    return created
