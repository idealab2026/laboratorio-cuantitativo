# KVUE → KMB — revisión de la liquidación de fracciones (2026-11-24)

## Evidencia incorporada

- [Kenvue Form 8-K, 2 de noviembre de 2026](https://www.sec.gov/Archives/edgar/data/1944048/000095015726001147/form8-k.htm): contraprestación de 0,14625 acciones KMB y 3,50 USD por acción KVUE, con efectivo en lugar de fracciones.
- [Prospecto S-4](https://www.sec.gov/Archives/edgar/data/55785/000114036125044277/ny20059815x1_s4.htm): para acciones ordinarias, la fracción se paga en efectivo usando la media de los VWAP diarios de las cinco sesiones anteriores al cierre del canje, redondeando al céntimo.
- [OCC memo 60189, 10 de noviembre de 2026](https://infomemo.theocc.com/infomemos?number=60189): para opciones ajustadas KMB1, OCC comunica una referencia definitiva de 109,2059 USD por acción KMB para el efectivo sustitutivo de fracciones. La fracción de 0,625 por contrato equivale a 68,25 USD. Es evidencia de la valoración en el contrato de opciones, no prueba de recepción de fondos en acciones ordinarias.

## Impacto indicativo sobre los derechos existentes

Lectura del libro clásico en commit 124195cc9cdf10598b7696b91ef16b726b1ca20e. Aplicando, únicamente como comprobación condicional, la referencia OCC a las fracciones de los dos derechos pendientes:

| Libro | Efectivo fijo (USD) | Fracción KMB | Efectivo fraccional indicativo (USD) | Total indicativo (USD) |
|---|---:|---:|---:|---:|
| IL-010 Equiponderación | 35,91 | 0,50056507250 | 54,66 | 90,57 |
| IL-012 Genético congelado | 2257,90 | 0,34802970125 | 38,01 | 2295,91 |

No hay autorización para contabilizar estos totales como fondos disponibles: falta una confirmación de la liquidación de acciones ordinarias acorde con el contrato vigente de `classic_sp500/corporate_actions.py`. El memo OCC no satisface por sí solo el requisito de evidencia del emisor y no confirma una fecha de pago de accionistas.

## Decisión operativa

Conservar intactos los libros, el bloqueo de gasto del derecho pendiente, los NAV ya publicados y la clasificación no certificada. No insertar una revisión en `merger_settlements` ni relajar las verificaciones de `settle_reviewed_claims`. La referencia se documenta para una posterior revisión prospectiva, diferenciando valoración de liquidación y sin reconstruir transacciones históricas.
