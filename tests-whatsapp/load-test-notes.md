# Load Test — Notas

## Scope

No es un test de carga real (no se cuenta con infraestructura para miles de usuarios).
Es una validación de que el sistema no se cae con uso concurrente moderado.

## Escenario

1. Levantar backend: `uvicorn main:app --host 127.0.0.1 --port 8000`
2. Levantar bridge: `npm start` (en `whatsapp-bridge/`)
3. Desde 3 teléfonos diferentes (o 3 cuentas WhatsApp distintas), iniciar conversaciones simultáneas.
4. Cada uno envía 5 mensajes en 2 minutos.

## Criterios de aceptación

- [ ] Ningún mensaje se pierde (el bridge los recibe todos).
- [ ] Respuestas llegan en < 10 segundos cada una.
- [ ] No hay errores HTTP 500 en el backend.
- [ ] Las conversaciones no se mezclan (usuario A no recibe respuesta de usuario B).
- [ ] El `ConversationStore` mantiene historiales separados (verificar `conversation_id` en logs).

## Limitaciones conocidas

- **ConversationStore in-memory**: si el backend se reinicia, se pierden las conversaciones activas. Los usuarios deberán iniciar nueva sesión.
- **Rate limiter por IP**: si todos los teléfonos usan la misma red WiFi (misma IP pública), el rate limiter de IP puede afectar. Mitigación: usar `conversation_id` en cada petición para que el rate limit opere por conversación.
- **Memoria de Chromium**: `whatsapp-web.js` lanza un proceso Chromium por sesión. En laptops con poca RAM puede ser lento. Reiniciar el bridge si hay degradación.

## Comandos útiles de monitoreo

```bash
# Ver logs del backend en tiempo real
uvicorn main:app --reload --log-level info

# Ver métricas del backend
curl http://localhost:8000/metrics

# Ver estado del rate limiter (si se expone)
curl http://localhost:8000/health
```
