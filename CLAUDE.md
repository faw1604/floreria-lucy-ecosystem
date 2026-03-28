# CLAUDE.md — Panel Admin Florería Lucy
## Refactor completo con 11 pestañas

---

## CONTEXTO

Estás trabajando en el repo `floreria-lucy-ecosystem` (FastAPI + PostgreSQL + Jinja2).
El panel admin vive en `/panel/` y ya tiene funcionalidad parcial.
El POS (`/panel/pos`) está completamente terminado — úsalo como referencia visual y de lógica.

**Identidad visual:**
- Verde oscuro: `#193a2c` | Verde medio: `#2d5a3d` | Dorado: `#d4a843`
- Fondo crema: `#faf8f5` | Texto: `#1a1a1a`
- Tipografía: Inter (body), Playfair Display (títulos)
- Badges: rojo `#ef4444` estilo iOS
- Semana: domingo a sábado (NUNCA lunes a domingo)
- Timezone: `America/Chihuahua` SIEMPRE

**Stack:**
- Backend: FastAPI + SQLAlchemy async + PostgreSQL
- Frontend: Jinja2 + HTML/CSS/JS vanilla (sin frameworks frontend)
- Imágenes: Cloudinary (cloud: `ddku2wmpk`)
- Deploy: Railway (auto-deploy desde GitHub main)

---

## OBJETIVO

Refactorizar el panel admin en `/panel/` para que tenga sidebar de 11 pestañas
con la misma lógica estructural del POS. Cada pestaña se muestra/oculta en el
mismo HTML sin recargar la página (igual que el POS).

---

## TAREA 1 — Auditoría previa

Antes de escribir código:

1. Lee `app/routers/panel.py` (o el archivo que define las rutas de `/panel/`)
2. Lee `app/templates/panel.html` (o el template actual del admin)
3. Lee `app/templates/pos.html` para entender el patrón sidebar + pestañas
4. Lee `app/models.py` para entender los modelos existentes
5. Identifica qué endpoints ya existen para no duplicarlos
6. Reporta qué archivos modificarás y cuáles crearás

---

## TAREA 2 — Estructura base del Panel Admin

### 2.1 Template principal

Refactoriza (o crea) `app/templates/admin.html` con:

**Sidebar izquierdo** — misma lógica visual que el POS:
```
FLORERÍA LUCY
[logo o ícono]

• VENTAS
• PENDIENTES      [badge con conteo en tiempo real]
• TRANSACCIONES
• CLIENTES
• PRODUCTOS
• CLAUDIA
• PÁGINA WEB
• FINANZAS
• ESTADÍSTICAS
• USUARIOS
• CONFIGURACIONES
```

**Layout:**
- Sidebar fijo izquierdo, ancho ~220px, fondo `#193a2c`, texto blanco
- Área de contenido derecha ocupa el resto del viewport
- Pestaña activa: fondo `#d4a843`, texto `#193a2c`, font-weight bold
- Al hacer click en pestaña: oculta todas las secciones, muestra solo la activa
- La URL refleja la pestaña activa con hash (`#ventas`, `#pendientes`, etc.)
- Al cargar la página, leer el hash y mostrar la pestaña correspondiente
- Default: mostrar `#ventas` si no hay hash

### 2.2 Ruta en FastAPI

En `app/routers/panel.py` (o donde corresponda):
- Asegúrate de que `GET /panel/` sirva `admin.html`
- La ruta debe estar protegida (verificar sesión/contraseña como el resto del panel)

---

## TAREA 3 — Pestaña VENTAS

**Descripción:** Misma funcionalidad que el POS completo.

**Implementación:**
- Incrusta el flujo de ventas del POS directamente en esta pestaña
- El admin puede crear cualquier tipo de pedido (mostrador, domicilio, pendiente, funeral)
- Mismas reglas de negocio: IVA, IEPS, hora específica +$80, link de pago +4%
- Mismos 4 modos de pedido, mismo carrito, mismo resumen
- Ticket digital y térmico disponibles
- Si el POS ya tiene este código como módulo reutilizable, referenciarlo;
  si no, copiar la lógica y adaptar al contexto admin

**Nota:** El admin puede ver y crear ventas de TODOS los operadores. En el selector
de "operador" o "cajero" aparece el nombre del admin como default.

---

## TAREA 4 — Pestaña PENDIENTES

**Descripción:** Igual que la sección "Pedidos pendientes" del POS, pero mostrando
pedidos de TODOS los canales y operadores.

**Implementación:**
- Tabla con filtros: por canal (POS/web/WhatsApp), por operador, por fecha
- Columnas: ID, cliente, canal, productos, total, estado, fecha, acciones
- Acciones: Ver detalle, Editar, Finalizar, Cancelar
- Badge en sidebar con conteo de pendientes (actualizar cada 30s)
- Incluir pedidos en estado: `pendiente`, `esperando_validacion`, `pendiente_pago`, `comprobante_recibido`

---

## TAREA 5 — Pestaña TRANSACCIONES

**Descripción:** Igual que Transacciones del POS, pero con vista global de todos los operadores.

**Implementación:**
- Resumen: total ventas hoy, semana, mes — con selector de período
- Tabla de transacciones con filtros: fecha, operador, canal, método de pago
- Botón "Ver ticket" en cada fila
- Corte de caja: generar corte del período seleccionado, exportar PDF
- Botón "Cancelar" con confirmación (solo admin puede cancelar transacciones cerradas)
- Totales desglosados: efectivo, tarjeta, transferencia, link de pago

---

## TAREA 6 — Pestaña CLIENTES

**Descripción:** Igual que Clientes del POS, con capacidades adicionales de admin.

**Implementación:**
- Búsqueda por nombre, teléfono, correo
- Ver historial completo de pedidos del cliente (todos los canales)
- Editar datos del cliente (nombre, teléfono, correo, dirección frecuente)
- Ver estadísticas del cliente: total gastado, número de pedidos, última compra
- Botón "Nuevo pedido" → lleva a pestaña Ventas con cliente prellenado
- Botón "WhatsApp" → abre wa.me con el número del cliente
- Exportar lista de clientes a CSV

---

## TAREA 7 — Pestaña PRODUCTOS

**Descripción:** CRUD completo de productos del catálogo.

### 7.1 Vista principal
- Tabla/grid de productos con:
  - Imagen (thumbnail), nombre, SKU, categoría, precio, stock, activo/inactivo
  - Filtros: por categoría, por estado (activo/inactivo), búsqueda por nombre/SKU
  - Ordenar por: nombre, precio, categoría
- Botón "Nuevo producto" → abre modal de creación

### 7.2 Modal de creación/edición
Campos:
```
- nombre*              (texto)
- descripcion          (textarea)
- sku                  (texto, auto-sugerido si está vacío)
- categoria_id*        (select — cargar desde BD)
- precio*              (número, 2 decimales)
- precio_mayoreo       (número, opcional)
- stock                (número entero)
- es_funeral           (checkbox — solo aparece en categorías tipo funeral)
- activo               (toggle on/off)
- imagen_url           (campo URL + botón "Subir imagen")
```

### 7.3 Subida de imagen
- Botón "Subir imagen" abre selector de archivo local
- Al seleccionar: subir a Cloudinary via endpoint del backend
- Al confirmar subida exitosa: poblar `imagen_url` con la URL resultante
- Mostrar preview de la imagen antes de guardar
- Cloudinary cloud: `ddku2wmpk`

### 7.4 Gestión de categorías
- Sub-sección o modal separado: lista de categorías
- CRUD de categorías: nombre, tipo (normal/funeral), orden de display
- No se puede eliminar una categoría que tenga productos activos

### 7.5 Activar / Desactivar masivo
- Checkboxes en la tabla para selección múltiple
- Botones: "Activar seleccionados", "Desactivar seleccionados"

### 7.6 Endpoints necesarios (crear si no existen)
```
GET    /api/admin/productos          → lista paginada con filtros
POST   /api/admin/productos          → crear producto
PUT    /api/admin/productos/{id}     → editar producto
DELETE /api/admin/productos/{id}     → soft delete (poner activo=false)
POST   /api/admin/productos/imagen   → subir imagen a Cloudinary
GET    /api/admin/categorias         → listar categorías
POST   /api/admin/categorias         → crear categoría
PUT    /api/admin/categorias/{id}    → editar categoría
DELETE /api/admin/categorias/{id}    → eliminar (si no tiene productos activos)
```

---

## TAREA 8 — Pestaña CLAUDIA

**Descripción:** Placeholder para integración futura del bot WhatsApp.

**Implementación:**
- Mostrar estado actual del bot (activo/inactivo) — leer de la tabla `configuracion_negocio`
  con clave `claudia_activa`
- Toggle para activar/desactivar Claudia
- Toggle para "Temporada alta" (todas las tarifas de envío = $99)
- Mostrar últimas 10 conversaciones activas (si el endpoint existe en el ecosistema)
- Botón "Abrir Claudia en nueva pestaña" → link al panel de Claudia en whatsapp-agentkit
- Sección de configuración básica:
  - Mensaje de bienvenida (editable, guardar en `configuracion_negocio`)
  - Horario de atención del bot
- Banner informativo: "Integración completa disponible en Fase 2"

---

## TAREA 9 — Pestaña PÁGINA WEB

**Descripción:** CMS para controlar el catálogo público en `/catalogo/`.

### 9.1 Sub-sección: Productos visibles
- Tabla de productos con toggle "Visible en catálogo web"
- Filtro rápido: "Solo visibles", "Solo ocultos", "Todos"
- El campo en BD es `visible_catalogo` (boolean) en la tabla de productos
  — si no existe, crear la migración
- Activar/desactivar masivo con checkboxes

### 9.2 Sub-sección: Banners
- Lista de banners activos con preview de imagen
- CRUD: subir imagen a Cloudinary, título, subtítulo, link destino, orden, activo/inactivo
- Tabla en BD: `banners_catalogo` (id, imagen_url, titulo, subtitulo, link, orden, activo)
  — si no existe, crear la migración
- Endpoints:
  ```
  GET    /api/admin/banners
  POST   /api/admin/banners
  PUT    /api/admin/banners/{id}
  DELETE /api/admin/banners/{id}
  POST   /api/admin/banners/imagen
  ```

### 9.3 Sub-sección: Textos del sitio
- Editor de textos clave del catálogo web, almacenados en `configuracion_negocio`:
  ```
  catalogo_titulo          → "Florería Lucy — Chihuahua"
  catalogo_subtitulo       → texto de bienvenida
  catalogo_whatsapp_msg    → mensaje pre-llenado al contactar por WA
  catalogo_footer          → texto del footer
  ```
- Inputs de texto/textarea simples, botón "Guardar" por campo o global

### 9.4 Sub-sección: Horarios y restricciones
- Mover/replicar la configuración de horarios especiales que ya existe en el panel
- Horario de corte por día de la semana (Lun–Sáb) para aceptar pedidos web
- Toggle "Modo temporada alta" (envíos a $99 todos los domicilios)
- Toggle "Abrir/cerrar catálogo web" temporalmente

### 9.5 Sub-sección: Código de descuento
- Lista de códigos activos con: código, descuento (% o $), usos, vigencia, activo
- CRUD de códigos de descuento
- Tabla en BD: `codigos_descuento` (id, codigo, tipo [porcentaje/monto], valor,
  usos_maximos, usos_actuales, fecha_inicio, fecha_fin, activo)
  — si no existe, crear la migración
- Endpoints:
  ```
  GET    /api/admin/descuentos
  POST   /api/admin/descuentos
  PUT    /api/admin/descuentos/{id}
  DELETE /api/admin/descuentos/{id}
  ```

---

## TAREA 10 — Pestaña FINANZAS

**Descripción:** Centro financiero consolidado.

### 10.1 Sub-sección: Resumen de ingresos
- Selector de período: hoy / esta semana / este mes / rango personalizado
- KPIs en cards:
  - Total ingresos del período
  - Desglose por método de pago (efectivo, tarjeta, transferencia, link)
  - Desglose por canal (POS, web, WhatsApp)
  - Número de transacciones
  - Ticket promedio
- Gráfica de barras: ingresos por día del período seleccionado
  (usar Chart.js desde CDN: `https://cdn.jsdelivr.net/npm/chart.js`)

### 10.2 Sub-sección: Egresos
- Formulario para registrar gasto manual:
  ```
  - fecha*
  - concepto*       (texto libre)
  - categoria       (select: insumos / nómina / servicios / mantenimiento / otro)
  - monto*
  - notas
  ```
- Tabla de egresos registrados con filtro por período y categoría
- Editar / eliminar egreso
- Tabla en BD: `egresos` (id, fecha, concepto, categoria, monto, notas, created_at)
  — si no existe, crear la migración
- Endpoints:
  ```
  GET    /api/admin/egresos
  POST   /api/admin/egresos
  PUT    /api/admin/egresos/{id}
  DELETE /api/admin/egresos/{id}
  ```

### 10.3 Sub-sección: Utilidad estimada
- Card con: Ingresos del período - Egresos del período = Utilidad bruta estimada
- Nota informativa: "Este cálculo es estimado y no incluye impuestos ni depreciaciones"
- Selector de período igual que en Resumen

### 10.4 Sub-sección: Cortes de caja históricos
- Tabla de todos los cortes de caja realizados desde el POS
- Filtro por fecha, por operador
- Botón "Ver detalle" → modal con el desglose del corte
- Botón "Descargar PDF" por corte

### 10.5 Exportar a Excel/CSV
- Botón "Exportar" disponible en cada sub-sección
- Exportar ingresos: genera CSV con todas las transacciones del período
- Exportar egresos: genera CSV con todos los egresos del período
- Exportar cortes: genera CSV con resumen de todos los cortes
- Usar `openpyxl` (ya debe estar instalado) para generar .xlsx
- Endpoint:
  ```
  GET /api/admin/finanzas/exportar?tipo=[ingresos|egresos|cortes]&desde=YYYY-MM-DD&hasta=YYYY-MM-DD
  ```
  — responde con file download (Content-Disposition: attachment)

---

## TAREA 11 — Pestaña ESTADÍSTICAS

**Descripción:** Dashboard de métricas del negocio con gráficas (Chart.js).

**Layout:** Grid de cards + gráficas. Selector de período global arriba (esta semana / este mes / este año).

### Cards KPI (fila superior):
- Ventas totales del período
- Número de pedidos
- Clientes nuevos vs recurrentes
- Producto más vendido

### Gráfica 1: Ventas por día
- Tipo: barras
- Datos: suma de ventas por día dentro del período

### Gráfica 2: Productos más vendidos
- Tipo: barras horizontales (top 10)
- Datos: productos ordenados por unidades vendidas

### Gráfica 3: Canal de venta
- Tipo: dona (doughnut)
- Segmentos: POS / Catálogo web / WhatsApp

### Gráfica 4: Zonas de entrega más activas
- Tipo: barras
- Datos: pedidos con domicilio agrupados por zona (morada/azul/verde/sin zona)

### Gráfica 5: Clientes nuevos vs recurrentes
- Tipo: línea
- Datos: por semana dentro del período

### Endpoints necesarios:
```
GET /api/admin/estadisticas/ventas-por-dia?desde=&hasta=
GET /api/admin/estadisticas/productos-top?desde=&hasta=&limit=10
GET /api/admin/estadisticas/canales?desde=&hasta=
GET /api/admin/estadisticas/zonas?desde=&hasta=
GET /api/admin/estadisticas/clientes?desde=&hasta=
```

**Usar Chart.js:** `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`
Colores de las gráficas: usar paleta de la marca (`#193a2c`, `#2d5a3d`, `#d4a843`, `#ef4444`, `#6b9e78`).

---

## TAREA 12 — Pestaña USUARIOS

**Descripción:** Gestión de accesos al sistema con roles.

### Roles disponibles:
```
admin       → acceso total (panel admin completo)
operador    → acceso solo al POS
florista    → acceso solo al panel taller
repartidor  → acceso solo al panel repartidor
```

### 12.1 Modelo en BD
Tabla `usuarios` (si no existe, crear migración):
```sql
id          SERIAL PRIMARY KEY
nombre      VARCHAR(100) NOT NULL
username    VARCHAR(50) UNIQUE NOT NULL
password_hash VARCHAR(255) NOT NULL
rol         VARCHAR(20) NOT NULL  -- admin | operador | florista | repartidor
activo      BOOLEAN DEFAULT true
created_at  TIMESTAMPTZ DEFAULT now()
```

### 12.2 Vista de usuarios
- Tabla: nombre, username, rol (badge de color), activo, fecha creación, acciones
- Colores de badges por rol:
  - admin → `#193a2c` (verde oscuro)
  - operador → `#2d5a3d` (verde medio)
  - florista → `#d4a843` (dorado)
  - repartidor → `#6b9e78` (verde claro)
- Acciones: Editar, Cambiar contraseña, Activar/Desactivar

### 12.3 Crear / Editar usuario
Modal con campos:
```
- nombre*
- username*
- contraseña* (solo en creación; en edición hay botón separado "Cambiar contraseña")
- rol*         (select)
- activo       (toggle)
```

### 12.4 Autenticación
- Hash de contraseñas con `bcrypt` (usar `passlib[bcrypt]`)
- Si ya existe sistema de sesiones en el panel, extenderlo para soportar roles
- Si no existe, implementar login básico con cookie de sesión:
  - `GET  /panel/login` → formulario de login
  - `POST /panel/login` → valida credenciales, crea cookie sesión
  - `GET  /panel/logout` → elimina cookie
  - Middleware que verifica sesión en todas las rutas `/panel/*`
  - El panel admin solo accesible con rol `admin`
  - Redirigir automáticamente al panel correcto según rol:
    - admin → `/panel/`
    - operador → `/panel/pos`
    - florista → `/panel/taller`
    - repartidor → `/panel/repartidor`

### 12.5 Endpoints:
```
GET    /api/admin/usuarios
POST   /api/admin/usuarios
PUT    /api/admin/usuarios/{id}
POST   /api/admin/usuarios/{id}/cambiar-password
DELETE /api/admin/usuarios/{id}   → soft delete (activo=false)
```

**IMPORTANTE:** Siempre debe existir al menos un usuario con rol `admin`.
No permitir desactivar o eliminar el último admin.

---

## TAREA 13 — Pestaña CONFIGURACIONES

**Descripción:** Configuración global del negocio. Ya existe la tabla `configuracion_negocio` — usarla.

### Claves a gestionar (todas en `configuracion_negocio`):

**Sección: Datos del negocio**
```
negocio_nombre          → "Florería Lucy"
negocio_direccion       → dirección física
negocio_telefono        → teléfono de contacto
negocio_whatsapp        → 5216143349392
negocio_email           → florerialucychihuahua@gmail.com
negocio_rfc             → RFC (para tickets)
```

**Sección: Datos bancarios (para pagos)**
```
banco_nombre            → nombre del banco
banco_titular           → nombre del titular
banco_cuenta            → número de cuenta
banco_clabe             → CLABE interbancaria
banco_concepto          → concepto sugerido para transferencia
```

**Sección: Ticket / POS**
```
ticket_mostrar_rfc      → true/false
ticket_mensaje_footer   → texto footer del ticket digital
ticket_termico_mensaje  → texto footer ticket térmico
pos_iva_default         → true/false (si IVA viene activado por default)
pos_ieps_default        → true/false
```

**Sección: WhatsApp / Claudia**
```
claudia_activa          → true/false
claudia_temporada_alta  → true/false
claudia_mensaje_bienvenida → texto
whatsapp_numero         → 5216143349392
```

**Sección: Catálogo web**
```
catalogo_activo                → true/false
catalogo_titulo
catalogo_subtitulo
catalogo_whatsapp_msg
catalogo_footer
catalogo_fecha_minima_dias     → 1 (número de días mínimo de anticipación)
```

### UI de configuraciones:
- Secciones con acordeón o tabs internos
- Cada campo con su label y input apropiado (text, textarea, toggle, number)
- Botón "Guardar" por sección (no por campo individual — salvo excepciones)
- Confirmación visual de guardado ("Guardado ✓" en verde por 2 segundos)
- Los campos de datos bancarios deben tener un ícono de ojo para mostrar/ocultar

### Endpoints:
```
GET  /api/admin/configuracion          → todas las claves (o por sección)
POST /api/admin/configuracion          → upsert de una o varias claves
     body: { clave: valor, ... }
```

---

## TAREA 14 — Migración y verificación de BD

Crear o verificar las siguientes tablas/columnas (usando Alembic o ejecutando
directamente con SQLAlchemy si el proyecto usa `create_all`):

1. `productos`: agregar columna `visible_catalogo BOOLEAN DEFAULT true` si no existe
2. `banners_catalogo`: crear si no existe (ver esquema en Tarea 9.2)
3. `codigos_descuento`: crear si no existe (ver esquema en Tarea 9.5)
4. `egresos`: crear si no existe (ver esquema en Tarea 10.2)
5. `usuarios`: crear si no existe (ver esquema en Tarea 12.1)
6. Agregar a `configuracion_negocio` todas las claves de Tarea 13 con valores
   default si no existen (usar INSERT ... ON CONFLICT DO NOTHING)

**Si el proyecto usa `Base.metadata.create_all()`**, agregar los nuevos modelos
y el sistema lo crea automáticamente al iniciar.

**Si usa Alembic**, generar la migración con:
```bash
alembic revision --autogenerate -m "panel_admin_completo"
alembic upgrade head
```

---

## TAREA 15 — Verificación final

Después de implementar todo:

1. Inicia el servidor: `uvicorn app.main:app --reload`
2. Verifica que `GET /panel/` carga el nuevo admin sin errores 500
3. Verifica que cada pestaña se activa correctamente con clicks en el sidebar
4. Verifica que el hash de URL funciona (#ventas, #productos, etc.)
5. Verifica que los endpoints de la API responden 200 con datos de prueba:
   - `GET /api/admin/productos`
   - `GET /api/admin/usuarios`
   - `GET /api/admin/configuracion`
   - `GET /api/admin/estadisticas/ventas-por-dia?desde=2026-03-01&hasta=2026-03-28`
6. Verifica que no hay imports rotos ni errores de Python
7. Si existe un test runner, ejecutar los tests existentes

---

## NOTAS IMPORTANTES

### Lo que NO debes hacer:
- No tocar `app/templates/pos.html` — solo léelo como referencia
- No cambiar la lógica de zonas KML ni de asignación de rutas
- No modificar el repo `whatsapp-agentkit`
- No hardcodear datos bancarios — siempre usar tabla `configuracion_negocio`
- No cambiar timezone a UTC — siempre `America/Chihuahua`
- IEPS nunca debe sumarse al total, solo desglosarse
- No mostrar productos sin `imagen_url` en catálogo público

### Prioridad de implementación:
Si necesitas priorizar por tiempo, el orden es:

**Crítico (antes del 10 de mayo):**
1. Estructura sidebar + navegación entre pestañas
2. VENTAS (reusar lógica del POS)
3. PENDIENTES + TRANSACCIONES (vistas globales)
4. PRODUCTOS (CRUD completo con imágenes)
5. PÁGINA WEB (visible_catalogo + horarios + descuentos)
6. CONFIGURACIONES (datos negocio + bancarios + tickets)
7. USUARIOS (login con roles)

**Importante pero puede ir en Fase 2:**
8. CLIENTES (ya funciona en POS, esta es la vista admin)
9. FINANZAS (egresos + exportar)
10. ESTADÍSTICAS (gráficas)
11. CLAUDIA (placeholder + toggles)

### Cambios quirúrgicos:
Modifica solo lo necesario. No reescribas archivos completos si puedes hacer
cambios quirúrgicos. Si un archivo es grande (>300 líneas), muestra qué secciones
modificarás antes de hacerlo.

---

## COMANDO PARA EJECUTAR

```
Lee el CLAUDE.md completo y ejecuta todas las tareas en orden
```

Con: `claude --dangerously-skip-permissions` (presionar 2 cuando pida aprobación)
