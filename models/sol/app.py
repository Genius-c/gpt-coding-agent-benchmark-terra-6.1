from pathlib import Path

from queue_server import JobQueue, QueueHTTPServer


def main():
    queue = JobQueue(Path(__file__).parent / 'jobs.sqlite3')
    server = None
    try:
        server = QueueHTTPServer(('127.0.0.1', 8765), queue)
        print('Dashboard: http://127.0.0.1:8765 (Ctrl+C to stop)', flush=True)
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.server_close()
        queue.close()


if __name__ == '__main__':
    main()
