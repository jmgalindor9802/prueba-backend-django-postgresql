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