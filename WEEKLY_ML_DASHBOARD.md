# MIDAS Weekly ML — dashboard

> **Forward activo.** Última señal registrada: **2026-11-27**. Las predicciones mostradas abajo fueron congeladas antes de conocer la semana objetivo.

## Progreso

| Modelo | Función | Estado | NAV | Retorno acumulado | Posiciones/órdenes | Trades cerrados |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **LightGBM Return** | Predice la rentabilidad semanal esperada de cada acción. | forward | 80,012.16 USD | -19.988% | 0 | 30 |
| **LightGBM Direction** | Estima la probabilidad de que la semana termine en positivo. | forward | 103,057.70 USD | 3.058% | 0 | 40 |
| **LightGBM Ranker** | Ordena el universo de mejor a peor oportunidad relativa. | forward | 78,493.53 USD | -21.506% | 10 | 60 |
| **MLP** | Red neuronal feed-forward sobre features tabulares. | forward | 81,579.41 USD | -18.421% | 10 | 60 |
| **LSTM** | Red temporal sobre la secuencia de las últimas 26 semanas. | forward | 87,805.79 USD | -12.194% | 10 | 60 |
| **ARIMA** | Modelo estadístico por acción sobre retornos semanales. | forward | 84,980.20 USD | -15.020% | 10 | 60 |
| **Ensemble** | Combina rankings y votos de los expertos anteriores. | forward | 77,956.88 USD | -22.043% | 10 | 60 |
| **SPY** | Benchmark S&P 500. | forward | 93,427.27 USD | -6.573% | 1 | 6 |
| **RSP** | Benchmark S&P 500 equiponderado. | forward | 102,835.31 USD | 2.835% | 1 | 6 |

## Predicciones del último forecast

**Cutoff:** 2026-11-27 · **Horizonte:** primera apertura → último cierre de la semana siguiente.

### LightGBM Return

Predice la rentabilidad semanal esperada de cada acción.

**Validación diagnóstica:** rank-IC -0.0128 · MAE 3.50 pp · iter 68

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **GEN** | 0.07% |
| 2 | **DASH** | 0.03% |
| 3 | **NOW** | -0.02% |
| 4 | **DDOG** | -0.02% |
| 5 | **FTNT** | -0.11% |
| 6 | **CRM** | -0.11% |
| 7 | **GOOGL** | -0.12% |
| 8 | **WDAY** | -0.12% |
| 9 | **GOOG** | -0.14% |
| 10 | **EXPE** | -0.15% |

### LightGBM Direction

Estima la probabilidad de que la semana termine en positivo.

**Validación diagnóstica:** accuracy 59.2% · Brier 0.2390 · iter 202

| # | Ticker | Prob. positiva |
| ---: | --- | ---: |
| 1 | **IQV** | 53.4% |
| 2 | **COP** | 52.9% |
| 3 | **DOW** | 52.6% |
| 4 | **XOM** | 52.5% |
| 5 | **CVX** | 52.5% |
| 6 | **APA** | 52.3% |
| 7 | **LH** | 52.2% |
| 8 | **ELV** | 51.9% |
| 9 | **EOG** | 51.9% |
| 10 | **PODD** | 51.6% |

### LightGBM Ranker

Ordena el universo de mejor a peor oportunidad relativa.

**Validación diagnóstica:** rank-IC -0.0535 · iter 8

| # | Ticker | Rank score |
| ---: | --- | ---: |
| 1 | **CRWD** | 0.1115 |
| 2 | **AMD** | 0.1063 |
| 3 | **AVGO** | 0.0869 |
| 4 | **STX** | 0.0667 |
| 5 | **WDC** | 0.0667 |
| 6 | **ADI** | 0.0651 |
| 7 | **INTU** | 0.0649 |
| 8 | **ANET** | 0.0645 |
| 9 | **DDOG** | 0.0533 |
| 10 | **AKAM** | 0.0518 |

### MLP

Red neuronal feed-forward sobre features tabulares.

**Validación diagnóstica:** rank-IC 0.0349 · MAE 3.94 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **TER** | 13.00% |
| 2 | **ON** | 8.45% |
| 3 | **HPQ** | 8.29% |
| 4 | **GEV** | 6.45% |
| 5 | **NOW** | 6.28% |
| 6 | **JCI** | 6.27% |
| 7 | **VST** | 6.07% |
| 8 | **CSCO** | 6.05% |
| 9 | **NTAP** | 6.05% |
| 10 | **AXON** | 5.60% |

### LSTM

Red temporal sobre la secuencia de las últimas 26 semanas.

**Validación diagnóstica:** rank-IC 0.0092 · MAE 3.56 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **COIN** | 1.44% |
| 2 | **STX** | 1.16% |
| 3 | **WDC** | 1.13% |
| 4 | **GLW** | 1.11% |
| 5 | **FICO** | 1.05% |
| 6 | **TPL** | 1.04% |
| 7 | **NRG** | 1.03% |
| 8 | **TER** | 1.03% |
| 9 | **MU** | 0.99% |
| 10 | **GEV** | 0.98% |

### ARIMA

Modelo estadístico por acción sobre retornos semanales.

**Validación diagnóstica:** —

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **MRNA** | 5.64% |
| 2 | **MHK** | 3.38% |
| 3 | **ZBRA** | 3.16% |
| 4 | **ACN** | 3.09% |
| 5 | **CRWD** | 3.01% |
| 6 | **ROP** | 2.99% |
| 7 | **CTSH** | 2.81% |
| 8 | **CRL** | 2.64% |
| 9 | **CLX** | 2.60% |
| 10 | **WTW** | 2.59% |

### Ensemble

Combina rankings y votos de los expertos anteriores.

**Validación diagnóstica:** —

| # | Ticker | Score | Retorno previsto | Votos + | Dispersión |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | **DDOG** | 0.8258 | 0.43% | 2 | 0.3181 |
| 2 | **CRWD** | 0.8159 | 1.72% | 3 | 0.2125 |
| 3 | **FFIV** | 0.8122 | 0.16% | 2 | 0.1534 |
| 4 | **MPC** | 0.7703 | 0.69% | 3 | 0.2773 |
| 5 | **WDAY** | 0.7514 | 0.84% | 3 | 0.2814 |
| 6 | **UAL** | 0.7509 | 0.77% | 3 | 0.1337 |
| 7 | **ZBRA** | 0.7505 | 1.78% | 3 | 0.2569 |
| 8 | **VLO** | 0.7488 | 0.30% | 3 | 0.2356 |
| 9 | **COIN** | 0.7461 | 0.57% | 2 | 0.3250 |
| 10 | **CRL** | 0.7452 | 1.42% | 3 | 0.3024 |


## Cómo interpretarlo

- **Predicción ≠ rentabilidad realizada.**
- La validación cronológica sirve para diagnóstico; no se suma al track record demo.
- El bootstrap está excluido del forward y fue generado antes de activar el sizing fraccionado; no se reescribe retrospectivamente.
- Cuando exista ledger forward, el NAV y los trades cerrados de cada experto se acumularán aquí.
- SPY y RSP son referencias, no modelos.

## Fuentes

- weekly_ml_state/forecasts/: forecasts forward inmutables.
- weekly_ml_state/ledger.json: NAV, órdenes y trades forward.
- weekly_ml_bootstrap_state/: bootstrap técnico inicial.
- strategy_state/dashboard.md: comparador global de todas las estrategias MIDAS.

