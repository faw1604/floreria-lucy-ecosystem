# CLAUDE.md — Florería Lucy Ecosystem
> Documento maestro consolidado. Leer COMPLETO antes de tocar cualquier archivo.
> Versión: 10-abr-2026
>
> ⚠️ La sección "PENDIENTES CRÍTICOS" puede quedar desactualizada entre sesiones.
> Para la lista viva de pendientes, leer SIEMPRE primero la memoria persistente:
> `~/.claude/projects/C--Users-EQUIPO-floreria-lucy-ecosystem/memory/project_pendientes_post_sesion2.md`

---

## IDENTIDAD DEL PROYECTO

**Operador:** Fernando Abaroa (Fer) — Chihuahua, México
**Negocios:** Florería Lucy (C. Sabino 610, Las Granjas, 31100 Chihuahua) + La Flore Chocolatier (bean-to-bar)
**Deadline crítico:** 10 de mayo 2026 — Día de las Madres
**Objetivo:** Reemplazar Kyte como POS/catálogo. Claudia recibe pedidos WhatsApp automáticamente → ticket al taller sin intervención humana → florista elabora → repartidor entrega con sus propios paneles digitales.
**Equipo:** Fer solo + asistente part-time

---

## REPOS Y URLS

| Recurso | URL |
|---------|-----|
| Ecosistema (trabajo activo) | github.com/faw1604/floreria-lucy-ecosystem |
| Claudia (CONGELADO) | github.com/faw1604/whatsapp-agentkit |
| API producción | https://floreria-lucy-ecosystem-production.up.railway.app |
| Panel admin | /panel/ |
| POS | /panel/pos |
| Taller | /panel/taller |
| Repartidor | /panel/repartidor |
| Catálogo público | /catalogo/ |
| WhatsApp negocio | 5216143349392 |
| Dev PC | C:\Users\EQUIPO\floreria-lucy-ecosystem |

---

## STACK TÉCNICO

```
Backend:     FastAPI + SQLAlchemy async + asyncpg + PostgreSQL (Railway)
Runtime:     Python 3.12 — NO usar 3.14 (incompatibilidad pydantic-core)
Templates:   HTML/CSS/JS vanilla (sin frameworks frontend)
Timezone:    America/Chihuahua — SIEMPRE. NUNCA UTC
Auth:        Cookie session SHA256 + bcrypt
WhatsApp:    Whapi.cloud — WHAPI_TOKEN en env
Imágenes:    Cloudinary — cloud: ddku2wmpk
Deploy:      Railway Nixpacks, auto-deploy desde GitHub main
```

⚠️ Variables de entorno en Railway — NUNCA en archivos trackeados por git.

---

## ESTRUCTURA DE ARCHIVOS CLAVE

```
app/
  main.py                       — FastAPI app, todos los routers registrados
  database.py                   — engine async, get_db(), inicializar_db() + migraciones auto
  core/
    config.py                   — Settings, TZ = ZoneInfo("America/Chihuahua")
    estados.py                  — EstadoPedido, EstadoFlorista, MetodoEntrega (fuente única)
    utils.py                    — ahora(), hoy(), generar_folio() (centralizados)
  models/
    pedidos.py                  — Pedido, ItemPedido, NotificacionLog
    reservas.py                 — Reserva (arreglos de vitrina)
    clientes.py, productos.py, flores.py, funerarias.py
    pagos.py, inventario.py, configuracion.py, usuarios.py
  routers/
    pos.py                      — POS completo + corte de caja
    taller.py                   — KDS taller (5 pestañas + reservas)
    reservas.py                 — CRUD reservas
    pedidos.py                  — CRUD pedidos + endpoints Claudia
    catalogo.py                 — catálogo público + POST /catalogo/pedido
    panel.py, repartidor.py, auth.py, admin.py
    clientes.py, productos.py, configuracion.py, inventario.py
  static/
    pos.css, pos.js             — separados de pos.html
  taller.html, pos.html, catalogo.html, repartidor.html, admin.html
```

---

## IDENTIDAD VISUAL

```css
--verde-oscuro:  #193a2c
--verde-medio:   #2d5a3d
--dorado:        #d4a843
--crema:         #faf8f5
--texto:         #1a1a1a
--rojo-badge:    #ef4444
--naranja:       #f97316
```

- **UI:** Inter | **Títulos:** Playfair Display
- **Tickets térmicos:** MAYÚSCULAS, SIN acentos ni ñ, 80mm

---

## REGLAS DE NEGOCIO CRÍTICAS

### Impuestos
- **IVA 16%:** SE SUMA al subtotal. Aplica a todo excepto chocolates
- **IEPS 8%:** SOLO SE DESGLOSA, NUNCA se suma. Solo "Chocolates Gourmet"
- Chocolates NO llevan IVA — solo IEPS desglosado

### Precios
- Todos en **centavos** en BD
- Hora específica: +$80 | Link de pago: +4% comisión

### Zonas envío
- Morada: $99 | Azul: $159 | Verde: $199
- Temporada alta: todas a $99

### Horarios
- Tienda: Lun-Vie 9-19h | Sáb 10-18h | Dom 11-15h
- Entrega: Mañana 9-14h | Tarde 14-18h | Noche 18-21h
- Fecha mínima web: mañana (nunca hoy)

### Seguridad
- Datos bancarios: SIEMPRE en tabla `configuracion_negocio`
- Datos de pago al cliente: NUNCA antes de validación del florista
- Sin Google Geocoding API sin aprobación de Fer

---

## ESTADOS DEL PEDIDO (app/core/estados.py)

```
esperando_validacion    ← llega de WhatsApp/Web
    ↓ florista acepta
pendiente_pago          ← Claudia manda datos de pago
    ↓ cliente paga
comprobante_recibido    ← Fer verifica
    ↓ confirma
pagado                  ← entra al taller
    ↓ florista elabora
En producción
    ↓ florista marca listo
listo_taller
    ↓ según metodo_entrega:
    → mostrador:  alerta POS "listo en lobby"
    → recoger:    pestaña "Por Recoger" + POS Entregas
    → envio:      panel repartidor
En camino               ← repartidor en ruta
Entregado               ← repartidor confirma
Cancelado               ← cancelado
```

### estado_florista
```
pendiente_aprobacion | aprobado | aprobado_con_modificacion | cambio_sugerido | rechazado | requiere_atencion
```

### metodo_entrega
```
mostrador | recoger | envio | funeral_envio | funeral_recoger
```

IMPORTANTE: Usar constantes de `app/core/estados.py` (EP, EF, ME), NO strings hardcodeados.

---

## SISTEMA DE RESERVAS

Arreglos pre-elaborados en vitrina. Control antirrobo: solo se venden reservas registradas.

**Taller:** Pestaña "Reservas" → "+ Nueva Reserva" (del catálogo o ⚡ especial) → foto opcional → pizarrón visual
**POS:** Botón verde "R" → seleccionar reserva → agregar al carrito → al finalizar se vincula al pedido
**Lógica POS:** Mostrador + solo reservas = "Listo" (se lo lleva). Cualquier otro = "En producción" (florista elabora).

---

## PANEL TALLER — KDS

6 pestañas: Nuevos | Producción (Hoy/Mañana) | Por Recoger | Próximos | Realizados | Reservas | Inventario

### Nuevos — 4 botones:
1. ✅ Aceptar → producción + descuenta inventario
2. ✏️ Modificar → modal texto, badge amarillo
3. 🔄 Cambio → buscador productos, badge naranja
4. ❌ No aceptar → dropdown razones, badge rojo

### Producción — urgencia por colores:
- Mostrador: ROJO pulsante, timer ascendente
- Recoger: countdown a hora-20min
- Envío: countdown a hora entrega
- Botón LISTO → estado listo_taller → modal imprimir ticket/etiqueta

### Por Recoger — tabla con:
- Fecha y hora entrega, ticket, botón Entregado, filas rojas si atrasado

### Botón "Volver al panel" solo visible para admin

---

## PANEL POS

Sidebar: Ventas | Pendientes | Transacciones | Clientes | Entregas | Claudia

- Polling cada 15s (Pendientes, Transacciones, Entregas)
- Refresh al volver al browser (visibilitychange + focus)
- Botón 📅 en Transacciones para editar fecha de pedidos pagados
- Entregas: Lobby | Por Recoger | Envíos + resumen del día

---

## UTILITIES CENTRALIZADOS (app/core/utils.py)

```python
ahora()          # datetime naive Chihuahua (para asyncpg TIMESTAMP sin TZ)
hoy()            # date Chihuahua
generar_folio()  # FL-YYYY-XXXX único con MAX
```

⚠️ asyncpg NO acepta datetime aware en columnas TIMESTAMP. SIEMPRE usar `ahora()`.

---

## ARQUITECTURA DE USUARIOS

| Rol | Acceso |
|-----|--------|
| admin | Panel admin completo + POS/taller/repartidor |
| operador | Solo POS |
| florista | Solo taller |
| repartidor | Solo panel repartidor |

---

## PENDIENTES CRÍTICOS

⚠️ **Esta lista NO se mantiene aquí.** La fuente autoritativa de pendientes vivos es la memoria persistente de Claude:

`~/.claude/projects/C--Users-EQUIPO-floreria-lucy-ecosystem/memory/project_pendientes_post_sesion2.md`

Claude debe leer ese archivo al inicio de cada sesión antes de listar pendientes a Fer. Se actualiza al final de cada sesión productiva. Mantener una copia aquí causa drift y confusión.

Última snapshot conocida (10-abr-2026, puede estar desactualizada):
1. Mensaje de bienvenida Claudia configurable — INCOMPLETO (Railway agentkit no agarró deploy, ver memoria)
2. Verificar flujo catálogo web end-to-end
3. Bugs panel repartidor
4. Migración ~550 fotos Kyte → Cloudinary
5. Armador cajas chocolates (CLAUDE_chocolates_caja.md listo)

---

## DOCUMENTOS AUXILIARES

- `CLAUDE_taller.md` — spec detallada del rediseño KDS (ya implementado)
- `CLAUDE_chocolates_caja.md` — spec armador cajas La Flore (pendiente)
- `CLAUDE_MAESTRO.md` — versión extendida con BD, hardware, finanzas, estadísticas

---

## LO QUE NUNCA SE DEBE HACER

- Tocar repo `whatsapp-agentkit` sin indicación de Fer
- Cambiar el número de WhatsApp: 5216143349392
- Hardcodear datos bancarios
- Mandar datos de pago antes de validación del florista
- Timezone UTC — siempre America/Chihuahua
- Mostrar productos sin imagen_url en catálogo
- Productos no-funeral en pedidos funeral
- IEPS sumando al total / IVA en chocolates
- datetime.now(TZ) directo en columnas TIMESTAMP — usar ahora()
- Strings de estado hardcodeados — usar EP/EF/ME de core/estados.py
- Instalar playwright en requirements.txt
- Python 3.14
- Reescribir archivos completos cuando basta un cambio quirúrgico
