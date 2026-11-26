# MIDAS · Operación en Idea Lab

La producción canónica reside en `idealab2026/laboratorio-cuantitativo` y su
GitHub Pages. Código, diarios impersonales, pruebas y automatismos se conservan
en el mismo repositorio institucional. Arquitectura: GitHub público, Actions y
Pages; coste cero siempre. Credenciales exclusivamente en GitHub Secrets.

## Captura y contabilidad diaria originales

1. `market_data_xnys.yml` captura la sesión XNYS recién cerrada a las 23:07 UTC
   laborables. Verifica el calendario, el universo congelado de 503 valores más
   SPY y barras RAW con fecha exacta, volumen y acciones corporativas.
2. El snapshot inicial es inmutable. `collect.py --phase recover` solo añade
   cotizaciones realmente ausentes mediante revisiones enlazadas por SHA. Tiene
   hasta 48 reintentos aislados; valores retirados del mercado permanecen ausentes.
   Nunca sustituye un activo ni una observación previamente registrada.
3. Después de publicar la fuente, se encadenan los consumidores originales:
   `classic_sp500`, `buy_the_dip_strategy`, `capital_cycle`, `weekly_ml_daily`,
   `timesfm_daily` y `timesfm_one_day`. También conservan sus horarios de respaldo.
   RSP es independiente del universo común; su lector exige una barra RAW fechada
   válida y reintenta de forma acotada antes de declarar ausencia.
4. `market_data/source_health.json` separa cobertura de fuente, resultados de jobs
   y libros actualizados o pausados. `strategy_state/dashboard.json` es la vista
   derivada de los diarios. Su fecha de generación no es un cierre de mercado.
5. Para una recuperación explícita dentro de la ventana causal, ejecutar el mismo
   workflow con `capture_session=true` y `run_consumers=true`. No admite seleccionar
   una sesión pasada. Una recuperación manual no demuestra continuidad programada:
   verificar después un nuevo ciclo natural y una sesión económica nueva.

Conservar señales, órdenes, fills simulados, cash, costes y NAV de cada campaña.
Cotizaciones ausentes o inválidas bloquean la transición correspondiente; nunca
se rellenan con el último cierre. Una cuarentena de una única sesión recién
cerrada puede liquidarse con retraso si conserva las órdenes fijadas al cierre
anterior y dispone de todas las barras comunes exactas. Reutiliza las mismas
comisiones, deslizamiento y reglas conservadoras de stop/objetivo. Las nuevas
marcas y operaciones incluyen fecha real de registro, hashes y aviso visible de
cálculo tardío; no acreditan ejecución puntual. Se rechazan huecos de varias
sesiones, señales históricas reconstruidas y acciones corporativas sin resolver.
Las nuevas decisiones se fijan antes de la siguiente apertura XNYS.

## Otros calendarios y campañas

Weekly ML, TimesFM semanal y selección multicriterio conservan sus horarios y señales congeladas;
no deben ejecutarse artificialmente como estrategias diarias. La campaña genética
conserva sus tres cohortes y requiere un traspaso de writer verificado antes de
activar `GENETIC_PUBLIC_ACTIVE`. No mezclar históricos ni crear otra cohorte para
ocultar un hueco. Las antiguas campañas de ocho activos/IBEX y modelos cuantitativos de referencia están
archivadas por su contrato original desde el 13/10/2026; conservar sus resultados
sin tratarlas como participantes activos del universo S&P 500.

El inventario tiene 64 estrategias. Disponer de código o de 47 diarios históricos
recuperados no demuestra que las 64 estén operativas. Consultar fechas, estado,
universo y comparabilidad de cada fila; no ordenar campañas incompatibles juntas.

## Prototipos separados

`public-market.yml`, los libros HMAC alternativos y las demos con precios
artificiales son desarrollos separados del motor original. Sus permisos y gates
propios siguen vigentes. No activarlos como un segundo writer para recuperar el
motor original ni atribuirles sus diarios. Capital virtual con cotizaciones reales
es paper trading; la demo de 23 estrategias usa precios artificiales y no acredita
resultados de mercado. Una simulación no garantiza ejecución de broker idéntica.

## Auditoría y retirada del origen

El auditor diario de ChatGPT «AUDITOR - MIDAS · IDEA LAB» comprueba la fuente,
los workflows, los diarios y la web institucionales, además del seguimiento de
las tesis. No depende de la UI, Worker ni repositorios personales del producto anterior. No confundir tests verdes, publicación, recuperación manual y continuidad
natural. Alertar solo de cambios materiales, preservando las incidencias abiertas.

El propietario autoriza retirar MIDAS del entorno anterior después de probar sustitución
funcional, conservación de históricos, acceso a documentos de trabajo impersonales,
restauración y continuidad. Hasta entonces conservar el respaldo y el fallback;
no detener automatismos originales ni afectar otras áreas. No activar servicios
de pago, facturación ni infraestructura Cloudflare para resolver esta migración.

### Recuperación de una interrupción de cotizaciones

La captura común reintenta a las 01:07 UTC las observaciones ausentes, mediante
revisiones enlazadas por SHA sin cambiar capturas anteriores. Weekly ML corre
tras la publicación común (00:17 UTC y respaldo 03:27 UTC). Los horarios reales
de GitHub Actions pueden retrasarse; un proceso verde no acredita que todas
las carteras hayan podido valorarse.

Si ya pasó la siguiente apertura, no ejecutar órdenes antiguas para rellenar el
hueco. En `MIDAS classic passive mark-only recovery` seleccionar `inactive`; en
`MIDAS Weekly ML daily paper` activar `recover_inactive`. Ambos usan el bloqueo
del escritor económico correspondiente, comprueban primero sin escribir y
registran únicamente cierres reales consecutivos (máximo cuatro sesiones).
Se conservan cartera, cantidades, coste e histórico; las órdenes cuya apertura
se perdió quedan canceladas y documentadas. El día parcial actual se mantiene
inactivo y la reanudación se fija en una apertura futura. Los derechos de cobro
corporativos conservan su valoración provisional y no se convierten en efectivo.
Las acciones corporativas no revisadas o cotizaciones ausentes siguen bloqueando
la recuperación; nunca usar cierres rellenados ni resultados sintéticos.

## Recuperación verificable de discrepancias del proveedor

La captura diaria original sigue siendo inmutable. Si una barra diaria de Yahoo
presenta un rango imposible, se conserva rechazada. Solo se puede añadir una
observación derivada si la cinta de cinco minutos cubre toda la sesión regular
XNYS, sin huecos ni barras inválidas, y sus aperturas y cierres coinciden con los
anclajes diarios RAW. H/L proceden de los extremos realmente observados en esa
cinta; O/C y volumen conservan los valores diarios. No se recortan rangos al
precio de apertura ni se rellenan intervalos. La revisión conserva ambos cuerpos
HTTP originales, sus URLs, hashes y el método `yahoo_regular_range_daily_ocv_v1`.
El lector vuelve a verificar y reproducir la derivación al consumirla.

Una cartera pasiva sin stops ni ventas pendientes puede valorarse con el cierre
fechado coincidente de las lecturas diaria e intradía, aunque no exista un rango
completo. Esos registros se guardan aparte en `XNYS/FECHA.closes/`, con alcance
`passive_nav_only`; nunca entran en el mapa canónico de barras ni permiten
compraventas o señales intradía. Se conservan posiciones, caja, operaciones e
histórico anteriores. Dividendos, splits, conflictos de cierre o ausencia de un
cierre terminal siguen bloqueando la recuperación hasta su revisión.

## KVUE → KMB — revisión de la liquidación de fracciones (2026-11-24)

### Evidencia incorporada

- [Kenvue Form 8-K, 2 de noviembre de 2026](https://www.sec.gov/Archives/edgar/data/1944048/000095015726001147/form8-k.htm): contraprestación de 0,14625 acciones KMB y 3,50 USD por acción KVUE, con efectivo en lugar de fracciones.
- [Prospecto S-4](https://www.sec.gov/Archives/edgar/data/55785/000114036125044277/ny20059815x1_s4.htm): para acciones ordinarias, la fracción se paga en efectivo usando la media de los VWAP diarios de las cinco sesiones anteriores al cierre del canje, redondeando al céntimo.
- [OCC memo 60189, 10 de noviembre de 2026](https://infomemo.theocc.com/infomemos?number=60189): para opciones ajustadas KMB1, OCC comunica una referencia definitiva de 109,2059 USD por acción KMB para el efectivo sustitutivo de fracciones. La fracción de 0,625 por contrato equivale a 68,25 USD. Es evidencia de la valoración en el contrato de opciones, no prueba de recepción de fondos en acciones ordinarias.

### Impacto indicativo sobre los derechos existentes

Lectura del libro clásico en commit 124195cc9cdf10598b7696b91ef16b726b1ca20e. Aplicando, únicamente como comprobación condicional, la referencia OCC a las fracciones de los dos derechos pendientes:

| Libro | Efectivo fijo (USD) | Fracción KMB | Efectivo fraccional indicativo (USD) | Total indicativo (USD) |
|---|---:|---:|---:|---:|
| IL-010 Equiponderación | 35,91 | 0,50056507250 | 54,66 | 90,57 |
| IL-012 Genético congelado | 2257,90 | 0,34802970125 | 38,01 | 2295,91 |

No hay autorización para contabilizar estos totales como fondos disponibles: falta una confirmación de la liquidación de acciones ordinarias acorde con el contrato vigente de `classic_sp500/corporate_actions.py`. El memo OCC no satisface por sí solo el requisito de evidencia del emisor y no confirma una fecha de pago de accionistas.

### Decisión operativa

Conservar intactos los libros, el bloqueo de gasto del derecho pendiente, los NAV ya publicados y la clasificación no certificada. No insertar una revisión en `merger_settlements` ni relajar las verificaciones de `settle_reviewed_claims`. La referencia se documenta para una posterior revisión prospectiva, diferenciando valoración de liquidación y sin reconstruir transacciones históricas.

## IL-061: adaptación prospectiva de momentum mensual (24/11/2026)

Primera pieza de productivización: `scripts/monthly_selection.py::choose_momentum`.
Contrato nuevo, no réplica literal del screener histórico: ranking 12-1 meses
por cierres ajustados de la misma captura, últimos días hábiles XNYS de los
meses de referencia, decisión al cierre mensual y antes de la próxima apertura.
Universo congelado 503, cobertura mínima 90%, hasta 20 valores con momentum
positivo y peso fijo de 4,75% cada uno; el resto queda en efectivo. Si falta
la evidencia de un valor ya mantenido no se emite señal. Ordenación determinista,
fechas de captura, referencias y hash; no se admite cierre posterior ni relleno.

Estado: contrato de selección en desarrollo, con pruebas offline. No hay
cartera activa IL-061, feed de precios ajustados acreditado ni writer de órdenes.
El siguiente gate es validar la procedencia y disponibilidad de los precios
ajustados, vincular un diario independiente de señales y un simulador causal de
órdenes con costes, y observar una primera apertura natural. Mantener los
libros mensuales IL-038/039 y sus hashes intactos; no activar el prototipo HMAC
alternativo como segundo escritor. No atribuir rentabilidad al screener histórico.

### Contrato de captura IL-061 (24/11/2026)

`capture_momentum_internal` permite capturar las dos anclas ajustadas de cada
instrumento en una misma descarga Yahoo por lotes de hasta 40, únicamente en
la ventana causal del cierre mensual. Rechaza anclas ausentes, ambiguas y
cambios de ticker que requieren revisión; conserva recibos normalizados y
hashes, no cuerpos HTTP originales. El fichero se crea exclusivamente fuera
del repositorio y sin sobreescritura; requiere confirmación explícita de
los derechos de uso interno ya definidos por el contrato Yahoo. No se modifica
el feed común RAW, no se programan descargas aún y no se crean señales ni fills
retroactivos. La prueba con proveedor real, persistencia interna entre runs y
el diario independiente de IL-061 siguen pendientes.

## Cohorte GS Quant inspirada — 25/11/2026

Revisión de https://github.com/goldmansachs/gs-quant (Apache 2.0) y
https://developer.gs.com/docs/gsquant/api/timeseries.html:
statistics (z-score, OLS), technicals/econometrics (volatilidad, retornos),
timeseries/backtesting (cestas) son referencias matemáticas locales; las
consultas de datasets, precios de derivados y riesgo remoto requieren Marquee.
La implementación es independiente, con NumPy, no importa código GS ni usa
credenciales GS. No representa estrategias propietarias ni recomendación.

GS-01: ranking de momentum de 20 sesiones dividido por volatilidad de log
retornos; GS-02: reversión z < -1,5 frente a 20 cierres anteriores; ambas
hasta 10 nombres con peso 9%. GS-03: equal risk contribution sobre una cesta
predefinida de 12 acciones, covarianza con shrinkage diagonal 20%. GS-04:
pares predefinidos, OLS de log precios con 20 observaciones previas y z-score
fuera de la regresión, correlación mínima 0,4; hasta cinco pares dollar-neutral
(9% por pierna), 3% anual de préstamo supuesto, sin acreditación de disponibilidad
de préstamo. GS-05: ranking 50% momentum, 30% baja volatilidad, 20% reversión
a cinco sesiones, hasta 10 nombres. Todos limitados al 90% de exposición bruta.
SPY 90% + caja es referencia de exposición para las estrategias largas.

Señales diarias fijadas al cierre antes de la próxima apertura, 21 snapshots
comunes consecutivos, mínimo 350 series completas de 503, sin imputar ni unir
splits/renombres. Precios RAW, dividendos reconocidos al ex-date, splits de
posiciones requieren revisión. 100.000 USD virtuales por libro, comisión 10 pb
y deslizamiento 5 pb por lado. Ejecución OHLC de apertura siguiente registrada
después del cierre, identificada explícitamente como simulación, no ejecución
observada. No retroceder señales ni rellenar operaciones ausentes. Si falta
precio de un objetivo se cancela el rebalanceo; si falta marca de tenencia,
se bloquea el libro. Conserva el inventario histórico de 64 entradas y muestra
la cohorte aparte en la misma página de competición; no se fusiona el ranking
certificado anterior ni se añade riesgo real. El primer cierre válido del
25 de noviembre inicia los libros y el primer rebalanceo es la apertura
siguiente que fije el calendario XNYS. Workflow aislado consume la fuente
común, con dos respaldos nocturnos y exclusión mutua del writer.

### GS Quant: trazabilidad de apertura y sesión reducida (26/11/2026)

Cada NAV nuevo registra `opening_execution` con resultado explícito de la orden
previa: sin orden, sin cambio, simulada o cancelada; si faltan barras exactas o
hay splits se conservan los símbolos afectados y cero fills. El siguiente
pronóstico no borra ese resultado. Además de comprobar el hash de la señal,
la fecha de emisión debe estar entre el cierre real de la sesión de origen y
la apertura real de destino, según XNYS. No se modifican las seis señales ya
congeladas el 25/11 ni el NAV inicial. La sesión del 27/11 cierra a las 18:00 UTC;
la liquidación OHLC sigue registrándose tras el cierre, sin certificar fill
observado ni disponibilidad real de préstamo.
