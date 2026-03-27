import os


def get_runtime_root() -> str:
    env_root = os.environ.get("PLAYEROK_BOT_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return project_root


def resolve_runtime_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(get_runtime_root(), path)
