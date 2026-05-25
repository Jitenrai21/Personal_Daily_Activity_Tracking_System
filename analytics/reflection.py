from analytics.models import DailyReflection


DEFAULT_PROMPTS = {
    "low_recovery": "What helped or hurt your recovery today, and what is one small adjustment for tonight?",
    "low_balance": "Which area got too little attention today, and how will you rebalance tomorrow?",
    "low_discipline": "What blocked your planned focus today, and what is one concrete fix for tomorrow?",
    "strong_day": "What worked especially well today, and how can you repeat it tomorrow?",
}


def choose_prompt(score):
    if score.recovery_score < 45:
        return DEFAULT_PROMPTS["low_recovery"]
    if score.balance_score < 45:
        return DEFAULT_PROMPTS["low_balance"]
    if score.discipline_score < 50:
        return DEFAULT_PROMPTS["low_discipline"]
    return DEFAULT_PROMPTS["strong_day"]


def ensure_daily_reflection(score):
    reflection, created = DailyReflection.objects.get_or_create(
        user=score.user,
        local_date=score.local_date,
        defaults={"prompt_text": choose_prompt(score)},
    )
    if not created and not reflection.answer_text:
        reflection.prompt_text = choose_prompt(score)
        reflection.save(update_fields=["prompt_text", "updated_at"])
    return reflection
