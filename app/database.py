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
            ("pedidos", "repartidor_id", "INTEGER"),
            ("pedidos", "cancelado_razon", "TEXT"),
            ("pedidos", "pago_confirmado_at", "TIMESTAMP"),
        ]
        for tabla, col, tipo in _migrations:
            try:
                await conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {col} {tipo}"))
                _log.info(f"  + {tabla}.{col}")
            except Exception as e:
                _log.info(f"  ~ {tabla}.{col}: {str(e)[:80]}")

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

    # 4. Seed configuración negocio
    async with engine.begin() as conn:
        from sqlalchemy import text
        _seeds = [
            ("clave_admin_pos", "1234", "Clave admin para cancelar/editar transacciones en POS"),
            ("temporada_modo", "regular", "Modo de temporada: regular o alta"),
            ("temporada_categoria", "", "Categoría de productos para temporada alta"),
            ("temporada_fecha_fuerte", "", "Fecha exacta del día fuerte (YYYY-MM-DD)"),
            ("temporada_dias_restriccion", "2", "Días antes de fecha fuerte para restringir catálogo"),
            ("temporada_acepta_funerales", "true", "Aceptar pedidos funerales en temporada alta"),
            ("temporada_envio_unico", "9900", "Precio envío único temporada alta en centavos"),
            ("zona_tarifa_morada", "9900", "Tarifa envío zona Morada en centavos"),
            ("zona_tarifa_azul", "15900", "Tarifa envío zona Azul en centavos"),
            ("zona_tarifa_verde", "19900", "Tarifa envío zona Verde en centavos"),
        ]
        for clave, valor, desc in _seeds:
            try:
                await conn.execute(text(
                    "INSERT INTO configuracion_negocio (clave, valor, descripcion) "
                    "VALUES (:c, :v, :d) ON CONFLICT (clave) DO NOTHING"
                ), {"c": clave, "v": valor, "d": desc})
            except Exception:
                pass
