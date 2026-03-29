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
    import logging
    _log = logging.getLogger("floreria")

    # 1. create_all para tablas existentes
    try:
        import app.models  # noqa: F401
    except Exception as e:
        _log.warning(f"Import app.models: {e}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Migraciones manuales en conexión separada
    async with engine.begin() as conn:
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
                _log.info(f"  + {tabla}.{col}")
            except Exception:
                pass

    # 3. Crear tabla reservas en conexión separada
    async with engine.begin() as conn:
        from sqlalchemy import text
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id SERIAL PRIMARY KEY,
                    producto_id INTEGER,
                    nombre_custom VARCHAR(200),
                    precio INTEGER NOT NULL,
                    foto_url TEXT,
                    florista_usuario VARCHAR(100) NOT NULL,
                    estado VARCHAR(20) DEFAULT 'disponible',
                    pedido_id INTEGER,
                    created_at TIMESTAMP,
                    vendida_at TIMESTAMP,
                    descartada_at TIMESTAMP,
                    descarte_razon TEXT
                )
            """))
            _log.info("Tabla reservas: OK")
        except Exception as e:
            _log.error(f"Tabla reservas ERROR: {e}")
