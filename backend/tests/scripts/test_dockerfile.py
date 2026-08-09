from pathlib import Path


def test_backend_dockerfile_uses_configurable_worker_count() -> None:
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"

    assert (
        'CMD ["sh", "-c", "exec fastapi run --workers ${BACKEND_WORKERS:-4} app/main.py"]'
        in dockerfile.read_text()
    )
