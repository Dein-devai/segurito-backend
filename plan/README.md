# Plan Segurito WhatsApp — Hackathon MVP

> Documentación completa para que 4 personas desarrollen el MVP de Segurito vía WhatsApp en 8 horas, sin perder tiempo en discusiones arquitectónicas.

## Cómo usar este plan

1. **Lee `ARQUITECTURA.md`** primero (5 minutos). Explica la arquitectura general, decisiones ya tomadas, y cómo fluye la información.
2. **Identifica tu Track** (A, B, C, o D). Cada track tiene su archivo guía detallado.
3. **Mira los diagramas PlantUML** en `diagramas/`. Ábrelos en https://editor.plantuml.com/
4. **Revisa los templates** en `templates/` para entender los flujos conversacionales.
5. **Lee `RIESGOS.md`** para saber qué puede fallar y cómo mitigarlo.

## Estructura del plan

| Archivo/Carpeta | Para quién | Qué contiene |
|---|---|---|
| `ARQUITECTURA.md` | Todos | Documento maestro. Arquitectura, ADRs, flujos, identificadores. |
| `diagramas/` | Todos | 4 diagramas PlantUML: componentes, secuencia, estados, despliegue. |
| `TRACK-A-bridge.md` | Dev técnico principal (JS) | Especificación completa del bridge WhatsApp Node.js. |
| `TRACK-B-backend.md` | Dev técnico principal (Python) | Extensiones mínimas al backend existente. |
| `TRACK-C-documentacion.md` | Dev apoyo | Qué documentar, demo script, preguntas frecuentes. |
| `TRACK-D-testing.md` | Dev apoyo | Casos de prueba, mock backend, checklist de regresión. |
| `templates/` | Tracks A + B | JSON de templates: reclamo-cmf, consulta-rapida, derivación. |
| `demo/` | Track C | Script exacto de demo de 5 minutos + 20 preguntas de prueba. |
| `tests-whatsapp/` | Track D | 15 casos de prueba manuales + mock backend en Node.js. |
| `RIESGOS.md` | Todos | 10 riesgos principales y cómo mitigarlos. |

## Tracks de trabajo

### Track A — WhatsApp Bridge (Node.js)
**Responsable:** Dev técnico principal.
**Archivo guía:** `TRACK-A-bridge.md`
**Entregable:** Directorio `whatsapp-bridge/` funcional. `npm start` conecta WhatsApp y reenvía mensajes al backend.

### Track B — Extensiones Backend (Python)
**Responsable:** Dev técnico principal.
**Archivo guía:** `TRACK-B-backend.md`
**Entregable:** Backend acepta adjuntos opcionales y detecta sub-intenciones de reclamo CMF. Todos los tests existentes pasan.

### Track C — Documentación y Demo
**Responsable:** Dev apoyo.
**Archivo guía:** `TRACK-C-documentacion.md`
**Entregable:** Demo script de 5 minutos, 20 preguntas de prueba, flujo explicado, slide de arquitectura.

### Track D — Testing y QA
**Responsable:** Dev apoyo.
**Archivo guía:** `TRACK-D-testing.md`
**Entregable:** 15 casos de prueba manuales ejecutados, mock backend funcional, checklist de regresión.

## Dependencias entre tracks

```
Track B (Backend)  <-- puede empezar inmediatamente
Track A (Bridge)   <-- puede empezar inmediatamente
Track C (Docs)     <-- puede empezar inmediatamente
Track D (Testing)  <-- necesita A+B para test end-to-end, pero puede empezar con mock backend

Integración A+B  <-- punto crítico: bridge hace POST real al backend
```

## Diagramas PlantUML

Abre cada archivo `.puml` en https://editor.plantuml.com/ para ver el diagrama renderizado.

1. `diagramas/arquitectura-general.puml` — Vista de componentes del sistema completo.
2. `diagramas/secuencia-mensaje.puml` — Flujo de un mensaje end-to-end (WhatsApp → Bridge → Backend → WhatsApp).
3. `diagramas/maquina-estados-reclamo.puml` — Estados del template principal de reclamo CMF.
4. `diagramas/despliegue.puml` — Cómo corre todo localmente en una laptop.

## Cómo empezar mañana (orden sugerido)

| Hora | Actividad | Tracks |
|---|---|---|
| 07:00 | Daily 10 min: leer archivo guía de cada track | Todos |
| 07:15 | Track A crea `whatsapp-bridge/` y conecta WhatsApp | A |
| 07:15 | Track B extiende schemas y plugin CMF | B |
| 07:15 | Track C prepara datos de prueba | C |
| 07:15 | Track D configura mock backend | D |
| 08:30 | Tracks A+B integran: POST real del bridge al backend | A, B |
| 09:30 | Track C finaliza demo script | C |
| 10:00 | Track D ejecuta casos de prueba manuales | D |
| 11:00 | Iteración de bugs y fixes | Todos |
| 14:00 | Dry-run de demo completa | Todos |
| 15:00 | Presentación | Todos |

## Contacto y dudas

- Si una decisión arquitectónica no está clara → revisar `ARQUITECTURA.md` §ADR.
- Si un template no está claro → revisar `templates/reclamo-cmf.json`.
- Si un endpoint del backend no está claro → revisar `backend/api/routers/chat.py` en el código existente.
- Si hay un bug nuevo → documentarlo y asignar al track correspondiente.

---

**Fecha:** 2026-05-05
**Versión:** 1.0 — MVP Hackathon
