from .base import Provider
class CryptoProvider(Provider):
    def observations(self,*args,**kwargs):
        raise NotImplementedError('Configure a selected crypto-data source in the next integration layer.')
