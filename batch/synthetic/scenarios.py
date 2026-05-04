from enum import Enum

class ScenarioType(str, Enum):
    SHARP_CREDENTIAL_MISUSE = "sharp_credential_misuse"
    SLOW_ROLL_BEHAVIORAL_DRIFT = "slow_roll_behavioral_drift"
    COORDINATED_MULTI_ENTITY_COMPROMISE = "coordinated_multi_entity_compromise"
    SERVICE_ACCOUNT_ABUSE = "service_account_abuse"
