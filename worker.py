import os

from redis import Redis
from rq import Connection, Worker


if __name__ == "__main__":
    redis_conn = Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")), db=0)
    with Connection(redis_conn):
        worker = Worker(["pop-jobs"])
        worker.work()
