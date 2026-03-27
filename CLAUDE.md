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
- Cambios quirúrgicos — no reemplazar archivos completos a menos que sea necesario
- Si algo falló antes no repetirlo, pensar diferente

---

## URLs en producción

- **API:** https://floreria-lucy-ecosystem-production.up.railway.app
- **Panel admin:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/
- **Taller:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/taller
- **Repartidor:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/repartidor
- **POS:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/pos
- **Catálogo público:** https://floreria-lucy-ecosystem-production.up.railway.app/catalogo/
- **Claudia (WhatsApp):** whatsapp-agentkit-production-4e69.up.railway.app
- **WhatsApp Florería Lucy:** 5216143349392
- **Correo:** florerialucychihuahua@gmail.com

## Repos GitHub
- **Ecosistema:** github.com/faw1604/floreria-lucy-ecosystem ← aquí trabajamos
- **Claudia:** github.com/faw1604/whatsapp-agentkit ← NO TOCAR

---

## Stack técnico

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Railway)
- **Runtime:** Python 3.12
- **Timezone:** America/Chihuahua — SIEMPRE usar `TZ` de `app/core/config.py`, NUNCA UTC
- **Auth:** Cookie session SHA256
- **IA panel:** Claude claude-sonnet-4-6 vía httpx
- **Imágenes:** Cloudinary (cloud: ddku2wmpk, API key: 543563876228939)
- **Deploy:** Railway con Nixpacks, auto-deploy desde GitHub main
- **PC desarrollo:** C:\Users\EQUIPO\floreria-lucy-ecosystem

## Variables de entorno Railway
```
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
WHAPI_TOKEN=[configurado en Railway]
```

---

## Identidad visual

- Verde oscuro: #193a2c | Verde medio: #2d5a3d | Dorado: #d4a843
- Fondo crema: #faf8f5 | Texto: #1a1a1a
- Tipografía: Inter (todo el POS — sin Playfair)
- Botón primario: fondo #193a2c, texto blanco
- Botón secundario: fondo blanco, borde #193a2c, texto #193a2c
- Descuentos y primera compra: #d4a843

---

## Reglas de negocio críticas

### Zonas de envío y tarifas
- Morada: $99 | Azul: $159 | Verde: $199
- Funeraria Miranda Villa Juárez = Azul $159 | Resto funerarias = Morada $99
- En temporada alta: todas las zonas = $99

### Horarios entrega
- Mañana: 9am–2pm | Tarde: 2pm–6pm | Noche: 6pm–9pm

### Impuestos
- IVA 16%: se SUMA al subtotal de productos (no al envío)
- IEPS 8%: ya está implícito en el precio — solo se DESGLOSA, NO se suma
- Sin impuesto: N/A

### Pedidos funeral
- Solo productos de categoría funeral — sin excepción
- Sin ruta asignada, tarifa fija según funeraria

### Métodos de pago
- Efectivo, Tarjeta crédito, Tarjeta débito, Transferencia, Link de pago, OXXO
- Combinables — la suma debe = total
- Link de pago: +4% comisión sumada al total

---

## Lo que está completado ✅

1. API FastAPI con 12 routers en producción
2. BD poblada (613 productos, 4,045 clientes, 15 funerarias)
3. Panel admin con asistente IA
4. Catálogo web completo
5. Pantalla del taller v2
6. Tickets 80mm (3 variantes) + mini tickets + endpoint digital
7. Panel del repartidor completo con rutas
8. Asignación automática de ruta (shapely + Nominatim)
9. Asignación automática de zona de envío (KML polígonos reales)
10. Endpoint POST /pedidos/desde-claudia
11. POS v1 funcionando (se va a rediseñar completamente en estas tareas)

---

## TAREAS PENDIENTES INMEDIATAS — Rediseño completo del POS

### Contexto
El POS actual (app/pos.html) se rediseña completamente con una nueva arquitectura
de flujo por ventanas/pasos, sidebar izquierdo de navegación, y UX inspirada en Kyte
pero con identidad Florería Lucy.

El archivo `app/pos.html` se reescribe desde cero. El router `app/routers/pos.py`
se mantiene y extiende con los nuevos endpoints necesarios.

---

### ARQUITECTURA GENERAL

```
┌──────────┬────────────────────────────────────────────┐
│ SIDEBAR  │  CONTENIDO PRINCIPAL                       │
│ izquierdo│                                            │
│          │  [Ventana activa según sección y paso]     │
│ Ventas   │                                            │
│ Pedidos  │                                            │
│ pendientes│                                           │
│Transacc. │                                            │
│ Clientes │                                            │
│ Claudia  │                                            │
└──────────┴────────────────────────────────────────────┘
```

**Sidebar izquierdo** (fijo, siempre visible):
- Fondo #193a2c, iconos y texto blanco
- Ítem activo: fondo #d4a843, texto #193a2c
- Ítems: Ventas (🛒) | Pedidos pendientes (⏳) | Transacciones (💰) | Clientes (👤) | Claudia (🤖)
- Logo "Florería Lucy" arriba del sidebar
- Enlace "← Panel" al fondo del sidebar

---

### SECCIÓN 1 — VENTAS (flujo de 3 ventanas)

La sección de Ventas tiene 3 ventanas/pasos secuenciales. Siempre se puede regresar
al paso anterior con un botón "← Regresar". El estado del pedido en curso se mantiene
en memoria JS mientras se navega entre pasos.

---

#### VENTANA 1 — Selección de productos

**Layout:**
```
┌─────────────────────────────┬──────────────────────┐
│  CATÁLOGO                   │  CARRITO             │
│                             │                      │
│  [🔍 Buscar] [Categorías ▼] │  items...            │
│  [☰ Lista] [⊞ Grid]  [⚡]  │                      │
│                             │  ─────────────────   │
│  productos...               │  SUBTOTAL    $X,XXX  │
│                             │  IVA 16% [×] $XXX    │
│                             │  IEPS 8%  [×] —      │
│                             │  ─────────────────   │
│                             │  TOTAL       $X,XXX  │
│                             │                      │
│                             │  [Continuar orden →] │
└─────────────────────────────┴──────────────────────┘
```

**Catálogo (columna izquierda ~65%):**
- Toggle vista: Grid (⊞) o Lista (☰) — el operador elige, persiste en localStorage
- Grid: 3 columnas, tarjetas con imagen cuadrada, nombre (2 líneas), precio
  - Si tiene precio_descuento: precio normal tachado + precio oferta en dorado
  - Sin stock: overlay gris "Sin stock", no clickeable
  - Solo mostrar productos CON imagen_url
- Lista: tabla compacta con imagen pequeña (40x40), nombre, código, precio, botón [+]
- Buscador en tiempo real (fetch a /pos/productos?q=)
- Dropdown de categorías (fetch a /pos/productos/categorias)
- Click en producto → agregar al carrito con animación

**Botón rayo ⚡ (producto no registrado):**
- Icono ⚡ junto al buscador
- Al click: modal pequeño con campos:
  - Nombre del item (obligatorio)
  - Precio (obligatorio, numérico)
  - Observaciones (opcional, textarea pequeño)
  - Botón "Agregar al carrito"
- El item se agrega al carrito como producto custom (sin producto_id, con nombre y precio manual)
- Se incluye en el pedido como item especial

**Carrito (columna derecha ~35%):**
- Lista de items con:
  - Nombre + código si existe
  - Controles cantidad: [−] [N] [+]
  - Precio unitario × cantidad = subtotal item
  - Botón [×] eliminar
  - Botón "Descuento" por item → input de % o $ con botón Aplicar
    - Al aplicar: mostrar precio tachado + precio con descuento en dorado
    - Botón [×] para quitar descuento del item
- Si carrito vacío: "Selecciona productos del catálogo" con ícono

**Sección de totales al fondo del carrito:**
```
N items                      Subtotal: $X,XXX
                    [ × IVA (16%): $XXX  ]   ← chip toggleable
                    [ × IEPS (8%): $XXX  ]   ← chip toggleable, solo desglosa
                    Dar descuento ↗           ← descuento global
──────────────────────────────────────────
                             TOTAL: $X,XXX
```
- IVA: chip con ×, al activar SUMA 16% al subtotal, al desactivar lo quita
- IEPS: chip con ×, al activar DESGLOSA 8% (no suma), al desactivar lo quita
- Ambos pueden estar activos o inactivos independientemente
- "Dar descuento": input de % o $ con botón Aplicar, aparece como línea en dorado
- Botón grande "Continuar orden →" en verde #193a2c

---

#### VENTANA 2 — Tipo de pedido

**Layout:**
```
← Regresar

¿Cómo es este pedido?

┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  🏪          │ │  🚚          │ │  🛍          │ │  🌹          │
│   Mostrador  │ │  Domicilio   │ │   Recoger    │ │   Funeral    │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```
- 4 botones grandes, centrados, con ícono y texto
- Al seleccionar uno → ir a Ventana 3 con el tipo seleccionado
- Botón "← Regresar" regresa a Ventana 1 (carrito se preserva)

---

#### VENTANA 3 — Datos del pedido (según tipo)

**Layout general:**
```
← Regresar          [Tipo de pedido]

┌─────────────────────────────┬──────────────────────┐
│  FORMULARIO (scroll)        │  RESUMEN DEL PEDIDO  │
│                             │  (fijo, siempre      │
│  [cajas según tipo]         │   visible)           │
│                             │                      │
│                             │  Subtotal: $X,XXX    │
│                             │  IVA:      $XXX      │
│                             │  Envío:    $XX       │
│                             │  Descuento:-$XX      │
│                             │  ────────────────    │
│                             │  TOTAL:    $X,XXX    │
│                             │                      │
│  [Descartar] [Guardar] [Finalizar]                 │
└─────────────────────────────┴──────────────────────┘
```

El resumen del pedido en la columna derecha se actualiza en tiempo real conforme
el operador llena los datos (zona de envío afecta el total, etc.).

**Botones de acción (fijo al fondo, siempre visibles):**
- "Descartar venta" (gris) → confirmar con modal "¿Descartar esta venta?" → limpiar todo
- "Guardar pedido" (blanco con borde) → POST /pos/pedido estado="pendiente_pago" → modal ticket
- "Finalizar venta" (verde #193a2c) → validar campos obligatorios → POST /pos/pedido estado="pagado" → modal ticket

**Modal post-venta (al guardar o finalizar):**
- Título: folio del pedido en grande
- Resumen: total, método de pago
- Botones:
  - "🖨 Imprimir ticket" → window.print() con ticket 80mm
  - "💬 Enviar por WhatsApp" → solo si hay cliente con teléfono → POST /pos/enviar-ticket-whatsapp
    (genera imagen con html2canvas y la envía vía Whapi)
- Botón "✕ Cerrar" en esquina superior derecha → limpia todo y vuelve a Ventana 1

---

#### VENTANA 3A — Mostrador

Cajas/secciones en el formulario:
1. **Método de pago** — igual que Kyte: radio buttons con ícono, al seleccionar muestra campo de monto.
   Opciones: Efectivo | Tarjeta débito | Tarjeta crédito | Transferencia | Link de pago | OXXO
   - Combinables: al seleccionar uno se puede agregar otro
   - Si Link de pago: mostrar "+4% = $X" en el resumen
   - Validar que suma de pagos = total

---

#### VENTANA 3B — Domicilio

Cajas/secciones:
1. **Cliente** — buscar por nombre/tel/código referido con autocompletado
   - Si no existe: botón "Registrar nuevo cliente" → modal con formulario (persona física o empresa)
   - Si tiene flag primera_compra = true: mostrar botón sugerencia "Aplicar 10% primera compra"
     (no automático — el operador decide aplicarlo)
2. **Datos de entrega**
   - Nombre de quien recibe (obligatorio)
   - Teléfono de quien recibe (obligatorio)
   - Dirección (obligatorio) + botón "📍 Verificar en Maps" → abre Google Maps en nueva pestaña
     - Checkbox "✓ Dirección verificada" (manual)
     - Al marcar verificada: fetch a /pos/geocodificar → badge de ruta + auto-asignación de zona
   - Notas para el repartidor (opcional)
   - Dedicatoria (opcional)
3. **Fecha y horario**
   - Date picker (obligatorio, mínimo hoy)
   - Selector horario: Mañana (9-2pm) | Tarde (2-6pm) | Noche (6-9pm) | Hora específica
   - Si Hora específica: input hora + nota "Mínimo 2 hrs anticipación"
4. **Zona de envío**
   - Auto-asignada si se verificó en Maps
   - Si no: selector manual (Morada $99 / Azul $159 / Verde $199)
   - En temporada alta: todas $99
5. **Método de pago** — igual que Mostrador

---

#### VENTANA 3C — Recoger (Pick up)

Cajas/secciones:
1. **Cliente** — igual que Domicilio
2. **Fecha y hora de recogida**
   - Date picker (obligatorio, mínimo hoy)
   - Time picker (obligatorio)
   - Label: "¿Cuándo pasa a recoger?"
3. **Método de pago** — igual que Mostrador

---

#### VENTANA 3D — Funeral

Cajas/secciones:
1. **Cliente** — igual que Domicilio (quien encarga)
2. **Datos del funeral**
   - Funeraria: input con autocompletado (/funerarias/buscar) (obligatorio)
   - Nombre del fallecido (obligatorio)
   - Sala (opcional)
   - Texto banda (opcional)
   - Dedicatoria (opcional)
   - Fecha de entrega: date picker (obligatorio)
   - Horario velación: radio "Ya inició" | "Inicia a las [selector hora]"
   - Validar: todos los productos deben ser categoría funeral
3. **Método de pago** — igual que Mostrador

---

### SECCIÓN 2 — PEDIDOS PENDIENTES

Lista de pedidos con estado = "pendiente_pago".
Fetch a GET /pos/pedidos-hoy (tab pendientes).
Cada pedido en tarjeta con:
- Folio, tipo, cliente o "Mostrador", productos (resumen), total
- Botón "Finalizar" → abre la Ventana 3 del tipo correspondiente con datos pre-cargados
- Botón "Ver detalle" → expandir tarjeta con todos los datos

---

### SECCIÓN 3 — TRANSACCIONES

Lista de pedidos con estado = "pagado" o "listo_taller" del día.
Fetch a GET /pos/pedidos-hoy (tab finalizados).
Cada pedido en tarjeta con folio, cliente, productos, total, método de pago.
- Botón "Editar" → modal con campos no críticos editables
- Botón "Reimprimir"
Al fondo: resumen del día con total por método de pago y total general.

---

### SECCIÓN 4 — CLIENTES

Buscador de clientes con autocompletado.
Lista de resultados con nombre, teléfono, número de pedidos.
Click en cliente → ver detalle (historial de pedidos, fechas especiales, código referido).
Botón "Nuevo cliente" → mismo modal de registro que en Ventas.

---

### SECCIÓN 5 — CLAUDIA

iframe o panel que muestra el panel de Claudia / chats activos.
URL: la del panel de WhatsApp ya existente en el ecosistema.
Si no hay URL directa disponible, mostrar placeholder "Próximamente".

---

### VALIDACIONES OBLIGATORIAS (antes de Finalizar)

**Mostrador:** al menos 1 producto, pagos cuadran con total
**Domicilio:** cliente, nombre destinatario, teléfono destinatario, dirección, fecha, horario, zona, pagos cuadran
**Recoger:** cliente, fecha recogida, hora recogida, pagos cuadran
**Funeral:** cliente, funeraria, nombre fallecido, fecha entrega, todos productos son categoría funeral, pagos cuadran

Al hacer click en "Finalizar": recorrer validaciones, marcar campos faltantes en rojo con mensaje,
hacer scroll al primer error. No proceder hasta que todo esté completo.
"Guardar pedido" no valida — guarda sin importar campos faltantes.

---

### ENDPOINTS NUEVOS O MODIFICADOS en app/routers/pos.py

Los endpoints existentes se mantienen. Agregar o modificar:

```
GET  /pos/pedidos-pendientes     → pedidos estado="pendiente_pago" del día
PATCH /pos/pedido/{id}/completar → finalizar un pedido pendiente con pagos
```

El endpoint POST /pos/pedido existente ya maneja todo lo demás.

---

### NOTAS DE IMPLEMENTACIÓN

1. **Estado del pedido en curso:** guardar en objeto JS `ordenActual` en memoria.
   Persiste al navegar entre ventanas 1→2→3. Se limpia al finalizar, descartar o cerrar modal.
2. **Productos no registrados (⚡):** incluir en items del pedido con producto_id = null,
   nombre y precio del campo manual, y observaciones en notas del item.
3. **Vista grid/lista:** guardar preferencia en localStorage con key "pos_vista_catalogo"
4. **Resumen siempre visible en Ventana 3:** columna derecha fija, no hace scroll.
   Se actualiza reactivamente con cada cambio en el formulario.
5. **El carrito NO usa localStorage** — solo memoria JS. Se pierde al recargar.
6. **Impresión:** window.print() con CSS @media print, mismo ticket 80mm existente.
7. **Whapi para WhatsApp:** usar WHAPI_TOKEN de variables de entorno.
   Endpoint existente POST /pos/enviar-ticket-whatsapp ya implementado.
8. **No usar fetch sin try/catch** — cada llamada con manejo de error visible al usuario.

---

## Roadmap pendiente (en orden de prioridad para mayo 10)

### Crítico para mayo:
1. ✅ Pantalla del taller
2. ✅ Tickets + mini tickets + endpoint digital
3. ✅ Panel del repartidor completo con rutas
4. **POS rediseño completo ← ESTAMOS AQUÍ**
5. Conectar Claudia al ecosistema

### Post-mayo:
- Migración 550 fotos restantes desde Kyte
- Historial ventas 2021–2024
- Auth personalizada para repartidor
- Afinar polígonos de rutas
- Apagar Kyte

---

## Decisiones de diseño tomadas (no revertir)

- **POS:** flujo de 3 ventanas secuenciales, sidebar izquierdo, resumen siempre visible
- **Carrito en JS puro** — sin localStorage
- **IVA suma, IEPS solo desglosa** — nunca al revés
- **10% primera compra:** sugerencia, no automático
- **Funerales sin ruta** — no geocodificar funerarias
- **Coordenadas:** verificación manual en Maps + Nominatim como geocodificador
- **Sin Google Geocoding API** — tiene costo, no autorizado

---

## LO QUE NUNCA SE DEBE HACER

- Tocar repo whatsapp-agentkit hasta que Fer confirme que el ecosistema está listo
- Cambiar el número de WhatsApp: 5216143349392
- Hardcodear API keys o passwords
- Cambiar timezone a UTC — siempre America/Chihuahua
- Mostrar productos sin imagen_url en catálogo o POS
- Permitir productos no-funeral en pedidos de funeral
- Usar Google Geocoding API sin aprobación de Fer
- IEPS sumando al total — solo desglosa
