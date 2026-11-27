# MIDAS AI · asistente experimental

El panel usa Transformers.js y un modelo público de Hugging Face que se ejecuta en el navegador mediante WebGPU. La carga se inicia al abrir el panel; no precisa una clave de API. La ejecución y el historial de la sesión permanecen en el dispositivo, mientras que los archivos del modelo se obtienen de Hugging Face. El navegador y el dispositivo deben tener suficiente memoria y compatibilidad; el tamaño inicial del modelo ronda 600 MB.

La aplicación consulta el registro institucional, las tesis públicas, los informes aprobados y una descripción verificable de la sala de trading. Las identificaciones inequívocas fijan la fuente y producen una ficha determinista; el LLM puede añadir una síntesis cualitativa. Solo una petición explícita muestra el texto literal como respuesta principal. Las referencias de la última entidad permiten preguntas de seguimiento en la sesión. La recuperación sigue siendo léxica y la generación experimental. No se indexan fuentes no aprobadas. Las tesis son hipótesis históricas, no precios actuales ni rentabilidades realizadas.

## Desarrollo

`node --test midas-ai/retrieval.test.mjs` comprueba selección de fuentes y abstención cuando faltan coincidencias. `npm ci --prefix midas-ai --ignore-scripts` instala la versión fijada del runtime para construir la web. El empaquetado de Pages copia exclusivamente los activos necesarios. La preparación de dependencias debe ocurrir después de la auditoría del árbol, para que `node_modules` no forme parte del repositorio ni se publique.

En la prueba inicial, el modelo pequeño interpretó mal un registro y se abstuvo ante una tesis existente. Por eso las cifras de entidades inequívocas se presentan con una ficha determinista independiente de la síntesis generativa. La calidad de las respuestas libres, las condiciones de seguridad y la compatibilidad entre navegadores requieren evaluación continua.
