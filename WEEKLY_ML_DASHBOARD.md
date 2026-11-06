# MIDAS Weekly ML — dashboard

> **Forward activo.** Última señal registrada: **2026-11-06**. Las predicciones mostradas abajo fueron congeladas antes de conocer la semana objetivo.

## Progreso

| Modelo | Función | Estado | NAV | Retorno acumulado | Posiciones/órdenes | Trades cerrados |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **LightGBM Return** | Predice la rentabilidad semanal esperada de cada acción. | forward | 83,303.11 USD | -16.697% | 2 | 20 |
| **LightGBM Direction** | Estima la probabilidad de que la semana termine en positivo. | forward | 100,705.31 USD | 0.705% | 10 | 30 |
| **LightGBM Ranker** | Ordena el universo de mejor a peor oportunidad relativa. | forward | 80,662.75 USD | -19.337% | 10 | 50 |
| **MLP** | Red neuronal feed-forward sobre features tabulares. | forward | 83,524.89 USD | -16.475% | 10 | 50 |
| **LSTM** | Red temporal sobre la secuencia de las últimas 26 semanas. | forward | 89,937.44 USD | -10.063% | 10 | 50 |
| **ARIMA** | Modelo estadístico por acción sobre retornos semanales. | forward | 88,351.04 USD | -11.649% | 10 | 50 |
| **Ensemble** | Combina rankings y votos de los expertos anteriores. | forward | 79,872.70 USD | -20.127% | 10 | 50 |
| **SPY** | Benchmark S&P 500. | forward | 93,206.21 USD | -6.794% | 1 | 5 |
| **RSP** | Benchmark S&P 500 equiponderado. | forward | 100,411.20 USD | 0.411% | 1 | 5 |

## Predicciones del último forecast

**Cutoff:** 2026-11-06 · **Horizonte:** primera apertura → último cierre de la semana siguiente.

### LightGBM Return

Predice la rentabilidad semanal esperada de cada acción.

**Validación diagnóstica:** rank-IC -0.0247 · MAE 3.47 pp · iter 14

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **SLB** | 0.53% |
| 2 | **CVS** | 0.51% |
| 3 | **BALL** | 0.47% |
| 4 | **BAX** | 0.47% |
| 5 | **BX** | 0.47% |
| 6 | **CAH** | 0.47% |
| 7 | **RL** | 0.47% |
| 8 | **TAP** | 0.47% |
| 9 | **AME** | 0.46% |
| 10 | **AVGO** | 0.46% |

### LightGBM Direction

Estima la probabilidad de que la semana termine en positivo.

**Validación diagnóstica:** accuracy 56.4% · Brier 0.2446 · iter 95

| # | Ticker | Prob. positiva |
| ---: | --- | ---: |
| 1 | **FTNT** | 60.6% |
| 2 | **HUM** | 59.5% |
| 3 | **ANET** | 59.4% |
| 4 | **META** | 59.0% |
| 5 | **CRWD** | 58.7% |
| 6 | **PANW** | 58.7% |
| 7 | **FFIV** | 58.6% |
| 8 | **TDY** | 58.4% |
| 9 | **ORCL** | 58.4% |
| 10 | **CDNS** | 58.2% |

### LightGBM Ranker

Ordena el universo de mejor a peor oportunidad relativa.

**Validación diagnóstica:** rank-IC -0.0114 · iter 22

| # | Ticker | Rank score |
| ---: | --- | ---: |
| 1 | **DELL** | 0.4027 |
| 2 | **MU** | 0.3683 |
| 3 | **WDC** | 0.3395 |
| 4 | **STX** | 0.3158 |
| 5 | **HWM** | 0.2920 |
| 6 | **GNRC** | 0.2885 |
| 7 | **AMD** | 0.2877 |
| 8 | **SMCI** | 0.2851 |
| 9 | **TER** | 0.2822 |
| 10 | **MRNA** | 0.2680 |

### MLP

Red neuronal feed-forward sobre features tabulares.

**Validación diagnóstica:** rank-IC 0.0096 · MAE 3.95 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **DELL** | 14.94% |
| 2 | **SMCI** | 10.86% |
| 3 | **NOW** | 10.73% |
| 4 | **EPAM** | 10.42% |
| 5 | **TER** | 9.66% |
| 6 | **IT** | 8.96% |
| 7 | **AKAM** | 8.02% |
| 8 | **CTSH** | 7.57% |
| 9 | **STX** | 7.29% |
| 10 | **HPE** | 7.00% |

### LSTM

Red temporal sobre la secuencia de las últimas 26 semanas.

**Validación diagnóstica:** rank-IC 0.0220 · MAE 3.48 pp

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **WDC** | 1.37% |
| 2 | **INTC** | 1.34% |
| 3 | **CAT** | 1.31% |
| 4 | **SMCI** | 1.28% |
| 5 | **AXON** | 1.27% |
| 6 | **TER** | 1.25% |
| 7 | **NRG** | 1.24% |
| 8 | **STX** | 1.23% |
| 9 | **KLAC** | 1.22% |
| 10 | **LRCX** | 1.17% |

### ARIMA

Modelo estadístico por acción sobre retornos semanales.

**Validación diagnóstica:** —

| # | Ticker | Retorno previsto |
| ---: | --- | ---: |
| 1 | **WDC** | 10.81% |
| 2 | **MCHP** | 9.31% |
| 3 | **WMB** | 6.30% |
| 4 | **MRNA** | 6.25% |
| 5 | **STX** | 6.07% |
| 6 | **ROK** | 5.50% |
| 7 | **CRWD** | 5.46% |
| 8 | **TRGP** | 5.43% |
| 9 | **ABNB** | 4.66% |
| 10 | **PANW** | 4.46% |

### Ensemble

Combina rankings y votos de los expertos anteriores.

**Validación diagnóstica:** —

| # | Ticker | Score | Retorno previsto | Votos + | Dispersión |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | **STX** | 0.9401 | 3.65% | 5 | 0.0769 |
| 2 | **WDC** | 0.9363 | 2.01% | 5 | 0.0774 |
| 3 | **DELL** | 0.8794 | 0.77% | 5 | 0.1462 |
| 4 | **AMD** | 0.8788 | 0.85% | 5 | 0.1177 |
| 5 | **MU** | 0.8743 | 0.75% | 5 | 0.1158 |
| 6 | **SMCI** | 0.8733 | 1.01% | 5 | 0.1356 |
| 7 | **NOW** | 0.8673 | 0.56% | 5 | 0.1762 |
| 8 | **NRG** | 0.8470 | 1.07% | 5 | 0.1118 |
| 9 | **HPE** | 0.8448 | 0.60% | 5 | 0.1534 |
| 10 | **GEV** | 0.8410 | 0.67% | 5 | 0.1528 |


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

