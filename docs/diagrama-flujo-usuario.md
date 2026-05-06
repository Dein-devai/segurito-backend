# Diagrama de Flujo del Usuario

Flujo completo desde la perspectiva del ciudadano que usa Segurito por WhatsApp.

## Diagrama general

```mermaid
graph TD
    A[📱 Usuario abre WhatsApp] --> B[Escribe al número de Segurito]
    B --> C{¿Qué tipo de mensaje?}

    C -->|Reclamo financiero| D[🤖 Detecta intención RECLAMO]
    C -->|Consulta general| E[🤖 Responde con información]
    C -->|Fuera de alcance| F[🤖 Deriva o delimita]

    D --> G[Inicia template guiado]
    G --> H[Pregunta: tipo de entidad]
    H --> I[Pregunta: nombre de entidad]
    I --> J[Pregunta: descripción del problema]
    J --> K{¿Tiene documentos?}
    K -->|Sí| L[Adjunta documentos]
    K -->|No| M[Escribe 'saltar']
    L --> N[Pregunta: plazo del problema]
    M --> N
    N --> O[Pregunta: ¿ya reclamaste?]
    O --> P[Muestra resumen del caso]
    P --> Q{¿Confirma?}
    Q -->|Sí| R[🔍 Analiza con normativa]
    Q -->|No| S[Modifica respuesta]
    S --> P

    R --> T[📋 Diagnóstico + Pasos a seguir]
    T --> U[✅ Fin del reclamo guiado]

    E --> V{¿Organismo es CMF?}
    V -->|Sí| W[Información normativa CMF]
    V -->|No| X[Deriva a organismo correcto]
    W --> U
    X --> U

    F --> Y{¿Es alerta de fraude?}
    Y -->|Sí| Z[🚨 Alerta inmediata + PDI 134]
    Y -->|No| AA[Mensaje de delimitación de alcance]
    Z --> U
    AA --> U
```

## Flujo detallado de reclamo CMF

```mermaid
stateDiagram-v2
    [*] --> Bienvenida: Mensaje del usuario

    Bienvenida --> DetectarIntencion: Haiku clasifica
    DetectarIntencion --> TemplateReclamo: RECLAMO + organismo = CMF
    DetectarIntencion --> ConsultaGeneral: CONSULTA
    DetectarIntencion --> Derivacion: No es CMF
    DetectarIntencion --> Alerta: ALERTA fraude
    DetectarIntencion --> FueraDeAlcance: OUT_OF_SCOPE

    TemplateReclamo --> Paso1_TipoEntidad
    Paso1_TipoEntidad --> Paso2_NombreEntidad
    Paso2_NombreEntidad --> Paso3_Descripcion
    Paso3_Descripcion --> Paso4_Adjuntos
    Paso4_Adjuntos --> Paso5_Plazo: Documento o 'saltar'
    Paso5_Plazo --> Paso6_ReclamoPrevio
    Paso6_ReclamoPrevio --> Resumen
    Resumen --> Analisis: Usuario confirma
    Resumen --> Paso3_Descripcion: Usuario quiere corregir
    Analisis --> [*]: Diagnóstico entregado

    ConsultaGeneral --> [*]: Respuesta directa
    Derivacion --> [*]: Derivación con info de contacto
    Alerta --> [*]: Advertencia + canales de emergencia
    FueraDeAlcance --> [*]: Mensaje de delimitación
```

## Flujo de derivación por organismo

```mermaid
graph LR
    A[Mensaje del usuario] --> B{Clasificación Haiku}

    B -->|CMF| C[Plugin CMF]
    B -->|SERNAC| D[Derivación SERNAC]
    B -->|SII| E[Derivación SII]
    B -->|Laboral| F[Derivación Tribunales]
    B -->|Fraude| G[Alerta PDI/Fiscalía]
    B -->|Otro| H[Delimitación de alcance]

    C --> C1[Reclamo guiado + normativa]
    D --> D1["SERNAC: Ley 19.496, garantía legal"]
    E --> E1["SII: boleta, declaración de renta"]
    F --> F1["Dirección del Trabajo / SUSESO"]
    G --> G1["PDI 134, no entregar datos"]
    H --> H1["No puedo ayudar con ese tema"]
```

## Tiempos estimados por paso

| Paso | Acción | Tiempo estimado |
|---|---|---|
| Bienvenida | Bot responde en 2-3 seg | 3s |
| Tipo entidad | Usuario selecciona | 5s |
| Nombre entidad | Usuario escribe | 10s |
| Descripción | Usuario escribe | 15s |
| Adjuntos | Sube foto o salta | 10s |
| Plazo | Usuario selecciona | 5s |
| Reclamo previo | Usuario responde sí/no | 5s |
| Confirmación | Usuario confirma | 3s |
| Análisis backend | Procesa con normativa | 5-10s |
| **Total estimado** | | **~60-90s** |