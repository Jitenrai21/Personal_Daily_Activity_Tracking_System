from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from analytics.reflection import ensure_daily_reflection
from analytics.scoring import rebuild_scores


class Command(BaseCommand):
    help = "Rebuild daily scores for the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--username", type=str, default="")

    def handle(self, *args, **options):
        days = options["days"]
        username = options["username"]

        users = get_user_model().objects.all()
        if username:
            users = users.filter(username=username)

        total = 0
        for user in users:
            scores = rebuild_scores(user, days)
            for score in scores:
                ensure_daily_reflection(score)
            total += len(scores)

        self.stdout.write(self.style.SUCCESS(f"Rebuilt {total} scores."))
