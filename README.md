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

## Fuente OHLC de acciones — política de continuidad

El proveedor de cotizaciones históricas elegido para MIDAS IDEA LAB es **Yahoo Finance**, leído con **`yfinance`**, sin cambiar a Alpha Vantage ni a otra API. El módulo `scripts/yahoo_source.py` recoge el contrato de investigación: barras RAW diarias de mercado XNYS, `interval="1d"`, `auto_adjust=False`, `actions=True`, volumen, dividendos y splits; 503 símbolos de un universo institucional congelado e independiente y `SPY` como benchmark separado; cobertura mínima del 90 % y un hash SHA-256 del snapshot exacto. Las fechas, la estructura y el proveedor se verifican; una cotización ausente nunca se sustituye por una fecha anterior.

La validación offline está incluida en las pruebas del repositorio y puede ejecutarse con `python3 scripts/yahoo_source.py --check-contract`. La función de descarga utiliza `yf.download` bajo demanda, pero **la aplicación pública no ingiere ni distribuye todavía series Yahoo**. La captura privada de investigación requiere habilitación deliberada y un almacenamiento ya existente fuera del repositorio público. Las ejecuciones previstas de Yahoo no se activan automáticamente por publicar el código. No se han transferido snapshots, posiciones, historiales, fuentes personales ni nombres de cuentas externas.

Esta distinción importa porque la documentación de `yfinance` advierte que la API subyacente de Yahoo está destinada al uso personal, y la licencia del código no confiere por sí sola derechos para republicar los datos. Para una web institucional accesible públicamente hay que verificar los derechos de explotación y publicación antes de habilitar esa exposición. No implica la contratación ni sustitución del proveedor por otro.

La equivalencia restante exige un universo institucional verificado y no identificable con un repositorio personal, calendario de capturas, almacenamiento de OHLC con acceso restringido, recuperación acotada de barras ausentes, distribución a los algoritmos, ejecución prospectiva y auditoría de los libros. Ninguna rentabilidad artificial debe pasar por resultado bursátil real.


## Comparativa íntegra de funcionalidades — 64 líneas

La pestaña **Inventario completo · 64** registra las familias del sistema de inversión que se pretende migrar: dos generaciones de clásicos, modelos semanales y heredados, selección multicriterio, cuatro predictores cuantitativos, modelos temporales diarios y semanales, estrategias de ciclo, compra en caídas e ideas de investigación histórica. La nomenclatura es institucional y los ID son nuevos para evitar reutilizar identificadores privados. La tabla está preparada para actividad, órdenes, posiciones, fechas, divisa, rentabilidad, volatilidad, drawdown, comparación homogénea y mini-histórico. Incluye filtros por familia, búsqueda y exportación CSV.

**Esto es cobertura de funciones, no importación de resultados.** Las 64 líneas comienzan expresamente como `not_migrated` con todos los resultados económicos en `null`, sin histórico y sin actividad real. El validador bloquea el intento de presentar una fila pendiente como cartera activa. Las 23 estrategias matemáticas de la demostración, las nueve carteras artificiales y el registro prospectivo del BCE siguen siendo módulos distintos, no equivalentes a ese universo de 64.

Para obtener equivalencia operativa faltan la base de precios Yahoo/yfinance con permisos de uso y almacenamiento institucional no público, los libros prospectivos independientes, las mismas versiones de modelos, la lógica de señales y las auditorías reales, además de la ingestión de documentación empresarial y la continuidad de tesis. No se puede deducir una fecha, un precio o un rendimiento del mero inventario.


## Universo de acciones idéntico al mercado de referencia

Se ha inmovilizado un catálogo institucional nuevo de `503` tickers de mercado XNYS para la composición de referencia del **29/09/2026**, con `SPY` definido por separado. El archivo `data/universe-xnys.json` contiene únicamente identificadores públicos de instrumentos y no incluye información personal ni operaciones. Los identificadores `BRK-B` y `BF-B` se mantienen en su notación válida para Yahoo; el identificador histórico `PSKY` se traduce al símbolo de proveedor `SKYD` únicamente para sesiones a partir del 06/10/2026. Esto evita errores por cambios de denominación de un mismo valor.

La compilación institucional valida el universo completo, sin descargar Yahoo ni publicar su serie OHLC. Para usos locales con derechos suficientes, el fichero `scripts/requirements-yahoo.txt` define el conjunto de dependencias del adaptador existente. La migración no está completa hasta verificar una captura real diaria y los libros de cada algoritmo en el nuevo entorno.


## Recuperación causal de sesiones omitidas

La contabilidad paper incorpora la misma regla estructural del motor de referencia: límite configurable de hasta **cinco sesiones omitidas** para una campaña, actualización de patrimonio y eventos con las barras correspondientes y ejecución modelizada de órdenes registradas antes de esas sesiones. Cada cierre no ejecutado se anota como `DECISION_MISSED` y **no se fabrica ninguna señal del cierre perdido**. Si excede el límite, falta alguna barra obligatoria, hay modificación de datos ya registrados o cambia la configuración, se bloquea la actualización. El ranking muestra el número de decisiones omitidas por cartera.

La recuperación utiliza retrospectivamente el OHLC para estimar los fills pasivos: no equivale a una operación aceptada por un bróker. Las pruebas emplean datos artificiales y no convierten el simulador en una competición real.


## Canal firmado entre el núcleo institucional y el tablero público

El archivo `data/institutional-paper-feed.json` declara explícitamente `not_connected` hasta que un núcleo independiente y autorizado entregue evidencias. Se ha creado `scripts/paper_feed.py` como validador y firmador de resúmenes económicos **sin datos brutos de Yahoo ni cuentas personales**. Un resumen admitido requiere fuente Yahoo/yfinance (503 acciones y SPY), sesión bursátil identificada, SHA-256 de captura, derechos de explotación expresamente declarados, hashes de configuración por cartera, fecha y divisa, NAV y retornos aritméticamente conciliados, indicadores de riesgo y firma HMAC-SHA256 que solo puede generarse con el secreto institucional `IDEALAB_PAPER_FEED_KEY`. La identidad y el contenido financiero del resumen se verifican en GitHub Actions antes de poder publicar una versión firmada.

El secreto **no debe incluirse en el código fuente ni en el JSON público**; debe existir como secreto de CI y únicamente en un entorno de ejecución privado propio de IDEA LAB. Los tests usan una clave falsa, independiente de cualquier secreto real. El navegador valida también el contrato estructural, pero la verificación criptográfica ocurre antes de publicar. La página sigue mostrando las 64 líneas como pendientes mientras no haya una ingesta institucional real. La firma y el hash verifican integridad y procedencia declarada, **no prueban que las cotizaciones sean legalmente redistribuibles** ni validan por sí solos la rentabilidad del modelo.

Prueba local sin secreto: `python3 scripts/paper_feed.py --validate data/institutional-paper-feed.json`; esto valida únicamente el marcador desconectado. Para firmar datos futuros se debe ejecutar desde el núcleo privado `python3 scripts/paper_feed.py --sign <resumen.json> --output <destino.json>` tras acreditar los permisos de uso. El repositorio personal y sus libros no son fuentes permitidas para este canal.


## Núcleo paper público · primera ejecución prospectiva dentro de IDEA LAB

El repositorio **público** incorpora el ejecutor `scripts/public_market_runner.py`, el libro firmado `data/public-paper-book.json` y el workflow `.github/workflows/public-market.yml`. **No es necesario crear otro repositorio privado**. El mismo workflow valida cada ejecución sin datos de mercado, y puede procesar sesiones reales únicamente cuando la cuenta institucional haya acreditado las condiciones de uso del proveedor y haya habilitado la variable `MIDAS_YAHOO_RIGHTS_CONFIRMED=true` y un secreto propio `IDEALAB_PAPER_FEED_KEY` de al menos 32 caracteres.

Esta primera fase implementa dos **referencias** de una campaña nueva, separadas de las 64 líneas históricas: SPY y una cesta equiponderada de ocho acciones de gran capitalización. Capital inicial 100.000 USD paper por referencia, gastos del 0,1 %, deslizamiento del 0,05 %, inversión inicial del 95 %, señal al cierre y fill simulado exclusivamente en la siguiente apertura XNYS. Se registran dividendos, splits, unidades, efectivo, historial de NAV, firmas HMAC y un resumen en `institutional-paper-feed.json` que el dashboard ya sabe verificar. El código es público, las claves no. No se realizan operaciones reales ni órdenes de bróker.

El workflow sigue el reloj de captura común de las 23:07 UTC de lunes a viernes. Con la variable de autorización **ausente por defecto**, solo ejecuta la verificación sin contactar Yahoo ni alterar el libro; con dicha variable y el secreto configurados, se obliga a disponer de una sesión NYSE completa, 503 símbolos más SPY con cobertura mínima del 90 %, las nueve cotizaciones requeridas y estado anterior firmado. No se conservan las velas OHLC brutas. El día inicial únicamente registra decisiones pendientes; no se abre ninguna posición de forma retroactiva. Si una sesión quedó omitida, el ejecutor se detiene para evitar fills inventados y requiere una recuperación auditada. GitHub Actions conserva el único writer de este libro.

**No confundir con migración completa:** los métodos clásicos y los dos modelos mensuales ya cuentan con motores y pruebas offline, pero faltan la operación con datos autorizados, el aprendizaje periódico y otros métodos predictivos; no se han importado sus pesos, históricos ni carteras antiguas. Tampoco hay derecho de uso institucional de Yahoo confirmado, por lo que estas dos nuevas referencias no están operando todavía. No debe activarse el workflow en nombre de una licencia no acreditada. Una publicación de resúmenes derivados también requiere revisar los derechos de uso del proveedor.


## Motor de señales clásico para 503 valores · fase de equivalencia

Se añade `scripts/classic_503.py` para calcular desde la misma fuente Yahoo/yfinance **ocho métodos clásicos** sobre 503 miembros fijos y una referencia SPY, utilizando el cierre completo de la sesión y la información histórica anterior (hasta 300 sesiones por valor). Cubre equiponderación, EMA/RSI, genético congelado, MACD, RSI-reversión, bandas de Bollinger y rupturas 20/10 y 55/20. Aplica la exigencia de al menos 453 de 503 valores elegibles, historial suficiente, OHLC válido y de sesión exacta, ranking determinista con momentum de 21 sesiones y congelación de las intenciones de compra/venta para el siguiente mercado. El motor conoce los límites del original: máximo ocho posiciones y 15 % por entrada, aunque **la contabilidad de las nueve variantes clásicas ya está implementada y continúa sin iniciar**.

La descarga histórica a través de `yfinance` está disponible como función aislada, sin escritura de datos, y **requiere la misma acreditación de permisos institucionales que el workflow existente**. El motor corre en los tests sin consultar Yahoo, utilizando únicamente series generadas. La colección original de ocho valores, los resultados previos y todas las carteras de ML y tesis siguen sin trasladar. Ninguna señal 503 se publica como operación bursátil o rentabilidad auténtica sin una sesión prospectiva autorizada. Es una base de ejecución real verificable para la siguiente fase, no un sustituto de las 64 líneas.


## Once diarios paper independientes sobre la fuente común (implementación condicionada)

El motor de la campaña clásica ampliada pasa de señales a **nueve libros paper firmados**, uno por método/benchmark, con un nuevo estado institucional `data/classic-503-book.json` y lógica de liquidación en `scripts/classic_503_book.py`. Se añaden a las dos referencias de ocho acciones y SPY ya implementadas, sin mezclar capitales ni importar diarios históricos. La cartera equiponderada calcula un presupuesto de entrada de (95%/503) del patrimonio para cada componente; las técnicas utilizan máximo ocho posiciones, entrada de hasta 15 % del patrimonio, comisiones 0,1 %, deslizamiento 0,05 %, unidades fraccionarias a seis decimales, stops/objetivos según configuración y tratamiento de dividendos y splits. En caso de cotización ausente de un valor mantenido o una venta pendiente, **solo se suspende la cartera afectada**, conservando la última valoración verificada. Las demás avanzan cuando sus marcas son válidas.

Las once cuentas quedan bajo **un único writer GitHub Actions y una única fuente Yahoo/NYSE**. El flujo genera primero todos los resultados de sesión y valida HMAC, NAV e información derivada; solo después publica ambos libros y un resumen institucional de once filas en un único commit. Las velas brutas e históricos descargados no se envían al repositorio ni al dashboard. La ejecución bursátil permanece **desactivada** mientras no haya acreditación efectiva de derechos institucionales para Yahoo y configuración del secreto. Por tanto no son once carteras ya operando ni se ha reconstruido el historial original. La cobertura de las demás familias de MIDAS y sus tesis sigue pendiente.


## Capital Cycle y Buy The Dip · selección mensual independiente

Se añade `scripts/monthly_selection.py` con los contratos de **dos estrategias distintas**, identificadas institucionalmente como `IL-038` y `IL-039`. Conserva el universo congelado de 503 valores y las reglas propias de la cartera cíclica (hasta 12 posiciones, cuatro por sector, entrada máxima 10 %, escasez/solvencia/tendencia, 3 meses de histéresis, exposición del 95 %) y de la estrategia de oportunidades (máximo diez posiciones, tres por sector, peso máximo 15 %, límite sectorial del 30 %, peso combinado valoración/calidad/asignación/dislocación/catalizador del 30/20/15/20/15 %, exposiciones 0/50/70/90/95 % y rotación ante deterioro o rerating).

El contrato exige como mínimo 35 y 80 candidatos puntuables respectivamente, tres a cuatro ejercicios de información financiera por compañía, un campo de disponibilidad conocido en la fecha de señal y evidencia con hash. La primera señal se admite al cierre inicial; las siguientes al fin de mes, sin fabricar una decisión mensual omitida. Los tests son artificiales, no afirman ninguna rentabilidad. **La puntuación primaria de balances y precios, la captura institucional permitida y el libro económico de estas dos estrategias todavía no están integrados**: su salida es únicamente una propuesta de pesos que no se contabiliza como operaciones en la competición.


## Contabilidad paper mensual independiente y desactivada por falta de fuente fundamental

Se añade `scripts/monthly_paper.py` y el marcador sin iniciar `data/monthly-paper-book.json`. Este módulo implementa dos cuentas independientes para Capital Cycle y Buy The Dip, cada una con 100.000 USD de capital inicial ficticio, órdenes de rebalanceo congeladas al cierre del mes, ejecución estimada a la apertura exacta de la sesión siguiente, reducciones antes de compras, comisiones 0,10 %, deslizamiento 0,05 %, posiciones, efectivo, splits, dividendos y NAV diario. Cada libro admite su política de concentración original; la firma HMAC impide modificar silenciosamente el capital o las posiciones guardadas. Una ausencia de barra de un valor mantenido provoca cuarentena solo en esa cartera. Un cierre mensual sin señal fundamental válida se rechaza; no se inventa una cartera con precios actuales retrospectivamente.

**Estado real:** los dos libros están marcados `not_started` y sus operaciones se han probado únicamente con datos artificiales. Falta el cálculo original completo de scores desde balances con disponibilidad *point-in-time* y fuentes Yahoo correctamente autorizadas. Hasta que eso exista, estas cuentas no se añaden a los resúmenes bursátiles publicados, no se inicializan y no tienen rentabilidad observada. Conservar el código público no implica tener derecho a redistribuir datos financieros del proveedor.


## Factorización económica y contable mensual — fuentes con fecha de disponibilidad

El nuevo `scripts/monthly_factors.py` calcula a partir de series diarias fechadas y tres o cuatro ejercicios anuales los factores requeridos para Capital Cycle y Buy The Dip, sin copiar carteras ni importar resultados. Exige como mínimo 760 cierres observados por empresa, incluido el cierre exacto de la sesión; para contabilidad se utiliza la fecha real en que la información fue observada y disponible, nunca una publicación posterior. La puntuación relativa por sector contempla infrainversión y contracción del capex, crecimiento de activos, FCF y márgenes, endeudamiento, rentabilidad, dislocación del precio y catalizadores. Los bancos se analizan de forma distinta mediante beneficio, ROE y valor contable en lugar de extrapolar su FCF corporativo.

Este módulo alimenta los selectores originales de pesos `IL-038` y `IL-039` en pruebas offline con datos artificiales. Permite verificar el mecanismo desde observaciones primarias hasta una señal al cierre, **pero no descarga todavía balances reales desde Yahoo ni publica rentabilidad nueva**. La autorización de uso de datos, la captura prospectiva de fundamentales, pruebas de equivalencia numérica y la integración de los dos libros con el workflow son condiciones de aceptación pendientes.


## Estado de aceptación al 31/10/2026

Las estrategias mensuales de escasez de capital y compra en caídas tienen selección, cálculo de factores con fechas verificables y contabilidad paper independiente. Existen además nueve libros clásicos de 503 emisores y dos libros de referencia separados. Todos esos motores han pasado pruebas offline. No equivalen a ejecución bursátil.

En la revisión institucional de las 20:10 UTC, el workflow de mercado terminó `validate=success`, `execute=skipped`; Pages publicó correctamente. Los archivos `data/public-paper-book.json`, `data/classic-503-book.json` y `data/monthly-paper-book.json` siguen con `not_started`, y el resumen público `data/institutional-paper-feed.json` sigue con `not_connected`. No hay rentabilidad bursátil prospectiva acreditada.

Pendientes verificables: derechos de uso de datos; reconciliación de puntuaciones por sector frente a datos fechados; acoplar factores y libros mensuales al mismo flujo causal; implementar aprendizaje semanal y series temporales con validación fuera de muestra; completar tesis y documentación oficial. No se inventan operaciones anteriores ni se marca como activa una cartera sin una captura válida.


## Contrato semanal de modelos predictivos — investigación, sin operaciones

Se añade un validador independiente para los nueve identificadores semanales: dos referencias bursátiles y siete salidas predictivas. Exige cobertura fechada del universo, ausencia de datos futuros, muestras históricas suficientes, cierre semanal acreditado y decisiones congeladas para la siguiente apertura. La selección teórica restringe cada modelo a diez títulos, 12 % máximo por título y 95 % de inversión; las pruebas se ejecutan exclusivamente con series artificiales.

**No hay modelos entrenados ni carteras semanales activas en IDEA LAB por este cambio.** Sus predicciones externas siguen siendo entradas sin certificación independiente y todavía faltan entrenamiento walk-forward, pruebas fuera de muestra, persistencia firmada de operaciones y permisos de cotización. Véase `docs/SCIENTIFIC_PARITY.md`.


## Evaluación real de dos estimadores básicos — laboratorio sintético

El módulo independiente `scripts/weekly_baselines.py` ajusta **regresión ridge y regresión logística**, y realiza evaluaciones *walk-forward* con transformación de variables ajustada exclusivamente sobre cada ventana histórica de entrenamiento. El orden de disponibilidad de etiquetas futuras se comprueba antes de cada predicción; se aplica un embargo temporal y se compara el error con una referencia nula calculada en la misma ventana. La validación funciona con datos artificiales de prueba y no necesita servicios externos.

Estas dos regresiones son **baselines nuevos**, no sustituyen ni acreditan como entrenados los modelos LightGBM, MLP, LSTM, ARIMA, TimesFM o ensemble de las 64 estrategias. No se han creado pesos bursátiles, posiciones, rendimientos reales ni un backtest de mercado. No se conecta este módulo al sistema de operaciones hasta disponer de fuentes autorizadas, modelos propios contrastados y controles independientes de validación económica.


## Modelos estadísticos y neuronales independientes — MLP y ARIMA(1,0,0)

Se incorporan dos estimadores **entrenados realmente con datos suministrados al módulo**: una red neuronal MLP de una capa oculta de cinco unidades y un ARIMA(1,0,0), es decir, una autorregresión AR(1) estacionaria, ajustada mediante mínimos cuadrados condicionales. La MLP entrena por descenso de gradiente determinista con normalización y etiquetas exclusivamente del conjunto de entrenamiento; el ARIMA utiliza solamente observaciones semanales consecutivas del mismo emisor. Ambos pueden evaluarse cronológicamente con comparación RMSE contra un promedio histórico de entrenamiento, embargo de disponibilidad y rechazo de datos inválidos.

**Alcance:** estas son implementaciones de investigación independientes, no réplicas certificadas de los modelos históricos de MIDAS. No son LightGBM ni LSTM y ARIMA(1,0,0) no representa toda la familia ARIMA(p,d,q). Las pruebas emplean datos sintéticos; no hay entrenamiento bursátil validado, rentabilidades demostradas, publicación de parámetros entrenados ni ejecución de órdenes. Las 64 líneas económicas continúan pendientes.


## LightGBM auténtico: tres objetivos de investigación, sin operativa de mercado

El módulo `scripts/weekly_lightgbm.py` utiliza la **biblioteca oficial LightGBM 4.7.0** con dependencia fijada en `scripts/requirements-research.txt`. Entrena tres modelos independientes: regresión de rentabilidad futura (`return`), probabilidad de rendimiento positivo (`direction`) y ranking transversal por semana mediante `lambdarank` (`rank`). Cada ajuste se realiza en modo determinista y un solo hilo, con hiperparámetros congelados y huella sobre todos los ejemplos, etiquetas y configuración utilizados. La evaluación `walk_forward` reentrena con etiquetas maduras previas a cada decisión y embargo temporal, usando RMSE/Brier o concordancia de pares, respectivamente.

**Limitación verificable:** las pruebas de GitHub utilizan exclusivamente datos sintéticos generados para validar la implementación. No se ha recuperado ni reproducido ningún artefacto entrenado del sistema anterior, ni está acreditada la calidad predictiva en cotizaciones reales. Estos modelos no alimentan las carteras institucionales ni modifican el inventario económico de 64 estrategias. La licencia y autorización sobre datos bursátiles deben acreditarse antes de pasar a ejecución prospectiva.


## LSTM recurrente de cuatro puertas — laboratorio sin datos bursátiles

Se incorpora `scripts/weekly_lstm.py`, un entrenamiento recurrente genuino de memoria corta/larga con NumPy y retropropagación temporal (*backpropagation through time*). Entrena las matrices de las cuatro puertas y la salida con ventanas semanales consecutivas de tres observaciones, sin cargar datos de cotizaciones externos. La media, la escala y los pesos se determinan exclusivamente con etiquetas maduras anteriores a cada fecha de predicción. El emisor, las fechas de disponibilidad, los gaps y la huella del entrenamiento quedan sometidos a pruebas automáticas. Las muestras son sintéticas.

**No es el LSTM histórico original de MIDAS**, ni su hiperparametrización está homologada, ni existe evaluación de mercado fuera de muestra. Tampoco están activados libros paper nuevos, algoritmos bursátiles o valores de cartera. Se preservan íntegramente las restricciones de derechos de datos y privacidad institucional.


## Auditoría LSTM cronológica de investigación

La evaluación temporal del LSTM se implementa en `scripts/lstm_walkforward.py` y prueba ventanas de entrenamiento fechadas, embargo de disponibilidad, predicciones fuera de muestra sintéticas y métricas de error frente a un predictor nulo. La evaluación es acotada y revela explícitamente las fechas examinadas, sin atribuir resultados a precios bursátiles reales. No modifica los 64 registros de actividad económica ni acredita rendimientos.


## Cobertura pública adicional: Rocket Lab

Se añade Rocket Lab Corporation (NASDAQ: RKLB) exclusivamente como **identidad bursátil contrastada independientemente**. La fuente primaria es [Rocket Lab Investor FAQs](https://investors.rocketlabcorp.com/resources/investor-faqs) y la reorganización societaria figura en el [aviso oficial Nasdaq de mayo de 2025](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2025-264). No se han importado tesis, parámetros históricos, vínculos privados, precios bursátiles, CAGR ni objetivos para este emisor. Su estado permanece pendiente de investigación y no cuenta como informe aprobado.
