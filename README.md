# MIDAS · Laboratorio cuantitativo de IDEA LAB

Laboratorio público e independiente para comparar estrategias de inversión **paper** (ficticias), investigar modelos y formalizar tesis verificables. La aplicación se ejecuta completamente en el navegador y no utiliza datos personales ni infraestructura privada.

**Estado científico: competición sintética y fuentes primarias separadas.** Los 23 resultados paper siguen basándose en activos ficticios. El piloto independiente del BCE ofrece observaciones oficiales de EUR/USD (referencias, no precios de operaciones), y existe un primer screening público fechado de una empresa. No se importan historiales ni modelos personales.

## Funcionalidades

| Módulo | Contenido implementado |
| --- | --- |
| Inicio | KPIs, familias metodológicas y tesis destacadas |
| Competición | 23 estrategias de seis familias, NAV, drawdown, volatilidad, Sharpe y costes |
| Fichas de algoritmos | Reglas, curva de capital, pesos, exposición, operaciones paper |
| Algoritmos | Catálogo y creación local de carteras con tres activos artificiales |
| Tesis | Seis ejemplos con condiciones de refutación, tres escenarios, CAGR y descuento |
| Seguimiento | Diario de compra/venta ficticia, costes, clasificación y exportaciones CSV |
| Metodología | Reloj causal, limitaciones, comparabilidad y requisitos de publicación |

### Algoritmos reconstruidos

- Clásicos: equiponderación, referencias concentradas, momentum, reversión, baja volatilidad y control de liquidez.
- Aprendizaje semanal: proxies deterministas de regresión, clasificación direccional, ranking, transformaciones no lineales y consenso.
- Modelización temporal: reglas heurísticas sobre información de cierres anteriores.
- Capital Cycle: propuestas de ciclo y valoración basadas en parámetros ficticios.
- Buy The Dip: reglas condicionales y escalonadas de exposición ante retrocesos.
- Modelos experimentales: multicriterio, ponderaciones fijas y control de estrés.

**No confundir los proxies de aprendizaje o temporales con modelos realmente entrenados**. No se han ejecutado modelos de árboles de gradiente, redes recurrentes, modelos fundacionales ni optimizadores evolutivos reales en esta versión.

## Cálculo

Las señales de la sesión `t` se deciden utilizando solo datos ficticios hasta `t - 1`, sin utilizar observaciones futuras para seleccionar exposiciones. Se actualiza el capital paper con costes proporcionales al cambio de peso y variación relativa de precios entre cierres. El motor genera un registro de órdenes con acciones, marcas, unidades e importes ficticios. La ausencia de cotización válida bloquea la simulación; no se crean fills ni valores liquidativos de respaldo.

La muestra empieza con 100.000 unidades de capital imaginario y 48 sesiones sin fechas reales de mercado, por lo que anualizar volatilidad o Sharpe es **meramente ilustrativo**. Los escenarios de tesis usan flujos, múltiplos y tasas requeridas inventados; no equivalen a una valoración financiera.

## Ejecución y pruebas

El cliente no necesita cuentas ni claves API, pero la compilación institucional consulta el servicio público del BCE. Servir la carpeta con un servidor HTTP local; las restricciones de los navegadores pueden impedir cargar JSON con `file://`.

```bash
python3 -m http.server 8000
node --test tests/metrics.test.mjs
python3 scripts/audit_public.py
```

GitHub Actions publica un paquete estático autorizado más el archivo validado `dist/data/official-fx.json`, descargado exclusivamente de la API oficial BCE. El flujo está programado de lunes a viernes a las 17:25 UTC y en cada push, pero las ejecuciones futuras necesitan comprobación individual.

## Frontera de publicación

Para incorporar resultados reales será necesario reconstruir y validar métodos científicos con código nuevo, obtener cotizaciones licenciadas con su instante de disponibilidad, verificar el registro anticipado de estrategias, permitir costes operativos realistas, evaluar fuera de muestra y publicar todas las exclusiones o errores de datos. Las tesis exigirán fuentes primarias, cambios versionados, valoración con supuestos y seguimiento posterior.

No se importan repositorios ni historiales de desarrollo personales. Se evita divulgar autores, trabajos académicos identificativos, datos bancarios, posiciones, opiniones personales o dependencias de fuentes privadas. **No puede garantizarse imposibilidad de atribución** por comparación con otros contenidos previamente públicos.

© IDEA LAB. Todos los derechos reservados salvo indicación expresa.


## Evaluación de aprendizaje realmente entrenado (solo laboratorio artificial)

La página [Modelos entrenados](research.html) ajusta regresión regularizada y clasificación logística **en cada ventana cronológica**, con normalización estimada exclusivamente sobre la muestra de entrenamiento. Publica RMSE, Brier y acierto direccional fuera de muestra sobre los mismos activos ficticios. No publica rentabilidad, señales operables ni asegura haber recuperado modelos históricos. Véase [puertas científicas](docs/SCIENTIFIC_PARITY.md).

```bash
node --test tests/*.test.mjs
python3 scripts/audit_public.py
```


## Piloto de datos oficiales

El panel «Salud operativa / diario» presenta la referencia EUR/USD del BCE, fecha, edad del dato, cobertura y hash SHA-256 de la respuesta; los datos son informativos, **no ejecutables ni convertibles en rentabilidad paper**. La fuente es [ECB Data Portal](https://data.ecb.europa.eu/help/api/data-examples), reutilizada con atribución «Source: ECB statistics». Si falla la ingesta o su contrato, la publicación se bloquea. La integración no implica que las 23 estrategias estén funcionando prospectivamente ni que exista un feed OHLC de acciones.


## Diario prospectivo institucional (BCE, sin posiciones)

Separado de los 23 algoritmos bursátiles sintéticos, el laboratorio incorpora un registro de predicciones del siguiente fixing EUR/USD. La fuente es exclusivamente la serie oficial del BCE, no un precio negociable. Tres reglas fijas —sin cambio, momentum de una referencia y reversión de una referencia— emiten una predicción después de recibir el último fixing. Cuando llega el siguiente dato, se incorpora un evento posterior con el error absoluto de cada modelo. No se fabrican señales anteriores al inicio del registro ni beneficios financieros.

El diario público está versionado en `data/fx-forecast-ledger.json`. La automatización `.github/workflows/fx-ledger.yml`, con permiso restringido a escritura de contenidos, está programada de lunes a viernes a las 17:40 UTC. Comprueba fuente, fechas, cadena de hashes y puntuación. Si falla la fuente, no hay suficientes fechas o el token no tiene permisos, no escribe datos y debe notificar error. Pages se publica posteriormente a las 18:25 UTC si sus comprobaciones pasan. La ejecución inicial por push del 31 de octubre sí completó una escritura real en Git; la primera ejecución natural del horario de lunes a viernes aún debe comprobarse.

La cadena SHA-256 hace detectable la alteración de eventos sin rehacerla; no impide que un administrador autorizado reescriba el historial completo. La auditoría debe corroborarse con los commits de Git.


**Incidencia de calidad 31/10/2026:** la primera señal emitida con fecha de fixing 30/10/2026 tenía invertido el orden de las dos últimas observaciones. Por ello el pronóstico «sin cambio» no coincidía con el valor contemporáneo. La señal original se conserva y se ha añadido un evento de **invalidación** enlazado por hash; no se puntúa y no cuenta como observación de éxito. Se ha corregido el orden cronológico y se han añadido pruebas de consistencia matemática. Los resultados evaluables solo empiezan a partir de una nueva señal válida emitida posteriormente.


## Fuente primaria SEC · informes 10-K, 10-Q y 8-K

Las fichas institucionales de ocho emisores con CIK verificado pueden incorporar un índice de hasta doce documentos recientes por entidad, extraído directamente de la API pública de EDGAR. El archivo `data/sec-filings.json` conserva ticker, CIK, nombre legal SEC, tipo de formulario, fecha de presentación, fecha de período y enlace al documento oficial; conserva además fecha de recuperación en UTC y SHA-256 de la respuesta SEC. La colección comienza con estado **not_collected**, por lo que no se inventan resultados ni documentos antes de una captura real.

`.github/workflows/sec-filings.yml` verifica ocho fuentes con un único request por emisor, pausa entre peticiones y el agente declarado **IDEA LAB Research**, con referencia exclusiva a la cuenta institucional. La tarea estuvo preparada para una programación diaria, pero está **suspendida tras el HTTP 403**. Solo se admite ejecución manual autorizada hasta resolver el acceso. Los nuevos datos se guardan mediante commits institucionales en el archivo permitido. Si la SEC bloquea el acceso, falta alguna fuente, se incumple el esquema o GitHub no permite la escritura, el job debe **fallar** sin cambiar el catálogo. La web conserva el último estado validado y Pages lo incluye en su siguiente despliegue. Un commit hecho con `GITHUB_TOKEN` no implica necesariamente que el workflow de Pages se dispare en ese mismo instante.

**Límite:** metadatos de formularios no equivalen a cifras financieras auditadas por el laboratorio. Todavía faltan extracción XBRL, coherencia entre períodos, márgenes, flujo de caja libre, valoraciones Bear/Base/Bull e ingestión autorizada de cotizaciones históricas. Para los demás emisores se consultarán los organismos reguladores competentes, no se atribuirán formularios SEC de otra sociedad.


### Bloqueo real de SEC (31/10/2026)

La primera ejecución institucional de la ingesta EDGAR fue rechazada por **HTTP 403 Forbidden** desde el runner de GitHub Actions. El estado continúa **not_collected**; ningún formulario ha sido importado. Para respetar la política de acceso de la SEC, se ha suspendido el cron y el disparador automático del colector: solo queda ejecución manual y requiere previamente configurar el secreto `SEC_CONTACT_EMAIL` con un contacto institucional **supervisado**. Se rechazan expresamente correos `noreply` y datos de contacto personales publicados en código. Disponer del contacto no garantiza que desaparezca el 403: debe comprobarse que la infraestructura tiene acceso permitido. La publicación de Pages y el seguimiento de divisas continúan sin depender de este colector.


## Referencia oficial de curva AAA euro a 10 años

El panel de seguimiento financiero incorpora un segundo origen público del BCE: `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`, la **tasa spot nominal a diez años de bonos soberanos AAA de la zona euro**, estimada mediante el modelo Svensson y expresada en porcentaje anual con capitalización continua. Los datos se descargan diariamente en cada construcción de Pages desde la API oficial del BCE, conservando fecha, valor literal, sello de recepción UTC y SHA-256 de la respuesta. La serie debe superar controles de identidad, unidad, antigüedad, fechas y límites antes de publicarse. No se utilizan servicios privados ni acceso a una cuenta personal.

**Restricción:** esta referencia modelizada no es un bono individual negociable ni garantiza una inversión libre de riesgo. No representa la tasa sin riesgo de una valoración en USD y no entra automáticamente en ningún descuento de flujos, CAGR o precio objetivo. Las futuras tesis de inversión deberán justificar explícitamente su divisa, estructura de descuento y supuestos contables.

## Nueve métodos técnicos y contabilidad artificial independiente

La pestaña **Señales técnicas · 9 métodos** presenta políticas de señal al cierre y un replay contable independiente, completamente artificial. El modelo contabiliza las órdenes en la apertura siguiente, costes, efectivo, posiciones, dividendos y splits, así como límites de cartera y salidas conservadoras. Cada método cuenta con un capital virtual independiente, sus propias operaciones simuladas y un diario inspeccionable. El conjunto se genera matemáticamente y **no muestra precios bursátiles reales**, operaciones de un bróker, campañas antiguas ni rendimientos financieros prospectivos.

Este módulo se mantiene separado de la competición original de 23 prototipos. No demuestra que los 23 métodos estén ejecutándose ni reemplaza los archivos de seguimiento de empresas. Permanecen pendientes una fuente de OHLC de acciones con autorización de uso, persistencia autónoma del libro bursátil, calibración de todas las estrategias y valoraciones verificadas de las empresas. Las pruebas automatizadas rechazan cambios retrospectivos de velas y duplicaciones de sesión.


El benchmark artificial se simula sobre un noveno símbolo ficticio y la referencia equiponderada sobre ocho símbolos ficticios distintos. La distribución de efectivo en las compras concurrentes se calcula a partir del efectivo disponible antes de ejecutar las órdenes, evitando pesos decrecientes por el orden de procesamiento. **Esta referencia no reproduce todavía SPY, sus dividendos ni un índice real:** los importes y porcentajes son simulaciones sin uso inversor.
