"""
Command-line interface for TwitchAdAvoider
"""
import argparse
from src.twitch_viewer import TwitchViewer

def main():
    parser = argparse.ArgumentParser(description='Watch Twitch streams while avoiding ads')
    parser.add_argument('channel', help='Name of the Twitch channel to watch')
    args = parser.parse_args()

    viewer = TwitchViewer()
    viewer.watch_stream(args.channel)

if __name__ == '__main__':
    main()
