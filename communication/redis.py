import msgpack
import logging
import redis
from dataclasses import dataclass
from retry import retry
from ml_sdk.communication import DispatcherInterface, WorkerInterface


logger = logging.getLogger(__name__)


@dataclass
class RedisSettings:
    topic: str
    host: str = 'redis'
    port: int = 6379
    db: int = 0

    @property
    def conf(self):
        return dict(host=self.host, db=self.db, port=self.port)


class RedisNode:
    def __init__(self, settings: RedisSettings):
        self.topic = settings.topic
        redis_pool = redis.ConnectionPool(**settings.conf)
        self.redis = redis.StrictRedis(connection_pool=redis_pool)

    @staticmethod
    def _decode(msg):
        return msgpack.unpackb(msg, use_list=False, raw=False)

    @staticmethod
    def _encode(msg):
        return msgpack.packb(msg, use_bin_type=True)


class RedisWorker(RedisNode, WorkerInterface):
    def __init__(self, settings: RedisSettings, handler):
        super(RedisWorker, self).__init__(settings)
        self.handler = handler
        self.pubsub = self.redis.pubsub()
        self.pubsub.psubscribe(f'{self.topic}*')
        self.pubsub.get_message()

        self.lock = self.redis.lock(f"lock: {self.topic}")

    def _produce(self, key, message):
        self.redis.set(key, self._encode(message))

    def _consume(self):

        @retry(ValueError, delay=0.5, logger=None)
        def cons():

            # Read broadcasted messages
            message = self.pubsub.get_message()
            if message is not None and message['type'] == 'pmessage':
                return message['data']

            # Read individual messages
            message = self.redis.lpop(self.topic)
            if message is not None:
                return message

            raise ValueError()

        message = self._decode(cons())
        key = message.pop('key')

        return key, message

    def exec_critical(self, function, *args):
        logger.info("Enter critical section")
        self.lock.acquire(blocking=True)
        logger.info("Executing critical section")
        res = function(*args)
        self.lock.release()
        logger.info("Exit critical section")
        return res


class RedisDispatcher(RedisNode, DispatcherInterface):

    def _produce(self, key, message):
        message['key'] = key
        self.redis.rpush(self.topic, self._encode(message))

    def _consume(self, key):

        @retry(ValueError, delay=0.1, backoff=2, max_delay=1,
               tries=15, logger=logger)
        def get(key):

            message = self.redis.getdel(key)

            if message is None:
                raise ValueError()

            message = self._decode(message)
            return message

        try:
            message = get(key)
        finally:
            self.redis.delete(key)

        return key, message

    def _broadcast(self, message):
        message['key'] = None
        self.redis.publish(self.topic, self._encode(message))
