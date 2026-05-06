# Regression Checklist — Segurito WhatsApp

Ejecutar antes de cada demo o presentación. Tiempo estimado: 5 minutos.

## Infraestructura

- [ ] Backend responde `GET /health` con 200
- [ ] Bridge muestra "Client is ready!" en logs
- [ ] QR **no** aparece (sesión persistida con LocalAuth)

## Flujos críticos (5 min)

- [ ] **TC-01**: Reclamo banco completo (entidad → nombre → descripción → saltar evidencia → plazo → reclamo previo → confirmar)
- [ ] **TC-07**: Derivación SERNAC ("me vendieron un celular defectuoso")
- [ ] **TC-09**: OUT_OF_SCOPE ("quiero pedir una pizza")
- [ ] **TC-10**: ALERTA fraude ("me llamaron diciendo que gané un premio")

## Calidad

- [ ] Sin errores 500 en logs del backend
- [ ] Sin errores no capturados en logs del bridge
- [ ] Respuestas < 2 000 caracteres
- [ ] Todos los pytest pasan (`pytest -q --tb=short`)
