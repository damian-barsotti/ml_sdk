import uuid
from abc import ABC, abstractmethod


class ProducerConsumerInterface(ABC):

    @abstractmethod
    def _produce(self, key, message):
        pass

    @abstractmethod
    def _consume(self, key=None):
        pass


class WorkerInterface(ProducerConsumerInterface):

    def _listen(self):

        def set_reply(key, message):
            self._produce(key, message)

        def execute(method, *args, **kwargs):
            func = getattr(self.handler, method)
            return func(**kwargs)

        key, kwargs = self._consume()
        method = kwargs.pop('method', None)

        result = execute(method, **kwargs)

        if key:
            set_reply(key, result)

    def serve_forever(self):
        while True:
            self._listen()


class DispatcherInterface(ProducerConsumerInterface):

    def dispatch(self, method, **kwargs):

        def get_reply(key):
            key, result = self._consume(key)
            return result

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