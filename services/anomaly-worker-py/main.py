"""Entrypoint for Module D — Real-Time Streaming Anomaly Worker."""

from __future__ import annotations

import logging
import signal
import sys

try:
    from config import WorkerConfig
    from consumer import TelemetryConsumer
    from detector import (
        DemandSpikeRule,
        FrequencyDeviationRule,
        LowPowerFactorRule,
        PhaseImbalanceRule,
        VoltageSagSwellRule,
    )
    from engine import AnomalyEngine
    from metrics import start_metrics_server
    from publisher import KafkaAlertPublisher
    from repository import PostgresAlertRepository
except ImportError:
    from .config import WorkerConfig
    from .consumer import TelemetryConsumer
    from .detector import (
        DemandSpikeRule,
        FrequencyDeviationRule,
        LowPowerFactorRule,
        PhaseImbalanceRule,
        VoltageSagSwellRule,
    )
    from .engine import AnomalyEngine
    from .metrics import start_metrics_server
    from .publisher import KafkaAlertPublisher
    from .repository import PostgresAlertRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("anomaly-worker")


def main() -> None:
    config = WorkerConfig()
    logging.getLogger().setLevel(config.log_level)
    logger.info("Starting Anomaly Worker with config: %s", config)

    # 1. Start Prometheus metrics HTTP server on port 8083
    start_metrics_server(port=config.metrics_port)

    # 2. Dependency Inversion: initialize repository and publisher abstractions
    repository = PostgresAlertRepository(dsn=config.database_url)
    publisher = KafkaAlertPublisher(
        bootstrap_servers=config.kafka_bootstrap_servers,
        topic=config.kafka_alert_topic,
    )

    # 3. Open/Closed Principle: plug in rules
    rules = [
        VoltageSagSwellRule(),
        DemandSpikeRule(),
        PhaseImbalanceRule(),
        LowPowerFactorRule(),
        FrequencyDeviationRule(),
    ]

    # 4. Initialize Core AnomalyEngine
    engine = AnomalyEngine(
        repository=repository,
        publisher=publisher,
        rules=rules,
        window_capacity=config.window_capacity,
    )

    # 5. Initialize consumer loop
    consumer = TelemetryConsumer(
        bootstrap_servers=config.kafka_bootstrap_servers,
        engine=engine,
        topic=config.kafka_input_topic,
        group_id=config.kafka_group_id,
    )

    def _handle_shutdown(signum, frame):
        logger.info("Received termination signal %d. Shutting down gracefully...", signum)
        consumer.stop()
        publisher.flush()
        repository.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    try:
        consumer.run()
    except Exception as e:
        logger.critical("Fatal consumer failure: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
