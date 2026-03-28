# CLAUDE.md — Documento maestro del proyecto Florería Lucy
> Este archivo es el puente entre sesiones de trabajo.
> Si estás en un chat nuevo, lee todo esto antes de hacer cualquier cosa.

---

## Quién es Fer y cómo trabajamos

Fernando Abaroa (Fer) opera dos negocios en Chihuahua, México:
- **Florería Lucy** — florería familiar fundada en 1988, actualmente en C. Sabino 610, Las Granjas
- **La Flore Chocolatier** — marca de chocolates artesanales bean-to-bar

Fer maneja casi todo solo con un asistente part-time. El objetivo es automatizar el negocio
para que para el 10 de mayo (Día de las Madres) Claudia reciba pedidos por WhatsApp
automáticamente y el ticket llegue al taller sin intervención humana.

### Dinámica de trabajo
- Claude Code lee el CLAUDE.md y ejecuta todas las tareas en orden
- Para evitar aprobaciones manuales: claude --dangerously-skip-permissions. Presionar 2 cuando pida aprobación.
- Cambios quirúrgicos — no reemplazar archivos completos sin necesidad

---

## URLs en producción

- **API:** https://floreria-lucy-ecosystem-production.up.railway.app
- **Catálogo:** https://floreria-lucy-ecosystem-production.up.railway.app/catalogo/
- **Panel admin:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/
- **POS:** https://floreria-lucy-ecosystem-production.up.railway.app/panel/pos

## Repos GitHub
- **Ecosistema:** github.com/faw1604/floreria-lucy-ecosystem ← aquí trabajamos
- **Claudia:** github.com/faw1604/whatsapp-agentkit ← NO TOCAR

---

## Stack técnico

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Railway)
- **Runtime:** Python 3.12 — Timezone: America/Chihuahua SIEMPRE
- **WhatsApp:** Whapi.cloud — WHAPI_TOKEN en variables de entorno
- **Imágenes:** Cloudinary (cloud: ddku2wmpk)

---

## Flujo del catálogo web (contexto crítico)

El catálogo web es un canal de venta donde el cliente navega, selecciona productos
y llena un formulario de pedido. A partir del formulario el flujo es idéntico al de WhatsApp.

**Flujo completo:**
1. Cliente navega el catálogo (modo tinder o modo clásico)
2. Agrega productos al carrito o hace super swipe
3. Va al formulario de pedido
4. Llena sus datos según el tipo de pedido
5. Sistema crea pedido en estado `esperando_validacion`
6. Cliente recibe WhatsApp de confirmación
7. Florista valida en taller → pasa a `pendiente_pago`
8. Claudia manda datos de pago al cliente
9. Cliente paga → manda comprobante
10. Fer confirma pago → pedido a producción

**Gestos del modo Tinder:**
- Swipe derecha → agrega al carrito
- Swipe izquierda → descarta
- **Super swipe (arriba)** → agrega al carrito + abre formulario directo sin pasar por carrito

**Nunca mandar datos de pago antes de validación del florista.**

---

## TAREAS PENDIENTES INMEDIATAS — Flujo catálogo web

### TAREA 1 — Super swipe en modo Tinder

En `app/catalogo.html`, modificar el gesto de super swipe (swipe hacia arriba):

Comportamiento actual: [verificar qué hace actualmente]
Comportamiento nuevo:
1. Al detectar swipe hacia arriba en una tarjeta de producto:
   - Agregar el producto al carrito (sessionStorage) igual que swipe derecha
   - Inmediatamente navegar al formulario de pedido (no mostrar pantalla de carrito)
   - El formulario se abre con ese producto ya en el carrito
2. Animación: la tarjeta sube y desaparece con un destello dorado (#d4a843)
   para indicar que es una acción especial distinta al swipe normal

---

### TAREA 2 — Botón "Ordenar ahora" en modo clásico

En `app/catalogo.html`, en el modo clásico (grid de productos):
- Cada tarjeta de producto ya tiene botón "Agregar al carrito"
- Agregar un segundo botón "Ordenar ahora" debajo:
  - Estilo: fondo #193a2c, texto dorado #d4a843
  - Al hacer click: agrega el producto al carrito + abre el formulario directo
  - Mismo comportamiento que el super swipe

---

### TAREA 3 — Formulario de pedido completo

En `app/catalogo.html`, rediseñar el formulario de pedido (la pantalla que aparece
al hacer checkout desde el carrito, super swipe u "Ordenar ahora").

El formulario reemplaza la pantalla de checkout existente.

**Paso 1 — Resumen del carrito:**
- Lista de productos seleccionados con imagen, nombre y precio
- Subtotal
- Botón "Modificar carrito" → regresa al catálogo
- Botón "Continuar →"

**Paso 2 — Tipo de pedido:**
- 3 botones grandes: Domicilio | Recoger | Funeral
- Botón "← Regresar"

**Paso 3 — Datos del pedido (según tipo):**

*Domicilio:*
- Nombre del cliente (obligatorio, mínimo 3 letras)
- Teléfono (obligatorio, selector código país +52 MX preseleccionado, +1 USA secundario)
- Correo electrónico (opcional)
- Nombre de quien recibe (obligatorio)
- Teléfono de quien recibe (obligatorio)
- Dirección de entrega (obligatorio) + botón "📍 Verificar en Maps"
  → abre Google Maps con la dirección en nueva pestaña
  → checkbox "✓ Dirección verificada" (manual)
- Dedicatoria (opcional, textarea)
- Notas para el repartidor (opcional)
- Fecha de entrega (date picker, mínimo mañana — no hoy)
- Horario: Mañana (9-2pm) | Tarde (2-6pm) | Noche (6-9pm) | Hora específica
  - Si hora específica: dropdown con opciones cada 30 min de 9am a 9pm
  - Nota: "Mínimo 2 horas de anticipación"

*Recoger:*
- Nombre del cliente (obligatorio)
- Teléfono (obligatorio)
- Correo (opcional)
- Fecha de recogida (date picker, mínimo mañana)
- Hora de recogida (dropdown cada 30 min, 9am a 9pm)

*Funeral:*
- Nombre del cliente que encarga (obligatorio)
- Teléfono (obligatorio)
- Correo (opcional)
- Búsqueda de funeraria con autocompletado (/funerarias/buscar)
- Nombre del fallecido (obligatorio)
- Sala (opcional)
- Texto de la banda (opcional)
- Dedicatoria (opcional)
- Fecha de entrega (date picker, obligatorio)
- Horario velación: "Ya inició" | "Inicia a las [hora]"
- Validar: todos los productos del carrito deben ser categoría funeral

**Paso 4 — Confirmación:**
- Resumen completo del pedido (productos + datos + tipo)
- Total estimado (subtotal de productos, sin envío — el envío se calcula después)
- Nota: "El costo de envío se confirmará junto con tu pedido"
- Botón "Confirmar pedido →" (verde #193a2c)
- Botón "← Regresar"

Al confirmar:
- POST /catalogo/pedido con todos los datos
- Si éxito: mostrar pantalla de confirmación (ver Tarea 4)
- Si error: mostrar mensaje de error visible

En cada paso hay botón "← Regresar" para volver al paso anterior.
Los datos llenados se preservan al regresar.

---

### TAREA 4 — Pantalla de confirmación post-pedido

En `app/catalogo.html`, pantalla que aparece después de confirmar el pedido:

```
🌸 ¡Pedido recibido!

Tu pedido FL-2026-XXXX está siendo revisado.

En cuanto verifiquemos disponibilidad te
contactaremos por WhatsApp al número
614 XXX XXXX con los datos para el pago.

¡Gracias por confiar en Florería Lucy!

[ Ver más productos ]    [ Ir al inicio ]
```

- Fondo crema #faf8f5, texto #193a2c
- Ícono de flor o checkmark en dorado
- Folio del pedido destacado
- Número de teléfono del cliente (últimos 4 dígitos visibles)
- Limpiar carrito (sessionStorage) al mostrar esta pantalla

---

### TAREA 5 — Endpoint POST /catalogo/pedido

En `app/routers/catalogo.py`, agregar endpoint público (sin auth):

```
POST /catalogo/pedido
```

Body:
```json
{
  "tipo": "domicilio|recoger|funeral",
  "items": [{"producto_id": 1, "cantidad": 1}],
  "cliente_nombre": "Ana García",
  "cliente_telefono": "526141234567",
  "cliente_email": "ana@email.com",
  "nombre_destinatario": "María García",
  "telefono_destinatario": "526141111111",
  "direccion_entrega": "Av. Tecnológico 4500",
  "dedicatoria": "Con amor",
  "notas_entrega": "Portón negro",
  "fecha_entrega": "2026-04-01",
  "horario_entrega": "manana|tarde|noche|hora_especifica",
  "hora_especifica": "14:00",
  "funeraria_id": null,
  "nombre_fallecido": null,
  "sala": null,
  "banda": null,
  "horario_velacion": null,
  "fecha_recoger": null
}
```

Lógica:
1. Validar campos obligatorios según tipo
2. Si tipo = funeral: validar que todos los productos son categoría funeral
3. Formatear teléfono del cliente (agregar 52 si no tiene)
4. Buscar o crear cliente en BD por teléfono
5. Generar folio FL-YYYY-XXXX
6. Crear pedido con:
   - estado = "esperando_validacion"
   - canal = "Web"
   - estado_florista = null (aún no llega al taller)
7. Enviar WhatsApp de confirmación al cliente vía Whapi:
   "Hola [nombre] 🌸 Recibimos tu pedido [folio] en Florería Lucy.
   En cuanto verifiquemos disponibilidad te contactamos con los datos para el pago.
   ¡Gracias por tu preferencia!"
8. Retornar `{ "ok": true, "folio": "FL-2026-XXXX" }`

Si el envío de WhatsApp falla: igual retornar éxito (el pedido se creó),
solo loguear el error de WhatsApp.

---

### TAREA 6 — Validación de funeral en carrito

En `app/catalogo.html`, cuando el cliente selecciona tipo "Funeral" en el formulario:
- Verificar que todos los productos del carrito son de categoría funeral
- Si hay productos que NO son de funeral: mostrar advertencia:
  "⚠ Solo puedes incluir arreglos de funeral en este tipo de pedido.
   Los siguientes productos serán removidos: [lista]"
- Con botón "Remover y continuar" o "Cancelar"
- Al remover: quitar esos productos del carrito y continuar con los de funeral

---

### NOTAS DE IMPLEMENTACIÓN

1. **Fecha mínima:** en el catálogo web la fecha mínima es MAÑANA (no hoy).
   El cliente web no puede pedir para el mismo día — ese flujo es solo para el POS.
2. **Teléfono del cliente:** es obligatorio porque es el canal de comunicación principal.
   Sin teléfono no se puede enviar el WhatsApp de confirmación.
3. **Preservar datos entre pasos:** usar un objeto JS `pedidoWeb` en memoria
   que acumule los datos de cada paso sin perderlos al navegar entre pasos.
4. **Carrito:** sigue usando sessionStorage igual que antes.
5. **El envío de WhatsApp usa WHAPI_TOKEN** ya configurado en Railway.
6. **No mostrar precio de envío** en el formulario web — solo el subtotal de productos.
   El envío se confirma cuando el florista valida el pedido.

---

## Roadmap pendiente

### Crítico para mayo 10:
1. ✅ Panel taller
2. ✅ Tickets
3. ✅ Panel repartidor con rutas
4. ✅ POS completo
5. ✅ Soporte flujo WhatsApp en ecosistema
6. **Flujo catálogo web ← ESTAMOS AQUÍ**
7. Conectar Claudia al ecosistema

### Post-mayo:
- Versión empleado y administrador del POS
- Sección Finanzas
- Migración 550 fotos desde Kyte
- Google Places Autocomplete
- Apagar Kyte

---

## LO QUE NUNCA SE DEBE HACER

- Tocar repo whatsapp-agentkit hasta que Fer lo indique
- Cambiar el número de WhatsApp: 5216143349392
- Hardcodear datos bancarios — usar tabla configuracion_negocio
- Mandar datos de pago sin validación previa del florista
- Cambiar timezone a UTC — siempre America/Chihuahua
- Mostrar productos sin imagen_url en catálogo
- Permitir productos no-funeral en pedidos de funeral
- Permitir fecha de entrega = hoy en pedidos web (mínimo mañana)
