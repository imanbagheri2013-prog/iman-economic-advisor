from abc import ABC, abstractmethod
class Provider(ABC):
    @abstractmethod
    def observations(self,*args,**kwargs):
        raise NotImplementedError
