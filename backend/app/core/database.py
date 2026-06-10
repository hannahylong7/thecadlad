from tortoise import Tortoise
from app.core.config import settings


def get_tortoise_config() -> dict:
    return {
        "connections": {
            "default": settings.database_url,
        },
        "apps": {
            "models": {
                "models": ["app.models.orm", "aerich.models"],
                "default_connection": "default",
            },
        },
    }

TORTOISE_ORM = get_tortoise_config()


async def init_db() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()


async def close_db() -> None:
    await Tortoise.close_connections()