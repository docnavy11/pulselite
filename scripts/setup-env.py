#!/usr/bin/env python3
"""
Interactive .env setup wizard for PulseLight.

Usage:
    python3 scripts/setup-env.py          # interactive setup
    python3 scripts/setup-env.py --check  # validate existing .env

No dependencies required — stdlib only.
"""
import os
import sys
import secrets
import base64
import string
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

# ── Terminal helpers ──────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

# Disable colors if not a TTY
if not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RED = CYAN = RESET = ""


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")


def step(n: int, total: int, text: str) -> None:
    print(f"{BOLD}[{n}/{total}]{RESET} {text}")


def ok(text: str) -> None:
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str) -> None:
    print(f"  {YELLOW}!{RESET} {text}")


def err(text: str) -> None:
    print(f"  {RED}✗{RESET} {text}")


def info(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    """Prompt the user for input with an optional default."""
    if default:
        display = f"{prompt} [{DIM}{default}{RESET}]: "
    else:
        display = f"{prompt}: "

    if secret and default:
        # Show masked default for secrets
        masked = default[:4] + "..." + default[-4:] if len(default) > 12 else "****"
        display = f"{prompt} [{DIM}{masked}{RESET}]: "

    try:
        value = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)

    return value if value else default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{prompt} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)

    if not answer:
        return default
    return answer in ("y", "yes")


def generate_secret(length: int = 48) -> str:
    """Generate a cryptographically secure random string."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_fernet_key() -> str:
    """Generate a Fernet-compatible key (base64-urlsafe 32-byte key)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


# ── .env parsing ──────────────────────────────────────────────────────────────

def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, preserving empty values."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def write_env(values: dict[str, str]) -> None:
    """Write values into .env, using .env.example as a template.

    Preserves comments and structure from .env.example, filling in values.
    Any keys in `values` not in .env.example are appended at the end.
    """
    if not ENV_EXAMPLE.exists():
        err(f"{ENV_EXAMPLE} not found — cannot generate .env")
        sys.exit(1)

    lines = ENV_EXAMPLE.read_text().splitlines()
    used_keys: set[str] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            output.append(line)
            continue
        if "=" not in stripped:
            output.append(line)
            continue

        key, _, _default = stripped.partition("=")
        key = key.strip()
        if key in values:
            output.append(f"{key}={values[key]}")
            used_keys.add(key)
        else:
            output.append(line)
            used_keys.add(key)

    # Append any extra keys not in .env.example
    extra = {k: v for k, v in values.items() if k not in used_keys}
    if extra:
        output.append("")
        output.append("# Additional configuration")
        for k, v in extra.items():
            output.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(output) + "\n")


# ── Check mode ────────────────────────────────────────────────────────────────

def check_env() -> None:
    """Validate an existing .env file and report issues."""
    header("PulseLight .env Check")

    if not ENV_FILE.exists():
        err(".env file not found. Run: python3 scripts/setup-env.py")
        sys.exit(1)

    values = parse_env_file(ENV_FILE)
    issues = 0

    # Required keys
    print(f"{BOLD}Required settings:{RESET}")
    for key, label in [
        ("SECRET_KEY", "App secret key"),
        ("JWT_SECRET_KEY", "JWT secret key"),
        ("FERNET_KEY", "Encryption key"),
        ("ADMIN_EMAIL", "Admin email"),
        ("ADMIN_PASSWORD", "Admin password"),
    ]:
        val = values.get(key, "")
        if not val:
            err(f"{label} ({key}) — not set")
            issues += 1
        elif key in ("SECRET_KEY", "JWT_SECRET_KEY") and "change-in-production" in val:
            warn(f"{label} ({key}) — using default dev value")
            issues += 1
        else:
            ok(f"{label} ({key})")

    # AI config
    print(f"\n{BOLD}AI configuration:{RESET}")
    ai_key = values.get("AI_API_KEY", "")
    ai_base = values.get("AI_BASE_URL", "")
    if ai_key and ai_base:
        ok(f"AI_API_KEY — set")
        ok(f"AI_BASE_URL — {ai_base}")
    elif ai_key and not ai_base:
        warn("AI_API_KEY set but AI_BASE_URL is empty — you'll need to configure it in the UI")
        issues += 1
    elif not ai_key:
        warn("AI_API_KEY — not set (you can configure AI later in Settings > AI Models)")

    default_model = values.get("DEFAULT_CHATBOT_MODEL", "")
    internal_model = values.get("INTERNAL_MODEL", "")
    if default_model:
        ok(f"DEFAULT_CHATBOT_MODEL — {default_model}")
    else:
        info("DEFAULT_CHATBOT_MODEL — not set (will be picked during setup wizard)")

    if internal_model:
        ok(f"INTERNAL_MODEL — {internal_model}")
    else:
        info("INTERNAL_MODEL — not set (will be picked during setup wizard)")

    # URLs
    print(f"\n{BOLD}URLs:{RESET}")
    for key, label in [
        ("BASE_URL", "Backend URL"),
        ("VITE_API_URL", "Frontend → Backend URL"),
        ("FRONTEND_URL", "Frontend URL"),
    ]:
        val = values.get(key, "")
        if val:
            ok(f"{label} — {val}")
        else:
            warn(f"{label} ({key}) — not set")
            issues += 1

    # Summary
    print()
    if issues == 0:
        ok(f"{BOLD}All checks passed!{RESET}")
    else:
        warn(f"{issues} issue(s) found — review above")

    sys.exit(0 if issues == 0 else 1)


# ── Interactive setup ─────────────────────────────────────────────────────────

AI_PROVIDERS = [
    ("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "sk-or-v1-..."),
    ("openai", "OpenAI", "https://api.openai.com/v1", "sk-..."),
    ("anthropic", "Anthropic", "https://api.anthropic.com/v1", "sk-ant-..."),
    ("local", "Local / Ollama", "http://localhost:11434/v1", "ollama"),
    ("custom", "Custom OpenAI-compatible", "", ""),
    ("skip", "Skip — I'll configure later in the UI", "", ""),
]


def run_setup() -> None:
    header("PulseLight Setup")
    print("This wizard will create your .env file.\n")

    # Load existing values if .env already exists
    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        existing = parse_env_file(ENV_FILE)
        warn(f".env already exists ({len(existing)} vars)")
        if not ask_yes_no("Overwrite with new values?", default=False):
            info("Keeping existing .env. Use --check to validate it.")
            sys.exit(0)
        # Back up existing .env
        backup = ENV_FILE.with_suffix(".env.backup")
        shutil.copy2(ENV_FILE, backup)
        ok(f"Backed up to {backup.name}")
    print()

    # Start from .env.example defaults
    values = parse_env_file(ENV_EXAMPLE)
    total_steps = 4

    # ── Step 1: Security keys ────────────────────────────────────────────
    step(1, total_steps, f"{BOLD}Security keys{RESET}")
    info("Generating cryptographically secure keys...")

    values["SECRET_KEY"] = existing.get("SECRET_KEY") or generate_secret(48)
    values["JWT_SECRET_KEY"] = existing.get("JWT_SECRET_KEY") or generate_secret(48)
    values["FERNET_KEY"] = existing.get("FERNET_KEY") or generate_fernet_key()

    # Don't regenerate if user already has non-default keys
    if existing.get("SECRET_KEY") and "change-in-production" not in existing["SECRET_KEY"]:
        ok("Keeping existing security keys")
    else:
        ok("Generated new SECRET_KEY, JWT_SECRET_KEY, FERNET_KEY")
    print()

    # ── Step 2: Admin account ────────────────────────────────────────────
    step(2, total_steps, f"{BOLD}Admin account{RESET}")
    info("This account is created on first startup if no users exist.\n")

    default_email = existing.get("ADMIN_EMAIL", "admin@localhost")
    default_pass = existing.get("ADMIN_PASSWORD", "")
    values["ADMIN_EMAIL"] = ask("  Admin email", default=default_email)

    suggested_pass = default_pass if default_pass and default_pass != "changeme" else generate_secret(16)
    values["ADMIN_PASSWORD"] = ask("  Admin password", default=suggested_pass, secret=True)
    ok(f"Admin: {values['ADMIN_EMAIL']}")
    print()

    # ── Step 3: AI provider ──────────────────────────────────────────────
    step(3, total_steps, f"{BOLD}AI provider{RESET}")
    info("PulseLight needs an OpenAI-compatible API for chatbots.\n")

    print("  Choose your AI provider:")
    for i, (key, label, url, _hint) in enumerate(AI_PROVIDERS):
        marker = f"  {BOLD}{i + 1}){RESET}"
        extra = f" {DIM}({url}){RESET}" if url else ""
        print(f"  {marker} {label}{extra}")

    choice_str = ask("\n  Provider", default="1")
    try:
        choice_idx = int(choice_str) - 1
        if choice_idx < 0 or choice_idx >= len(AI_PROVIDERS):
            raise ValueError
    except ValueError:
        choice_idx = 0

    provider_key, provider_name, provider_url, provider_hint = AI_PROVIDERS[choice_idx]

    if provider_key == "skip":
        values["AI_BASE_URL"] = ""
        values["AI_API_KEY"] = ""
        warn("Skipped — configure AI later in Settings > AI Models")
    else:
        if provider_key == "custom":
            values["AI_BASE_URL"] = ask("  Base URL (e.g. https://your-proxy.com/v1)")
        else:
            custom_url = ask(f"  Base URL", default=provider_url)
            values["AI_BASE_URL"] = custom_url

        default_key = existing.get("AI_API_KEY", "")
        hint = f"({provider_hint})" if provider_hint else ""
        values["AI_API_KEY"] = ask(f"  API key {hint}", default=default_key, secret=True)

        if values["AI_API_KEY"]:
            ok(f"Configured: {provider_name} at {values['AI_BASE_URL']}")
        else:
            warn("No API key entered — you can add one later in Settings > AI Models")

        # Model suggestions
        print()
        info("Optionally set default models (leave blank to pick in the UI later):")

        model_hints = {
            "openrouter": ("openai/gpt-4o-mini", "openai/gpt-4o-mini"),
            "openai": ("gpt-4o-mini", "gpt-4o-mini"),
            "anthropic": ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
            "local": ("llama3", "llama3"),
        }
        hint_default, hint_internal = model_hints.get(provider_key, ("", ""))

        dm = ask("  Default chatbot model", default=existing.get("DEFAULT_CHATBOT_MODEL", hint_default))
        values["DEFAULT_CHATBOT_MODEL"] = dm

        im = ask("  Background tasks model", default=existing.get("INTERNAL_MODEL", hint_internal))
        values["INTERNAL_MODEL"] = im

    print()

    # ── Step 4: URLs ─────────────────────────────────────────────────────
    step(4, total_steps, f"{BOLD}URLs{RESET}")
    info("Defaults work for local Docker setup. Change for remote/proxy setups.\n")

    backend_url = ask("  Backend URL", default=existing.get("BASE_URL", "http://localhost:8000"))
    frontend_url = ask("  Frontend URL", default=existing.get("FRONTEND_URL", "http://localhost:3001"))

    values["BASE_URL"] = backend_url
    values["VITE_API_URL"] = backend_url
    values["VITE_APP_URL"] = frontend_url
    values["FRONTEND_URL"] = frontend_url
    values["BACKEND_CORS_ORIGINS"] = f'["{frontend_url}"]'

    ok(f"Backend:  {backend_url}")
    ok(f"Frontend: {frontend_url}")
    print()

    # ── Write .env ───────────────────────────────────────────────────────
    write_env(values)

    header("Setup complete!")
    print(f"  {GREEN}Created .env with your configuration.{RESET}\n")
    print("  Next steps:")
    print(f"    {BOLD}make up{RESET}        Start all services")
    print(f"    {BOLD}make migrate{RESET}   Run database migrations")
    print(f"    {BOLD}make seed{RESET}      Seed dev data (optional)")
    print()
    print(f"  Then open {BOLD}{frontend_url}{RESET} and log in with:")
    print(f"    Email:    {BOLD}{values['ADMIN_EMAIL']}{RESET}")
    print(f"    Password: {BOLD}{values['ADMIN_PASSWORD']}{RESET}")
    print()

    if not values.get("AI_API_KEY"):
        warn("AI is not configured yet — the app will guide you through setup on first login.")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if "--check" in sys.argv:
        check_env()
    elif "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__.strip())
        print()
        print("Options:")
        print("  --check    Validate an existing .env file")
        print("  --help     Show this help message")
    else:
        run_setup()


if __name__ == "__main__":
    main()
