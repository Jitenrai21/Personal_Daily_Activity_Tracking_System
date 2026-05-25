from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from analytics.reflection import ensure_daily_reflection
from analytics.scoring import upsert_daily_score
from analytics.services import get_user_timezone, update_daily
from planner.models import ScheduleBlock
from tracking.models import Session


def _local_date_from_dt(user, timestamp):
    tz = get_user_timezone(user)
    return timestamp.astimezone(tz).date()


def _recompute_for_session(session):
    user = session.user
    dates = set()
    if session.start:
        dates.add(_local_date_from_dt(user, session.start))
    if session.end:
        dates.add(_local_date_from_dt(user, session.end))
    if session.local_date:
        dates.add(session.local_date)

    for local_date in dates:
        score = upsert_daily_score(user, local_date)
        ensure_daily_reflection(score)


def _recompute_for_block(block):
    user = block.user
    local_date = block.date
    update_daily(user, local_date)
    score = upsert_daily_score(user, local_date)
    ensure_daily_reflection(score)


@receiver(post_save, sender=Session)
def session_saved_recompute(sender, instance, **kwargs):
    _recompute_for_session(instance)


@receiver(post_delete, sender=Session)
def session_deleted_recompute(sender, instance, **kwargs):
    _recompute_for_session(instance)


@receiver(post_save, sender=ScheduleBlock)
def schedule_block_saved(sender, instance, **kwargs):
    _recompute_for_block(instance)


@receiver(post_delete, sender=ScheduleBlock)
def schedule_block_deleted(sender, instance, **kwargs):
    _recompute_for_block(instance)
