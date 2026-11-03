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
