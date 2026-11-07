import readchar
from picrawler import Picrawler

from driver import RobotDriver

DRIVE_KEYS = {"w": (0.0, 1.0), "s": (0.0, -1.0), "a": (-1.0, 0.0), "d": (1.0, 0.0)}
ACTION_KEYS = {"1": "wave", "2": "sit", "3": "stand"}

# The Pi runs the old picrawler 0.0.1 / robot_hat 1.1.0, which needs an explicit
# pin list. These are 1-based pins; the repo's newer PIN_LIST won't work with it.
PIN_LIST = [10, 11, 12, 4, 5, 6, 1, 2, 3, 7, 8, 9]


def main():
    crawler = Picrawler(PIN_LIST)
    driver = RobotDriver(crawler)
    driver.start()

    try:
        while True:
            key = readchar.readkey().lower()
            if key == readchar.key.CTRL_C:
                break
            elif key in DRIVE_KEYS:
                x, y = DRIVE_KEYS[key]
                driver.drive(x, y)
            elif key in ACTION_KEYS:
                name = ACTION_KEYS[key]
                driver.action(name)
    finally:
        driver.stop()


if __name__ == "__main__":
    main()
