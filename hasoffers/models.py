class Model(object):
    def __init__(self, d):

        if not type(d) == dict:
            raise Exception('Неверный тип аругмента.')

        for k, v in d.items():
            if k == 'id':
                self.__dict__[k] = int(v)
            else:
                self.__dict__[k] = v


class Offer(Model):

    contains = [
        {'class': 'Advertiser', 'relation': 'one'},
        {'class': 'Country', 'relation': 'many'}
    ]


class Advertiser(Model):
    pass


class Conversion(Model):
    pass


class Affiliate(Model):
    pass


class RelatedModel(Model):
    pass


class OfferPixel(Model):
    pass


class Country(Model):
    pass
