# Lazy import: agent requires google.adk which may not be installed
# during test runs of agent_runtime modules.
try:
    from . import agent  # noqa: F401
except ImportError:
    pass

