import pytest


class TestEstimateTokenCost:
    def test_known_model(self):
        from app.services.credits import estimate_token_cost
        # gpt-4o-mini: 1 credit per 1K tokens
        assert estimate_token_cost("gpt-4o-mini", 5000) == 5

    def test_unknown_model_uses_default_rate(self):
        from app.services.credits import estimate_token_cost
        # Default: 2 credits per 1K tokens
        assert estimate_token_cost("unknown-model", 3000) == 6

    def test_minimum_cost_is_one(self):
        from app.services.credits import estimate_token_cost
        assert estimate_token_cost("gpt-4o-mini", 1) == 1

    def test_byok_halves_cost(self):
        from app.services.credits import estimate_token_cost
        normal = estimate_token_cost("gpt-4o", 10000)
        byok = estimate_token_cost("gpt-4o", 10000, is_byok=True)
        assert byok == max(1, normal // 2)

    def test_byok_minimum_is_one(self):
        from app.services.credits import estimate_token_cost
        assert estimate_token_cost("gpt-4o-mini", 1, is_byok=True) == 1

    def test_expensive_model(self):
        from app.services.credits import estimate_token_cost
        # claude-opus-4-6: 15 credits per 1K tokens
        cost = estimate_token_cost("claude-opus-4-6", 2000)
        assert cost == 30
