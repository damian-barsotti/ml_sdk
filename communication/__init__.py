import uuid
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ProducerInterface(ABC):

    @abstractmethod
    def _produce(self, key, message):
        pass


class ConsumerInterface(ABC):

    @abstractmethod
    def _consume(self):
        pass


class ConsumerKeyInterface(ABC):

    @abstractmethod
    def _consume(self, key):
        pass

class WorkerInterface(ProducerInterface, ConsumerInterface):

    def _listen(self):

        def set_reply(key, message):
            self._produce(key, message)

        def execute(method, *args, **kwargs):
            func = getattr(self.handler, method)
            return func(**kwargs)

        key, kwargs = self._consume()
        method = kwargs.pop('method', None)

        logger.info(f"Service execute {method}")
        result = execute(method, **kwargs)

        if key:
            set_reply(key, result)

    def serve_forever(self):
        while True:
            self._listen()


class DispatcherInterface(ProducerInterface, ConsumerKeyInterface):

    def dispatch(self, method, **kwargs):

        def get_reply(key):
            key, result = self._consume(key)
            return result

        logger.info(f"API dispatch {method}")

        key = uuid.uuid4().hex
        kwargs['method'] = method
        self._produce(key, kwargs)
        result = get_reply(key)
        return result

    def broadcast(self, method, **kwargs):
        kwargs['method'] = method
        return self._broadcast(kwargs)

    @abstractmethod
    def _broadcast(self, message):
        pass


__all__ = [
    "WorkerInterface",
    "DispatcherInterface",
]
