Tu aplicación no sería simplemente un mapa de emergencias: sería una **plataforma colaborativa de información y coordinación para la respuesta ante desastres, conectada mediante una red Mesh comunitaria**.

Además, hay un aspecto diferenciador: tus nodos estarán distribuidos entre comunidades, socorristas, albergues temporales y Puestos de Mando Unificado (PMU). Por tanto, no todos los reportes tendrán el mismo contexto ni todos los usuarios tendrán las mismas capacidades de actuación.

Te propongo la siguiente arquitectura funcional.

# 1. Concepto general del sistema

El objetivo sería que cualquier persona con un nodo pueda reportar una situación y que el sistema:

1. Reciba el reporte mediante la red Mesh.
2. Identifique su ubicación y procedencia.
3. Clasifique el tipo de desastre o afectación.
4. Identifique la situación y sus necesidades.
5. Determine una prioridad preliminar.
6. Muestre el incidente en un mapa.
7. Permita que los organismos y personas autorizadas conozcan la situación.
8. Registre su atención y evolución.

La IA funcionaría como un agente de análisis de información y apoyo a la toma de decisiones.

## 2. Los cuatro tipos de participantes

Considero importante diferenciar los participantes de la red.

| Participante | Función | Qué puede reportar |
| --- | --- | --- |
| Comunidad | Informar situaciones locales | Personas atrapadas, inundaciones, daños |
| Socorristas | Informar operaciones | Rescates, heridos, evacuaciones |
| Albergues temporales | Informar necesidades | Agua, alimentos, medicamentos, capacidad |
| PMU | Coordinar y consolidar información | Incidentes confirmados, recursos y necesidades |

Esto implica que cada nodo debería tener un atributo `node_type`.

Por ejemplo:

json

```
{
  "node_id": 15,
  "node_type": "COMMUNITY",
  "organization": null,
  "location": {
    "latitude": 5.068,
    "longitude": -75.517
  }
}
```

Para un albergue:

json

```
{
  "node_id": 28,
  "node_type": "SHELTER",
  "organization": "Albergue Norte",
  "location": {
    "latitude": 5.071,
    "longitude": -75.520
  }
}
```

El tipo de participante aporta contexto, pero no debe determinar automáticamente la credibilidad del reporte. Un reporte comunitario puede ser tan importante como uno institucional.

# 3. Clasificación general de situaciones

Ampliaría las ocho categorías anteriores para cubrir tanto el desastre como sus consecuencias.

| Código | Categoría | Ejemplos |
| --- | --- | --- |
| RES | Rescate | Personas atrapadas, desaparecidas, aisladas |
| SAL | Salud | Heridos, enfermedades, medicamentos |
| ABA | Abastecimiento | Agua, alimentos, ropa |
| INF | Infraestructura | Viviendas, puentes, carreteras |
| NAT | Fenómenos naturales | Sismos, inundaciones, deslizamientos |
| SER | Servicios básicos | Electricidad, acueducto, gas |
| ALB | Albergues | Capacidad, ocupación, necesidades |
| COM | Comunicaciones | Zonas incomunicadas, pérdida de señal |
| PRO | Protección | Población vulnerable, evacuaciones |
| AMB | Ambiental | Contaminación, residuos, afectación ambiental |
| LOG | Logística | Transporte, equipos, recursos disponibles |

Una ventaja de esta organización es que permite identificar no solamente qué desastre ocurrió, sino también qué consecuencias está generando.

Por ejemplo:

Un terremoto puede producir simultáneamente:

- Viviendas colapsadas.
- Personas atrapadas.
- Heridos.
- Cortes de electricidad.
- Interrupción del suministro de agua.
- Comunidades incomunicadas.
- Necesidad de albergues.

Todos estos reportes pueden relacionarse con un mismo evento principal.

# 4. Sistema de prioridades

Mantendría los tres niveles que planteaste.

| Prioridad | Color | Descripción |
| --- | --- | --- |
| Alta | 🔴 | Riesgo inmediato para la vida o seguridad |
| Media | 🟡 | Afectación importante que requiere atención prioritaria |
| Baja | 🟢 | Necesidad o afectación sin riesgo inmediato identificado |

Añadiría un cuarto estado que no representa prioridad:

**⚪ Pendiente de clasificación.**

Esto es importante porque no todos los reportes tendrán suficiente información.

Por ejemplo:

| Reporte | Clasificación | Prioridad preliminar |
| --- | --- | --- |
| Persona atrapada bajo escombros | RES | Alta |
| Vivienda inundada con personas en su interior | NAT/RES | Alta |
| Albergue sin agua potable | ALB/ABA | Según disponibilidad y población afectada |
| Vía secundaria bloqueada | INF | Media |
| Vivienda con daños menores | INF | Baja |
| Zona sin comunicación | COM | Por evaluar según aislamiento y riesgo |

Las prioridades son ejemplos de diseño, no instrucciones de despacho. La asignación final debe seguir criterios validados por las autoridades de respuesta.

# 5. Cómo debería funcionar el agente de IA

Aquí es donde tu servidor local adquiere importancia.

Yo dividiría el agente en cinco funciones.

### Función 1. Clasificación semántica

Recibe el reporte y determina:

- Categoría.
- Subcategoría.
- Tipo de desastre.
- Daño ocasionado.
- Necesidad identificada.

### Función 2. Evaluación de prioridad

Analiza:

- Riesgo para la vida.
- Gravedad.
- Urgencia.
- Personas afectadas.
- Vulnerabilidad.
- Información disponible.

La IA propone una clasificación y el motor de reglas determina la prioridad operativa.

### Función 3. Correlación de reportes

Imagina que tienes estos reportes:

text

```
Nodo 001: Se cayó una vivienda.
Nodo 002: Hay personas atrapadas.
Nodo 003: Se escuchan gritos debajo de los escombros.
Nodo 004: Hay tres personas heridas.
```

El sistema podría identificar que posiblemente pertenecen al mismo incidente.

En lugar de mostrar cuatro incidentes independientes, podría crear un incidente principal con cuatro reportes asociados.

### Función 4. Análisis de necesidades

Aquí los albergues y PMU cobran especial importancia.

Por ejemplo:

text

```
Albergue Norte:
- Capacidad: 100 personas.
- Ocupación: 85 personas.
- Agua disponible: insuficiente.
- Alimentos: disponibles.
- Medicamentos: necesidad pendiente.
```

La IA podría identificar necesidades y relacionarlas con los recursos disponibles en otros puntos.

### Función 5. Generación de alertas

El sistema podría detectar:

- Incremento de reportes en una zona.
- Varias comunidades incomunicadas.
- Necesidades repetidas de agua.
- Saturación de albergues.
- Nuevas afectaciones en una infraestructura.

La IA generaría alertas para revisión de los operadores.

# 6. Diseño del mapa de la aplicación

Esta sería una de las pantallas principales, adaptar el mapa que se tiene en la app.

El mapa tendría cuatro capas principales:

| Capa | Información |
| --- | --- |
| Incidentes | Reportes de emergencias |
| Socorristas | Ubicación y disponibilidad reportada |
| Albergues | Capacidad, ocupación y necesidades |
| PMU | Puestos de coordinación |

Cada incidente tendría un marcador según su prioridad.

Al seleccionar un marcador se abriría una ficha:

text

```
INCIDENTE #000152

Categoría: RESCATE
Subcategoría: Persona atrapada
Prioridad: ALTA

Ubicación:
Sector Norte

Reportado por:
Nodo comunitario 015

Hora:
14:35

Estado:
Pendiente de verificación

Reportes relacionados:
3

Última actualización:
14:42
```

Importante: mostrar la ubicación de socorristas y recursos debe estar sujeto a permisos, protección de datos y seguridad operacional. No todos los usuarios necesitan ver todas las ubicaciones.

# 7. Arquitectura tecnológica que propongo

Para tu proyecto utilizaría:

| Componente | Tecnología |
| --- | --- |
| Nodos | ESP32-S3/C6 |
| Radio | RFM69HCW 915 MHz |
| Red | Mesh multisalto |
| Gateway | ESP32 + Wi-Fi |
| Backend | Python + FastAPI |
| Base de datos | PostgreSQL + PostGIS |
| Mensajería interna | MQTT |
| IA local | Ollama |
| Interfaz | React |
| Mapas | Leaflet + OpenStreetMap |

La arquitectura sería:

text

```
       COMUNIDADES       SOCORRISTAS
            |                |
            +-------+--------+
                    |
                 RED MESH
                    |
             +------+------+
             |             |
          ALBERGUE        PMU
             |             |
             +------+------+
                    |
                 GATEWAY
                    |
              SERVIDOR LOCAL
                    |
       +------------+-------------+
       |            |             |
   PostgreSQL    FastAPI       Ollama
   + PostGIS        |             |
       |            |             |
       +------------+-------------+
                    |
             MOTOR DE REGLAS
                    |
              DASHBOARD GIS
                    |
             MAPA DE EVENTOS
```

# 8. Algo que debemos resolver: el modelo de información

Mi recomendación es que no guardes cada reporte como si fuera un incidente independiente.

Debes manejar tres entidades:

- **Evento:** el desastre principal, por ejemplo, un terremoto.
- **Incidente:** una afectación específica, por ejemplo, una vivienda colapsada.
- **Reporte:** el mensaje enviado por un nodo que describe una situación.

Ejemplo:

text

```
EVENTO: Terremoto
   |
   +--- INCIDENTE 001: Vivienda colapsada
   |       |
   |       +--- Reporte nodo 001
   |       +--- Reporte nodo 005
   |
   +--- INCIDENTE 002: Falta de agua
   |       |
   |       +--- Reporte albergue 003
   |
   +--- INCIDENTE 003: Vía bloqueada
           |
           +--- Reporte socorrista 007
```

Esta estructura permitirá consolidar información, evitar duplicados y tener una visión mucho más completa de la emergencia.

---

# 9. Una decisión importante sobre el funcionamiento del sistema

Quiero proponerte una distinción que considero esencial para tu proyecto.

No todos los usuarios deberían tener las mismas funciones dentro de la aplicación.

| Perfil | Consultar mapa | Reportar | Validar | Gestionar incidentes |
| --- | --- | --- | --- | --- |
| Comunidad | Sí | Sí | Confirmación comunitaria | No |
| Socorrista | Sí | Sí | Según autorización | Según rol |
| Albergue | Sí | Sí | Sobre su albergue | Sobre sus necesidades |
| PMU | Sí | Sí | Sí | Sí |
| Administrador | Sí | Sí | Sí | Sí |

Los reportes de cualquier usuario pueden aparecer inicialmente en el mapa, identificados como no verificados. Los PMU y los responsables autorizados podrán confirmar, corregir o cerrar incidentes.

La IA no debe convertir automáticamente un reporte en una emergencia confirmada.

# 10. Documentos de referencia para fundamentar el proyecto

Para que esta arquitectura tenga sustento técnico y pueda presentarse académica o institucionalmente, utilizaría:

- Guía EDAN de la OPS/OMS — Evaluación de daños y necesidades.
- EDAN de la Organización Panamericana de la Salud — Evaluación de salud, agua, saneamiento y albergues.
- Guía metodológica de respuesta municipal de la UNGRD — Organización de la respuesta territorial.
- Manual de logística para atención de emergencias de la UNGRD — Coordinación de recursos y respuesta.

## Mi recomendación para continuar

Antes de seleccionar Qwen, Llama o cualquier otro modelo, definiría el **catálogo maestro de eventos, incidentes, subcategorías, necesidades y prioridades**.

Ese catálogo será el lenguaje común entre:

- El firmware de los ESP32.
- Los paquetes de la red Mesh.
- El servidor.
- El agente de IA.
- La base de datos.
- El mapa de la aplicación.

Y hay una decisión que quisiera dejar planteada para el siguiente paso:

**¿Quieres que el sistema permita que las personas que tienen nodos también puedan ofrecer ayuda voluntaria?**

Por ejemplo, que alguien pueda reportar que tiene un vehículo disponible, medicamentos, alimentos, herramientas o conocimientos de primeros auxilios.

Esto permitiría que la aplicación no solamente identifique dónde están los problemas, sino también dónde existen recursos comunitarios para responder a las necesidades.