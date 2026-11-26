from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    # TROCAR POR PROJETO: o modelo. O prefixo `us.` é um inference profile
    # cross-region; a role do Runtime já pode invocar qualquer modelo/profile
    # da conta (o CDK concede), então só um modelo de Marketplace exige policy
    # extra em global-policy.json.
    return BedrockModel(model_id="us.anthropic.claude-haiku-5-5")
