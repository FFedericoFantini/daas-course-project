import argparse
import logging
import time

from shared.config import DEFAULT_MANUAL_DRONE_ID
from apps.drone_simulator.fleet import SimulatorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drones", type=int, default=5)
    parser.add_argument("--manual-drone-id", default=DEFAULT_MANUAL_DRONE_ID)
    args = parser.parse_args()

    service = SimulatorService(drones=args.drones, manual_drone_id=args.manual_drone_id)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
