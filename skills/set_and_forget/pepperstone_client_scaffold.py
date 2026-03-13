from pathlib import Path

import pepperstone_client


def build_client_scaffold(base_dir: Path, order_intent: dict):
    return pepperstone_client.build_client_scaffold(base_dir, order_intent)
