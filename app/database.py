from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)
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

    # 1b. Extensión unaccent para búsquedas sin acentos
    async with engine.begin() as conn:
        from sqlalchemy import text
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            _log.info("Extensión unaccent: OK")
        except Exception as e:
            _log.warning(f"Extensión unaccent: {e}")

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
            ("pedidos", "tracking_token", "VARCHAR(64)"),
            ("gastos_recurrentes", "proveedor", "VARCHAR(200)"),
            ("gastos_recurrentes", "metodo_pago", "VARCHAR(100)"),
            ("pedidos", "ticket_enviado_at", "TIMESTAMP"),
            ("productos", "destacado", "BOOLEAN DEFAULT FALSE"),
            ("productos", "vender_por_fraccion", "BOOLEAN DEFAULT FALSE"),
            ("items_pedido", "gramos", "INTEGER"),
            ("egresos", "cuenta_id", "INTEGER"),
            ("productos", "imagenes_extra", "TEXT"),
            ("pedidos", "pagos_detalle", "TEXT"),
            ("pedidos", "forma_pago", "VARCHAR(100)"),
        ]
        for tabla, col, tipo in _migrations:
            try:
                await conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {col} {tipo}"))
                _log.info(f"  + {tabla}.{col}")
            except Exception as e:
                _log.info(f"  ~ {tabla}.{col}: {str(e)[:80]}")
        try:
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_pedidos_tracking_token ON pedidos (tracking_token) WHERE tracking_token IS NOT NULL"))
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
        ]
        for clave, valor, desc in _seeds:
            try:
                await conn.execute(text(
                    "INSERT INTO configuracion_negocio (clave, valor, descripcion) "
                    "VALUES (:c, :v, :d) ON CONFLICT (clave) DO NOTHING"
                ), {"c": clave, "v": valor, "d": desc})
            except Exception:
                pass

        # Seed cuentas financieras (Caja + Caja Chica) si no existen
        try:
            from datetime import date as _date
            hoy_seed = _date.today()
            _cuentas_seed = [
                ("Caja", "caja", 0, 100000),  # fondo $1000
                ("Caja Chica", "caja_chica", 0, 0),
            ]
            for nombre, tipo, saldo, fondo in _cuentas_seed:
                await conn.execute(text(
                    "INSERT INTO cuentas_financieras (nombre, tipo, saldo_inicial, fecha_inicio, fondo_base, activo) "
                    "VALUES (:n, :t, :s, :f, :fb, true) ON CONFLICT (nombre) DO NOTHING"
                ), {"n": nombre, "t": tipo, "s": saldo, "f": hoy_seed, "fb": fondo})
        except Exception as e:
            _log.warning(f"Seed cuentas_financieras: {e}")

    # 5. Seed funerarias nuevas + actualizar dirección Elian Perches
    async with engine.begin() as conn:
        from sqlalchemy import text
        _nuevas_funerarias = [
            {"nombre": "Réquiem Hernández", "zona": "Azul", "costo_envio": 15900},
            {"nombre": "Lux Nostra", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "Lozano Escudero", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "Jardines Eternos", "zona": "Verde", "costo_envio": 19900},
            {"nombre": "Funeraria y Cementerio Jardines de Santa Fe", "zona": "Azul", "costo_envio": 15900},
            {"nombre": "Protectodeco Bolívar", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "Velatorio IMSS", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "Memorial", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "La Nueva Luz (Calle Aldama)", "zona": "Morada", "costo_envio": 9900,
             "direccion": "C. Juan Aldama #3313, Zona Dorada, 31000 Chihuahua, Chih."},
            {"nombre": "Funerales La Nueva Luz (Cerro de la Cruz)", "zona": "Azul", "costo_envio": 15900,
             "direccion": "C. 70a. 2404, Cerro de la Cruz, 31460 Chihuahua, Chih."},
            {"nombre": "Funerales La Nueva Luz (Plaza Nogales)", "zona": "Azul", "costo_envio": 15900,
             "direccion": "Vialidad Los Nogales 1301, Atanasio Ortega, 31137 Chihuahua, Chih."},
            {"nombre": "Funerales La Nueva Luz (Villa Juárez)", "zona": "Verde", "costo_envio": 19900,
             "direccion": "16 de Septiembre 1003, Villa Juárez, 31064 Chihuahua, Chih."},
            {"nombre": "El Legado", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "La Cineraria Zarco", "zona": "Morada", "costo_envio": 9900},
            {"nombre": "La Piedad Funeraria", "zona": "Verde", "costo_envio": 19900},
        ]
        for f in _nuevas_funerarias:
            try:
                # Check if already exists
                result = await conn.execute(text(
                    "SELECT id FROM funerarias WHERE nombre = :nombre"
                ), {"nombre": f["nombre"]})
                if result.fetchone() is None:
                    direccion_val = f.get("direccion")
                    if direccion_val:
                        await conn.execute(text(
                            "INSERT INTO funerarias (nombre, zona, costo_envio, direccion) "
                            "VALUES (:nombre, :zona, :costo, :dir)"
                        ), {"nombre": f["nombre"], "zona": f["zona"], "costo": f["costo_envio"], "dir": direccion_val})
                    else:
                        await conn.execute(text(
                            "INSERT INTO funerarias (nombre, zona, costo_envio) "
                            "VALUES (:nombre, :zona, :costo)"
                        ), {"nombre": f["nombre"], "zona": f["zona"], "costo": f["costo_envio"]})
                    _log.info(f"Funeraria agregada: {f['nombre']}")
            except Exception as e:
                _log.warning(f"Seed funeraria {f['nombre']}: {e}")

        # Actualizar dirección de Elian Perches
        try:
            await conn.execute(text(
                "UPDATE funerarias SET direccion = :dir WHERE LOWER(nombre) LIKE '%elian%perches%'"
            ), {"dir": "C. Vigésimo Novena #505, Centro, 31000 Chihuahua, Chih."})
            _log.info("Funeraria Elian Perches: dirección actualizada")
        except Exception as e:
            _log.warning(f"Update Elian Perches: {e}")

    # 6. Seed productos Barra de Café (solo POS, no catálogo web)
    async with engine.begin() as conn:
        from sqlalchemy import text
        _cafe_productos = [
            ("Agua Natural", 400, 1000),
            ("Refresco", 1500, 3500),
            ("Iced Cappuccino", 3500, 7500),
            ("Iced Mocha", 3500, 7500),
            ("Lemon Americano", 2500, 5200),
            ("Chai Latte Frio", 3500, 7500),
            ("Té GD", 2000, 4500),
            ("Matcha Latte GD", 4000, 8600),
            ("Dirty Chai GD", 4000, 9000),
            ("Chai Latte GD", 8200, 8200),
            ("Chai Latte CH", 7000, 7000),
            ("Chai GD", 7800, 7800),
            ("Chocolate de la casa GD", 8000, 8000),
            ("Chocolate de la casa CH", 7000, 7000),
            ("Chocolate Oaxaqueño GD", 8500, 8500),
            ("Chocolate Oaxaqueño CH", 7000, 7000),
            ("Chocolate Macchiato GD", 8500, 8500),
            ("Chocolate Macchiato CH", 8000, 8000),
            ("Chocolate Blanco GD", 7800, 7800),
            ("Chocolate Blanco CH", 6500, 6500),
            ("Chocolate Clásico GD", 7500, 7500),
            ("Cappuccino GD", 7500, 7500),
            ("Caramel GD", 3500, 7500),
            ("Mocha GD", 3500, 7500),
            ("Latte GD", 2000, 6500),
            ("Americano GD", 1500, 4800),
            ("Bombón", 1000, 4500),
            ("Extra pump", 500, 1000),
            ("Extra shot", 700, 2500),
            ("Iced Caramel", 3800, 7500),
            ("Caramel CH", 3000, 6500),
            ("Orange Americano", 2000, 5500),
            ("Tisana GD", 3000, 6800),
            ("Chocolate Frio", 3500, 7000),
            ("Tisana CH", 2000, 5800),
            ("Limonada", 2000, 4000),
            ("Soda Italiana", 2000, 4500),
            ("Té Helado", 2000, 4000),
            ("Taro Frio", 3800, 7500),
            ("Matcha Latte Frio", 4000, 8000),
            ("Espresso Tonic", 3000, 6000),
            ("Chai Frio", 3200, 6500),
            ("Smoothie", 3000, 7200),
            ("Frappe - Taro / Matcha / Choc Blanco", 3900, 8000),
            ("Frappe - Cappuccino / Cookies / Java", 3800, 7800),
            ("Iced Latte", 3500, 7500),
            ("Cappuccino en las rocas", 3500, 7500),
            ("Americano en las rocas", 2500, 4800),
            ("Affogato", 2500, 5000),
            ("Dirty Chai CH", 3500, 7500),
            ("Chai CH", 3000, 6700),
            ("Chocolate Clásico CH", 3000, 6500),
            ("Té CH", 1500, 3500),
            ("Matcha Latte CH", 3500, 7000),
            ("Mocha CH", 2500, 6500),
            ("Cappuccino CH", 3500, 6500),
            ("Latte CH", 1000, 5500),
            ("Americano CH", 2000, 4000),
            ("Espresso Doble", 1500, 3500),
            ("Cortado", 2000, 4000),
            ("Macchiato", 1500, 3500),
            ("Espresso Sencillo", 1000, 3000),
            ("Café del día", 1500, 3000),
        ]
        for nombre, costo, precio in _cafe_productos:
            try:
                result = await conn.execute(text(
                    "SELECT id FROM productos WHERE nombre = :nombre AND categoria = :cat"
                ), {"nombre": nombre, "cat": "Barra de Café"})
                if result.fetchone() is None:
                    await conn.execute(text(
                        "INSERT INTO productos (nombre, categoria, precio, costo, costo_unitario, activo, visible_catalogo, disponible_hoy) "
                        "VALUES (:nombre, :cat, :precio, :costo, :costo_u, true, false, true)"
                    ), {"nombre": nombre, "cat": "Barra de Café", "precio": precio, "costo": costo, "costo_u": costo / 100.0})
                    _log.info(f"Producto café: {nombre}")
            except Exception as e:
                _log.warning(f"Seed café {nombre}: {e}")
