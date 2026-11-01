# MIDAS · Puesta en producción en el repositorio público existente

El repositorio público aloja los algoritmos, el controlador y las pruebas. No es necesario crear otro repositorio. Los ficheros de posiciones, cotizaciones sujetas a licencia y credenciales deben respetar por separado sus permisos de acceso.

## Condición previa: datos y firma

La tarea existente `.github/workflows/public-market.yml` intenta capturar una sesión XNYS real solo si la variable de repositorio `MIDAS_YAHOO_RIGHTS_CONFIRMED` vale `true` y está configurado el secreto `IDEALAB_PAPER_FEED_KEY` (32 caracteres o más). La variable se debe establecer **únicamente después de comprobar que el uso del proveedor y la publicación de resultados derivados están autorizados**. No equivale a comprar una licencia ni acredita por sí sola los derechos.

En GitHub, configurar en **Settings → Secrets and variables → Actions**. No incluir nunca claves en commits, incidencias, comentarios, historial de terminal o conversaciones públicas.

El motor registra **paper**, no órdenes bancarias. El día inicial congela señales al cierre, la siguiente sesión ejecuta las entradas hipotéticas a la apertura correspondiente. Los libros solo pasan a activos si el capturador obtiene OHLC coherente, cobertura suficiente y hash de la fuente; si faltan barras, fechas o firmas se rechaza la actualización.

## Operación y auditoría

- Ejecutar la acción **MIDAS institutional public-code Yahoo paper runtime**, seleccionando `execute=true`, solo después de satisfacer las condiciones previas y en un día bursátil ya cerrado.
- La ejecución programada existente funciona lunes a viernes a las **23:07 UTC**. No inventa sesiones cerradas, y una ausencia de cotizaciones no puede contabilizarse como un resultado de cero.
- La acción **MIDAS operational state audit** genera un informe independiente sin descargar precios, lunes a viernes a las **23:47 UTC**. Puede ejecutarse manualmente cuando sea necesario.
- Ejecutar en el repositorio `python3 scripts/operational_status.py` para consultar si están conectadas la fuente y los libros y cuántas estrategias se han observado.
- Verificar los trabajos `validate` y `execute` de la acción del mercado, los hashes de los cierres, NAV y P/L, y el despliegue de Pages. El éxito del control de calidad no demuestra que se hayan realizado sesiones económicas.
- El lector de archivo histórico puede representar resultados anteriores de manera **local y manual**. No se reescribe el libro prospectivo ni se presenta esa recuperación como rentabilidad generada por IDEA LAB.

## Alcance y decisión de corte

La infraestructura actual ofrece once libros de referencia bursátil prospectivos preparados: dos carteras base y nueve variantes clásicas. Otros modelos figuran en el catálogo, pero no son equivalentes a once motores plenamente operativos ni a 64 algoritmos corriendo con datos bursátiles nuevos.

No se debe retirar la implementación anterior hasta tener evidencia verificable de: licencias y seguridad, ejecución continuada sin ordenador local, paridad por estrategia y fuente, registros económicos auditados, fiabilidad ante fallos, acceso privado a la información restringida y ensayo de restauración.

## Otras fuentes

Si no se dispone de derechos de uso para el proveedor actual, debe evaluarse otro contrato de datos. Por ejemplo, Alpaca distingue datos IEX gratuitos (cobertura parcial del mercado) y SIP de cobertura consolidada, con condiciones de acceso diferentes. Un feed de IEX **no es automáticamente equivalente** al conjunto OHLC de todas las bolsas ni sustituye dividendos, splits, históricos y metadatos requeridos por los motores. No se activará un proveedor nuevo hasta integrarlo y probar su contrato real.
