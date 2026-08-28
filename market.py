from .base import Provider
class MarketProvider(Provider):
    def observations(self,*args,**kwargs):
        raise NotImplementedError('Configure a selected market-data source in the next integration layer.')
