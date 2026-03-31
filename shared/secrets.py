"""
Shared secrets validation module for all TicketRemaster services.
Validates that critical secrets are properly configured before application startup.
"""
import os
import sys


# Critical secrets that must be set to non-default values
CRITICAL_SECRETS = [
    'JWT_SECRET',
    'QR_SECRET',
    'OUTSYSTEMS_API_KEY',
    'STRIPE_SECRET_KEY',
    'STRIPE_WEBHOOK_SECRET',
]

# Database-related secrets that must be set
DATABASE_SECRETS = [
    'USER_SERVICE_DB_PASSWORD',
    'VENUE_SERVICE_DB_PASSWORD',
    'SEAT_SERVICE_DB_PASSWORD',
    'EVENT_SERVICE_DB_PASSWORD',
    'SEAT_INVENTORY_SERVICE_DB_PASSWORD',
    'TICKET_SERVICE_DB_PASSWORD',
    'TRANSFER_SERVICE_DB_PASSWORD',
    'MARKETPLACE_SERVICE_DB_PASSWORD',
    'CREDIT_TRANSACTION_SERVICE_DB_PASSWORD',
    'TICKET_LOG_SERVICE_DB_PASSWORD',
    'NOTIFICATION_SERVICE_DB_PASSWORD',
    'OTP_WRAPPER_DB_PASSWORD',
    'STRIPE_WRAPPER_DB_PASSWORD',
]

# Known insecure default values that must not be used
INSECURE_DEFAULTS = {
    'JWT_SECRET': ['change_me', 'secret', 'jwt_secret', 'your-secret-key'],
    'QR_SECRET': ['change_me', 'secret', 'qr_secret'],
    'OUTSYSTEMS_API_KEY': ['change_me', 'your-api-key'],
    'STRIPE_SECRET_KEY': ['sk_test_change_me', 'sk_live_change_me'],
    'STRIPE_WEBHOOK_SECRET': ['whsec_change_me'],
}

# Database password insecure defaults
DB_INSECURE_DEFAULTS = ['change_me', 'password', 'postgres', 'admin', 'root']


def validate_secrets(strict: bool = True) -> list[str]:
    """
    Validate that all critical secrets are properly configured.
    
    Args:
        strict: If True, raises RuntimeError on validation failure.
                If False, returns list of issues without raising.
    
    Returns:
        List of validation issues found.
    
    Raises:
        RuntimeError: If strict=True and validation fails.
    """
    issues = []
    
    # Validate critical secrets
    for secret in CRITICAL_SECRETS:
        value = os.environ.get(secret)
        if not value:
            issues.append(f"Missing required secret: {secret}")
            continue
        
        # Check against known insecure defaults
        insecure_values = INSECURE_DEFAULTS.get(secret, ['change_me'])
        if value.lower() in [v.lower() for v in insecure_values]:
            issues.append(
                f"Secret {secret} is set to an insecure default value. "
                f"Please set a secure, unique value."
            )
        
        # Check minimum length for secrets
        if len(value) < 16:
            issues.append(
                f"Secret {secret} is too short ({len(value)} chars). "
                f"Minimum recommended length is 32 characters."
            )
    
    # Validate database passwords (only check if corresponding DB host is configured)
    for db_secret in DATABASE_SECRETS:
        value = os.environ.get(db_secret)
        if not value:
            # Only flag if the service appears to be configured
            service_prefix = db_secret.replace('_DB_PASSWORD', '').upper()
            db_host = os.environ.get(f"{service_prefix}_DB_HOST")
            if db_host:
                issues.append(f"Missing database password for {service_prefix}")
            continue
        
        if value.lower() in [v.lower() for v in DB_INSECURE_DEFAULTS]:
            issues.append(
                f"Database password for {db_secret} is set to an insecure default value. "
                f"Please set a secure, unique password."
            )
    
    # Validate Stripe keys if Stripe functionality is enabled
    if os.environ.get('STRIPE_SECRET_KEY') and not os.environ.get('STRIPE_WEBHOOK_SECRET'):
        issues.append(
            "STRIPE_SECRET_KEY is set but STRIPE_WEBHOOK_SECRET is missing. "
            "Both are required for secure Stripe integration."
        )
    
    if issues and strict:
        error_msg = "Secret validation failed:\n" + "\n".join(f"  - {issue}" for issue in issues)
        raise RuntimeError(error_msg)
    
    return issues


def validate_database_url(db_url: str | None, service_name: str) -> str:
    """
    Validate and return a database URL, ensuring it's properly configured.
    
    Args:
        db_url: The database URL to validate.
        service_name: Name of the service for error messages.
    
    Returns:
        The validated database URL.
    
    Raises:
        RuntimeError: If the database URL is missing or invalid.
    """
    if not db_url:
        raise RuntimeError(
            f"Database URL must be set for {service_name}. "
            f"Set {service_name.upper()}_DATABASE_URL environment variable."
        )
    
    # Check for common misconfigurations
    if 'change_me' in db_url:
        raise RuntimeError(
            f"Database URL for {service_name} contains 'change_me'. "
            f"Please configure proper credentials."
        )
    
    return db_url


def init_secrets(strict: bool = True) -> None:
    """
    Initialize and validate all secrets for a service.
    Should be called early in application startup.
    
    Args:
        strict: If True, raises RuntimeError on validation failure.
    """
    issues = validate_secrets(strict=False)
    
    if issues:
        if strict:
            error_msg = f"\n{'='*60}\nSecret Validation Failed\n{'='*60}\n"
            error_msg += "The following issues must be resolved before startup:\n\n"
            for issue in issues:
                error_msg += f"  ❌ {issue}\n"
            error_msg += f"\n{'='*60}\n"
            error_msg += "See .env.example for configuration guidance.\n"
            raise RuntimeError(error_msg)
        else:
            for issue in issues:
                print(f"WARNING: {issue}", file=sys.stderr)
