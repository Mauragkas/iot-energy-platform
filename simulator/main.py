"""Smart Meter Edge Simulator - Main CLI Runner.

Simulates an IoT fleet of 3-phase smart meters streaming high-frequency telemetry
over MQTT v5 (QoS 1) with fault injection and offline replay buffering.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path when invoked directly as python simulator/main.py
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import paho.mqtt.client as mqtt  # noqa: E402

from simulator.anomalies import FaultInjector, FaultType, ReplayBuffer, apply_fault  # noqa: E402
from simulator.meter import SmartMeter, create_fleet  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("simulator")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Smart Meter Edge Simulator (3-phase MZ-3P-xxxx over MQTT v5)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("MQTT_BROKER_HOST", "localhost"),
        help="MQTT broker hostname (default: localhost or MQTT_BROKER_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MQTT_BROKER_PORT", "1883")),
        help="MQTT broker port (default: 1883 or MQTT_BROKER_PORT)",
    )
    parser.add_argument(
        "--meters",
        type=int,
        default=int(os.getenv("SIMULATOR_METERS", "500")),
        help="Number of virtual smart meters to simulate (default: 500)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=float(os.getenv("SIMULATOR_RATE", "0.5")),
        help="Messages per meter per second in streaming mode, or target msg/s in load mode (default: 0.5)",
    )
    parser.add_argument(
        "--inject-anomalies",
        action="store_true",
        default=False,
        help="Inject grid faults and anomalies on ~5%% of meters (default: False)",
    )
    parser.add_argument(
        "--replay-offline",
        action="store_true",
        default=False,
        help="Enable gateway offline buffering and out-of-order burst replay with duplicates (default: False)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["streaming", "load"],
        default="streaming",
        help="Simulation mode: 'streaming' (realistic diurnal curve) or 'load' (high-throughput load generator)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Simulation run duration in seconds (default: None, runs until Ctrl+C)",
    )
    return parser


class SimulatorRunner:
    """Coordinates smart meter fleet simulation and MQTT publishing."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialize simulation runner from parsed arguments."""
        self.args = args
        self.running = False
        self.total_published = 0
        self.total_anomalies = 0
        self.total_replayed = 0
        self.total_duplicates = 0

        # Initialize meter fleet
        self.meters: list[SmartMeter] = create_fleet(count=args.meters)
        logger.info(
            "Initialized fleet of %d smart meters (MZ-3P-0001 .. MZ-3P-%04d)",
            len(self.meters),
            len(self.meters),
        )

        # Fault injection setup (~5% of meters designated for anomalies)
        self.fault_injector = FaultInjector(fault_probability=0.05)
        self.anomalous_meter_ids: set[str] = set()
        if args.inject_anomalies:
            num_anomaly_meters = max(1, int(len(self.meters) * 0.05))
            # Pick a deterministic 5% sample of meters
            sampled_meters = random.sample(self.meters, num_anomaly_meters)
            self.anomalous_meter_ids = {m.meter_id for m in sampled_meters}
            logger.info(
                "Anomaly injection enabled on %d meters (~5%%): %s",
                len(self.anomalous_meter_ids),
                ", ".join(sorted(self.anomalous_meter_ids)[:5])
                + ("..." if len(self.anomalous_meter_ids) > 5 else ""),
            )

        # Offline replay buffer setup (simulates a gateway holding 30s of packets)
        self.replay_buffer: ReplayBuffer | None = None
        self.replay_meter_ids: set[str] = set()
        if args.replay_offline:
            self.replay_buffer = ReplayBuffer(
                buffer_duration_seconds=30.0, duplicate_ratio=0.20
            )
            # Assign first ~10% of meters (or at least 1) to this offline gateway
            num_replay_meters = max(1, min(50, int(len(self.meters) * 0.10)))
            self.replay_meter_ids = {
                m.meter_id for m in self.meters[:num_replay_meters]
            }
            logger.info(
                "Offline replay buffer active for gateway managing %d meters (30s window, burst with duplicates)",
                len(self.replay_meter_ids),
            )

        # MQTT v5 client setup
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTv5,
            client_id=f"meter-sim-{os.getpid()}-{random.randint(1000, 9999)}",
        )
        self.client.max_inflight_messages_set(2000)
        self.client.max_queued_messages_set(0)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle MQTT connection established callback."""
        if reason_code == 0:
            logger.info(
                "Connected to MQTT v5 broker at %s:%d (reason: %s)",
                self.args.host,
                self.args.port,
                reason_code,
            )
        else:
            logger.warning("Failed to connect to MQTT broker: reason %s", reason_code)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle MQTT disconnect callback."""
        if self.running:
            logger.warning(
                "Disconnected from MQTT broker: reason %s. Will auto-reconnect.",
                reason_code,
            )

    def connect(self) -> None:
        """Connect to MQTT broker and start background network loop."""
        try:
            self.client.connect(self.args.host, self.args.port, keepalive=60)
            self.client.loop_start()
        except Exception as exc:
            logger.error(
                "Could not connect to MQTT broker %s:%d: %s",
                self.args.host,
                self.args.port,
                exc,
            )
            raise

    def disconnect(self) -> None:
        """Stop network loop and cleanly disconnect."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except (OSError, RuntimeError) as exc:
            logger.debug("Error during MQTT disconnect: %s", exc)

    def publish_reading(self, reading: dict[str, Any], zone: str) -> bool:
        """Publish a single reading dictionary to MQTT v5 topic with QoS 1."""
        topic = f"meazon/grid/{zone}/meter/{reading['meter_id']}/telemetry"
        payload = json.dumps(reading)
        res = self.client.publish(topic, payload, qos=1)
        if res.rc == mqtt.MQTT_ERR_SUCCESS:
            self.total_published += 1
            return True
        else:
            logger.debug("Failed publish to %s (code %d)", topic, res.rc)
            return False

    def run(self) -> None:
        """Run the main simulation loop."""
        self.running = True
        self.connect()

        start_time = time.time()
        logger.info(
            "Starting simulation in '%s' mode: %d meters, rate=%.2f msg/s",
            self.args.mode,
            len(self.meters),
            self.args.rate,
        )

        try:
            if self.args.mode == "streaming":
                self._run_streaming(start_time)
            else:
                self._run_load(start_time)
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user (SIGINT)")
        finally:
            self.running = False
            self.disconnect()
            elapsed = time.time() - start_time
            avg_rate = self.total_published / max(0.001, elapsed)
            logger.info(
                "Simulation stopped. Published: %d msgs in %.2fs (avg %.1f msg/s). Anomalies: %d. Replayed: %d.",
                self.total_published,
                elapsed,
                avg_rate,
                self.total_anomalies,
                self.total_replayed,
            )

    def _run_streaming(self, start_time: float) -> None:
        """Run realistic diurnal streaming mode."""
        # Interval per meter
        meter_interval = 1.0 / max(0.001, self.args.rate)
        num_meters = len(self.meters)

        # Distribute initial next_send_time across meter_interval to stagger emission
        next_send = {}
        now = time.time()
        for idx, m in enumerate(self.meters):
            stagger = (idx / max(1, num_meters)) * meter_interval
            next_send[m.meter_id] = now + stagger

        available_faults = list(FaultType)
        fault_cycle = 0

        while self.running:
            loop_now = time.time()

            # Check duration limit
            if (
                self.args.duration is not None
                and (loop_now - start_time) >= self.args.duration
            ):
                logger.info("Specified duration of %.1fs reached", self.args.duration)
                break

            # Check replay buffer flush
            if self.replay_buffer and self.replay_buffer.should_flush(loop_now):
                burst = self.replay_buffer.flush_burst()
                seen_pairs = set()
                duplicates_count = 0
                for pkt in burst:
                    pair = (pkt["meter_id"], pkt["timestamp"])
                    if pair in seen_pairs:
                        duplicates_count += 1
                    else:
                        seen_pairs.add(pair)
                    # Find meter zone
                    m_zone = self.meters[0].zone
                    for m in self.meters:
                        if m.meter_id == pkt["meter_id"]:
                            m_zone = m.zone
                            break
                    self.publish_reading(pkt, m_zone)
                    self.total_replayed += 1

                self.total_duplicates += duplicates_count
                logger.info(
                    "Replay gateway burst: sent %d packets (%d intentional duplicates, out-of-order)",
                    len(burst),
                    duplicates_count,
                )

            # Send due readings
            for meter in self.meters:
                if loop_now >= next_send[meter.meter_id]:
                    # Advance next scheduled time
                    next_send[meter.meter_id] += meter_interval

                    # Generate reading
                    reading = meter.generate_reading(datetime.now(UTC))

                    # Maybe inject anomaly
                    if meter.meter_id in self.anomalous_meter_ids:
                        fault = available_faults[fault_cycle % len(available_faults)]
                        fault_cycle += 1
                        reading = apply_fault(reading, fault)
                        self.total_anomalies += 1

                    # Check if meter is behind offline gateway
                    if self.replay_buffer and meter.meter_id in self.replay_meter_ids:
                        self.replay_buffer.add(reading, loop_now)
                    else:
                        self.publish_reading(reading, meter.zone)

            # Short sleep to prevent busy spinning (10ms)
            time.sleep(0.01)

    def _run_load(self, start_time: float) -> None:
        """Run high-throughput load generator mode for HPA demos."""
        # In load mode, determine target aggregate message rate
        if self.args.rate >= 1.0:
            target_msg_per_sec = self.args.rate
        else:
            target_msg_per_sec = len(self.meters) * self.args.rate

        target_interval = 1.0 / max(0.1, target_msg_per_sec)
        logger.info(
            "Load mode target throughput: %.1f msg/s (interval %.5fs)",
            target_msg_per_sec,
            target_interval,
        )

        meter_idx = 0
        num_meters = len(self.meters)
        next_send_time = time.time()

        while self.running:
            loop_now = time.time()

            if (
                self.args.duration is not None
                and (loop_now - start_time) >= self.args.duration
            ):
                logger.info("Specified duration of %.1fs reached", self.args.duration)
                break

            meter = self.meters[meter_idx]
            meter_idx = (meter_idx + 1) % num_meters

            # Rapid synthetic reading
            reading = meter.generate_reading(
                datetime.now(UTC), override_delta_seconds=target_interval
            )

            if meter.meter_id in self.anomalous_meter_ids:
                reading = apply_fault(reading, FaultType.DEMAND_SPIKE)
                self.total_anomalies += 1

            self.publish_reading(reading, meter.zone)

            next_send_time += target_interval
            sleep_time = next_send_time - time.time()
            if sleep_time > 0.001:
                time.sleep(sleep_time)
            elif sleep_time < -0.5:
                # Catch up clock if falling behind
                next_send_time = time.time()


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    runner = SimulatorRunner(args)

    def _sig_handler(signum: int, frame: Any) -> None:
        logger.info("Signal %d received, stopping simulator...", signum)
        runner.running = False

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        runner.run()
    except Exception:
        logger.exception("Simulator encountered fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
