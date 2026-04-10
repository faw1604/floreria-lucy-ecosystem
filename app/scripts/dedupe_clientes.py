"""
Detecta y fusiona clientes duplicados por teléfono normalizado.

Uso:
    python -m app.scripts.dedupe_clientes              # dry-run (solo reporta)
    python -m app.scripts.dedupe_clientes --apply      # ejecuta la fusión

Lógica:
1. Carga todos los clientes y los agrupa por limpiar_telefono(c.telefono).
2. En cada grupo de tamaño > 1 elige un sobreviviente:
     - El que tenga MÁS pedidos
     - empate → el más antiguo (id menor)
3. Reasigna al sobreviviente:
     - pedidos.customer_id
     - notificaciones_log.customer_id
     - datos_fiscales_cliente.cliente_id
     - clientes.referido_por (si apuntaba al codigo_referido de un perdedor)
4. Mergea datos faltantes en el sobreviviente (email, dirección, fecha_nac, etc).
5. Borra los perdedores.

NUNCA borra clientes con datos en uso sin reasignar antes. Si algo falla,
hace rollback del grupo completo.
"""
import asyncio
import sys
import os
import argparse
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, update, func, text
from app.database import async_session, inicializar_db
from app.models.clientes import Cliente
from app.models.pedidos import Pedido, NotificacionLog
from app.core.utils import limpiar_telefono


def elegir_sobreviviente(clientes_y_pedidos):
    """Recibe lista de (cliente, n_pedidos). Devuelve el sobreviviente."""
    # Ordenar por: n_pedidos desc, id asc (más antiguo)
    return sorted(clientes_y_pedidos, key=lambda x: (-x[1], x[0].id))[0][0]


def mergear_campos(survivor: Cliente, loser: Cliente):
    """Llena campos vacíos del survivor con datos del loser."""
    campos = [
        "email", "direccion_default", "fecha_nacimiento", "fecha_aniversario",
        "fechas_especiales", "codigo_referido", "referido_por",
    ]
    for campo in campos:
        if not getattr(survivor, campo) and getattr(loser, campo):
            setattr(survivor, campo, getattr(loser, campo))
    # Sumar descuento_referido (saldo a favor)
    if loser.descuento_referido:
        survivor.descuento_referido = (survivor.descuento_referido or 0) + loser.descuento_referido
    # primera_compra: si alguno ya la usó (False), el survivor también
    if not loser.descuento_primera_compra:
        survivor.descuento_primera_compra = False
    # registrado_web: True si cualquiera lo está
    if loser.registrado_web:
        survivor.registrado_web = True


async def detectar_duplicados(session):
    """Devuelve dict {telefono_normalizado: [Cliente, ...]} con grupos > 1."""
    result = await session.execute(select(Cliente))
    todos = result.scalars().all()
    grupos = defaultdict(list)
    for c in todos:
        norm = limpiar_telefono(c.telefono)
        if not norm or norm.startswith("sin-"):
            continue  # ignorar placeholders sin teléfono
        grupos[norm].append(c)
    return {tel: cs for tel, cs in grupos.items() if len(cs) > 1}


async def contar_pedidos(session, cliente_id):
    r = await session.execute(
        select(func.count(Pedido.id)).where(Pedido.customer_id == cliente_id)
    )
    return r.scalar() or 0


async def fusionar_grupo(session, telefono_norm, clientes, apply: bool):
    # Obtener pedidos por cliente
    enriched = []
    for c in clientes:
        n = await contar_pedidos(session, c.id)
        enriched.append((c, n))

    survivor = elegir_sobreviviente(enriched)
    perdedores = [c for c, _ in enriched if c.id != survivor.id]

    print(f"\n  Tel normalizado: {telefono_norm}")
    for c, n in enriched:
        marca = "★ SURVIVOR" if c.id == survivor.id else "  perdedor"
        print(f"    {marca}  id={c.id:5}  tel={c.telefono!r:20}  pedidos={n}  nombre={c.nombre!r}")

    if not apply:
        return

    # Normalizar el teléfono del survivor a la forma canónica
    if survivor.telefono != telefono_norm:
        survivor.telefono = telefono_norm

    # Reasignar referencias y mergear
    for loser in perdedores:
        # 1. Pedidos
        await session.execute(
            update(Pedido).where(Pedido.customer_id == loser.id).values(customer_id=survivor.id)
        )
        # 2. NotificacionLog
        await session.execute(
            update(NotificacionLog).where(NotificacionLog.customer_id == loser.id).values(customer_id=survivor.id)
        )
        # 3. Datos fiscales (tabla puede no existir en algunas instalaciones)
        try:
            await session.execute(
                text("UPDATE datos_fiscales_cliente SET cliente_id = :s WHERE cliente_id = :l"),
                {"s": survivor.id, "l": loser.id},
            )
        except Exception as e:
            print(f"    (skip datos_fiscales: {e})")
        # 4. Si el código de referido del loser fue usado por otros, repuntarlos al del survivor
        if loser.codigo_referido and loser.codigo_referido != survivor.codigo_referido:
            await session.execute(
                update(Cliente)
                .where(Cliente.referido_por == loser.codigo_referido)
                .values(referido_por=survivor.codigo_referido)
            )
        # 5. Mergear campos
        mergear_campos(survivor, loser)

    # Limpiar telefonos de perdedores antes de borrar (evita choque con unique)
    for i, loser in enumerate(perdedores):
        loser.telefono = f"__deleted_{loser.id}_{i}"
    await session.flush()

    # Borrar perdedores
    for loser in perdedores:
        await session.delete(loser)

    await session.flush()
    print(f"    → Fusionado: {len(perdedores)} perdedor(es) → survivor id={survivor.id}")


async def main(apply: bool):
    await inicializar_db()
    async with async_session() as session:
        duplicados = await detectar_duplicados(session)

        if not duplicados:
            print("✓ No se detectaron clientes duplicados por teléfono normalizado.")
            return

        print(f"Se detectaron {len(duplicados)} grupo(s) de duplicados:")
        if not apply:
            print("(modo DRY-RUN — no se modificará nada. Usa --apply para ejecutar)")

        grupos_ok = 0
        grupos_fallidos = 0
        clientes_eliminados = 0
        clientes_serian = 0
        for tel, clientes in duplicados.items():
            n_perdedores = len(clientes) - 1
            try:
                await fusionar_grupo(session, tel, clientes, apply)
                if apply:
                    # Commit por grupo: si truena el siguiente, lo ya hecho queda persistido
                    await session.commit()
                    grupos_ok += 1
                    clientes_eliminados += n_perdedores
                else:
                    clientes_serian += n_perdedores
            except Exception as e:
                print(f"  ✗ Error en grupo {tel}: {type(e).__name__}: {e}")
                if apply:
                    await session.rollback()
                    grupos_fallidos += 1
                    print("    rollback de este grupo, continuando con el siguiente")
                    continue

        if apply:
            print(f"\n✓ Terminado.")
            print(f"   Grupos fusionados: {grupos_ok}")
            print(f"   Grupos fallidos:   {grupos_fallidos}")
            print(f"   Clientes eliminados: {clientes_eliminados}")
        else:
            print(f"\nDRY-RUN: {clientes_serian} cliente(s) serían fusionados. Usa --apply para ejecutar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detecta y fusiona clientes duplicados por teléfono.")
    parser.add_argument("--apply", action="store_true", help="Ejecutar la fusión (por defecto solo reporta)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
