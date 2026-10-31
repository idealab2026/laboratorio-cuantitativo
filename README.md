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
