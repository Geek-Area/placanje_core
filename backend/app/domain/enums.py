from enum import StrEnum


class FormType(StrEnum):
    REGULAR = "regular"
    IPS = "ips"
    SUBSCRIPTION = "subscription"


class TransactionStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SCHEDULED = "scheduled"


class AccountType(StrEnum):
    ORGANIZATION = "organization"
    POS = "pos"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class MembershipScope(StrEnum):
    ACCOUNT_ONLY = "account_only"
    ACCOUNT_AND_DESCENDANTS = "account_and_descendants"


class SubscriptionCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
