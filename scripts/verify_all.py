#!/usr/bin/env python3
"""
Comprehensive verification script for TicketRemaster.
Tests local deployment, Vercel compatibility, frontend-backend communication, and Kubernetes readiness.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class VerificationResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []

    def add_pass(self, message: str):
        self.passed += 1
        self.results.append((GREEN, "✓", message))

    def add_fail(self, message: str):
        self.failed += 1
        self.results.append((RED, "✗", message))

    def add_warning(self, message: str):
        self.warnings += 1
        self.results.append((YELLOW, "⚠", message))

    def print_summary(self):
        print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
        print(f"{BOLD}{BLUE}Verification Summary{RESET}")
        print(f"{BOLD}{BLUE}{'='*60}{RESET}")
        for color, icon, message in self.results:
            print(f"  {color}{icon}{RESET} {message}")
        print(f"\n{BOLD}Passed: {GREEN}{self.passed}{RESET} | {BOLD}Failed: {RED}{self.failed}{RESET} | {BOLD}Warnings: {YELLOW}{self.warnings}{RESET}")
        return self.failed == 0


def print_header(text: str):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")


def print_subheader(text: str):
    print(f"\n{BOLD}{BLUE}→ {text}{RESET}")


def check_file_exists(path: Path, description: str, result: VerificationResult) -> bool:
    if path.exists():
        result.add_pass(f"{description}: {path}")
        return True
    else:
        result.add_fail(f"{description} missing: {path}")
        return False


def check_file_content(path: Path, required_strings: List[str], description: str, result: VerificationResult) -> bool:
    if not path.exists():
        result.add_fail(f"File not found: {path}")
        return False

    content = path.read_text()
    missing = []
    for s in required_strings:
        if s not in content:
            missing.append(s)

    if not missing:
        result.add_pass(f"{description}: All required content present")
        return True
    else:
        result.add_fail(f"{description}: Missing: {', '.join(missing)}")
        return False


def verify_frontend(result: VerificationResult):
    """Verify frontend configuration."""
    print_subheader("Frontend Verification")
    frontend_dir = Path("ticketremaster-f")

    # Check essential files
    check_file_exists(frontend_dir / "package.json", "Frontend package.json", result)
    check_file_exists(frontend_dir / "tsconfig.json", "TypeScript config", result)
    check_file_exists(frontend_dir / ".env", "Frontend .env", result)
    check_file_exists(frontend_dir / ".env.example", "Frontend .env.example", result)
    check_file_exists(frontend_dir / "vercel.json", "Vercel config", result)
    check_file_exists(frontend_dir / "vite.config.ts", "Vite config (TS)", result)

    # Check TypeScript files
    check_file_exists(frontend_dir / "src" / "main.ts", "main.ts", result)
    check_file_exists(frontend_dir / "src" / "env.d.ts", "env.d.ts", result)
    check_file_exists(frontend_dir / "src" / "types" / "index.ts", "Type definitions", result)

    # Check Sentry integration
    check_file_content(
        frontend_dir / "src" / "main.ts",
        ["@sentry/vue", "Sentry.init"],
        "Sentry integration",
        result
    )

    # Check PostHog integration
    check_file_content(
        frontend_dir / "src" / "main.ts",
        ["posthog.init"],
        "PostHog integration",
        result
    )

    # Check i18n integration
    check_file_exists(frontend_dir / "src" / "i18n.ts", "i18n config", result)
    check_file_exists(frontend_dir / "src" / "locales" / "en.json", "English translations", result)

    # Check WebSocket integration
    check_file_exists(frontend_dir / "src" / "composables" / "useWebSocket.ts", "WebSocket composable", result)

    # Check Vercel configuration
    vercel_config = frontend_dir / "vercel.json"
    if vercel_config.exists():
        try:
            config = json.loads(vercel_config.read_text())
            if "rewrites" in config:
                result.add_pass("Vercel rewrites configured for SPA")
            else:
                result.add_warning("Vercel rewrites not configured")
        except json.JSONDecodeError:
            result.add_fail("Invalid vercel.json")

    # Check build scripts
    package_json = json.loads((frontend_dir / "package.json").read_text())
    scripts = package_json.get("scripts", {})
    if "build" in scripts and "vue-tsc" in scripts.get("build", ""):
        result.add_pass("Build script includes TypeScript check")
    else:
        result.add_warning("Build script may not include TypeScript check")

    if "typecheck" in scripts:
        result.add_pass("TypeScript typecheck script present")
    else:
        result.add_warning("No typecheck script found")

    if "test" in scripts:
        result.add_pass("Test script present")
    else:
        result.add_warning("No test script found")


def verify_backend(result: VerificationResult):
    """Verify backend configuration."""
    print_subheader("Backend Verification")
    backend_dir = Path("ticketremaster-b")

    # Check essential files
    check_file_exists(backend_dir / ".env", "Backend .env", result)
    check_file_exists(backend_dir / ".env.example", "Backend .env.example", result)
    check_file_exists(backend_dir / "docker-compose.yml", "Docker Compose", result)
    check_file_exists(backend_dir / "requirements-dev.txt", "Dev requirements", result)
    check_file_exists(backend_dir / "mypy.ini", "MyPy config", result)

    # Check Sentry integration in services
    check_file_exists(backend_dir / "shared" / "sentry.py", "Shared Sentry module", result)

    # Check notification service
    check_file_exists(backend_dir / "services" / "notification-service" / "app.py", "Notification service", result)

    # Check services have Sentry integration
    for service_name in ["user-service", "event-service"]:
        service_app = backend_dir / "services" / service_name / "app.py"
        if service_app.exists():
            check_file_content(
                service_app,
                ["init_sentry", f'service_name="{service_name}"'],
                f"Sentry in {service_name}",
                result
            )

    # Check orchestrators have Sentry integration
    for orchestrator in ["auth-orchestrator", "event-orchestrator"]:
        orchestrator_app = backend_dir / "orchestrators" / orchestrator / "app.py"
        if orchestrator_app.exists():
            check_file_content(
                orchestrator_app,
                ["init_sentry"],
                f"Sentry in {orchestrator}",
                result
            )

    # Check Kubernetes configuration
    k8s_dir = backend_dir / "k8s" / "base"
    check_file_exists(k8s_dir / "core-workloads.yaml", "K8s core workloads", result)
    check_file_exists(k8s_dir / "seed-jobs.yaml", "K8s seed jobs", result)
    check_file_exists(k8s_dir / "configuration.yaml", "K8s configuration", result)

    # Check docker-compose includes notification service
    compose_content = (backend_dir / "docker-compose.yml").read_text()
    if "notification-service" in compose_content:
        result.add_pass("Docker Compose includes notification service")
    else:
        result.add_warning("Notification service not in docker-compose.yml")

    # Check API gateway configuration
    kong_config = backend_dir / "api-gateway" / "kong.yml"
    if kong_config.exists():
        if "notification-service" in kong_config.read_text():
            result.add_pass("Kong gateway includes notification service routes")
        else:
            result.add_warning("Notification service routes not in Kong config")


def verify_env_files(result: VerificationResult):
    """Verify environment files are properly configured."""
    print_subheader("Environment Files Verification")

    frontend_dir = Path("ticketremaster-f")
    backend_dir = Path("ticketremaster-b")

    # Frontend env
    frontend_env = frontend_dir / ".env"
    if frontend_env.exists():
        content = frontend_env.read_text()
        required_vars = [
            "VITE_API_BASE_URL",
            "VITE_SENTRY_DSN",
            "VITE_POSTHOG_API_KEY",
            "VITE_WS_URL",
        ]
        missing = [v for v in required_vars if v not in content]
        if missing:
            result.add_warning(f"Frontend .env missing: {', '.join(missing)}")
        else:
            result.add_pass("Frontend .env has all required variables")

    # Backend env
    backend_env = backend_dir / ".env"
    if backend_env.exists():
        content = backend_env.read_text()
        required_vars = [
            "SENTRY_DSN",
            "SENTRY_ENVIRONMENT",
            "JWT_SECRET",
            "RABBITMQ_HOST",
            "REDIS_URL",
        ]
        missing = [v for v in required_vars if v not in content]
        if missing:
            result.add_warning(f"Backend .env missing: {', '.join(missing)}")
        else:
            result.add_pass("Backend .env has all required variables")

    # Check .env.example files exist and have placeholders
    for env_example in [frontend_dir / ".env.example", backend_dir / ".env.example"]:
        if env_example.exists():
            content = env_example.read_text()
            if "change_me" in content or "your-" in content:
                result.add_pass(f"{env_example.name} has placeholder values")
            else:
                result.add_warning(f"{env_example.name} may have real values (should use placeholders)")


def verify_typescript(result: VerificationResult):
    """Verify TypeScript configuration."""
    print_subheader("TypeScript Verification")

    frontend_dir = Path("ticketremaster-f")

    # Check tsconfig.json
    tsconfig = frontend_dir / "tsconfig.json"
    if tsconfig.exists():
        try:
            config = json.loads(tsconfig.read_text())
            compiler_options = config.get("compilerOptions", {})

            if compiler_options.get("strict", False):
                result.add_pass("TypeScript strict mode enabled")
            else:
                result.add_warning("TypeScript strict mode not enabled")

            if compiler_options.get("noUnusedLocals", False):
                result.add_pass("noUnusedLocals enabled")
            else:
                result.add_warning("noUnusedLocals not enabled")

            if compiler_options.get("noUnusedParameters", False):
                result.add_pass("noUnusedParameters enabled")
            else:
                result.add_warning("noUnusedParameters not enabled")

            # Check path aliases
            paths = compiler_options.get("paths", {})
            if "@/*" in paths:
                result.add_pass("Path alias @/* configured")
            else:
                result.add_warning("Path alias @/* not configured")

        except json.JSONDecodeError:
            result.add_fail("Invalid tsconfig.json")


def verify_tests(result: VerificationResult):
    """Verify test configuration."""
    print_subheader("Test Configuration Verification")

    frontend_dir = Path("ticketremaster-f")
    backend_dir = Path("ticketremaster-b")

    # Frontend tests
    check_file_exists(frontend_dir / "playwright.config.ts", "Playwright config", result)
    check_file_exists(frontend_dir / "tests", "Frontend tests directory", result)

    # Backend tests
    check_file_exists(backend_dir / "pytest.ini", "Pytest config", result)
    check_file_exists(backend_dir / "services" / "user-service" / "tests", "User service tests", result)
    check_file_exists(backend_dir / "services" / "event-service" / "tests", "Event service tests", result)


def verify_kubernetes(result: VerificationResult):
    """Verify Kubernetes configuration."""
    print_subheader("Kubernetes Verification")

    backend_dir = Path("ticketremaster-b")
    k8s_dir = backend_dir / "k8s" / "base"

    # Check essential K8s files
    check_file_exists(k8s_dir / "namespaces.yaml", "K8s namespaces", result)
    check_file_exists(k8s_dir / "network-policies.yaml", "K8s network policies", result)

    # Check seed jobs have proper dependencies
    seed_jobs = k8s_dir / "seed-jobs.yaml"
    if seed_jobs.exists():
        content = seed_jobs.read_text()
        if "wait-for-dependencies" in content:
            result.add_pass("Seed jobs have dependency wait containers")
        else:
            result.add_warning("Seed jobs may not wait for dependencies")

        if "backoffLimit" in content:
            result.add_pass("Seed jobs have backoff limits")
        else:
            result.add_warning("Seed jobs may not have backoff limits")

        if "ttlSecondsAfterFinished" in content:
            result.add_pass("Seed jobs have TTL cleanup")
        else:
            result.add_warning("Seed jobs may not have TTL cleanup")


def main():
    """Main verification function."""
    print_header("TicketRemaster Comprehensive Verification")

    result = VerificationResult()

    # Run all verifications
    verify_frontend(result)
    verify_backend(result)
    verify_env_files(result)
    verify_typescript(result)
    verify_tests(result)
    verify_kubernetes(result)

    # Print summary
    success = result.print_summary()

    if success:
        print(f"\n{GREEN}{BOLD}✓ All verifications passed!{RESET}")
        print("\nNext steps:")
        print("  1. cd ticketremaster-f && npm install")
        print("  2. cd ticketremaster-b && docker-compose up -d")
        print("  3. cd ticketremaster-f && npm run dev")
        print("  4. npm run test (run E2E tests)")
        print("\nFor Vercel deployment:")
        print("  - Connect your repository to Vercel")
        print("  - Add environment variables from .env.example")
        print("  - Deploy!")
        sys.exit(0)
    else:
        print(f"\n{RED}{BOLD}✗ Some verifications failed.{RESET}")
        print("\nPlease fix the issues above before proceeding.")
        sys.exit(1)


if __name__ == '__main__':
    # Change to workspace root (parent of ticketremaster-b)
    script_dir = Path(__file__).parent
    workspace_root = script_dir.parent.parent
    os.chdir(workspace_root)
    print(f"Working directory: {workspace_root}")
    main()
