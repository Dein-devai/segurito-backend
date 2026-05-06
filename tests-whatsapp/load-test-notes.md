# Load Test — Notas

## Scope
No es un test de carga real (no tenemos infraestructura para miles de usuarios).
Es una validación de que no se cae con uso concurrente moderado.

## Escenario
1. Levantar backend y bridge.
2. Desde 3 teléfonos diferentes, iniciar conversaciones simultáneas.
3. Cada uno envía 5 mensajes en 2 minutos.

## Criterios de aceptación
- Ningún mensaje se pierde.
- Respuestas llegan en < 10 segundos cada una.
- No hay errores 500 en backend.
- Conversaciones no se mezclan (usuario A no recibe respuesta de usuario B).

## Limitaciones conocidas
- ConversationStore del backend es in-memory. Si el backend se reinicia, se pierden conversaciones activas.
- Rate limiter por IP puede afectar si todos los teléfonos usan la misma red WiFi (misma IP pública).
  - Mitigación: usar `conversation_id` para rate limit por conversación, no solo por IP.