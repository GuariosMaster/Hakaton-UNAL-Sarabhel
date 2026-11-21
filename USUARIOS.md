# Usuarios, roles e inicio de sesión

Cada persona entra con un **usuario único** y un **PIN de 4 dígitos**, en la app y en el dashboard.

## Roles

| Rol | Dónde trabaja | Qué puede hacer |
|---|---|---|
| **Administrador** | Puesto de mando (dashboard o app) | Todo lo del puesto de mando + **crear, editar, desactivar y eliminar usuarios**, cambiar roles, asignar equipos y reiniciar PIN. |
| **Puesto de mando** | Dashboard o app en modo Mando | Ver mapa, alertas, mensajes y energía; **gestionar alertas** (atender, asignar equipo, notas); enviar mensajes a los albergues; exportar CSV. |
| **Socorrista** | App en modo Campo | SOS, mensajes y mapa; pestaña **Asignadas** con las alertas que el puesto de mando asignó a **su equipo**, que puede marcar como *En camino* / *Atendida* con una nota. |
| **Sin cuenta** | App (botón 🆘 *Emergencia*) | SOS, mensajes rápidos, chat y mapa a través del Wi‑Fi del albergue. **Pedir ayuda nunca exige cuenta.** |

El portal Wi‑Fi de cada nodo de albergue sigue siendo abierto, por la misma razón.

## Cómo se obtiene una cuenta

**Cada persona crea la suya desde la app**: pantalla de inicio → **Crear cuenta** → nombre, usuario
(se sugiere a partir del nombre), PIN de 4 dígitos repetido y equipo opcional → entra de inmediato.

- Las cuentas creadas así son siempre de **socorrista**: nadie puede darse a sí mismo permisos de
  puesto de mando o administrador. El administrador sube el rol de quien lo necesite.
- Para crear la cuenta el teléfono debe estar conectado al **Wi‑Fi del puesto de mando** (la pantalla
  de inicio muestra si lo encuentra). Después ya puede entrar sin conexión.
- El administrador puede cerrar el registro con `REGISTRATION_OPEN=0`; entonces solo él crea cuentas.

## Primer uso del sistema

1. Al iniciar el servidor por primera vez se crea el usuario **`admin` con PIN `1234`**
   (o el valor de la variable `ADMIN_PIN`). Mientras no se cambie, la pantalla de inicio lo recuerda.
2. Entrar con ese usuario → la app/dashboard pide **cambiar el PIN**.
3. Dar el rol **Puesto de mando** a quienes coordinan (dashboard: **👥 Usuarios**; app: **Ajustes →
   Administrar usuarios**). También se pueden crear cuentas allí con un PIN inicial.
4. A los socorristas asignarles un **equipo** (p. ej. “Bomberos 2”) si no lo pusieron al registrarse:
   es lo que conecta las alertas que asigna el puesto de mando con su pestaña *Asignadas*.

## Seguridad del PIN

Un PIN de 4 dígitos tiene solo 10.000 combinaciones, así que:

- El servidor guarda un **PBKDF2-SHA256 con sal** del PIN, nunca el PIN.
- Tras **5 intentos fallidos** el usuario queda **bloqueado 5 minutos**.
- Las sesiones **vencen a las 12 h** y se cierran al desactivar un usuario o reiniciar su PIN.
- No se aceptan PIN obvios (0000, 1111, 1234…) al cambiarlo.
- La app recuerda la sesión, así que no hay que escribir el PIN cada vez que se abre.

## Entrar sin conexión (socorristas en campo)

En campo el teléfono solo ve el Wi‑Fi del albergue, no el servidor. Por eso, **la primera vez hay que
entrar conectado al puesto de mando**; desde entonces el teléfono guarda una verificación local del
PIN (PBKDF2 con sal propia, nunca el PIN) y permite entrar sin conexión. En ese modo funcionan SOS,
mensajes y mapa; *Asignadas* y la administración necesitan volver a entrar con conexión.

## API (para integraciones)

| Método | Ruta | Rol |
|---|---|---|
| POST | `/api/auth/login` `{usuario, pin}` → `{token, rol, …}` | público |
| POST | `/api/auth/registro` `{usuario, nombre, pin, equipo?}` → crea un socorrista y entra | público (si el registro está abierto) |
| GET | `/api/auth/estado` → `{registro, admin_inicial}` | público |
| GET | `/api/auth/me` · POST `/api/auth/logout` · POST `/api/auth/pin` `{actual, nuevo}` | cualquiera |
| GET/POST | `/api/users` · PATCH/DELETE `/api/users/{usuario}` | admin |
| PATCH | `/api/alerts/{id}` | mando/admin; socorrista solo estado y nota de las alertas de su equipo |
| POST | `/api/send` · GET `/api/export/*.csv` | mando/admin |
| GET | `/api/nodes`, `/api/messages`, `/api/alerts`, `/api/stream`, `/api/device/*` | cualquiera con sesión |

El token va en `Authorization: Bearer <token>`; en enlaces y en `/api/stream` (SSE) va como `?token=`.
