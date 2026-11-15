import argparse
from blindspot.meal_kiosk import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Continuous local meal barcode station')
    parser.add_argument('--camera', type=int, default=0)
    run(parser.parse_args().camera)
