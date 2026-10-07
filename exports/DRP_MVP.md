# MVP DRP - Inventario AWS

Fecha: 2026-07-21  
Cuenta objetivo inicial: `afex-prod`  
Flujo evaluado: `Virginia / us-east-1` -> `Ohio / us-east-2`

## Objetivo

Crear una vista inicial para orientar decisiones de DRP usando el inventario AWS existente.

La vista no certifica que Ohio pueda operar produccion. Su objetivo es acelerar la pregunta practica:

> Si Virginia cae, que productos tienen evidencia suficiente para intentar operar o probar en Ohio, y que falta revisar o replicar?

## Menu creado

Se agrego un nuevo menu lateral:

```text
DRP
```

El menu contiene cuatro secciones:

```text
Resumen
Por Producto
Brechas
Evidencia
```

## Alcance del MVP

El MVP usa solo informacion disponible en cache local:

- Nombre del recurso.
- Region.
- Servicio AWS.
- Producto inferido.
- Ambiente inferido.
- Configuracion principal capturada por el inventario.
- Estado de frescura del cache.

No usa tags como requisito, porque actualmente la cuenta AWS no los tiene de forma consistente.

## Reglas de ambiente

El MVP clasifica ambiente desde el nombre:

```text
prod, prd, production, produccion -> prod
cert, certification, certificacion, qa, uat -> cert
dev, des, development, test, testing -> no-prod
sin marcador -> desconocido
```

Esta regla es intencionalmente simple. Sirve como punto de partida para equipos que aun no tienen tagging maduro.

## Agrupacion por producto

El analisis DRP reutiliza la inferencia de producto ya existente en la app.

Cuando no hay tags, se deduce producto desde nombres de recursos como:

```text
accounting-api-prod-auth-check-user
accounting-api-cert-auth-check-user
bill-payment-module-backend-production
bill-payment-module-backend-cert
```

La idea es comparar por:

```text
producto + servicio + componente base
```

El componente base elimina marcadores como:

```text
prod
cert
Virginia
Ohio
us-east-1
us-east-2
```

## Estados DRP

La vista clasifica cada componente en:

| Estado | Significado |
|---|---|
| Listo aparente | Existe equivalente en ambas regiones y la configuracion principal coincide. |
| Parcial | Existe equivalente, pero hay diferencias principales de configuracion. |
| Dudoso | Existe equivalente, pero el ambiente detectado no permite asumir que sea DR productivo. |
| Bloqueado | Existe en Virginia, pero no se detecta equivalente en Ohio. |
| Solo Ohio | Existe en Ohio sin equivalente en Virginia. Puede ser cert, prueba o soporte de failback. |
| Sin clasificar | Falta evidencia minima para clasificar. |

## Vistas

### Resumen

Muestra KPIs de productos:

```text
Productos
Listos aparentes
Parciales
Bloqueados
Dudosos
```

Incluye una tabla ejecutiva por producto:

```text
Producto
Estado DRP
Readiness
Componentes
Bloqueados
Parciales
Dudosos
Listos aparentes
Servicios
Accion principal
```

### Por Producto

Permite seleccionar un producto y ver:

- Estado general.
- Porcentaje de readiness.
- Cantidad de componentes.
- Cantidad de bloqueantes.
- Semaforo por servicio.
- Detalle de componentes Virginia vs Ohio.

### Brechas

Lista los puntos que requieren accion:

```text
Prioridad
Producto
Servicio
Componente base
Estado DRP
Impacto
Observacion
Accion sugerida
Virginia
Ohio
```

Esta es la vista mas accionable para preparar una prueba DRP.

### Evidencia

Muestra el detalle tecnico usado para justificar la clasificacion:

```text
Producto
Servicio
Componente base
Virginia
Ohio
Ambiente Virginia
Ambiente Ohio
Estado DRP
Config Virginia
Config Ohio
Cache Virginia
Cache Ohio
Confianza
Duplicados Virginia
Duplicados Ohio
```

## Reglas de accion sugerida

El MVP agrega recomendaciones basicas por servicio.

Ejemplos:

| Servicio | Accion sugerida |
|---|---|
| RDS | Definir replica, snapshot restaurable o procedimiento de restore probado en Ohio. |
| Lambda | Replicar funcion, runtime, variables, layers, rol, VPC config y alias/version. |
| API Gateway | Validar rutas, stages, integraciones Lambda, dominios y certificados. |
| SSM | Replicar parametros/configuracion y validar cifrado KMS. |
| KMS | Validar alias, key policy, permisos y disponibilidad regional. |
| DynamoDB | Validar Global Tables, backups/PITR o restauracion y modo de capacidad. |
| SQS | Validar cola, DLQ, FIFO, policy y cifrado KMS. |
| VPC | Validar CIDR, subnets, rutas, security groups y conectividad requerida. |

## Resultado observado con cache actual

Con el cache disponible al momento de la prueba automatizada:

```text
Productos: 610
Listos aparentes: 3
Parciales: 357
Bloqueados: 69
Dudosos: 153
```

Importante: estos numeros dependen del cache local. Antes de usar la vista para una decision DRP real, se debe refrescar cache de `afex-prod` para `us-east-1` y `us-east-2`.

## Limitaciones conocidas

- La clasificacion depende del nombre de los recursos.
- No prueba trafico real.
- No valida DNS, Route53, ALB/NLB, CloudFront ni certificados si no estan inventariados.
- No valida datos reales ni replicacion efectiva.
- No valida failback Ohio -> Virginia.
- No reemplaza una prueba controlada de DRP.
- Puede clasificar como dudoso cuando Ohio existe pero esta nombrado como `cert`.

## Siguiente iteracion recomendada

Despues de revisar el MVP con inventario fresco:

1. Agregar export Excel/Markdown desde la propia pantalla DRP.
2. Agregar filtro por estado, producto y servicio.
3. Incorporar una vista `Failover / Failback`.
4. Incluir servicios faltantes criticos: Route53, ALB/NLB, Secrets Manager, CloudWatch alarms, EventBridge, Backup.
5. Crear una tabla configurable de productos criticos y RTO/RPO esperados.
6. Empezar a aceptar tags cuando existan, aumentando la confianza automaticamente.

## Criterio de uso

La vista DRP debe usarse como guia inicial:

```text
Verde: candidato a prueba controlada.
Amarillo: revisar antes de probar.
Rojo: no apagar Virginia sin corregir o aceptar el riesgo.
Gris: falta evidencia.
```

El valor principal del MVP es convertir el inventario en una lista priorizada de preguntas y acciones antes de ejecutar un DRP.
