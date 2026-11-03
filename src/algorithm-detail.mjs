/**
 * Public, explanatory methodology registry for MIDAS paper strategies.
 * Equations are pedagogical reference models, not a claim that unknown
 * internal hyperparameters, trained weights or orders were recovered.
 * Never import personal history or invent live performance.
 */
const family=(theory,equation,signal,validation)=>({theory,equation,signal,validation});
const CATALOG={
 passive:family(
  "Exposición pasiva de referencia. Sirve para medir si la selección activa compensa su complejidad y costes.",
  "R(t) = NAV(t) / NAV(0) − 1;  NAV(t) = efectivo(t) + Σ acciones(i,t) × precio(i,t).",
  "Mantener el instrumento de referencia entre rebalanceos; registrar dividendos, costes y divisa cuando proceda.",
  "Comparar con el mismo calendario, moneda y fuente de cotizaciones; distinguir seguimiento de índice y cartera invertible."),
 equal:family(
  "Equiponderación: diversificar el peso inicial entre N valores. No equivale a ponderación por capitalización.",
  "w(i,t₀) = 1/N;  NAV(t) = efectivo(t) + Σ q(i,t) × P(i,t).",
  "Reequilibrar solo en las sesiones definidas en el protocolo; no suponer rotación diaria sin evidencia.",
  "Separar efecto del universo de acciones, frecuencia de rebalanceo, costes y supervivencia de los valores."),
 ema:family(
  "Cruce de tendencia suavizada y control de momentum mediante medias móviles exponenciales y RSI.",
  "EMA(t) = α·P(t) + (1−α)·EMA(t−1), α=2/(n+1); RSI = 100−100/(1+RS).",
  "La regla exacta de entrada/salida y los umbrales requieren el archivo de configuración de esta variante; la fórmula solo identifica la familia.",
  "Evaluar desfase de señales, reversión de tendencia, sensibilidad de ventanas y costes de rotación."),
 genetic:family(
  "Búsqueda evolutiva de reglas o parámetros bajo una función de aptitud. La versión congelada aplica parámetros escogidos previamente; no reentrena en cada sesión.",
  "θ* = arg maxθ Fitness(θ);  Fitness(θ) = utilidad(R, riesgo, costes), definida antes de evaluar.",
  "Aplicar reglas congeladas al universo y periodo de la campaña; no interpretar la rentabilidad como prueba de generalización genética.",
  "Exigir evidencia de partición train/test, semilla, límite de búsqueda, sensibilidad y riesgo de sobreajuste."),
 macd:family(
  "Indicador de convergencia y divergencia de medias exponenciales para medir cambios de momentum.",
  "MACD(t) = EMA₁₂(P)(t) − EMA₂₆(P)(t); Señal(t) = EMA₉(MACD)(t).",
  "Los cruces MACD–señal son una posible condición de entrada; filtros de volumen y exposición requieren configuración corroborada.",
  "Examinar costes, whipsaw en mercados laterales, señales en t y ejecución posterior."),
 rsi:family(
  "Reversión a la media a partir de la fortaleza relativa de las subidas y bajadas recientes.",
  "RSI₁₄(t) = 100 − 100/(1 + media_subidas₁₄/media_bajadas₁₄).",
  "Los umbrales 70/30 solo se atribuyen a variantes cuyo nombre lo documenta; en otras quedan sujetos a verificación.",
  "Evaluar tendencias persistentes, señales contradictorias, gaps y costes del paso por efectivo."),
 bollinger:family(
  "Bandas de volatilidad sobre una media móvil. Una ruptura intenta capturar continuación de movimiento, no necesariamente reversión.",
  "Banda_sup(t) = SMA₂₀(t) + k·σ₂₀(t); Banda_inf(t) = SMA₂₀(t) − k·σ₂₀(t).",
  "La ventana de 20 periodos figura en la variante; el multiplicador k y la regla exacta de negociación requieren configuración.",
  "Comprobar sensibilidad a volatilidad, falsas rupturas, dependencia temporal y costes."),
 turtle:family(
  "Seguimiento de tendencia mediante canales de máximos/mínimos precedentes, con salida por una ventana más corta.",
  "Entrada_larga(t): P(t)>máx(P(t−n)…P(t−1)); salida: P(t)<mín(P(t−m)…P(t−1)).",
  "Las variantes 20/10 y 55/20 tienen n/m indicados por su nombre. La evaluación evita usar el máximo/mínimo del futuro.",
  "Analizar mercados laterales, gap overnight, stop, sizing y costes de cambio de posiciones."),
 turtleShort:family(
  "Contrapartida bajista del enfoque Donchian: explotar rupturas de mínimos mediante exposición corta, si el motor lo admite.",
  "Entrada_corta(t): P(t)<mín(P(t−n)…P(t−1)); salida: P(t)>máx(P(t−m)…P(t−1)).",
  "Horizontes documentados en el nombre de cada variante; las operaciones cortas exigen disponibilidad de préstamo y costes.",
  "Modelar financiación y margen, borrow fees, gaps adversos y restricciones legales."),
 lightgbmReturn:family(
  "Gradient boosting sobre árboles para estimar retornos condicionales a variables conocidas antes del corte.",
  "ŷ(t+1) = Σₖ η·fₖ(X(t));  fₖ = árbol entrenado en datos anteriores al corte.",
  "Ordenar activos por retorno previsto bajo restricciones de liquidez; los modelos/pesos realmente entrenados han de estar versionados.",
  "Validación walk-forward, purging, disponibilidad efectiva de features y comparación con baseline."),
 lightgbmDirection:family(
  "Clasificación supervisada del signo del retorno futuro.",
  "p(t) = σ(F(X(t)));  señal = 1[p(t)>τ], con τ fijado fuera de muestra.",
  "La predicción de signo no determina el tamaño del retorno ni la rentabilidad después de costes.",
  "Calibración, precisión direccional, clases desbalanceadas y evaluación económica neta."),
 lightgbmRank:family(
  "Ranking cross-sectional: escoger valores con mejor orden relativo de oportunidades.",
  "score(i,t) = F(X(i,t));  ranking(t) = argsort_i score(i,t).",
  "Seleccionar los primeros K del universo elegible; K, universo y restricciones deben proceder de configuración verificable.",
  "NDCG/IC fuera de muestra, supervivencia de universo, coste de turnover y concentración."),
 mlp:family(
  "Red neuronal multicapa para aproximar relaciones no lineales entre indicadores y un objetivo financiero.",
  "h₁ = φ(W₁X+b₁); …; ŷ = W_L h_(L−1)+b_L.",
  "La arquitectura y los pesos no se reconstruyen desde los diarios NAV; requieren artefactos de entrenamiento.",
  "Separación temporal, regularización, sensibilidad, semillas, drift y contraste contra modelos lineales."),
 lstm:family(
  "Red recurrente con compuertas para dependencias temporales sin incorporar datos posteriores a t.",
  "fₜ=σ(W_f·[hₜ₋₁,xₜ]+b_f); cₜ=fₜ⊙cₜ₋₁+iₜ⊙ĉₜ.",
  "El horizonte de input, features, pesos y criterio de rebalanceo requieren el modelo validado.",
  "Pruebas rolling-origin, embargo temporal, estabilidad de entrenamiento y comparativa ARIMA/naive."),
 arima:family(
  "Modelo estadístico autorregresivo e integrado con componente de media móvil para series temporales.",
  "φ(B)(1−B)^d yₜ = θ(B) εₜ, donde B es el operador retardo.",
  "La elección de (p,d,q), estacionalidad y señal económica necesita su registro de ajuste.",
  "Residuos, estacionariedad, intervalos, recálculo por ventana y baseline de paseo aleatorio."),
 ensemble:family(
  "Combinación de distintos estimadores para reducir dependencia de una única familia de modelos.",
  "ŷ_ens(t) = Σₖ wₖ · ŷₖ(t);  Σₖ wₖ=1.",
  "Ponderaciones y procedimiento de agregación deben fijarse antes de medir el resultado evaluado.",
  "Diversidad de errores, correlación de señales, ablation y mejora incremental neta."),
 ahp:family(
  "Selección multicriterio: integrar señales técnicas, preferencias de riesgo y criterios ordinales mediante AHP.",
  "A·w = λ_max·w; Σwᵢ=1; ratio_consistencia = CI/RI.",
  "Los pesos exactos y las matrices de comparación históricas deben recuperarse de una versión documental, no deducirse de los NAV.",
  "Consistencia de juicios, estabilidad de ranking, sesgo de optimización y restricciones operativas."),
 capitalCycle:family(
  "Capital Cycle: la inversión y la retirada de oferta alteran futuros retornos sobre capital. Combina infrainversión, calidad y catalizadores de cambio de ciclo.",
  "ROIC = NOPAT / capital_invertido; spread = ROIC − WACC; señal = f(disciplina_capex, calidad, giro).",
  "El nombre describe factores de investigación; la ponderación concreta y cada compra/venta requieren el libro original.",
  "Controlar disponibilidad temporal de cuentas, revisiones, concentraciones, liquidez, costes y robustez por sector."),
 buyDip:family(
  "Compra escalonada en caídas condicionada a valoración y situaciones especiales, reservando capacidad de compra para descensos posteriores.",
  "drawdown(t) = P(t)/máx(P(0..t))−1; exposición(t)=f(drawdown, valoración, liquidez).",
  "Los umbrales y tamaño de escalones necesitan un protocolo congelado; no se deducen de una rentabilidad positiva.",
  "Distinguir rebote frente a deterioro permanente, coste de oportunidad del efectivo, supervivencia y drawdown."),
 timesfm:family(
  "Modelo fundacional preentrenado de series temporales en enfoque zero-shot, condicionado a ventanas de precios/retornos.",
  "ŷ(t+1:t+H) = f_preentrenado(x(t−L+1:t)); no implica fine-tuning.",
  "Confirmar la versión de TimesFM, disponibilidad real del modelo y cómo la proyección se traduce en órdenes paper.",
  "Baselines ingenuos, cambios de régimen, precisión de horizontes y ejecución neta."),
 ichimoku:family(
  "Sistema de tendencia, soporte/resistencia y momentum mediante máximos/mínimos de múltiples ventanas.",
  "Tenkan = [máx₉(H)+mín₉(L)]/2; Kijun=[máx₂₆(H)+mín₂₆(L)]/2.",
  "Desplazamientos del indicador en gráfico no deben implicar acceso anticipado a cierres futuros.",
  "Separar señal, disponibilidad, ejecución, filtros de tendencia y gaps."),
 gap:family(
  "Estrategia intradía basada en diferencia entre apertura y cierre previo.",
  "gap(t) = Open(t)/Close(t−1) − 1; R_OC(t) = Close(t)/Open(t) − 1.",
  "La entrada a apertura exige datos y órdenes factibles a esa hora; la brecha no puede usarse retrospectivamente para comprar al mismo precio sin coste.",
  "Examinar subastas, spreads, capacidad, slippage y selección condicional."),
 momentum:family(
  "Momentum cross-sectional: preferencia por activos con mayor rentabilidad pasada en un horizonte fijado.",
  "mom(i,t) = P(i,t)/P(i,t−L) − 1; selección = top_K(mom).",
  "Frecuencia mensual y tratamiento de delistings y universo histórico requieren auditoría independiente.",
  "Rotación, sesgo de supervivencia, rebalanceo y factores de riesgo."),
 markowitz:family(
  "Asignación media-varianza: optimizar exposición entre retornos esperados y covarianzas estimadas.",
  "min_w wᵀΣw − λ μᵀw;  Σwᵢ=1, con límites de posición.",
  "Parámetros estimados, restricciones y riesgo de inestabilidad deben estar documentados; no inferir de una curva.",
  "Error de estimación, regularización, ventanas rolling y comparación equiponderada."),
 fundamental:family(
  "Filtro fundamental: combinar criterios de valoración, calidad y rentabilidad empresarial antes de seleccionar candidatos.",
  "FCF_yield = FCF / capitalización;  EV/EBIT = valor_empresa / EBIT.",
  "La regla de decisión se fija con los estados financieros disponibles en la fecha de señal y sus revisiones posteriores.",
  "Disponibilidad de informes, sesgos de look-ahead, costes y diferencia entre screening y operaciones."),
 crypto:family(
  "Exposición a criptomercados; la disponibilidad 24/7 y los costes de la plataforma difieren de las sesiones bursátiles.",
  "NAV(t) = efectivo(t) + cantidad_BTC(t) × precio_BTC(t); retorno= NAV(t)/NAV(0)−1.",
  "Sin ledger específico no puede afirmarse qué órdenes se ejecutaron, ni con qué comisión.",
  "Reconciliar timestamps, spreads, comisiones, discontinuidades de exchange y custodia."),
 general:family(
  "El registro permite identificar una estrategia, pero no sustituye su protocolo científico original.",
  "R_acum = 100 × [NAV_último / capital_inicial − 1], si ambos están verificados.",
  "No atribuir señales, umbrales ni pesos no presentes en la fuente técnica del algoritmo.",
  "Exigir código versionado, parámetros, fuentes, reloj causal, sesiones y libro de NAV antes de afirmar comparabilidad.")
};
const priority=[
 [/^(?:classic_sp500_)?benchmark_spy$|benchmark_(?:spy|rsp)/, "passive"],
 [/buy_hold_equal_weight|classic_sp500_buy_hold_equal_weight/,"equal"],
 [/capital_cycle/,"capitalCycle"],
 [/timesfm_.*spy_eur/,"passive"],
 [/buy_the_dip/,"buyDip"],
 [/timesfm/,"timesfm"],
 [/ema_rsi/,"ema"],
 [/genetic|genetico/,"genetic"],
 [/macd/,"macd"],
 [/bollinger/,"bollinger"],
 [/turtle_short_|short_.*turtle/,"turtleShort"],
 [/turtle/,"turtle"],
 [/rsi/,"rsi"],
 [/lgbm_combined|ensemble/,"ensemble"],
 [/lgbm.*ranker/,"lightgbmRank"],
 [/lgbm.*direction/,"lightgbmDirection"],
 [/lgbm|lightgbm/,"lightgbmReturn"],
 [/ensemble|combined/,"ensemble"],
 [/lstm/,"lstm"],
 [/mlp/,"mlp"],
 [/arima/,"arima"],
 [/ichimoku/,"ichimoku"],
 [/gap/,"gap"],
 [/momentum/,"momentum"],
 [/markowitz/,"markowitz"],
 [/fundamental/,"fundamental"],
 [/coinbase|btc|crypto/,"crypto"],
 [/ahp|multicriterio/,"ahp"]
];
export function algorithmTheory(sourceId,group=""){
 const key=typeof sourceId==="string"?sourceId.toLowerCase():"";
 const familyId=priority.find(([matcher])=>matcher.test(key))?.[1]||
  (/multicriterio/.test(group.toLowerCase())?"ahp":"general");
 const detail=CATALOG[familyId];
 return Object.freeze({...detail,familyId,scope:
  "Formulación teórica de referencia; los parámetros, pesos y reglas exactas solo se consideran verificados si constan en el protocolo y código de la campaña."});
}
export function paperLeaderboard(entries){
 if(!Array.isArray(entries))throw Error("Invalid paper leaderboard source");
 const rows=entries.filter(row=>row&&!row.candidate&&
  row.record&&typeof row.record.return_pct==="number"&&
  Number.isFinite(row.record.return_pct)&&
  typeof row.record.first_session==="string"&&
  /^\d{4}-\d\d-\d\d$/.test(row.record.first_session)&&
  Number.isInteger(row.record.session_count)&&row.record.session_count>=1);
 return [...rows].sort((a,b)=>b.record.return_pct-a.record.return_pct||
  a.id.localeCompare(b.id))[0]||null;
}
