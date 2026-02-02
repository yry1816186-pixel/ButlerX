import time
import uuid


def utc_ts() -> int:
    return int(time.time())


def new_uuid() -> str:
    return str(uuid.uuid4())
