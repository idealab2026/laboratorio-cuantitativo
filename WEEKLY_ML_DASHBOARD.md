# MIDAS Weekly ML — dashboard

> **Forward activo.** Última señal registrada: **2026-11-20**. Las predicciones mostradas abajo fueron congeladas antes de conocer la semana objetivo.

## Progreso

| Modelo | Función | Estado | NAV | Retorno acumulado | Posiciones/órdenes | Trades cerrados |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **LightGBM Return** | Predice la rentabilidad semanal esperada de cada acción. | forward | 83,303.11 USD | -16.697% | 10 | 20 |
| **LightGBM Direction** | Estima la probabilidad de que la semana termine en positivo. | forward | 100,705.31 USD | 0.705% | 10 | 30 |
| **LightGBM Ranker** | Ordena el universo de mejor a peor oportunidad relativa. | forward | 80,662.75 USD | -19.337% | 10 | 50 |
| **MLP** | Red neuronal feed-forward sobre features tabulares. | forward | 83,524.89 USD | -16.475% | 10 | 50 |
| **LSTM** | Red temporal sobre la secuencia de las últimas 26 semanas. | forward | 89,937.44 USD | -10.063% | 10 | 50 |
| **ARIMA** | Modelo estadístico por acción sobre retornos semanales. | forward | 88,351.04 USD | -11.649% | 10 | 50 |
| **Ensemble** | Combina rankings y votos de los expertos anteriores. | forward | 79,872.70 USD | -20.127% | 10 | 50 |
| **SPY** | Benchmark S&P 500. | forward | 93,206.21 USD | -6.794% | 1 | 5 |
| **RSP** | Benchmark S&P 500 equiponderado. | forward | 100,411.20 USD | 0.411% | 1 | 5 |

## Predicciones del último forecast

**Cutoff:** 2026-11-20 · **Horizonte:** primera apertura → último cierre de la semana siguiente.

### LightGBM Return

Predice la rentabilidad semanal esperada de cada acción.

**Validación diagnóstica:** rank-IC -0.0098 · MAE 3.54 pp · iter 70

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **STX** | 8.54% |
| 2 | **WDC** | 8.21% |
| 3 | **SMCI** | 8.07% |
| 4 | **GLW** | 7.94% |
| 5 | **INTC** | 7.44% |
| 6 | **FIS** | 7.34% |
| 7 | **COIN** | 7.23% |
| 8 | **AMD** | 7.13% |
| 9 | **MU** | 7.11% |
| 10 | **FICO** | 6.95% |

### LightGBM Direction

Estima la probabilidad de que la semana termine en positivo.

**Validación diagnóstica:** accuracy 56.7% · Brier 0.2458 · iter 74

| # | Ticker | Prob. positiva |
| ---: | --- | ---: |
| 1 | **TPL** | 84.6% |
| 2 | **EQT** | 84.3% |
| 3 | **EXE** | 84.3% |
| 4 | **BSX** | 84.3% |
| 5 | **VICI** | 84.0% |
| 6 | **PODD** | 83.9% |
| 7 | **SCHW** | 83.7% |
| 8 | **GLW** | 83.7% |
| 9 | **FICO** | 83.6% |
| 10 | **NOC** | 83.6% |

### LightGBM Ranker

Ordena el universo de mejor a peor oportunidad relativa.

**Validación diagnóstica:** rank-IC -0.0295 · iter 8

| # | Ticker | Rank score |
| ---: | --- | ---: |
| 1 | **MU** | 0.2279 |
| 2 | **TER** | 0.2279 |
| 3 | **LRCX** | 0.2254 |
| 4 | **ADI** | 0.2198 |
| 5 | **SWKS** | 0.2102 |
| 6 | **MPWR** | 0.2040 |
| 7 | **AMD** | 0.1983 |
| 8 | **PWR** | 0.1922 |
| 9 | **TXN** | 0.1922 |
| 10 | **CHTR** | 0.1902 |

### MLP

Red neuronal feed-forward sobre features tabulares.

**Validación diagnóstica:** rank-IC 0.0068 · MAE 4.02 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **MRNA** | 18.18% |
| 2 | **HPE** | 16.51% |
| 3 | **AMD** | 12.85% |
| 4 | **ABNB** | 12.76% |
| 5 | **MU** | 11.76% |
| 6 | **MOH** | 11.65% |
| 7 | **DELL** | 11.38% |
| 8 | **MOS** | 11.37% |
| 9 | **AVGO** | 11.30% |
| 10 | **DXCM** | 9.35% |

### LSTM

Red temporal sobre la secuencia de las últimas 26 semanas.

**Validación diagnóstica:** rank-IC 0.0177 · MAE 3.56 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **GLW** | 1.76% |
| 2 | **NVDA** | 1.64% |
| 3 | **CAT** | 1.47% |
| 4 | **GEV** | 1.44% |
| 5 | **COIN** | 1.31% |
| 6 | **CTVA** | 1.30% |
| 7 | **NRG** | 1.26% |
| 8 | **TPL** | 1.21% |
| 9 | **CMI** | 1.17% |
| 10 | **INTC** | 1.16% |

### ARIMA

Modelo estadístico por acción sobre retornos semanales.

**Validación diagnóstica:** —

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **AMD** | 9.00% |
| 2 | **MU** | 7.74% |
| 3 | **ANET** | 6.81% |
| 4 | **ADI** | 6.74% |
| 5 | **MRNA** | 6.49% |
| 6 | **TXN** | 6.15% |
| 7 | **MPC** | 5.67% |
| 8 | **URI** | 5.65% |
| 9 | **IRM** | 5.58% |
| 10 | **CEG** | 5.55% |

### Ensemble

Combina rankings y votos de los expertos anteriores.

**Validación diagnóstica:** —

| # | Ticker | Score | Retorno previsto | Votos + | Dispersión |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | **STX** | 0.9167 | 4.35% | 5 | 0.0731 |
| 2 | **ADI** | 0.8794 | 6.14% | 5 | 0.1297 |
| 3 | **MPWR** | 0.8743 | 4.15% | 5 | 0.0836 |
| 4 | **ARE** | 0.8610 | 3.02% | 5 | 0.0932 |
| 5 | **MCHP** | 0.8511 | 3.35% | 5 | 0.0879 |
| 6 | **GS** | 0.8502 | 4.48% | 5 | 0.1008 |
| 7 | **AVGO** | 0.8494 | 5.24% | 5 | 0.1605 |
| 8 | **ANET** | 0.8408 | 5.98% | 5 | 0.1868 |
| 9 | **KLAC** | 0.8342 | 3.67% | 5 | 0.2145 |
| 10 | **MRNA** | 0.8313 | 5.75% | 5 | 0.2862 |


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

