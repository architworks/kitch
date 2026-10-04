"""Create or print Kitch's standard Vertex AI Memory Bank resource.

This creates an empty Agent Engine resource, which provides Memory Bank.  It
does not upload or deploy the Kitch agent to Agent Engine Runtime. Authentication
uses Google Application Default Credentials.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env.local")
load_dotenv(BACKEND_DIR / ".env")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create a new empty Memory Bank when no ID is configured.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    configured_id = os.environ.get("KITCH_MEMORY_BANK_ID", "").strip()
    if configured_id:
        print(f"KITCH_MEMORY_BANK_ID={configured_id}")
        print("Using the configured Memory Bank; no resource was created.")
        return

    if not args.create:
        raise SystemExit(
            "KITCH_MEMORY_BANK_ID is not configured. Re-run with --create to "
            "create an empty Memory Bank."
        )

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip()
    if not project:
        raise SystemExit(
            "GOOGLE_CLOUD_PROJECT is required. Authenticate first with "
            "'gcloud auth application-default login'."
        )

    try:
        import agentplatform
    except ImportError:  # Compatibility with older supported 1.x SDK releases.
        import vertexai as agentplatform

    client = agentplatform.Client(project=project, location=location)
    agent_engine = client.agent_engines.create()
    resource_name = str(agent_engine.api_resource.name)
    memory_bank_id = resource_name.rstrip("/").split("/")[-1]
    print(f"KITCH_MEMORY_BANK_ID={memory_bank_id}")
    print("Created an empty Memory Bank resource. No agent runtime was deployed.")


if __name__ == "__main__":
    main()
