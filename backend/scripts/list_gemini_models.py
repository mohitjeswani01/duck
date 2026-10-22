"""Prints every Gemini model visible to the configured API keys, flagging Flash models.

Run this once real keys are in backend/.env, to confirm the exact model name to pin
in GEMINI_MODEL instead of guessing. Usage (from backend/, with the venv active):

    python scripts/list_gemini_models.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.gemini_key_pool import get_gemini_key_pool  # noqa: E402


async def main() -> None:
    pool = get_gemini_key_pool()

    async def _list(client):
        return await client.aio.models.list()

    models = await pool.execute(_list)

    print(f"{'MODEL NAME':<40} {'FLASH?':<8} SUPPORTED ACTIONS")
    print("-" * 90)
    for model in models:
        name = getattr(model, "name", "") or ""
        actions = getattr(model, "supported_actions", None) or getattr(
            model, "supported_generation_methods", []
        )
        is_flash = "yes" if "flash" in name.lower() else ""
        print(f"{name:<40} {is_flash:<8} {actions}")


if __name__ == "__main__":
    asyncio.run(main())
