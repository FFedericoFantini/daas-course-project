import logging
import time

from apps.airspace_core.core import AirspaceCore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
    service = AirspaceCore()
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
