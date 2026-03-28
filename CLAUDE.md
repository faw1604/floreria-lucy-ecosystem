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
- **Para evitar aprobaciones manuales:** claude --dangerously-skip-permissions. Cuando pida aprobación presionar 2.

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
- **Claudia:** github.com/faw1604/whatsapp-agentkit ← NO TOCAR hasta indicación de Fer

---

## Stack técnico

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Railway)
- **Runtime:** Python 3.12
- **Timezone:** America/Chihuahua — SIEMPRE usar `TZ` de `app/core/config.py`, NUNCA UTC
- **Auth:** Cookie session SHA256
- **IA panel:** Claude claude-sonnet-4-6 (Anthropic) vía httpx
- **WhatsApp:** Whapi.cloud — WHAPI_TOKEN en variables de entorno
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

## Flujo de venta por WhatsApp (contexto crítico)

El flujo completo con dos puntos de control humano:

1. Cliente contacta → Claudia identifica necesidad, muestra catálogo
2. Cliente escoge → Claudia recopila todos los datos del pedido
3. Claudia crea pedido en ecosistema → estado `esperando_validacion`
   - Manda resumen al cliente por WhatsApp
   - Notifica al florista en panel del taller
4. Florista valida en pestaña "Nuevos pedidos" del taller:
   - Aceptar → pedido pasa a `pendiente_pago`
   - Modificar/Cambio → Claudia notifica al cliente, cliente acepta o rechaza
   - Rechazar → Claudia sugiere alternativas al cliente
5. Al pasar a `pendiente_pago` → Claudia manda ticket + datos de pago al cliente
   ⚠️ NUNCA mandar datos de pago antes de validación del florista
6. Cliente paga → manda comprobante por WhatsApp a Claudia
7. Claudia notifica a Fer: "Comprobante de pago pendiente de verificar"
   - Badge rojo aparece en POS (Pedidos pendientes) y Panel admin (sección Pagos)
8. Fer verifica en su banco → confirma pago en ecosistema
9. Pedido pasa a `pagado` → aparece en taller para producción

---

## Reglas de negocio críticas

### Horario (America/Chihuahua — NUNCA UTC)
- Lun–Vie: 9–19 | Sáb: 10–18 | Dom: 11–15
- Semana: domingo a sábado

### Zonas de envío
- Morada: $99 | Azul: $159 | Verde: $199
- Temporada alta: todas $99

### Impuestos
- IVA 16%: SE SUMA al subtotal
- IEPS 8%: ya implícito — solo SE DESGLOSA
- Hora específica: +$80
- Link de pago: +4% comisión

### Pedidos funeral
- Solo productos categoría funeral — sin excepción
- Sin ruta asignada

---

## Lo que está completado ✅

1. API FastAPI con 12 routers en producción
2. BD poblada (613 productos, 4,045 clientes, 15 funerarias)
3. Panel admin con asistente IA
4. Catálogo web completo
5. Panel del taller (5 pestañas, flujo de aprobación completo)
6. Tickets 80mm (3 variantes) + mini tickets
7. Panel del repartidor completo con rutas y zonas
8. Asignación automática de zona y ruta (shapely + KML reales)
9. POS completo (Ventas, Pedidos pendientes, Transacciones, Clientes, Claudia placeholder)
10. Ticket digital elegante + ticket térmico (Helvetica, mayúsculas, sin acentos)
11. Corte de caja en Transacciones
12. Endpoint POST /pedidos/desde-claudia (puente listo)
13. Soporte flujo WhatsApp en ecosistema (9 tareas completadas):
    - Nuevos estados (esperando_validacion, comprobante_recibido, pagado, rechazado)
    - Campos WhatsApp en Pedido + migración ejecutada en Railway
    - Endpoints: confirmar-pago, subir-comprobante, estado-para-claudia, webhook-estado
    - Tabla configuracion_negocio con CRUD en panel admin
    - Sección "Pagos pendientes" en panel admin con polling 60s
    - Pedidos comprobante_recibido visibles en POS con botón confirmar
    - Taller: soporte esperando_validacion, badge WhatsApp, aceptar→pendiente_pago

---

## TAREAS PENDIENTES INMEDIATAS — Soporte para flujo WhatsApp

### Contexto
Preparar el ecosistema para cuando Claudia se conecte. Todo el trabajo
es en el ecosistema (NO tocar whatsapp-agentkit todavía).

---

### TAREA 1 — Nuevos estados en el modelo Pedido

En `app/models/pedidos.py`, los nuevos valores de estado que el flujo de WhatsApp necesita:
- `esperando_validacion` — pedido creado por Claudia, esperando que el florista valide
- `pendiente_pago` — florista validó, esperando que el cliente pague (ya existe pero confirmar)
- `comprobante_recibido` — cliente mandó comprobante, Fer debe verificar
- `pagado` — Fer confirmó el pago, pasa a producción (ya existe pero confirmar)

Verificar que estos estados están contemplados en todos los filtros existentes
(taller, repartidor, POS) y agregarlos donde falten.

---

### TAREA 2 — Campos adicionales en Pedido para flujo WhatsApp

En `app/models/pedidos.py`, agregar campos:
```python
canal: Mapped[str] = mapped_column(default="POS")  # "POS" | "WhatsApp" | "Web"
comprobante_pago_url: Mapped[Optional[str]] = mapped_column(nullable=True)
comprobante_pago_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
pago_confirmado_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
pago_confirmado_por: Mapped[Optional[str]] = mapped_column(nullable=True)  # "admin"
nota_validacion: Mapped[Optional[str]] = mapped_column(nullable=True)  # nota del florista
```

Crear script `scripts/migrate_whatsapp_flow.py` con ALTER TABLE para los nuevos campos
y ejecutarlo contra Railway.

---

### TAREA 3 — Endpoint para confirmar pago (Fer)

En `app/routers/pedidos.py`, agregar:

```
POST /pedidos/{id}/confirmar-pago
```
- Requiere auth (solo admin)
- Cambia estado de `comprobante_recibido` a `pagado`
- Guarda `pago_confirmado_at = now()` y `pago_confirmado_por = "admin"`
- Retorna `{ "ok": true, "folio": "FL-2026-XXXX" }`

```
POST /pedidos/{id}/subir-comprobante
```
- Público (sin auth) — lo llama Claudia cuando el cliente manda el comprobante
- Requiere `CLAUDIA_API_KEY` en header `X-API-Key`
- Body: multipart/form-data con campo `comprobante` (imagen)
- Sube imagen a Cloudinary carpeta `comprobantes/`
- Guarda `comprobante_pago_url` y `comprobante_pago_at`
- Cambia estado a `comprobante_recibido`
- Retorna `{ "ok": true, "url": "..." }`

---

### TAREA 4 — Sección "Pagos pendientes" en panel admin

En `app/panel.html`, agregar una sección o pestaña "Pagos pendientes":
- Badge rojo con número de pedidos en estado `comprobante_recibido`
- Lista de pedidos con: folio, cliente, total, fecha comprobante, link al comprobante (imagen)
- Botón "✓ Confirmar pago" en cada pedido → POST /pedidos/{id}/confirmar-pago
- Al confirmar: pedido desaparece de la lista, badge se actualiza
- Polling cada 60 segundos para detectar nuevos comprobantes

---

### TAREA 5 — Sección "Pagos pendientes" en POS

En `app/pos.html`, en la sección "Pedidos pendientes":
- Filtrar también pedidos con estado `comprobante_recibido`
- Mostrarlos con badge especial "💳 Comprobante recibido" en naranja
- Botón "✓ Confirmar pago" en esos pedidos → POST /pedidos/{id}/confirmar-pago
- Badge rojo del sidebar debe incluir también los pedidos con comprobante recibido

---

### TAREA 6 — Pestaña "Nuevos pedidos" del taller — soporte para WhatsApp

En `app/taller.html`, pestaña "Nuevos pedidos":
- Los pedidos en estado `esperando_validacion` deben aparecer aquí
- Mostrar badge o etiqueta "WhatsApp" en los pedidos que vienen de ese canal
- Los botones Aceptar/Modificar/Cambio/Rechazar ya funcionan — verificar que
  al hacer Aceptar un pedido en `esperando_validacion` pase a `pendiente_pago`
- Al hacer Rechazar: cambiar estado a `rechazado` (nuevo estado)

---

### TAREA 7 — Endpoint de notificación para Claudia

En `app/routers/pedidos.py`, agregar:

```
GET /pedidos/{id}/estado-para-claudia
```
- Requiere `CLAUDIA_API_KEY` en header `X-API-Key`
- Retorna el estado actual del pedido y datos relevantes para que Claudia
  notifique al cliente:
```json
{
  "folio": "FL-2026-XXXX",
  "estado": "pendiente_pago",
  "estado_label": "Validado por el florista",
  "cliente_telefono": "526141234567",
  "total": 1299,
  "nota_validacion": "Solo tenemos rosas rojas disponibles",
  "datos_pago": {
    "banco": "BBVA",
    "cuenta": "...",
    "clabe": "...",
    "titular": "Fernando Abaroa"
  }
}
```
- Los datos de pago solo se incluyen cuando estado = `pendiente_pago`
- En cualquier otro estado, datos_pago = null

**IMPORTANTE:** Los datos bancarios se obtienen de la configuración del negocio
en BD (tabla `configuracion` o similar). NO hardcodear datos bancarios en el código.
Si no existe tabla de configuración, crearla con campos básicos del negocio.

---

### TAREA 8 — Tabla de configuración del negocio

Crear modelo `app/models/configuracion.py`:
```python
class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"
    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(unique=True)  # ej: "banco_nombre"
    valor: Mapped[str] = mapped_column()
    descripcion: Mapped[Optional[str]] = mapped_column(nullable=True)
```

Insertar valores iniciales con script:
- `banco_nombre`: "BBVA"
- `banco_titular`: "Fernando Abaroa"
- `banco_cuenta`: "[Fer completa esto]"
- `banco_clabe`: "[Fer completa esto]"
- `banco_concepto`: "Pedido Florería Lucy"
- `negocio_nombre`: "Florería Lucy"
- `negocio_direccion`: "C. Sabino 610, Las Granjas, Chihuahua"
- `negocio_telefono`: "6143349392"
- `negocio_email`: "florerialucychihuahua@gmail.com"

Agregar endpoint en panel admin para editar estos valores (CRUD simple).

---

### TAREA 9 — Webhook para Claudia (notificaciones de cambio de estado)

En `app/routers/pedidos.py`, agregar:

```
POST /pedidos/{id}/webhook-estado
```
- Requiere `CLAUDIA_API_KEY`
- Registra una URL de webhook que Claudia quiere recibir cuando el estado cambie
- Body: `{ "webhook_url": "https://..." }`

Cuando un pedido cambia de estado (en cualquier endpoint que modifique estado):
- Si tiene webhook_url registrada, hacer POST a esa URL con:
  `{ "folio": "FL-2026-XXXX", "estado_anterior": "X", "estado_nuevo": "Y" }`
- Fire-and-forget (no esperar respuesta, no bloquear)

---

## Roadmap pendiente

### Crítico para mayo 10:
1. ✅ Panel taller
2. ✅ Tickets
3. ✅ Panel repartidor con rutas
4. ✅ POS completo
5. ✅ Soporte flujo WhatsApp en ecosistema
6. **Conectar Claudia al ecosistema ← SIGUIENTE**
7. Flujo catálogo web

### Post-mayo:
- Versión empleado del POS
- Versión administrador del POS con Configuración
- Sección Finanzas
- Migración 550 fotos desde Kyte
- Google Places Autocomplete
- Apagar Kyte

---

## Decisiones críticas (no revertir)

- **Datos de pago NUNCA se mandan antes de validación del florista**
- **Semana:** domingo a sábado
- **IVA suma, IEPS solo desglosa**
- **Funerales:** solo productos categoría funeral, sin ruta
- **Tickets impresos:** Helvetica/Arial, mayúsculas, sin acentos ni ñ
- **Sin Google Geocoding API** sin aprobación de Fer

---

## LO QUE NUNCA SE DEBE HACER

- Tocar repo whatsapp-agentkit hasta que Fer lo indique
- Cambiar el número de WhatsApp: 5216143349392
- Hardcodear datos bancarios en el código — usar tabla configuracion_negocio
- Mandar datos de pago al cliente sin validación previa del florista
- Cambiar timezone a UTC — siempre America/Chihuahua
- Mostrar productos sin imagen_url en catálogo o POS
- Permitir productos no-funeral en pedidos de funeral
- IEPS sumando al total — solo desglosa
