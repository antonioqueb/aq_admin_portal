# -*- coding: utf-8 -*-
"""Integra el LISTADO DE PENDIENTES 23/08/26 al portal de Operaciones y Administración.

Uso:  python3 aq_admin_portal/tools/import_pendientes.py [--dry-run]
Idempotente: cada elemento lleva su clave (HEX-VENT-01, SOM-ENT-01, SAI-CRE-01…) al inicio del nombre.
Todo se crea a nombre de OdooBot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from odoo_client import OdooClient  # noqa

DRY = "--dry-run" in sys.argv
HOY = "2026-08-23"

# ---------------------------------------------------------------- frentes (proyectos)
FRENTES = [
    dict(key="HEX-VENT", name="Hexágonos · Ventas multilínea", partner="Hexágonos Mexicanos", service_type="desarrollo", stage="estabilizacion",
         objective="Cerrar el ajuste posterior a la entrega del módulo de órdenes multilínea y confirmar su cobro.",
         scope="Módulo de ventas multilínea entregado y facturado. Pendiente: mostrar el folio en las líneas de la orden.",
         next_action="Entregar el ajuste del folio en las líneas de la orden", next_date="2026-08-24"),
    dict(key="HEX-RH", name="Hexágonos · Control de asistencias y Recursos Humanos", partner="Hexágonos Mexicanos", service_type="desarrollo", stage="estabilizacion",
         objective="Corregir, validar y formalizar la entrega del módulo de asistencias para habilitar su aceptación y su pago.",
         scope="Importación del reloj checador, asociación con empleados, operación entre plantas, documentación para supervisores y proceso de alta de empleados.",
         next_action="Obtener el archivo que falló y corregir la importación del reloj checador", next_date="2026-08-26"),
    dict(key="HEX-LOG", name="Hexágonos · Facturado contra entregado", partner="Hexágonos Mexicanos", service_type="desarrollo", stage="ejecucion",
         objective="Reconstruir el seguimiento de facturación contra entregas usando el folio de factura de CONTPAQi como clave operativa.",
         scope="Importación del Excel de CONTPAQi, identificación por folio de factura, entregas parciales y aceptación de la versión corregida. Proyecto aún no facturado.",
         next_action="Definir el modelo de identificación por folio de factura", next_date="2026-08-26"),
    dict(key="HEX-INV", name="Hexágonos · Inventario y entregas", partner="Hexágonos Mexicanos", service_type="implementacion", stage="ejecucion",
         objective="Conciliar el inventario mensual y comenzar a operar las entregas reales dentro del sistema.",
         scope="Recepción y conciliación del inventario de corte, arranque de entregas reales y gobierno del catálogo de productos.",
         next_action="Solicitar a Hexágonos el archivo de inventario del corte de agosto", next_date="2026-08-26"),
]

EPICAS = {
    "SOM": ["Estabilización de entregas", "Aplicación móvil", "Compras y lotes", "Recepciones", "Costos y catálogo de productos"],
    "SAI": ["Etapa 2 · Formalización (canal Creattivo)", "Solicitudes de Calidad (canal SAI)"],
    "HEX-RH": ["Corrección y aceptación del módulo", "Documentación y adopción", "Nuevos alcances por cotizar"],
    "HEX-LOG": ["Corrección del modelo y la importación", "Funcionalidad y aceptación"],
    "HEX-INV": ["Conciliación y arranque de operación", "Catálogo de productos"],
}

P = lambda x: {"Crítica": "2", "Alta": "1", "Media": "0", "Media/Baja": "0", "Baja": "0"}[x]

# ---------------------------------------------------------------- elementos de trabajo
ITEMS = [
    # ---------- HEXÁGONOS · VENTAS MULTILÍNEA
    dict(code="HEX-VENT-01", proj="HEX-VENT", epic=None, title="Mostrar el folio en las líneas de la orden", type="tarea", prio="Crítica", due="2026-08-24",
         owner="Antonio", est=4, state="por_hacer", client=True,
         sit="El módulo de órdenes multilínea ya fue entregado, pero para conocer el folio asociado todavía deben consultar el reporte de entregas.",
         acc=["Agregar una columna en las líneas de la orden que muestre directamente el folio correspondiente."],
         crit="El folio se visualiza correctamente desde la orden, sin entrar al reporte de entregas.", extra="Tipo: ajuste posterior a entrega."),
    # ---------- HEXÁGONOS · RH
    dict(code="HEX-RH-01", proj="HEX-RH", epic="Corrección y aceptación del módulo", title="Corregir la importación del reloj checador", type="defecto", prio="Crítica",
         due="2026-08-26", est=12, state="por_hacer", found="produccion", unplanned=True,
         sit="El módulo falló durante la prueba productiva al importar el archivo generado por el reloj checador.",
         acc=["Obtener el archivo exacto que falló.", "Compararlo con el formato utilizado anteriormente.",
              "Identificar diferencias de columnas, identificadores, fechas, plantas y empleados.", "Corregir el proceso de importación y asociación.",
              "Repetir la prueba con datos reales."],
         crit="El archivo se importa completamente, los registros hacen match con los empleados correctos y no existen asistencias omitidas o duplicadas."),
    dict(code="HEX-RH-02", proj="HEX-RH", epic="Corrección y aceptación del módulo", title="Ejecutar la validación productiva completa", type="entregable", prio="Crítica",
         due="2026-08-28", est=8, deps=["HEX-RH-01"], client=True,
         sit="Validación y aceptación del módulo de asistencias con Recursos Humanos.",
         acc=["Realizar una prueba controlada, preferentemente en una planta, comparando durante un periodo definido: archivo del reloj checador, registros históricos o captura anterior y resultado generado en Odoo."],
         crit="Recursos Humanos confirma que la información coincide y acepta formalmente el módulo."),
    dict(code="HEX-RH-04", proj="HEX-RH", epic="Documentación y adopción", title="Crear el manual para supervisores", type="entregable", prio="Alta", due="2026-09-04", est=10, client=True,
         sit="Documentación y adopción del módulo de asistencias.",
         acc=["Consulta de empleados.", "Revisión de asistencias.", "Importación o validación de registros.", "Tratamiento de incidencias.",
              "Operación entre plantas.", "Ruta de escalamiento cuando un registro no coincide."],
         crit="Manual entregado, validado y accesible para los supervisores."),
    dict(code="HEX-RH-05", proj="HEX-RH", epic="Documentación y adopción", title="Definir el proceso de alta de empleados", type="entregable", prio="Media", due="2026-09-11", est=8, client=True,
         sit="Diseño operativo del alta de empleados para evitar duplicados o registros sin correspondencia con el reloj checador.",
         acc=["Contratación.", "Toma de fotografía.", "Alta en el reloj checador.", "Alta en Odoo.", "Asignación de planta o plantas.",
              "Validación de que los identificadores coincidan."],
         crit="Una secuencia única documentada que evite empleados duplicados o sin correspondencia con el reloj checador."),
    # ---------- HEXÁGONOS · FACTURADO CONTRA ENTREGADO
    dict(code="HEX-LOG-01", proj="HEX-LOG", epic="Corrección del modelo y la importación", title="Corregir el modelo de identificación de facturas", type="requerimiento", prio="Crítica",
         due="2026-08-26", est=10, state="por_hacer",
         sit="La versión entregada utiliza el folio de venta como identificador principal, pero la operación necesita controlar el folio de factura de CONTPAQi.",
         acc=["Usar el folio de factura como clave operativa del proceso.", "Mantener el folio de venta solamente como referencia complementaria.",
              "Revisar cómo se resolverán folios duplicados, notas de crédito o varias facturas relacionadas con una venta."],
         crit="Una factura importada puede identificarse y seguirse independientemente de la orden de venta de origen."),
    dict(code="HEX-LOG-02", proj="HEX-LOG", epic="Corrección del modelo y la importación", title="Corregir la importación del Excel de CONTPAQi", type="defecto", prio="Crítica",
         due="2026-08-28", est=12, deps=["HEX-LOG-01"], found="produccion", unplanned=True,
         sit="La importación del archivo de CONTPAQi no relaciona correctamente las facturas.",
         acc=["Mapear las columnas reales del archivo.", "Identificar el folio de factura.", "Validar fecha, cliente, importe y referencias.",
              "Generar un reporte claro de filas aceptadas, rechazadas o duplicadas."],
         crit="Las facturas se importan y relacionan usando el folio correcto."),
    dict(code="HEX-LOG-03", proj="HEX-LOG", epic="Funcionalidad y aceptación", title="Habilitar entregas parciales por factura", type="requerimiento", prio="Alta", due="2026-09-04", est=16, client=True,
         sit="Funcionalidad pendiente: registrar múltiples entregas contra una misma factura.",
         acc=["Cantidad facturada.", "Cantidad entregada.", "Saldo pendiente.", "Fechas de entrega.", "Evidencias.", "Estado: sin entregar, parcial o completada."],
         crit="La factura solamente se considera completada cuando se cubre toda la entrega correspondiente."),
    dict(code="HEX-LOG-04", proj="HEX-LOG", epic="Funcionalidad y aceptación", title="Corregir, validar y aceptar la versión entregada", type="entregable", prio="Alta", due="2026-09-08", est=8,
         deps=["HEX-LOG-02", "HEX-LOG-03"], client=True,
         sit="Ya se entregó una versión, pero no corresponde al funcionamiento solicitado.",
         acc=["Corregirla, ejecutar una prueba con un Excel real y conseguir aceptación formal."],
         crit="Aceptación formal del cliente sobre la versión corregida, probada con un archivo real.",
         extra="Tratamiento comercial: el proyecto todavía no se ha facturado; la facturación debe realizarse después de entregar la versión correcta o conforme al acuerdo comercial aplicable."),
    # ---------- HEXÁGONOS · INVENTARIO
    dict(code="HEX-INV-01", proj="HEX-INV", epic="Conciliación y arranque de operación", title="Recibir el inventario mensual", type="tarea", prio="Alta", due="2026-08-26", est=1,
         waiting=True, client=True, state="por_hacer",
         sit="Dependencia externa: Hexágonos Mexicanos debe entregar el archivo del corte de agosto.",
         acc=["Solicitar y recibir el archivo correspondiente al corte de agosto."],
         crit="Archivo de inventario del corte recibido y cargado en el expediente del proyecto."),
    dict(code="HEX-INV-02", proj="HEX-INV", epic="Conciliación y arranque de operación", title="Conciliar el inventario mensual", type="tarea", prio="Alta", due="2026-09-01", est=12, deps=["HEX-INV-01"],
         sit="Saneamiento operativo previo a operar entregas reales.",
         acc=["Comparar inventario físico, archivo recibido y existencias en Odoo.", "Documentar diferencias.", "Autorizar y ejecutar los ajustes necesarios."],
         crit="Existe un inventario inicial confiable desde el cual operar."),
    dict(code="HEX-INV-03", proj="HEX-INV", epic="Conciliación y arranque de operación", title="Iniciar las entregas reales dentro del sistema", type="entregable", prio="Alta", due="2026-09-05", est=8,
         deps=["HEX-INV-02"], client=True,
         sit="Las entregas reales todavía no se están llevando completamente en el sistema.",
         acc=["Puesta en operación de las entregas en Odoo con evidencia y trazabilidad."],
         crit="Las nuevas entregas se registran en Odoo y pueden rastrearse hasta su factura y evidencia correspondiente."),
    # ---------- SOM · ESTABILIZACIÓN DE ENTREGAS
    dict(code="SOM-ENT-01", proj="SOM", epic="Estabilización de entregas", title="Consolidar los escenarios pendientes", type="tarea", prio="Crítica", due="2026-08-25", est=6,
         owner="Jhon", state="por_hacer",
         sit="Levantamiento de incidencias. Responsable declarado: Jonathan.",
         acc=["Entregar un listado único de órdenes afectadas describiendo: folio, estado actual, resultado esperado, error observado, evidencia y si el problema continúa ocurriendo o proviene de un error ya corregido."],
         crit="Listado único de órdenes afectadas entregado y revisado con el equipo."),
    dict(code="SOM-ENT-02", proj="SOM", epic="Estabilización de entregas", title="Sanear las órdenes históricas afectadas", type="tarea", prio="Crítica", due="2026-09-01", est=24, deps=["SOM-ENT-01"],
         sit="Aproximadamente 95% de los errores del flujo ya fueron corregidos, pero las órdenes creadas mientras existían esos errores siguen bloqueando la operación.",
         acc=["Revisar caso por caso.", "Corregir estados, cantidades, asignaciones, tránsitos, devoluciones o permisos afectados.", "Documentar cada saneamiento."],
         crit="Ninguna orden histórica permanece detenida por un error que ya fue corregido en código."),
    dict(code="SOM-ENT-03", proj="SOM", epic="Estabilización de entregas", title="Validar el 5% residual de entregas", type="prueba", prio="Alta", due="2026-09-05", est=12, deps=["SOM-ENT-02"],
         sit="Estabilización y QA del flujo de entregas.",
         acc=["Entregas completas y parciales.", "Material reservado.", "Material en tránsito.", "Permisos por perfil.", "Devoluciones.", "Diferencias de pago."],
         crit="Los casos críticos funcionan y cualquier incidencia residual queda registrada con folio reproducible."),
    dict(code="SOM-ENT-04", proj="SOM", epic="Estabilización de entregas", title="Aplicar tolerancia de pago de hasta $100 MXN", type="requerimiento", prio="Crítica", due="2026-08-27", est=6, state="por_hacer",
         sit="Ajuste de regla de negocio: permitir la entrega sin autorización cuando el saldo pendiente sea de hasta $100 MXN.",
         acc=["Diferencia de $0.01 a $100.00 MXN: entrega permitida.", "Diferencia superior a $100.00 MXN: requiere autorización.",
              "Confirmar si el límite incluye exactamente $100.", "Definir si aplica exclusivamente a diferencias cambiarias.", "Registrar la tolerancia utilizada en la trazabilidad."],
         crit="Las diferencias menores dejan de consumir autorizaciones directivas."),
    # ---------- SOM · MÓVIL
    dict(code="SOM-MOB-01", proj="SOM", epic="Aplicación móvil", title="Publicar la aplicación en App Store y Play Store", type="entregable", prio="Alta", due="2026-09-12", est=20, client=True,
         sit="La aplicación funciona; Android se distribuye manualmente e iOS mediante TestFlight.",
         acc=["Completar los requisitos de ambas tiendas.", "Corregir observaciones de publicación.", "Dar seguimiento hasta obtener aceptación."],
         crit="Aplicación publicada y disponible en App Store y Play Store."),
    dict(code="SOM-MOB-02", proj="SOM", epic="Aplicación móvil", title="Controlar la renovación de TestFlight", type="tarea", prio="Alta", due="2026-09-15", est=1, recurring=90,
         sit="Mantenimiento temporal mientras no exista publicación en tiendas.",
         acc=["Registrar una renovación recurrente antes del vencimiento de cada periodo de 90 días."],
         crit="Se elimina este pendiente cuando la versión productiva está publicada en App Store."),
    dict(code="SOM-MOB-03", proj="SOM", epic="Aplicación móvil", title="Mantener la optimización móvil", type="tarea", prio="Media", due="2026-09-30", est=4,
         sit="Operativo. Funciones disponibles: escaneo de placas, apartados, ventas y creación de órdenes.",
         acc=["Registrar nuevas mejoras como solicitudes independientes, sin confundirlas con incidencias de la aplicación actual."],
         crit="Las mejoras nuevas entran como solicitudes clasificadas y no como incidencias del módulo actual."),
    # ---------- SOM · COMPRAS Y LOTES
    dict(code="SOM-COM-01", proj="SOM", epic="Compras y lotes", title="Corregir la ruptura de lotes entre tránsito y recepción física", type="defecto", prio="Crítica", due="2026-08-28", est=16,
         state="por_hacer", found="produccion", unplanned=True,
         sit="El material recibe un lote durante la recepción en tránsito, pero el lote puede cambiar al llegar físicamente. El sistema pierde la relación y no permite continuar.",
         acc=["Definir cuál es el identificador permanente de la placa o material.", "Permitir el cambio controlado de lote durante la recepción física.",
              "Conservar la relación entre lote provisional y lote definitivo.", "Evitar que las asignaciones realizadas en tránsito se pierdan."],
         crit="El material puede cambiar a su lote definitivo sin romper pedidos, asignaciones ni trazabilidad."),
    dict(code="SOM-COM-02", proj="SOM", epic="Compras y lotes", title="Identificar el 5–10% de inconsistencias de compras", type="tarea", prio="Alta", due="2026-09-04", est=10,
         sit="Estabilización: dejar de manejar el problema como un porcentaje genérico y convertirlo en casos concretos y medibles.",
         acc=["Crear un registro de compras problemáticas y clasificarlas como: error de sistema, captura incorrecta, cambio de lote, problema documental o configuración de moneda o proveedor."],
         crit="Registro de compras problemáticas clasificado, con casos concretos y medibles."),
    dict(code="SOM-COM-03", proj="SOM", epic="Compras y lotes", title="Corregir la orden creada en MXN que debía estar en USD", type="defecto", prio="Crítica", due="2026-08-27", est=8,
         state="por_hacer", found="produccion", unplanned=True,
         sit="Saneamiento financiero y de inventario de una orden de compra con moneda equivocada.",
         acc=["Identificar la orden afectada.", "Determinar por qué se seleccionó MXN.", "Corregir moneda, tipo de cambio y lista de precios.",
              "Recalcular el impacto sobre el costo del producto.", "Validar si ya generó recepciones, valuaciones o movimientos contables."],
         crit="Orden, recepción, valuación y costo del material quedan consistentes en USD y moneda de compañía.",
         extra="Precaución: no debe modificarse únicamente la moneda visible; debe revisarse toda la cadena de costeo."),
    # ---------- SOM · RECEPCIONES
    dict(code="SOM-REC-01", proj="SOM", epic="Recepciones", title="Crear automáticamente la orden de recepción", type="defecto", prio="Crítica", due="2026-08-26", est=8,
         state="por_hacer", found="produccion", unplanned=True,
         sit="Cuando un embarque cambia a “Entregado en sitio”, no se genera el folio de recepción. Por ello, el usuario no ve el botón para recibir.",
         acc=["Hacer que el cambio al estado correspondiente genere automáticamente la orden y el folio de recepción.", "No generar recepciones duplicadas.",
              "Permitir reintento seguro si la creación falla.", "Mostrar la recepción desde el embarque.", "Notificar o dejar evidencia de errores."],
         crit="El receptor puede abrir el embarque llegado y comenzar la recepción sin intervención administrativa adicional."),
    # ---------- SOM · COSTOS Y CATÁLOGO
    dict(code="SOM-COS-01", proj="SOM", epic="Costos y catálogo de productos", title="Validar los costos de los materiales", type="tarea", prio="Alta", due="2026-09-08", est=10, deps=["SOM-COM-03"],
         sit="Auditoría de datos de costos.",
         acc=["Revisar una muestra representativa que incluya moneda, tipo de cambio, costos de compra y costos asociados a la importación."],
         crit="Muestra auditada sin diferencias de moneda ni de costo, con hallazgos documentados."),
    dict(code="SOM-CAT-01", proj="SOM", epic="Costos y catálogo de productos", title="Evitar la creación incorrecta de productos por duplicación", type="requerimiento", prio="Alta", due="2026-09-08", est=12,
         sit="Los usuarios duplican productos en lugar de utilizar el configurador, arrastrando información y configuraciones que no corresponden.",
         acc=["Restringir o advertir la duplicación.", "Dirigir la creación hacia el configurador.", "Registrar quién creó cada producto y por qué vía.",
              "Identificar y sanear los productos mal configurados.", "Capacitar a los usuarios responsables."],
         crit="Los nuevos productos se crean por el flujo autorizado y no heredan configuraciones erróneas."),
    # ---------- SAI · CANAL CREATTIVO
    dict(code="SAI-CRE-01", proj="SAI", epic="Etapa 2 · Formalización (canal Creattivo)", title="Realizar sesión con David Aguirre", type="tarea", prio="Crítica", due="2026-08-26", est=2,
         owner="Antonio", state="por_hacer",
         sit="Revisión comercial y documental de la Etapa 2. Participantes: Antonio, David Aguirre y equipo de Creattivo. Esta sesión es con Creattivo, no directamente con SAI.",
         acc=["Programar una sesión para revisar los cambios necesarios en el documento de la Etapa 2."],
         crit="Lista acordada de cambios y responsable de generar la siguiente versión."),
    dict(code="SAI-CRE-02", proj="SAI", epic="Etapa 2 · Formalización (canal Creattivo)", title="Actualizar el documento de la Etapa 2", type="entregable", prio="Crítica", due="2026-08-31", est=12,
         deps=["SAI-CRE-01"], client=True,
         sit="Documentación de alcance de la Etapa 2.",
         acc=["Incorporar los cambios acordados.", "Separar entregables, dependencias y supuestos.", "Identificar qué corresponde a corrección y qué corresponde a ampliación.",
              "Definir el mecanismo de estimación, autorización y corte de horas."],
         crit="Documento de Etapa 2 actualizado, con entregables, dependencias, supuestos y mecanismo de corte de horas."),
    dict(code="SAI-CRE-03", proj="SAI", epic="Etapa 2 · Formalización (canal Creattivo)", title="Conseguir la aceptación formal de la Etapa 2", type="entregable", prio="Crítica", due="2026-09-04", est=4,
         deps=["SAI-CRE-02"], client=True, waiting=True,
         sit="Autorización comercial. Responsable de decisión: Creattivo y las partes que deban validar con SAI.",
         acc=["Obtener evidencia formal de aceptación y autorización para comenzar."],
         crit="Existe evidencia formal de aceptación y autorización para comenzar.",
         extra="Estimación global de referencia: 223 a 413 horas, con aproximadamente 300 horas como referencia, cobrando el trabajo efectivamente ejecutado y registrado."),
    dict(code="SAI-CRE-04", proj="SAI", epic="Etapa 2 · Formalización (canal Creattivo)", title="Planificar los primeros entregables y cortes de facturación", type="tarea", prio="Alta", due="2026-09-10", est=6,
         deps=["SAI-CRE-03"],
         sit="Planeación posterior a la aceptación formal.",
         acc=["Seleccionar los primeros paquetes de trabajo.", "Asignar responsables.", "Definir criterios de aceptación.", "Registrar horas ejecutadas.",
              "Programar los primeros cortes de facturación."],
         crit="Plan de trabajo con responsables, criterios de aceptación y cortes de facturación programados."),
    # ---------- SAI · CANAL CALIDAD
    dict(code="SAI-CAL-01", proj="SAI", epic="Solicitudes de Calidad (canal SAI)", title="Consolidar las solicitudes de Calidad", type="tarea", prio="Alta", due="2026-08-28", est=6, state="por_hacer",
         sit="Levantamiento de las recomendaciones del área de Calidad.",
         acc=["Crear un inventario único de recomendaciones, con evidencia, proceso afectado y resultado esperado."],
         crit="Inventario único de solicitudes de Calidad, con evidencia y proceso afectado."),
    dict(code="SAI-CAL-02", proj="SAI", epic="Solicitudes de Calidad (canal SAI)", title="Clasificar cada solicitud", type="tarea", prio="Crítica", due="2026-09-01", est=6, deps=["SAI-CAL-01"],
         sit="Análisis funcional y comercial de cada solicitud recibida.",
         acc=["Error reproducible del sistema.", "Entregable pendiente de aceptación.", "Ajuste de configuración o datos.", "Cambio de alcance.", "Mejora continua."],
         crit="Ninguna solicitud pasa directamente a desarrollo sin clasificación."),
    dict(code="SAI-CAL-03", proj="SAI", epic="Solicitudes de Calidad (canal SAI)", title="Corregir y validar los errores confirmados", type="defecto", prio="Alta", due="2026-09-08", est=16, deps=["SAI-CAL-02"],
         sit="Correctivo sobre los errores confirmados por Calidad y Producción.",
         acc=["Reproducir el error.", "Corregirlo.", "Validarlo con Calidad y Producción.", "Documentar evidencia de aceptación."],
         crit="Errores corregidos, validados con Calidad y Producción y con evidencia de aceptación documentada."),
    dict(code="SAI-CAL-05", proj="SAI", epic="Solicitudes de Calidad (canal SAI)", title="Obtener autorización del gerente de Producción", type="entregable", prio="Crítica", due="2026-09-10", est=2,
         deps=["SAI-CAL-02"], waiting=True, client=True,
         sit="Aprobación previa al desarrollo de cualquier cambio de alcance. Responsable de decisión: gerente de Producción.",
         acc=["Presentar estimación e impacto y obtener la autorización formal."],
         crit="Autorización formal y trazable antes de consumir horas del nuevo alcance."),
    dict(code="SAI-CAL-06", proj="SAI", epic="Solicitudes de Calidad (canal SAI)", title="Crear un backlog de mejora continua", type="tarea", prio="Media", due="2026-09-18", est=4, deps=["SAI-CAL-02"],
         sit="Planeación de producto para las mejoras autorizadas.",
         acc=["Ordenar las mejoras autorizadas por impacto operativo, urgencia, esfuerzo y dependencia."],
         crit="Backlog priorizado de mejora continua, sin solicitudes informales fuera del alcance aprobado."),
]

# ---------------------------------------------------------------- cambios de alcance
CAMBIOS = [
    dict(code="HEX-RH-03", proj="HEX-RH", title="Unificar plantas y admitir empleados multiplanta", est=16, prio="Alta",
         desc="Revisar cómo están modeladas actualmente las plantas; permitir que un empleado pueda estar relacionado con más de una planta o ubicación; definir cómo se asignan asistencias cuando un empleado registra entrada en una planta distinta.",
         analysis="Ajuste funcional por clasificar: debe determinarse qué parte corresponde al alcance original y qué parte debe cotizarse como extensión.",
         impact="Afecta el modelo de datos de empleados y la asignación de asistencias; sin definirlo, las asistencias entre plantas quedan sin regla."),
    dict(code="HEX-RH-06", proj="HEX-RH", title="Incorporar información de familiares", est=12, prio="Media",
         desc="Registrar familiares, parentesco y fechas de nacimiento de hijos u otros dependientes.",
         analysis="Cambio de alcance. Acción siguiente: levantar campos, permisos, reportes y uso esperado antes de estimarlo.",
         impact="Nuevos campos y permisos en el expediente de personal; requiere definición de uso antes de estimar."),
    dict(code="HEX-RH-07", proj="HEX-RH", title="Incorporar videocapacitación al ingreso", est=20, prio="Media",
         desc="Bloque adicional para el proceso de inducción que permita asignar un video al nuevo empleado, registrar visualización o cumplimiento e integrarlo al flujo de contratación.",
         analysis="Cambio de alcance facturable. Dependencia: primero debe definirse el proceso de alta de empleados (HEX-RH-05). Tratamiento comercial: cotizar como un nuevo bloque de horas.",
         impact="Depende del proceso de alta de empleados; se cotiza como bloque de horas independiente."),
    dict(code="HEX-CAT-01", proj="HEX-INV", title="Crear o ajustar familias de productos", est=12, prio="Media",
         desc="Definir familias, criterios de agrupación, productos actuales afectados y reportes que utilizarán dichas familias.",
         analysis="Mejora funcional por estimar. Debe administrarse como un frente independiente de Recursos Humanos.",
         impact="Afecta catálogo y reportes; requiere definición de criterios antes de estimar."),
    dict(code="SAI-CAL-04", proj="SAI", title="Estimar los cambios de alcance de Calidad", est=8, prio="Alta",
         desc="Preparar estimación, impacto, dependencia y entregable para cada cambio identificado en la clasificación de solicitudes de Calidad.",
         analysis="Desarrollo facturable. Dependencia: clasificación de solicitudes (SAI-CAL-02). No puede ejecutarse sin autorización del gerente de Producción (SAI-CAL-05).",
         impact="Define el consumo de horas de la Etapa 2; sin estimación y autorización no debe consumirse tiempo."),
]

# ---------------------------------------------------------------- riesgos
RIESGOS = [
    dict(proj="HEX-RH", name="Módulo de asistencias facturado sin aceptación formal ni pago", prob="3", imp="3",
         desc="El servicio ya tiene factura emitida pero el módulo no ha sido aceptado ni pagado; la corrección pendiente retrasa el cobro.",
         action="Corregir la importación, ejecutar la validación productiva y enviar evidencia de cierre para solicitar el pago.", due="2026-08-28"),
    dict(proj="HEX-LOG", name="Versión entregada con modelo de identificación incorrecto", prob="3", imp="3",
         desc="La versión entregada identifica por folio de venta y no por folio de factura; el proyecto aún no se factura y la operación no puede usarlo.",
         action="Corregir el modelo, probar con un Excel real y obtener aceptación antes de facturar.", due="2026-09-08"),
    dict(proj="SOM", name="Órdenes históricas creadas con errores ya corregidos bloquean la operación", prob="3", imp="3",
         desc="Aunque cerca del 95% de los errores del flujo están corregidos en código, las órdenes generadas mientras existían siguen detenidas.",
         action="Consolidar el listado de Jonathan y sanear caso por caso, documentando cada corrección.", due="2026-09-01"),
    dict(proj="SOM", name="Trazabilidad por placa y lote en riesgo por el cambio de lote entre tránsito y recepción", prob="3", imp="3",
         desc="Cualquier corrección en compras, recepción o moneda impacta asignaciones, pedidos, inventario, costos y entregas.",
         action="Definir el identificador permanente del material y permitir el cambio controlado de lote conservando la relación.", due="2026-08-28"),
    dict(proj="SAI", name="Etapa 2 sin autorización formal: riesgo de ejecutar trabajo sin contrato", prob="3", imp="3",
         desc="La Etapa 2 se encuentra en formalización y planeación; no debe reportarse como en ejecución ni consumir horas antes de la aceptación.",
         action="Cerrar el documento con Creattivo y obtener la aceptación formal antes de iniciar ejecución.", due="2026-09-04"),
    dict(proj="SAI", name="Solicitudes de Calidad sin clasificar pueden consumir horas no autorizadas", prob="2", imp="3",
         desc="Si una solicitud pasa directamente a desarrollo sin clasificarse, se ejecuta trabajo que puede no estar en alcance ni autorizado.",
         action="Clasificar toda solicitud antes de desarrollar y exigir autorización del gerente de Producción para los cambios de alcance.", due="2026-09-01"),
]

# ---------------------------------------------------------------- administración (cobranza / comercial)
ADMIN = [
    dict(code="HEX-COB-01", admin_project="Hexágonos Mexicanos · Proyecto Odoo", title="Formalizar la entrega del módulo de asistencias y dar seguimiento al pago",
         desc="El servicio ya tiene factura emitida, pero continúa pendiente de pago. Después de la validación productiva, enviar evidencia de cierre y solicitar la liquidación de la factura. "
              "Control adicional: confirmar también el estado de pago de la factura correspondiente al proyecto de ventas multilínea.",
         due="2026-08-31", risk="factura", executor="Marina"),
    dict(code="SAI-CRE-03A", admin_project="SAI · Proyecto Odoo", title="Formalizar comercialmente la Etapa 2 de SAI (aceptación y condiciones)",
         desc="La Etapa 2 está en formalización: documento actualizado con Creattivo, aceptación formal y mecanismo de estimación, autorización y corte de horas. "
              "Estimación global de referencia: 223 a 413 horas (~300 horas), cobrando el trabajo efectivamente ejecutado y registrado.",
         due="2026-09-04", risk="contractual", executor="Antonio"),
]


class Importer:
    def __init__(self):
        self.c = OdooClient(); self.c.conectar()
        self.stats = {}
        self.ids = {}
        self.members = {m["name"]: m["id"] for m in self.c.search_read("aq.portal.member", [], ["name"])}

    def bump(self, k):
        self.stats[k] = self.stats.get(k, 0) + 1

    def bot(self, model, vals):
        self.bump("create:" + model)
        if DRY:
            return -len(self.stats)
        return self.c.execute("aq.ops.engine", "bot_create", [model, [vals]])[0]

    def member(self, name):
        if not name:
            return False
        for k, v in self.members.items():
            if name.lower() in k.lower():
                return v
        return False

    def find_one(self, model, dom, fields=("id",)):
        r = self.c.search_read(model, dom, list(fields), limit=1)
        return r[0] if r else None

    # ---------- proyectos y épicas
    def project(self, key):
        if key in self.ids:
            return self.ids[key]
        if key == "SOM":
            p = self.find_one("aq.ops.project", [["name", "=", "SOM GROUP MONTERREY"]]) or self.find_one("aq.ops.project", [["name", "ilike", "Stonia"]])
        elif key == "SAI":
            p = self.find_one("aq.ops.project", [["name", "ilike", "SAI"]])
        else:
            f = next(x for x in FRENTES if x["key"] == key)
            p = self.find_one("aq.ops.project", [["name", "=", f["name"]]])
            if not p:
                partner = self.find_one("res.partner", [["name", "=", f["partner"]], ["is_company", "=", True]])
                pid = self.bot("aq.ops.project", {
                    "name": f["name"], "partner_id": partner["id"], "service_type": f["service_type"], "stage": f["stage"], "methodology": "kanban",
                    "pm_id": self.members.get("Antonio (Dirección)"), "objective": f["objective"], "scope_current": f["scope"],
                    "next_action": f["next_action"], "next_action_owner_id": self.members.get("Antonio (Dirección)"), "next_action_date": f["next_date"],
                    "date_start": HOY, "client_visible": True, "session_prefix": "HMX"})
                p = {"id": pid}
        self.ids[key] = p["id"] if p else False
        return self.ids[key]

    def epic(self, proj_key, name):
        if not name:
            return False
        k = "epic:%s:%s" % (proj_key, name)
        if k in self.ids:
            return self.ids[k]
        pid = self.project(proj_key)
        e = self.find_one("aq.ops.item", [["project_id", "=", pid], ["item_type", "=", "epica"], ["name", "=", name]])
        if not e:
            eid = self.bot("aq.ops.item", {"name": name, "item_type": "epica", "project_id": pid, "state": "en_progreso",
                                           "description": "<p>Frente de trabajo del listado de pendientes del 23/08/2026.</p>", "tags": "pendientes-23ago"})
            e = {"id": eid}
        self.ids[k] = e["id"]
        return e["id"]

    # ---------- elementos
    def item(self, d):
        pid = self.project(d["proj"])
        exist = self.find_one("aq.ops.item", [["project_id", "=", pid], ["name", "like", d["code"]]])
        if exist:
            self.ids[d["code"]] = exist["id"]; self.bump("skip:existente"); return exist["id"]
        acc = "".join("<li>%s</li>" % a for a in d.get("acc", []))
        desc = "<p><b>Situación.</b> %s</p>" % d.get("sit", "")
        if acc:
            desc += "<p><b>Acciones siguientes</b></p><ul>%s</ul>" % acc
        if d.get("extra"):
            desc += "<p><i>%s</i></p>" % d["extra"]
        if d.get("deps"):
            desc += "<p><b>Dependencia:</b> %s</p>" % ", ".join(d["deps"])
        desc += "<p style='color:#888;font-size:11px'>Origen: Listado de pendientes del 23/08/2026 · clave %s</p>" % d["code"]
        vals = {"name": "%s · %s" % (d["code"], d["title"]), "item_type": d["type"], "project_id": pid, "parent_id": self.epic(d["proj"], d.get("epic")),
                "state": d.get("state", "backlog"), "priority": P(d["prio"]), "date_due": d["due"], "date_start": HOY,
                "assignee_id": self.member(d.get("owner")) or self.members.get("Antonio (Dirección)"),
                "estimate_hours": d.get("est", 4), "remaining_hours": d.get("est", 4), "acceptance_criteria": d.get("crit"),
                "description": desc, "tags": "pendientes-23ago,%s" % d["code"], "client_visible": bool(d.get("client")),
                "waiting_client": bool(d.get("waiting")), "unplanned": bool(d.get("unplanned"))}
        if d.get("found"):
            vals["found_in"] = d["found"]
        if d.get("recurring"):
            vals.update(is_recurring=True, recurrence_days=d["recurring"])
        if d.get("waiting"):
            rec = self.c.search_read("aq.ops.project", [["id", "=", pid]], ["partner_id"]) if pid and pid > 0 else []
            vals["validator_partner_id"] = (rec[0]["partner_id"][0] if rec and rec[0]["partner_id"] else False)
            vals["assignee_id"] = False
        iid = self.item_create(vals, d["code"])
        return iid

    def item_create(self, vals, code):
        iid = self.bot("aq.ops.item", vals)
        self.ids[code] = iid
        return iid

    def link_deps(self):
        for d in ITEMS:
            if not d.get("deps"):
                continue
            me = self.ids.get(d["code"])
            deps = [self.ids.get(x) for x in d["deps"] if self.ids.get(x) and self.ids.get(x) > 0]
            if me and me > 0 and deps and not DRY:
                self.c.execute("aq.ops.engine", "bot_write", ["aq.ops.item", [me], {"depends_on_ids": [[6, 0, deps]]}])
                self.bump("write:dependencias")

    def cambios(self):
        for ch in CAMBIOS:
            pid = self.project(ch["proj"])
            if self.find_one("aq.ops.change", [["project_id", "=", pid], ["name", "like", ch["code"]]]):
                self.bump("skip:existente"); continue
            cid = self.bot("aq.ops.change", {"name": "%s · %s" % (ch["code"], ch["title"]), "project_id": pid, "description": ch["desc"],
                                             "scope_analysis": ch["analysis"], "impact": ch["impact"], "estimate_hours": ch["est"],
                                             "estimated_by_id": self.members.get("Antonio (Dirección)"), "state": "analisis",
                                             "requested_by": "Listado de pendientes 23/08/2026", "client_visible": True})
            self.ids[ch["code"]] = cid

    def riesgos(self):
        for r in RIESGOS:
            pid = self.project(r["proj"])
            if self.find_one("aq.ops.raid", [["project_id", "=", pid], ["name", "=", r["name"]]]):
                self.bump("skip:existente"); continue
            self.bot("aq.ops.raid", {"name": r["name"], "raid_type": "risk", "project_id": pid, "description": r["desc"],
                                     "probability": r["prob"], "impact": r["imp"], "owner_id": self.members.get("Antonio (Dirección)"),
                                     "state": "abierto", "next_action": r["action"], "next_action_date": r["due"], "due_date": r["due"]})

    def admin(self):
        for a in ADMIN:
            proj = self.find_one("aq.portal.project", [["name", "=", a["admin_project"]]])
            if not proj:
                continue
            if self.find_one("aq.portal.agreement", [["name", "like", a["code"]]]):
                self.bump("skip:existente"); continue
            self.bump("create:aq.portal.agreement")
            if DRY:
                continue
            self.c.execute("aq.ops.engine", "bot_create", ["aq.portal.agreement", [{
                "name": "%s · %s" % (a["code"], a["title"]), "description": a["desc"], "project_id": proj["id"], "source": "reunion",
                "requested_by": "Dirección", "executor_id": self.member(a["executor"]), "due_date": a["due"], "meeting_date": HOY,
                "in_scope": "si", "risk_type": a["risk"], "state": "pendiente", "formalized": True,
                "completion_evidence": "Evidencia de cierre enviada al cliente y confirmación de pago o autorización formal."}]])

    def next_actions(self):
        """La regla no negociable: cada proyecto con siguiente acción, responsable y fecha."""
        acciones = {"SOM": ("Obtener de Jonathan el listado único de órdenes problemáticas", "2026-08-25", "Jhon"),
                    "SAI": ("Programar la sesión con David Aguirre para cerrar el documento de la Etapa 2", "2026-08-26", "Antonio")}
        for k, (accion, fecha, resp) in acciones.items():
            pid = self.project(k)
            if pid and not DRY:
                self.c.execute("aq.ops.engine", "bot_write", ["aq.ops.project", [pid],
                                                              {"next_action": accion, "next_action_date": fecha, "next_action_owner_id": self.member(resp)}])
                self.bump("write:siguiente_accion")

    def run(self):
        for f in FRENTES:
            self.project(f["key"])
        for d in ITEMS:
            self.item(d)
        self.link_deps()
        self.cambios()
        self.riesgos()
        self.admin()
        self.next_actions()
        print("\nResumen%s:" % (" (simulación)" if DRY else ""))
        for k, v in sorted(self.stats.items()):
            print("  %-34s %d" % (k, v))


if __name__ == "__main__":
    Importer().run()
