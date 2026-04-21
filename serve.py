import os

from waitress import serve

from app import create_app


if __name__ == "__main__":
    host = os.getenv("HOST") or "0.0.0.0"
    port = int(os.getenv("PORT") or "5000")
    serve(create_app(), host=host, port=port, threads=8)

