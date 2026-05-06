# Preguntas Frecuentes para Demo y Validación

20 preguntas curadas para probar el MVP, con respuestas esperadas y organismos destino.

| # | Pregunta del usuario | Organismo esperado | Intención esperada | Keywords que debe mencionar la respuesta |
|---|---|---|---|---|
| 1 | "me cobraron de más en mi tarjeta de crédito" | CMF | RECLAMO_PRODUCTO | Circular CMF, Ley 19.496, reclamar al banco, 10 días hábiles |
| 2 | "mi AFP no me quiere devolver los aportes" | CMF | RECLAMO_SERVICIO | CMF, AFP, cotización, plazo |
| 3 | "mi seguro no me pagó el siniestro del auto" | CMF | RECLAMO_SERVICIO | aseguradora, póliza, CMF Online, plazo 30 días |
| 4 | "una mutuaria me cobra intereses abusivos" | CMF | RECLAMO_PRODUCTO | mutuaria, interés máximo, DFL 3, superintendencia |
| 5 | "mi corredora de bolsa me hizo perder plata" | CMF | RECLAMO_SERVICIO | corredora, riesgo, carta de adhesión, CMF |
| 6 | "el banco no me quiere dar mi certificado de deuda" | CMF | TRAMITE | certificado de deudas, CMF, trámite, documento |
| 7 | "¿cómo puedo saber si mi deuda está en Dicom?" | CMF | CONSULTA | informe de deudas, CMF, consulta gratuita |
| 8 | "me vendieron un celular defectuoso en el retail" | SERNAC | CONSULTA | SERNAC, garantía legal, 3 meses, Ley 19.496 |
| 9 | "una tienda no me quiere cambiar un producto" | SERNAC | CONSULTA | SERNAC, derecho de retracto, 10 días |
| 10 | "no me devolvieron el IVA de una compra" | SII | CONSULTA | SII, boleta electrónica, devolución IVA |
| 11 | "¿cómo declaro renta si soy independiente?" | SII | CONSULTA | SII, boleta honorarios, operación renta |
| 12 | "mi empleador no me pagó la indemnización" | SUSESO / Tribunales | DERIVACION | SUSESO, tribunales, demanda laboral |
| 13 | "me despidieron injustificadamente" | SUSESO / Tribunales | DERIVACION | SUSESO, tutela laboral, demanda |
| 14 | "me llegó una carta de notificación de cobranza que no es mía" | CMF / SERNAC | RECLAMO_INFORMACION | identidad, fraude, PDI, CMF |
| 15 | "¿es seguro invertir en criptomonedas?" | CMF | CONSULTA | CMF, criptoactivos, riesgo, no regulado |
| 16 | "alguien me llamó diciendo que soy ganador de un premio y deposite" | ALERTA | ALERTA | no entregues datos, fraude, PDI 134, Fiscalía |
| 17 | "quiero pedir una pizza" | OUT_OF_SCOPE | OUT_OF_SCOPE | delimitación, no puedo ayudar |
| 18 | "mi banco me cobra un seguro que no contraté" | CMF | RECLAMO_PRODUCTO | seguro de desgravamen, cobro indebido, CMF |
| 19 | "¿qué hago si perdí mi clave de la CMF Online?" | CMF | TRAMITE | CMF Online, recuperar clave, claveúnica |
| 20 | "tengo una duda sobre mi crédito hipotecario" | CMF | CONSULTA | hipotecario, cuota, renegociación, CMF |

## Cómo usar esta tabla

1. **Track C** usa esto para preparar el `script-demo.md`.
2. **Track D** usa esto como casos de prueba manuales (TC-01 a TC-15 principales, los demás opcionales).
3. **Track A** usa esto para probar que el bridge enruta correctamente.
4. **Track B** usa esto para validar que el backend detecta el organismo correcto.

## Notas

- Las respuestas exactas varían según el LLM, pero las **keywords** deben aparecer.
- Si una respuesta no menciona la normativa correcta, es un bug del plugin o del prompt.
- El caso 16 (ALERTA) debe detener la conversación inmediatamente sin tool-loop.
