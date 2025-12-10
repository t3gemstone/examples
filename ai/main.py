import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modeldir', required=True)
    parser.add_argument('--graph', default='detect.tflite')
    parser.add_argument('--labels', default='labelmap.txt')
    parser.add_argument('--threshold', default='0.5')
    parser.add_argument('--artifacts', default=None)
    parser.add_argument('--device', default=None)
    parser.add_argument('--no-tidl', action='store_true')
    args = parser.parse_args()

    app = Application(args)
    app.run()


if __name__ == "__main__":
    main()
