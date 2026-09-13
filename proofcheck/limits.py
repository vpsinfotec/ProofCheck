"""Resource limits shared by the CLI and API; invalid environment values fail clearly."""
import os


def env_int(name: str, default: int, minimum: int = 1, maximum: int = 2**31 - 1) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


MAX_PAGES = env_int("PROOFCHECK_MAX_PAGES", 1000)
MAX_TEXT_CHARS = env_int("PROOFCHECK_MAX_TEXT_CHARS", 10_000_000)
MAX_CELLS = env_int("PROOFCHECK_MAX_CELLS", 200_000)
MAX_ROWS = env_int("PROOFCHECK_MAX_ROWS", 100_000)
MAX_IMAGE_PIXELS = env_int("PROOFCHECK_MAX_IMAGE_PIXELS", 40_000_000)
MAX_WORKBOOK_BYTES = env_int("PROOFCHECK_MAX_WORKBOOK_MB", 256) * 1024 * 1024
