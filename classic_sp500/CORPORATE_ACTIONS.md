# Canje KVUE → KMB: contabilidad y continuidad paper

El canje efectivo el 2 de noviembre de 2026 transforma cada acción KVUE en un derecho a 0,14625 acciones KMB y 3,50 USD. Las fracciones KMB se liquidan en efectivo. Fuentes: [emisor/SEC](https://www.sec.gov/Archives/edgar/data/55785/000110465926120990/tm2628636d1_8k.htm) y [OCC 60113](https://infomemo.theocc.com/infomemos?number=60113).

OCC publica para los contratos ajustados una referencia temporal basada en KMB mientras se determina el importe de las fracciones. Este laboratorio adopta esa relación exclusivamente como convención de valoración provisional de sus derechos paper. No representa una cotización negociable de KVUE ni acredita el precio final del pago.

El motor registra acciones KMB enteras y un derecho de cobro separado, compuesto por el efectivo fijo y la fracción pendiente. Hasta verificar el pago, ese derecho no aumenta el efectivo disponible para comprar. La parte fraccionaria se valora provisionalmente al cierre KMB de la misma sesión; el efectivo fijo se mantiene a su importe contractual, redondeado a céntimos. Las participaciones fraccionarias de KVUE proceden del modelo paper original; no se atribuye esta política a ningún broker.

Las posiciones KMB previas se conservan y agregan cuando carecen de protecciones incompatibles. El coste original se reparte proporcionalmente entre las acciones recibidas y el derecho de cobro utilizando la referencia temporal de la apertura efectiva; la suma de costes se conserva. Es atribución contable del modelo, no una compra ni un criterio fiscal. Los stops y objetivos del lote convertido se trasladan por la relación económica del canje.

La recuperación conserva los NAV y trades anteriores. Los cierres no procesados se registran como días sin operaciones; las órdenes vencidas y los stops cruzados quedan sin ejecutar. La primera apertura habilitada siempre es futura. El cierre del día parcialmente transcurrido también permanece sin operaciones; sus nuevas señales solo pueden usarse en la siguiente apertura.

Todos los NAV que incorporan derechos sin liquidar llevan una marca de valoración provisional. La fila pública muestra el aviso y queda fuera de la comparación certificada. Una revisión posterior con evidencia del emisor y fecha de pago permite acreditar el efectivo una sola vez. La liquidación se registra como un evento nuevo; no se sobrescriben los NAV provisionales ya publicados.

La recuperación manual se ejecuta desde el workflow existente de recuperación clásica, seleccionando `merger`. Las ejecuciones ordinarias mantienen y valoran los derechos pendientes cada día, incluso si se vende la totalidad de las acciones KMB. Un cierre sin barra KMB o una acción corporativa nueva sin revisar vuelve a bloquear la cartera afectada.
