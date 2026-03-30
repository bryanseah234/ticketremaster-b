"""
Environment verification script for TicketRemaster.
Checks all required environment variables and service connectivity.
"""
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")


def print_success(text: str):
    print(f"  {GREEN}✓{RESET} {text}")


def print_error(text: str):
    print(f"  {RED}✗{RESET} {text}")


def print_warning(text: str):
    print(f"  {YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    print(f"  {BLUE}→{RESET} {text}")


def check_env_file(env_path: str) -> Tuple[bool, List[str], List[str]]:
    """Check if .env file exists and parse its contents."""
    if not os.path.exists(env_path):
        return False, [], []

    required_vars = []
    optional_vars = []

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key = line.split('=', 1)[0].strip()
                value = line.split('=', 1)[1].strip()
                if value and value != 'change_me':
                    required_vars.append(key)
                else:
                    optional_vars.append(key)

    return True, required_vars, optional_vars


def check_required_vars(env_vars: dict, required: List[str]) -> Tuple[List[str], List[str]]:
    """Check which required variables are set."""
    missing = []
    present = []

    for var in required:
        if var in env_vars and env_vars[var] and env_vars[var] != 'change_me':
            present.append(var)
        else:
            missing.append(var)

    return present, missing


def check_service_urls(env_vars: dict) -> List[Tuple[str, str]]:
    """Check if service URLs are configured."""
    service_urls = []
    for key, value in env_vars.items():
        if key.endswith('_URL') and value and value != 'change_me':
            service_urls.append((key, value))
    return service_urls


def check_database_urls(env_vars: dict) -> List[Tuple[str, str]]:
    """Check if database URLs are configured."""
    db_urls = []
    for key, value in env_vars.items():
        if 'DATABASE_URL' in key and value and value != 'change_me':
            db_urls.append((key, value))
    return db_urls


def main():
    """Main verification function."""
    print_header("TicketRemaster Environment Verification")

    # Determine the base directory
    script_dir = Path(__file__).parent
    backend_dir = script_dir
    frontend_dir = script_dir.parent / 'ticketremaster-f' if (script_dir.parent / 'ticketremaster-f').exists() else None

    all_checks_passed = True

    # ── Backend Environment Check ──────────────────────────────────────
    print(f"{BOLD}Backend Environment ({backend_dir}){RESET}")
    print("-" * 40)

    backend_env_path = backend_dir / '.env'
    env_exists, required_vars, optional_vars = check_env_file(str(backend_env_path))

    if not env_exists:
        print_error(f".env file not found at {backend_env_path}")
        all_checks_passed = False
    else:
        print_success(f".env file found at {backend_env_path}")

        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv(backend_env_path)
        env_vars = dict(os.environ)

        # Check required variables
        backend_required = [
            'JWT_SECRET',
            'SENTRY_DSN',
            'RABBITMQ_HOST',
            'REDIS_URL',
        ]

        present, missing = check_required_vars(env_vars, backend_required)

        if missing:
            print_error(f"Missing required variables: {', '.join(missing)}")
            all_checks_passed = False
        else:
            print_success("All required variables are set")

        # Check database URLs
        db_urls = check_database_urls(env_vars)
        print_info(f"Database URLs configured: {len(db_urls)}")

        # Check service URLs
        service_urls = check_service_urls(env_vars)
        print_info(f"Service URLs configured: {len(service_urls)}")

        # Check observability
        if 'SENTRY_DSN' in env_vars and env_vars['SENTRY_DSN'] != 'change_me':
            print_success("Sentry error tracking configured")
        else:
            print_warning("Sentry not configured")

    # ── Frontend Environment Check ─────────────────────────────────────
    if frontend_dir:
        print(f"\n{BOLD}Frontend Environment ({frontend_dir}){RESET}")
        print("-" * 40)

        frontend_env_path = frontend_dir / '.env'
        env_exists, required_vars, optional_vars = check_env_file(str(frontend_env_path))

        if not env_exists:
            print_error(f".env file not found at {frontend_env_path}")
            all_checks_passed = False
        else:
            print_success(f".env file found at {frontend_env_path}")

            # Load frontend env
            frontend_required = [
                'VITE_API_BASE_URL',
                'VITE_SENTRY_DSN',
                'VITE_POSTHOG_API_KEY',
            ]

            frontend_env_vars = {}
            with open(frontend_env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        frontend_env_vars[key.strip()] = value.strip()

            present, missing = check_required_vars(frontend_env_vars, frontend_required)

            if missing:
                print_error(f"Missing required variables: {', '.join(missing)}")
                all_checks_passed = False
            else:
                print_success("All required variables are set")

            # Check observability
            if 'VITE_SENTRY_DSN' in frontend_env_vars and frontend_env_vars['VITE_SENTRY_DSN'] != 'change_me':
                print_success("Sentry error tracking configured")
            else:
                print_warning("Sentry not configured")

            if 'VITE_POSTHOG_API_KEY' in frontend_env_vars and frontend_env_vars['VITE_POSTHOG_API_KEY'] != 'change_me':
                print_success("PostHog analytics configured")
            else:
                print_warning("PostHog not configured")

    # ── Summary ────────────────────────────────────────────────────────
    print_header("Summary")

    if all_checks_passed:
        print(f"{GREEN}{BOLD}✓ All checks passed!{RESET}")
        print("\nYou can now start the services:")
        print("  Backend:  cd ticketremaster-b && docker-compose up -d")
        print("  Frontend: cd ticketremaster-f && npm install && npm run dev")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}✗ Some checks failed.{RESET}")
        print("\nPlease fix the issues above and try again.")
        sys.exit(1)


if __name__ == '__main__':
    main()
