FORBIDDEN_ACTIONS = [
    "save",
    "save_as",
    "purge",
    "explode",
    "explode_block_definition",
    "bulk_delete_existing_objects",
    "auto_remap_existing_layers",
]


def default_blocked_actions() -> list[str]:
    return list(FORBIDDEN_ACTIONS)
