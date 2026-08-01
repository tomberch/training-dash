import os

from arq import create_pool
from arq.connections import RedisSettings


def get_redis_settings() -> RedisSettings:
    host = os.environ.get("REDIS_HOST", "")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return RedisSettings(host=host or "localhost", port=port)


def redis_available() -> bool:
    return bool(os.environ.get("REDIS_HOST"))


async def create_redis_pool():
    return await create_pool(get_redis_settings())