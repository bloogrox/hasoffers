import requests, json, logging, sys, time
from http_build_query import http_build_query
from . import models


class Error(Exception):
    pass
class ValidateError(Error):
    pass
class APIUsageExceededRateLimit(Error):
    pass

ROOT = 'http://api.hasoffers.com/v3/'
ERROR_MAP = {
    'ValidateError': ValidateError
}

logger = logging.getLogger('hasoffers')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stderr))


TILL_SUCCESS = 'TILL_SUCCESS'


class Hasoffers(object):

    def __init__(self, network_token, network_id, debug=False, retry_count=1):

        if debug:
            self.level = logging.INFO
        else:
            self.level = logging.DEBUG

        self.retry_count = retry_count

        if network_id is None or network_token is None:
            raise Error('You must provide Hasoffers NETWORK ID and NETWORK TOKEN')

        self.network_token = network_token
        self.network_id = network_id

        self.mapper = HasoffersDataMapper(debug=debug)

        self.offer = Offer(self)
        self.conversion = Conversion(self)
        self.affiliate = Affiliate(self)
        self.advertiser = Advertiser(self)
        self.application = Application(self)
        self.offer_pixel = OfferPixel(self)
        self.offer_file = OfferFile(self)
        self.affiliate_user = AffiliateUser(self)

    def call(self, target, params=None, return_model=None, request_method='GET', request_data={}):
        if params is None:
            params = {}
        params['NetworkId'] = self.network_id
        params['NetworkToken'] = self.network_token

        base_url = ROOT + '%s.json?' % target
        url = base_url + http_build_query(params)

        request = Request(url, params, target, return_model=return_model, method=request_method, **request_data)

        return self.send(request)

    def send(self, request):
        self.log('Executing %s' % request.url)
        request.attempts += 1
        start = time.time()
        if request.method == 'GET':
            r = requests.get(request.url)
        elif request.method == 'POST':
            _kwargs = dict()
            if request.files:
                _kwargs = {'files': request.files}
            r = requests.post(request.url, **_kwargs)
        complete_time = time.time() - start
        response_body = r.text
        self.log('Received %s in %.2fms: %s' % (r.status_code, complete_time * 1000, r.text))

        result = json.loads(response_body)

        if 'response' not in result or result['response']['status'] != 1:
            try:
                raise self.cast_error(result)
            except APIUsageExceededRateLimit:
                if self.retry_count == TILL_SUCCESS:
                    self.log('Retrying request!')
                    time.sleep(0.25)
                    return self.send(request)
                elif self.retry_count > 1 and request.attempts < self.retry_count:
                    self.log('Retrying request: attempts %d!' % request.attempts)
                    time.sleep(0.25)
                    return self.send(request)
                else:
                    raise self.cast_error(result)

        # self.last_response = result
        # return self.get_response()
        response = Response(request, result)

        return self.mapper.map(request, response)

    # def get_response(self):
    #     if self.last_response:
    #         return self.mapper.map(self.last_response)
    #     return None

    def cast_error(self, result):
        if not 'response' in result or not 'status' in result['response']:
            return Error('We received an unexpected error: %r' % result)
        if 'API usage exceeded rate limit' in result['response']['errorMessage']:
            return APIUsageExceededRateLimit(result['response']['errorMessage'])
        return Error(result['response']['errorMessage'])

    def log(self, *args, **kwargs):
        '''Proxy access to the hasoffers logger, changing the level based on the debug setting'''
        logger.log(self.level, *args, **kwargs)

    def __repr__(self):
        return '<Hasoffers %s>' % self.network_id


class Request(object):

    def __init__(self, url, params, target, return_model=None, method='GET', files=None):
        self.url = url
        self.params = params
        self.target = target
        self.return_model = return_model
        self.attempts = 0
        self.method = method
        self.files = files


class Response(object):

    def __init__(self, request, response_body):
        self.request = request
        self.target = response_body['request']['Target']
        self.method = response_body['request']['Method']
        self.response_body = response_body
        self.status = response_body['response']['status']
        self.httpStatus = response_body['response']['httpStatus']
        self.errors = response_body['response']['errors']
        self.errorMessage = response_body['response']['errorMessage']
        self.data = response_body['response']['data']


class Offer(object):

    relations = {
        'Country': 'MANY',
        'Advertiser': 'ONE'
    }

    target = 'Offer'

    def __init__(self, master):
        self.master = master

    def find_all(self, filters=None, sort=None, limit=None, page=None, fields=None, contain=None):
        _params = {'Method': 'findAll'}
        if filters:
            _params['filters'] = filters
        if sort:
            _params['sort'] = sort
        if limit:
            _params['limit'] = limit
        if page:
            _params['page'] = page
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain

        return self.master.call(self.target, _params)

    def find_by_id(self, id, fields=[], contain=[]):
        _params = {
            'Method': 'findById',
            'id': id,
            'fields': fields,
            'contain': contain
        }
        return self.master.call(self.target, _params)

    def get_pixels(self, id, status=None):
        _params = {
            'Method': 'getPixels',
            'id': id,
        }
        if status:
            _params['status'] = status
        return self.master.call(self.target, _params, return_model='OfferPixel')

    def create(self, data, return_object=False):
        _params = {
            'Method': 'create',
            'data': data,
            'return_object': return_object
        }
        return self.master.call(self.target, _params)

    def set_categories(self, id_, category_ids):
        _params = {
            'Method': 'setCategories',
            'id': id_,
            'category_ids': category_ids
        }
        return self.master.call(self.target, _params)

    def set_affiliate_approval(self, offer_id, affiliate_id, status):
        _params = {
            'Method': 'setAffiliateApproval',
            'id': offer_id,
            'affiliate_id': affiliate_id,
            'status': status
        }
        return self.master.call(self.target, _params)

    def add_group(self, id_, group_id):
        _params = {
            'Method': 'addGroup',
            'id': id_,
            'group_id': group_id
        }
        return self.master.call(self.target, _params)

    def add_target_country(self, id_, country_code, regions=None, region_code=None):
        _params = {
            'Method': 'addTargetCountry',
            'id': id_,
            'country_code': country_code,
        }
        if regions:
            _params['regions'] = regions
        if region_code:
            _params['region_code'] = region_code
        return self.master.call(self.target, _params)

    def update_field(self, id_, field, value, return_object=False):
        _params = {
            'Method': 'updateField',
            'id': id_,
            'field': field,
            'value': value,
            'return_object': return_object
        }
        return self.master.call(self.target, _params)

    def update(self, id_, data, return_object=False):
        _params = {
            'Method': 'update',
            'id': id_,
            'data': data,
            'return_object': return_object
        }
        return self.master.call(self.target, _params)

    def generate_tracking_pixel(self, id_, params=None, options=None):
        _params = {
            'Method': 'generateTrackingPixel',
            'offer_id': id_
        }
        if params:
            _params['params'] = params
        if options:
            _params['options'] = options
        return self.master.call(self.target, _params)

    def generate_tracking_link(self, id_, affiliate_id, params=None, options=None, optionalFields=None):
        _params = {
            'Method': 'generateTrackingLink',
            'offer_id': id_,
            'affiliate_id': affiliate_id
        }
        if params:
            _params['params'] = params
        if options:
            _params['options'] = options
        if optionalFields:
            _params['optionalFields'] = optionalFields
        return self.master.call(self.target, _params)


class Conversion(object):

    target = 'Conversion'

    def __init__(self, master):
        self.master = master

    def find_all(self, filters=None, sort=None, limit=None, page=None, fields=None, contain=None):
        _params = {
            'Method': 'findAll'
        }
        if filters:
            _params['filters'] = filters
        if sort:
            _params['sort'] = sort
        if limit:
            _params['limit'] = limit
        if page:
            _params['page'] = page
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain

        return self.master.call(self.target, _params)

    def update_status(self, id, status):
        _params = {
            'Method': 'updateStatus',
            'id': id,
            'status': status
        }
        return self.master.call(self.target, _params)

    def update(self, id, data, return_object=False, ad_id=None, transaction_id=None, should_standardize=None):
        _params = {
            'Method': 'update',
            'id': id,
            'data': data,
            'return_object': return_object
        }
        if ad_id:
            _params['ad_id'] = ad_id
        if transaction_id:
            _params['transaction_id'] = transaction_id
        if should_standardize:
            _params['shouldStandardize'] = should_standardize

        return self.master.call(self.target, _params)

    def find_by_id(self, id=None, fields=None, contain=None, ad_id=None, transaction_id=None):
        _params = {
            'Method': 'findById'
        }
        if id:
            _params['id'] = id
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain
        if ad_id:
            _params['ad_id'] = ad_id
        if transaction_id:
            _params['transaction_id'] = transaction_id

        return self.master.call(self.target, _params)


class Affiliate(object):

    target = 'Affiliate'

    def __init__(self, master):
        self.master = master

    def find_all(self, filters=None, sort=None, limit=None, page=None, fields=None, contain=None):
        _params = {
            'Method': 'findAll'
        }
        if filters:
            _params['filters'] = filters
        if sort:
            _params['sort'] = sort
        if limit:
            _params['limit'] = limit
        if page:
            _params['page'] = page
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain

        return self.master.call(self.target, _params)

    def get_offer_pixels(self, id, status=None):
        _params = {
            'Method': 'getOfferPixels',
            'id': id,
        }
        if status:
            _params['status'] = status
        return self.master.call(self.target, _params, 'OfferPixel')

    def add_account_note(self, id_, note):
        _params = {
            'Method': 'addAccountNote',
            'id': id_,
            'note': note
        }
        return self.master.call(self.target, _params)


class AffiliateUser(object):

    target = 'AffiliateUser'

    def __init__(self, master):
        self.master = master

    def find_all(self, filters=None, sort=None, limit=None, page=None, fields=None, contain=None):
        _params = {
            'Method': 'findAll'
        }
        if filters:
            _params['filters'] = filters
        if sort:
            _params['sort'] = sort
        if limit:
            _params['limit'] = limit
        if page:
            _params['page'] = page
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain

        return self.master.call(self.target, _params)


class Advertiser(object):

    target = 'Advertiser'

    def __init__(self, master):
        self.master = master

    def find_all(self, filters=None, sort=None, limit=None, page=None, fields=None, contain=None):
        _params = {
            'Method': 'findAll'
        }
        if filters:
            _params['filters'] = filters
        if sort:
            _params['sort'] = sort
        if limit:
            _params['limit'] = limit
        if page:
            _params['page'] = page
        if fields:
            _params['fields'] = fields
        if contain:
            _params['contain'] = contain

        return self.master.call(self.target, _params)

    def find_by_id(self, id_, fields=[], contain=[]):
        _params = {
            'Method': 'findById',
            'id': id_,
            'fields': fields,
            'contain': contain
        }
        return self.master.call(self.target, _params)

class Application(object):

    target = 'Application'

    def __init__(self, master):
        self.master = master

    def add_offer_group(self, data):
        _params = {
            'Method': 'addOfferGroup',
            'data': data
        }
        return self.master.call(self.target, _params)


class OfferPixel(object):

    target = 'OfferPixel'

    def __init__(self, master):
        self.master = master

    def create(self, data, return_object=False):
        _params = {
            'Method': 'create',
            'data': data,
            'return_object': return_object
        }
        return self.master.call(self.target, _params)


class OfferFile(object):

    target = 'OfferFile'

    def __init__(self, master):
        self.master = master

    def create(self, data, filepath, return_object=False):
        _params = {
            'Method': 'create',
            'data': data,
            'return_object': return_object
        }
        files = {data['filename']: open(filepath, 'rb')}
        return self.master.call(self.target, _params, request_method='POST', request_data={'files': files})

#-----------------------------------------------------------------
HASOFFERS_ENTITY_MAP = {
    'Offer': models.Offer,
    'Advertiser': models.Advertiser,
    'Conversion': models.Conversion,
    'Affiliate': models.Affiliate,
    'OfferPixel': models.OfferPixel,
    'Country': models.Country
}


# -------------------
NO = 1
INT = 2
OBJECT = 3
COLLECTION = 4
BOOLEAN = 5
# -------------------


METHODS_MAPPING = {
    'Offer': {
        'findById': OBJECT,
        'findAll': COLLECTION,
        'getPixels': COLLECTION
    },
    'Conversion': {
        'findAll': COLLECTION
    },
    'Affiliate': {
        'findAll': COLLECTION,
        'getOfferPixels': COLLECTION
    },
    'Advertiser': {
        'findAll': COLLECTION,
        'findById': OBJECT,
    }
}


class HasoffersDataMapper(object):

    def __init__(self, debug=False):
        if debug:
            self.level = logging.INFO
        else:
            self.level = logging.DEBUG

    def log(self, *args, **kwargs):
        '''Proxy access to the hasoffers logger, changing the level based on the debug setting'''
        logger.log(self.level, *args, **kwargs)

    def map(self, request, response):
        target = response.target
        method = response.method

        # mapping_type = None
        if target in METHODS_MAPPING and method in METHODS_MAPPING[target]:
            mapping_type = METHODS_MAPPING[target][method]
        else:
            mapping_type = NO

        model_name = request.return_model or target

        if mapping_type == OBJECT:
            return self.map_one_object(model_name, response.data)

        elif mapping_type == COLLECTION:

            _is_limit = False
            if 'limit' in request.params and request.params['limit']:
                value = int(request.params['limit'])
                if value > 0:
                    _is_limit = True

            if _is_limit:
                data = response.data['data']
            else:
                data = response.data

            return self.map_to_collection(model_name, data)

        else:
            return response #response.data['response']['data']

    def map_one(self, object_name, data):
        return HASOFFERS_ENTITY_MAP[object_name](data)

    def map_to_collection(self, object_name, data):

        self.log('Mapping to collection %s data:%s' % (object_name, json.dumps(data)))

        if not len(data):
            return None

        collection = []
        for object_id, object_scope in data.items():
            obj = self.map_one(object_name, object_scope[object_name])
            obj.__dict__['raw_data'] = object_scope
            collection.append(obj)
        return collection

    def map_one_object(self, object_name, data):
        if not len(data):
            return None
        obj = self.map_one(object_name, data[object_name])
        obj.__dict__['raw_data'] = data
        return obj

    def map_related(self, object, data):
        contains = getattr(object, 'contains')
        for row in contains:
            entity = row['class']
            if entity in data:
                if row['relation'] == 'one':
                    object.__dict__[entity] = self.map_one(entity, data[entity])
                elif row['relation'] == 'many':
                    object.__dict__[entity] = self.map_to_collection(entity, data[entity])
        return object
