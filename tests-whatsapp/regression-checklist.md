# Regression Checklist — Segurito WhatsApp

Correr antes de cada demo o presentación. Tiempo estimado: 5 minutos.

## Infraestructura
- [ ] Backend responde `GET /health` con 200
- [ ] Bridge muestra "Client is ready" en logs
- [ ] QR no aparece (sesión persistida)

## Flujos críticos (5 min)
- [ ] TC-01: Reclamo banco completo
- [ ] TC-07: Derivación SERNAC
- [ ] TC-09: OUT_OF_SCOPE

## Calidad
- [ ] Ningún error en logs del bridge
- [ ] Ningún error en logs del backend
- [ ] Respuestas < 2000 caracteres