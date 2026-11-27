# MIDAS AI · asistente experimental

El panel usa Transformers.js y un modelo público de Hugging Face que se ejecuta en el navegador mediante WebGPU. La descarga es opcional; no precisa una clave de API. La ejecución y el historial de la sesión permanecen en el dispositivo, mientras que los archivos del modelo se obtienen de Hugging Face. El navegador y el dispositivo deben tener suficiente memoria y compatibilidad; el tamaño inicial del modelo ronda 600 MB.

La aplicación consulta el registro institucional de estrategias y el archivo público de tesis. No incorpora todas las fuentes de MIDAS. Para identificadores y empresas inequívocos muestra el fragmento original. Las consultas generales se responden con un modelo pequeño y recuperación léxica; la salida es experimental, puede ser incorrecta y debe contrastarse con las fuentes. Las tesis son hipótesis históricas, no precios actuales ni rentabilidades realizadas.

## Desarrollo

`node --test midas-ai/retrieval.test.mjs` comprueba selección de fuentes y abstención cuando faltan coincidencias. `npm ci --prefix midas-ai --ignore-scripts` instala la versión fijada del runtime para construir la web. El empaquetado de Pages copia exclusivamente los activos necesarios. La preparación de dependencias debe ocurrir después de la auditoría del árbol, para que `node_modules` no forme parte del repositorio ni se publique.

En la prueba inicial, el modelo pequeño interpretó mal un registro y se abstuvo ante una tesis existente. Por eso las consultas con identificación inequívoca muestran datos de la fuente directamente. La calidad de las respuestas libres, las condiciones de seguridad y la compatibilidad entre navegadores requieren evaluación continua.
