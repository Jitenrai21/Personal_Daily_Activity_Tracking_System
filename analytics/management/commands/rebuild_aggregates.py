from django.core.management.base import BaseCommand

from analytics.services import rebuild_last_days


class Command(BaseCommand):
    help = "Rebuild daily aggregates for the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = options["days"]
        total = rebuild_last_days(days)
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {total} daily aggregates."))
