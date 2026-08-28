from .base import Provider
class IranMarketProvider(Provider):
    def observations(self,*args,**kwargs):
        raise NotImplementedError('Configure a selected Iran data source in the next integration layer.')
