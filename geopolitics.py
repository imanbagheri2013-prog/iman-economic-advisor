from .base import Provider
class GeopoliticalProvider(Provider):
    def observations(self,*args,**kwargs):
        raise NotImplementedError('Configure a selected news/geopolitical source in the next integration layer.')
