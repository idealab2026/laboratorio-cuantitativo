# Laboratorio cuantitativo · IDEA LAB

Sitio público independiente para una competición de estrategias **paper**, comparadores y tesis de investigación falsables.

**Estado de la versión:** aplicación interactiva con datos completamente sintéticos; ninguna cifra representa carteras, inversiones ni operaciones reales.

## Arquitectura
- Frontend estático: `index.html`, `styles.css`, `src/site.mjs`.
- Contratos y estadísticas en `src/metrics.mjs`.
- Muestra ficticia explícita en `data/demo.json`.
- Pipeline gratuito GitHub Pages con pruebas, control de procedencia e inclusión explícita de artefactos.

## Diseño experimental
Cada estrategia exige reglas, una fecha de preregistro, universo, costes, divisa, NAV y benchmark. Una posición pendiente por ausencia de precio no es un fill. La comparación requiere ventana común, métricas verificables y documentación del sesgo retrospectivo.

## Política de datos
No reutilizar código, históricos ni identificadores de ningún sistema previo. No conectar cuentas de inversión, operaciones reales, credenciales, servidores o hojas privadas. Antes de incorporar material no sintético, verificar permisos de distribución de cotizaciones y metodología de ejecución.

## Privacidad
Todos los archivos y commits son institucionales. El paquete web utiliza una lista blanca; el pipeline bloquea datos inesperados. El anonimato absoluto ante correlaciones con información pública anterior no puede garantizarse.

## Licencia
Todos los derechos reservados salvo indicación expresa en futuras incorporaciones.
