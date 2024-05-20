import uuid
from abc import ABCMeta, abstractmethod


class WorkerInterface(metaclass=ABCMeta):

    def _listen(self):

        def set_reply(key, message):
            self._produce(message, key)

        def execute(method, *args, **kwargs):
            func = getattr(self.handler, method)
            return func(**kwargs)

        key, kwargs = self._consume()
        method = kwargs.pop('method', None)

        result = execute(method, **kwargs)

        if key:
            set_reply(key, result)

    def serve_forever(self):
        self.stop = False
        while not self.stop:
            self._listen()

    def stop(self):
        self.stop = True

    @abstractmethod
    def _produce(self, message, key=None):
        pass

    @abstractmethod
    def _consume(self, key=None):
        pass


class DispatcherInterface(metaclass=ABCMeta):
    def dispatch(self, method, **kwargs):
        key = uuid.uuid4().hex
        kwargs['method'] = method
        self._produce(kwargs, key)
        result = self._get_reply(key)
        return result

    def broadcast(self, method, **kwargs):
        kwargs['method'] = method
        return self._broadcast(kwargs)

    def _get_reply(self, key):
        key, result = self._consume(key)
        return result

    @abstractmethod
    def _produce(self, message, key=None):
        pass

    @abstractmethod
    def _broadcast(self, message):
        pass

    @abstractmethod
    def _consume(self, key=None):
        pass
