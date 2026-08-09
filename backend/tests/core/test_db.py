from app.core.config import settings
from app.core.db import engine
from app.core.metrics import InstrumentedQueuePool


def test_engine_uses_configured_pool_settings() -> None:
    assert isinstance(engine.pool, InstrumentedQueuePool)
    assert engine.pool.size() == settings.DB_POOL_SIZE
    assert engine.pool._max_overflow == settings.DB_MAX_OVERFLOW
    assert engine.pool._recycle == settings.DB_POOL_RECYCLE_SECONDS
    assert engine.pool._pre_ping is settings.DB_POOL_PRE_PING
