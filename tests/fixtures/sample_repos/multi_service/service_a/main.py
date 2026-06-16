from service_b.client import call_service_b


def entrypoint() -> str:
    return call_service_b()
