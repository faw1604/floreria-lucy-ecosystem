# CLAUDE.md — Documento maestro del proyecto Florería Lucy
> Este archivo es el puente entre sesiones de trabajo.
> Si estás en un chat nuevo, lee todo esto antes de hacer cualquier cosa.

---

## Quién es Fer y cómo trabajamos

Fernando Abaroa (Fer) opera dos negocios en Chihuahua, México:
- **Florería Lucy** — florería familiar fundada en 1988, actualmente en C. Sabino 610, Las Granjas
- **La Flore Chocolatier** — marca de chocolates artesanales bean-to-bar

Fer maneja casi todo solo con un asistente part-time. El objetivo del proyecto es automatizar el negocio para que para el 10 de mayo (Día de las Madres — temporada más fuerte del año) Claudia reciba pedidos por WhatsApp automáticamente y el ticket llegue al taller sin intervención humana.

### Dinámica de trabajo establecida
- **Fer describe qué quiere** → yo diseño, tomo decisiones técnicas y genero un `CLAUDE.md` con instrucciones
- **Fer descarga el CLAUDE.md** → lo copia a la raíz del repo `floreria-lucy-ecosystem`
- **Claude Code lee y ejecuta:** `Lee el CLAUDE.md completo y ejecuta todas las tareas en orden`
- **Fer reporta resultados** → yo actualizo y genero el siguiente CLAUDE.md
- **Para evitar aprobaciones manuales:** claude --dangerously-skip-permissions ya está configurado en la terminal abierta

### Reglas de comunicación con Fer
- Respuestas directas y concisas — Fer está ocupado operando el negocio
- Nunca hacer cambios sin que Fer los apruebe primero
- Cuando hay decisiones de diseño o negocio, presentar opciones y esperar confirmación
- No reescribir código existente que funciona sin necesidad
- Cambios quirúrgicos — no reemplazar archivos completos a menos que sea necesario
- Si algo falló antes no repetirlo, pensar diferente

---

## URLs en producción

- **API:** https://floreria-lucy-ecosystem-production.up.railway.app
- **Panel admin:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/
- **Taller:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/taller
- **Repartidor:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/repartidor
- **POS:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/pos ← NUEVO
- **Catálogo público:** https://floreria-lucy-ecosystem-production.up.railway.app/catalogo/
- **Claudia (WhatsApp):** whatsapp-agentkit-production-4e69.up.railway.app
- **WhatsApp Florería Lucy:** 5216143349392
- **Correo:** florerialucychihuahua@gmail.com
- **Maps:** https://maps.app.goo.gl/J2josMqSyLJFyk1V9

## Repos GitHub
- **Ecosistema:** github.com/faw1604/floreria-lucy-ecosystem ← aquí trabajamos
- **Claudia:** github.com/faw1604/whatsapp-agentkit ← NO TOCAR hasta que ecosistema esté completo

---

## Stack técnico

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Railway)
- **Runtime:** Python 3.12 (NO usar 3.14 — incompatibilidad con pydantic-core)
- **Timezone:** America/Chihuahua — SIEMPRE usar `TZ` de `app/core/config.py`, NUNCA UTC
- **Auth:** Cookie session SHA256
- **IA panel:** Claude claude-sonnet-4-6 (Anthropic) vía httpx
- **IA Claudia:** GPT-4o-mini (OpenAI) — repo separado
- **Imágenes:** Cloudinary (cloud: ddku2wmpk, API key: 543563876228939)
- **Deploy:** Railway con Nixpacks, auto-deploy desde GitHub main
- **PC desarrollo:** C:\Users\EQUIPO\floreria-lucy-ecosystem
- **Bash path Windows:** "C:/Program Files/Git/bin/bash.exe"

## Variables de entorno Railway (floreria-lucy-ecosystem)
```
DATABASE_URL=postgresql://... (auto Railway)
DATABASE_PUBLIC_URL=[REDACTED]
SECRET_KEY=floreria-lucy-secret-2025
SESSION_SECRET=floreria-lucy-session-2025
PANEL_PASSWORD=[configurado en Railway]
ENVIRONMENT=production
ANTHROPIC_API_KEY=[configurado en Railway]
CLOUDINARY_CLOUD_NAME=ddku2wmpk
CLOUDINARY_API_KEY=543563876228939
CLOUDINARY_API_SECRET=[configurado en Railway]
CLAUDIA_API_KEY=floreria-claudia-2025
```

---

## Estructura del proyecto

```
app/
  main.py
  database.py
  panel.html
  taller.html
  repartidor.html
  pos.html                  ← NUEVO
  catalogo.html
  static/
  core/
    config.py
    security.py
  models/
    clientes.py
    productos.py
    flores.py
    funerarias.py
    pagos.py
    pedidos.py
    inventario.py
  routers/
    auth.py
    clientes.py
    productos.py
    flores.py
    funerarias.py
    pagos.py
    pedidos.py
    panel.py
    catalogo.py
    inventario.py
    repartidor.py
    pos.py                  ← NUEVO
  services/
    rutas.py
  scripts/
    ...
    rutas_chihuahua.kml
    rutas_chihuahua.geojson
```

---

## Estado actual de la BD en producción

- 613 productos (52 con imagen_url en Cloudinary)
- 4,045 clientes importados de Kyte
- 15 funerarias con tarifas
- 5 métodos de pago
- 15 flores base
- 84 insumos florales + 26 no florales
- Tabla pedidos con campos de repartidor y campo `ruta`

---

## Zonas de ruta (8 zonas)

Central, NORTE, NORESTE, NOROESTE, PONIENTE, ORIENTE, SUR, SURESTE
- Geocodificación: Nominatim bounded al bounding box de Chihuahua
- Fallback: zona más cercana, nunca null para domicilios
- Funerales: sin ruta

---

## Identidad visual

### Florería Lucy
- Verde oscuro: #193a2c | Verde medio: #2d5a3d | Dorado: #d4a843
- Fondo crema: #faf8f5 | Texto: #1a1a1a
- Tipografía: Playfair Display (títulos) + Inter (UI)

---

## Reglas de negocio críticas

### Horario (America/Chihuahua — NUNCA UTC)
- Lun–Vie: 9–19 | Sáb: 10–18 | Dom: 11–15

### Zonas de envío
- Morada: $99 | Azul: $159 | Verde: $199
- Funeraria Miranda Villa Juárez = Azul $159 | Resto funerarias = Morada $99

### Horarios entrega (regular)
- Mañana: 9am–2pm | Tarde: 2pm–6pm | Noche: 6pm–9pm

### Pagos
- Transferencia, OXXO, link tarjeta (4% comisión), efectivo/tarjeta en tienda
- Pedido a producción SOLO con pago confirmado

### Impuestos
- Arreglos: precio sin IVA, +16% al facturar
- Chocolates La Flore: precio incluye IEPS 8% implícito
- Productos de flor suelta: N/A (exento)

### Pedidos funeral
- Solo productos de categoría funeral — sin excepción
- Sin ruta asignada
- Tarifa fija según funeraria

---

## Lo que está completado ✅

1. API FastAPI con 11 routers en producción
2. BD poblada con todos los datos base
3. Panel admin con asistente IA
4. Catálogo web completo
5. Pantalla del taller v2 — 5 pestañas
6. Tickets 80mm (3 variantes) + mini tickets + endpoint digital
7. Panel del repartidor completo (filtros, rutas, foto, Google Maps, llamada nativa)
8. Asignación automática de ruta con shapely + Nominatim
9. Endpoint POST /pedidos/desde-claudia

---

## TAREAS PENDIENTES INMEDIATAS — POS Mostrador

### Contexto y diseño general

Layout igual a Kyte pero con identidad Florería Lucy:
- **Columna izquierda (65%):** catálogo de productos
- **Columna derecha (35%):** carrito / resumen del pedido
- **Header:** modo de venta + cliente seleccionado
- Pantalla completa optimizada para tablet y PC de mostrador
- Misma auth que el panel admin

---

### TAREA 1 — Router `app/routers/pos.py`

Endpoints necesarios:

```
GET  /panel/pos                  → Sirve pos.html (requiere auth)
GET  /pos/productos              → Lista productos con imagen, nombre, precio, stock
                                   Solo productos con imagen_url
                                   Soporta ?q=búsqueda y ?categoria=X
GET  /pos/clientes/buscar        → Búsqueda por nombre, teléfono o código referido (?q=)
POST /pos/cliente                → Registrar cliente rápido
POST /pos/geocodificar           → Geocodifica dirección, retorna lat/lng/ruta
POST /pos/pedido                 → Crear pedido completo desde el POS
```

**POST /pos/pedido — body:**
```json
{
  "tipo": "mostrador|domicilio|recoger|funeral",
  "cliente_id": 123,
  "items": [{"producto_id": 1, "cantidad": 2, "precio_unitario": 680}],
  "tipo_impuesto": "IVA|IEPS|NA",
  "horario_entrega": "manana|tarde|noche|hora_especifica|funeral|null",
  "hora_especifica": "14:30",
  "zona_envio": "Morada|Azul|Verde",
  "ruta": "NORTE",
  "lat": 28.69,
  "lng": -106.11,
  "nombre_destinatario": "Ana García",
  "telefono_destinatario": "6141234567",
  "direccion_entrega": "Av. Tecnológico 4500",
  "dedicatoria": "Feliz cumpleaños",
  "notas_entrega": "Portón negro",
  "funeraria_id": 5,
  "nombre_fallecido": "Juan Pérez",
  "sala": "Sala 2",
  "banda": "Descanse en paz",
  "horario_velacion": "ya_inicio|14:00",
  "fecha_recoger": "2026-04-01T15:00",
  "pagos": [
    {"metodo_pago_id": 1, "monto": 500},
    {"metodo_pago_id": 2, "monto": 200}
  ],
  "estado": "pagado|pendiente_pago"
}
```

Lógica del endpoint:
- Validar suma de pagos = total cuando estado = "pagado"
- Si tipo = "funeral": validar que todos los productos son categoría funeral, rechazar si no
- Si link de tarjeta (metodo_pago nombre contiene "link"): sumar 4% al total
- Aplicar descuento 10% si cliente_id != null y es primera compra (sin pedidos previos pagados)
- Generar folio FL-YYYY-XXXX
- Estado del pedido: "listo_taller" si pagado, "pendiente_pago" si no
- Retornar pedido creado con folio y total final

---

### TAREA 2 — Registrar router en `app/main.py`

Importar y registrar `pos_router` igual que los demás.

---

### TAREA 3 — Crear `app/pos.html`

#### Layout general (dos columnas fijas, sin scroll en el contenedor principal)

```
┌──────────────────────────────────────────────────────────┐
│ HEADER                                                   │
│ 🌸 Florería Lucy POS  [Mostrador][Domicilio][Funeral]    │
│                          [👤 Seleccionar cliente]        │
├─────────────────────────────┬────────────────────────────┤
│  CATÁLOGO (65%)             │  CARRITO (35%)             │
│  scroll interno             │  scroll interno            │
│                             │                            │
│  [Buscar...] [Categorías ▼] │  ← contenido dinámico     │
│                             │     según modo             │
│  grid de productos          │                            │
│                             │  [Guardar] [Finalizar ✓]   │
└─────────────────────────────┴────────────────────────────┘
```

#### Colores y tipografía
- Fondo general: #faf8f5
- Header: fondo #193a2c, texto blanco
- Columna carrito: fondo blanco, borde izquierdo 1px #e0ddd8
- Botón "Finalizar": fondo #193a2c, texto blanco
- Botón "Guardar": fondo blanco, borde #193a2c, texto #193a2c
- Precios y totales: color #193a2c
- Descuento: color #d4a843
- Fuente: Inter en todo el POS (sin Playfair)
- Tabs de modo activo: fondo #d4a843, texto #193a2c

#### Header
- Logo "🌸 Florería Lucy" a la izquierda
- 3 tabs de modo: **Mostrador | Domicilio / Recoger | Funeral**
- A la derecha: botón "👤 Sin cliente" que abre modal de búsqueda
  - Solo habilitado en modos Domicilio y Funeral
  - Cuando hay cliente: mostrar nombre + badge "10% primera compra" si aplica en dorado
- Enlace "← Panel" que va al panel admin

#### Columna izquierda — Catálogo

- Input de búsqueda con ícono de lupa
- Dropdown de categorías (carga desde API)
- Grid 3 columnas (2 en tablet < 1024px)
- Cada tarjeta:
  - Imagen cuadrada con object-fit: cover
  - Nombre (2 líneas máximo, truncar)
  - Si tiene precio_descuento: precio normal tachado en gris + precio oferta en #193a2c
  - Si no: solo precio normal
  - Click → agregar al carrito con animación (escala rápida)
  - Sin stock (stock = 0): overlay semitransparente gris + texto "Sin stock", no clickeable
- Fetch a /pos/productos al cargar, refetch al cambiar búsqueda o categoría

#### Columna derecha — Carrito

El carrito se construye con secciones que aparecen/desaparecen según el modo activo.
Todas las secciones tienen título en mayúsculas pequeñas con separador.

**[SIEMPRE] — Items del pedido**
- Si carrito vacío: mensaje "Selecciona productos del catálogo"
- Lista de items:
  - Nombre del producto
  - Controles de cantidad: [−] [N] [+]
  - Precio unitario × cantidad = subtotal
  - Botón [×] eliminar
- Si modo = Funeral y algún producto NO es categoría funeral:
  banner de advertencia rojo: "⚠ Solo productos de funeral permitidos en este modo"

**[DOMICILIO / FUNERAL] — Cliente**
- Si no hay cliente: botón "Seleccionar o registrar cliente" (borde punteado)
- Si hay cliente: tarjeta con nombre, teléfono, badge descuento si aplica
  - Botón "Cambiar"
- Modal búsqueda de cliente:
  - Input de búsqueda en tiempo real (fetch a /pos/clientes/buscar)
  - Lista de resultados con nombre + teléfono
  - Botón "Registrar nuevo cliente" al fondo
- Modal registro de cliente:
  - Radio: Persona física | Empresa
  - Campos según tipo (ver especificación detallada en reglas de negocio)
  - Teléfono: selector de código país (+52 MX preseleccionado, +1 USA secundario)
  - Sección "Datos de facturación" colapsable (opcional)
  - Botón "Guardar cliente" → POST /pos/cliente → seleccionar automáticamente

**[DOMICILIO — subtipo general] — Entrega**
- Nombre de quien recibe (input)
- Teléfono de quien recibe (input)
- Dirección de entrega (input) + botón "📍 Verificar"
  - Al click: abrir Maps en nueva pestaña con la dirección
  - Checkbox "✓ Dirección verificada" (manual)
  - Al marcar verificada: fetch a /pos/geocodificar → badge de ruta asignada (ej. "NORTE")
- Dedicatoria (textarea, placeholder "Opcional")
- Notas para el repartidor (textarea, placeholder "Opcional")

**[DOMICILIO — subtipo funeral] — Datos funeral**
- Input funeraria con autocompletado (/funerarias/buscar)
- Nombre del fallecido
- Sala (opcional)
- Texto banda (opcional)
- Dedicatoria (opcional)
- Horario velación: radio "Ya inició" | "Inicia a las [selector hora]"

**[RECOGER] — Datos recogida**
- Selector de fecha (date picker)
- Selector de hora
- Nota: "El cliente pasará el [fecha] a las [hora]"

**[DOMICILIO] — Horario de entrega**
- 4 botones: Mañana (9–2pm) | Tarde (2–6pm) | Noche (6–9pm) | Hora específica
- Si "Hora específica": input de hora + nota "Mínimo 2 horas de anticipación"

**[DOMICILIO general] — Zona y envío**
- Si dirección verificada y geocodificada: zona asignada automáticamente con badge
- Si no: selector manual con 8 zonas
- Mostrar costo: Morada $99 / Azul $159 / Verde $199
  (verificar si hay temporada activa → todas $99)

**[SIEMPRE] — Impuesto**
- Selector 3 opciones: IVA 16% | IEPS 8% | Sin impuesto
- IEPS: solo habilitado si hay productos La Flore en el carrito
- Mostrar nota explicativa según selección

**[SIEMPRE] — Resumen de totales**
```
Subtotal:           $930
IVA (16%):          $148
Envío (Morada):      $99
Descuento 10%:      -$93   ← en dorado, solo si aplica
─────────────────────────
TOTAL:            $1,084
```

**[SIEMPRE] — Métodos de pago**
- 6 opciones (chips seleccionables, múltiple):
  Efectivo | Tarjeta crédito | Tarjeta débito | Transferencia | Link de pago | OXXO
- Cada chip seleccionado despliega input de monto
- Si "Link de pago" seleccionado: mostrar "+4% comisión = $X" y sumar al total
- Indicador: "Asignado: $X / Total: $Y" — se pone verde cuando cuadra
- Si no cuadra al intentar finalizar: error "Falta asignar $X"

**[SIEMPRE] — Botones de acción (pegados al fondo)**
```
[ Guardar pedido ]    [ ✓ Finalizar venta ]
```
- "Guardar": POST /pos/pedido con estado="pendiente_pago" sin validar pagos
- "Finalizar": validar pagos → POST /pos/pedido con estado="pagado" → imprimir → limpiar

**Impresión al finalizar:**
- window.print() automático después de crear el pedido
- CSS @media print muestra solo el ticket (mismo formato que taller)
- Si tipo = domicilio: imprimir comprador + repartidor
- Si tipo = mostrador/recoger/funeral: solo comprador
- Después de imprimir: limpiar todo el carrito y regresar al estado inicial

---

### TAREA 4 — Endpoint geocodificación para POS

```
POST /pos/geocodificar
Body: { "direccion": "Av. Tecnológico 4500, Col. Las Granjas" }
```
- Reutilizar la lógica existente en /pedidos/{id}/ruta (servicio rutas.py)
- Retornar: `{ "lat": 28.xx, "lng": -106.xx, "ruta": "NORTE", "display_name": "..." }`
- Si falla: `{ "error": "No se pudo geocodificar" }`

---

### TAREA 5 — Agregar enlace en `app/panel.html`

En el header del panel admin agregar junto a los otros enlaces:
```html
<a href="/panel/pos" target="_blank">🛒 POS</a>
```

---

### NOTAS DE IMPLEMENTACIÓN

1. **Sin imagen = no mostrar** en catálogo del POS — igual que catálogo público
2. **Validación funeral:** rechazar POST /pos/pedido si tipo=funeral y algún producto no es categoría funeral
3. **Primera compra:** en /pos/pedido verificar si cliente tiene pedidos previos con estado != "pendiente_pago"
4. **Impresión:** window.print() con CSS @media print, mismo formato que taller
5. **Carrito en JS puro** sin localStorage — se limpia al finalizar o recargar
6. **Link de pago:** calcular 4% y mostrar desglose — la generación real del link va después
7. **Temporada alta:** consultar configuración existente para aplicar tarifa $99 en todas las zonas
8. **No usar fetch con async/await sin try/catch** — cada llamada con manejo de error visible

---

## Roadmap pendiente (en orden de prioridad para mayo 10)

### Crítico para mayo:
1. ✅ Pantalla del taller
2. ✅ Tickets + mini tickets + endpoint digital
3. ✅ Panel del repartidor completo con rutas
4. **POS mostrador ← ESTAMOS AQUÍ**
5. Conectar Claudia al ecosistema

### Post-mayo:
- Migración 550 fotos restantes desde Kyte
- Historial ventas 2021–2024
- Auth personalizada para repartidor
- Afinar polígonos de rutas
- Apagar Kyte

---

## Decisiones de diseño tomadas (no revertir)

- **Layout POS:** igual a Kyte — catálogo izquierda, carrito derecha, identidad Florería Lucy
- **Un solo diseño de ticket** para comprador, repartidor y digital
- **Carrito en JS puro** — sin localStorage
- **Registro no obligatorio** en catálogo público
- **Claudia sobre factura:** "Sí, claro, +IVA 🌸"
- **Fotos:** no mostrar productos sin imagen_url en catálogo ni POS
- **Funerales sin ruta** — no geocodificar funerarias
- **Ruta fallback:** zona más cercana, nunca null para domicilios
- **Coordenadas POS:** verificación manual en Maps + Nominatim
- **Asistente IA panel** = Claude | **Claudia** = GPT-4o-mini

---

## LO QUE NUNCA SE DEBE HACER

- Tocar repo whatsapp-agentkit hasta que Fer confirme que el ecosistema está listo
- Cambiar el número de WhatsApp: 5216143349392
- Hardcodear API keys o passwords
- Cambiar timezone a UTC — siempre America/Chihuahua
- Mostrar productos sin imagen_url en catálogo o POS
- Hacer el registro obligatorio en el catálogo
- Dar datos bancarios directamente
- Confirmar hora específica sin doble confirmación florista+repartidor
- Usar Google Geocoding API sin aprobación de Fer (tiene costo)
- Permitir productos no-funeral en pedidos de funeral
