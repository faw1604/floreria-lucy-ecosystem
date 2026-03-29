from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session

async def inicializar_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Auto-migrate: agregar columnas nuevas si no existen
        from sqlalchemy import text
        _migrations = [
            ("pedidos", "metodo_entrega", "VARCHAR(30)"),
            ("pedidos", "modo_fecha_fuerte_lote", "VARCHAR(100)"),
            ("pedidos", "listo_at", "TIMESTAMP"),
            ("pedidos", "produccion_at", "TIMESTAMP"),
            ("pedidos", "cancelado_razon", "TEXT"),
        ]
        for tabla, col, tipo in _migrations:
            try:
                await conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}"))
            except Exception:
                pass  # ya existe
