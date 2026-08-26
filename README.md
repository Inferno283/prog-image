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
* ### POST /images
    This takes an image file in the request body. Returns an ```image_uuid``` to be used to retrieve the stored image.
* ### GET /images/{image-uuid}
    This requires an image_uuid provided by the POST /images endpoint. Returns an image file.

## Running Tests

Integration tests require PostgreSQL and MinIO to be running:

```docker compose up -d```

Run the complete test suite with:

```uv run pytest tests -v```

# Discussion points
I chose to build the service using FastAPI, based on its flexibility, my familiarity with the framework, and its support for asynchronous operations.

### API

I made the endpoints asynchronous because storing and retrieving images involves IO-bound operations. This allows the service to handle other requests while waiting for storage operations to complete, helping maintain responsiveness under load.

### Storage

I chose a PostgreSQL + blob storage approach rather than storing images directly in the database:

* PostgreSQL stores image metadata such as filename, size, content type, storage provider, and blob key.
    * Storing the provider and blob key separately allows the storage provider to be changed in the future without changing how the metadata is represented.
    * Storing metadata in PostGreSQL also allows for more flexible querying and future functionality such as filtering, auditing, or authorisation/authentication.
* Blob storage stores the actual image objects.
    * This avoids placing large binary objects directly in the database, which can negatively affect database performance and is more cost-effective.

### Consistency Trade-off

The main downside of this approach is the potential for inconsistency between PostgreSQL and blob storage.

For example:
1. The image is successfully uploaded to blob storage.
2. The PostgreSQL write fails.
3. The blob remains without a corresponding database record.

The implementation attempts to mitigate this by deleting the blob if the database operation fails. However, that cleanup operation could also fail, leaving an orphaned object. In production, this could be further mitigated with a periodic reconciliation/cleanup job to identify and remove orphaned objects.

Overall, I felt this was a worthwhile trade-off for the benefits of structured metadata, future queryability, and keeping large objects out of PostgreSQL.