# prog-image

prog-image is an asynchronous image storage and retrieval service built with FastAPI.

## Installation Prerequisites
You will need:

- Python 3.14+
- uv
- Docker and Docker Compose

Clone the repository and navigate into the project. Install the project dependencies using:

```uv sync```

### Environment Configuration

Create a ```.env``` file in the project root (same folder as this README). Copy the contents of ```dev.env``` to it.

### Running Docker Compose

The project uses Docker Compose to run PostgreSQL and MinIO locally.

Start/stop the services with:

```
docker compose up -d
docker compose down
```

### MinIO

MinIO is used as a local blob storage.
The application expects a bucket called ```images``` to be present. Create this using the web UI once Docker Compose has been started: 

MinIO Web UI: http://localhost:9001

The default credentials are:
```
Username: minio
Password: minio123
```

## Running the Project

Once the dependencies and Docker services are running, start the FastAPI application from the project root:

```uv run python -m uvicorn app.main:app --loop asyncio```

The API will be available at: http://localhost:8000

FastAPI's interactive API documentation is available at: http://localhost:8000/docs

There are 2 endpoints.
- ### POST /images
    This takes an image file in the request body. Returns an ```image_uuid``` to be used to retrieve the stored image.
- ### GET /images/{image-uuid}
    This requires an image_uuid provided by the POST /images endpoint. Returns an image file.

## Running Tests

Integration tests require PostgreSQL and MinIO to be running:

```docker compose up -d```

Run the complete test suite with:

```uv run pytest tests -v```

