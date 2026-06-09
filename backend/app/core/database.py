from tortoise import Tortoise


TORTOISE_ORM = {
    "connections": {
        "default": "sqlite:///data/cad_agent.db",
    },
    "apps": {
        "models": {
            "models": ["app.models.orm", "aerich.models"],
            "default_connection": "default",
        },
    },
}


async def init_db() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()


async def close_db() -> None:
    await Tortoise.close_connections()