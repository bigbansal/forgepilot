from forgepilot_backend.models import RiskLevel


class PolicyEngine:
    @staticmethod
    def classify_risk(prompt: str) -> RiskLevel:
        text = prompt.lower()
        if any(word in text for word in ["delete all", "drop table", "secret", "production", "destroy"]):
            return RiskLevel.CRITICAL
        if any(word in text for word in ["install", "migration", "schema", "docker", "deploy"]):
            return RiskLevel.HIGH
        if any(word in text for word in ["refactor", "rename", "update", "modify"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def requires_approval(risk: RiskLevel) -> bool:
        return risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
