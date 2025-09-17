# Prueba Backend Django + PostgreSQL

Este repositorio contiene el punto de partida para desarrollar la API solicitada en la prueba técnica. A continuación se describen los pasos iniciales para ejecutar el proyecto con PostgreSQL y Django REST Framework.

## Requisitos previos

- Python 3.12+
- PostgreSQL 14+ (local o en contenedor)
- `pip` para instalar dependencias

## Configuración inicial

1. Crea y activa un entorno virtual (opcional pero recomendado):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\\Scripts\\activate
   ```

2. Instala las dependencias del proyecto:

   ```bash
   pip install -r requirements.txt
   ```

3. Copia el archivo de ejemplo de variables de entorno y ajusta los valores según tu entorno de PostgreSQL:

   ```bash
   cp .env.example .env
   ```

   Variables disponibles:

   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG`
   - `DJANGO_ALLOWED_HOSTS`
   - `POSTGRES_DB`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_HOST`
   - `POSTGRES_PORT`

4. Crea la base de datos indicada en `POSTGRES_DB` si aún no existe. Con PostgreSQL local puedes ejecutar:

   ```bash
   createdb failfast
   ```

5. Ejecuta las migraciones iniciales de Django:

   ```bash
   python manage.py migrate
   ```

6. Levanta el servidor de desarrollo:

   ```bash
   python manage.py runserver
   ```

Con esta configuración el proyecto ya apunta a PostgreSQL y tiene listo el esqueleto para agregar los modelos, viewsets y endpoints requeridos.

## Endpoint dinámico `related`

Cada ViewSet expone una ruta auxiliar `/<recurso>/related/` que permite navegar
relaciones arbitrarias entre modelos sin tener que crear endpoints nuevos. Las
consultas aceptan los siguientes parámetros opcionales:

- `join`: lista separada por comas con las relaciones a cargar (se aceptan
  notaciones `.` o `__`). Cada recurso define una **lista blanca** de joins
  válidos y se limita la profundidad máxima a tres saltos; si el cliente supera
  este tope recibirá un `400` con el mensaje `"La ruta ... supera la
  profundidad máxima"`.
- `fields[modelo]`: campos concretos de cada modelo que se desean incluir en la
  respuesta. El nombre del modelo debe ir en minúsculas
  (`fields[product]=id,name`). Si se solicita un campo inexistente la API
  devuelve `400` indicando el atributo inválido.
- `filter[lookup]`: filtros dinámicos compatibles con el ORM de Django. Se
  pueden encadenar relaciones con `__`. Cuando un mismo filtro aparece varias
  veces sin operador explícito (`filter[name]=A&filter[name]=B`) se interpreta
  automáticamente como un `__in`. Los valores se castean en la medida de lo
  posible (booleanos, números, decimales y fechas ISO) para que los filtros
  funcionen como en un queryset nativo.
- `ordering`: lista separada por comas con los campos para ordenar (se admiten
  `-campo` y notación para relaciones). Cualquier ruta inválida produce un
  `400` descriptivo.
- `distinct`: si se envía como `true/1/yes/on` activa `queryset.distinct()`.
  Úsalo con criterio porque puede aumentar el costo del SQL cuando hay muchos
  joins.

### Respuesta y metadatos

`get_related` siempre devuelve resultados paginados reutilizando la misma
configuración de paginación del proyecto. El cuerpo incluye `count`, `next`,
`previous` y la lista de objetos serializados bajo `results`. Además, se agrega
una sección `meta` que expone información útil para depurar cada consulta:

```json
{
  "count": 5,
  "next": "http://localhost:8000/api/products/related/?page=2",
  "previous": null,
  "results": [...],
  "meta": {
    "applied_filters": {"brand__name": "Samsung"},
    "applied_joins": ["brand", "order_items.order.customer"],
    "selected_fields": {"product": ["id", "name"], "brand": ["*"]},
    "ordering": ["-created_at"],
    "distinct": false,
    "query_time_ms": 2.731,
    "warnings": []
  }
}
```

Los `selected_fields` muestran `"*"` cuando se devuelven todos los campos de un
modelo. Los mensajes de validación siempre se devuelven con código `400` y un
texto claro indicando el parámetro rechazado.

### Ejemplos prácticos

1. **Productos de una marca dentro de órdenes de un cliente concreto**

   ```http
   GET /api/products/related/?join=brand,order_items.order.customer&filter[brand__name]=Samsung&filter[order_items__order__customer__email]=cliente@example.com&fields[product]=id,name,sku&fields[brand]=id,name&fields[order]=id,status
   ```

   La respuesta incluirá cada producto que cumpla los filtros junto a la marca
   y las órdenes (con su cliente) en las que aparece.

2. **Pagos donde se facturó un producto específico con más de 5 unidades**

   ```http
   GET /api/payments/related/?join=order.customer,order.items.product&filter[order__items__product__sku]=ABC-123&filter[order__items__qty__gt]=5&fields[payment]=id,amount,status&fields[order]=id,status&fields[product]=id,name,sku
   ```

   Se obtendrán los pagos asociados a órdenes cuyo detalle registra el producto
   indicado con cantidades superiores a cinco unidades. Puedes ordenar por
   monto con `ordering=-amount` o eliminar duplicados con `distinct=true`
   cuando un join multiplique filas.