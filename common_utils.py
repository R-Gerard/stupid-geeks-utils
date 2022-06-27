#!/usr/bin/env python3

from functools import wraps
from typing import Any, Dict, List, ForwardRef
import os
import json
import time
import datetime
import requests


def init(
    config_file: str,
) -> Dict[str, Any]:
    config = load_cached_json('', config_file)
    os.makedirs(config['CACHE_DIR'], exist_ok=True)
    CacheJson.cache_dir = config['CACHE_DIR']
    InvalidatesCache.cache_dir = config['CACHE_DIR']
    return config


def load_sku_file(
    filename: str,
) -> List[str]:
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return []

    with open(filename, 'r') as f:
        return f.readlines()


def load_cached_json(
    cache_dir: str,
    filename: str,
) -> Dict[str, Any]:
    full_path = os.path.join(cache_dir, filename)
    if not os.path.exists(full_path):
        raise Exception(f"File not found: {full_path}")

    with open(full_path, 'r') as f:
        data = json.loads(f.read())
        return data


def write_text_to_file(
    cache_dir: str,
    filename: str,
    data: str,
) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, filename), 'w') as f:
        f.write(data)


class CacheJson:
    """
    Decorator to wrap functions with a simple file caching layer. Checks an
    optional keyword argument 'product_sku' passed to the wrapped function to
    control the cached file name.

    Cache files are stored at either:
    - "{cache_dir}/{product_sku}{file_suffix}"
    - "{cache_dir}/GLOBAL{file_suffix}"
    """
    cache_dir = None
    create_times_file = 'GLOBAL_CacheIndex.json'

    def __init__(
        self,
        file_suffix: str,
        expires_in: datetime.timedelta=None
    ) -> ForwardRef('CacheJson'):
        self.file_suffix = file_suffix
        self.expires_in = expires_in

    def __call__(self, func):
        @wraps(func)
        def wrapper_cache_json(*args, **kwargs):
            if 'product_sku' in kwargs:
                filename = kwargs['product_sku'] + self.file_suffix
            else:
                filename = 'GLOBAL' + self.file_suffix

            try:
                if self.is_expired(filename):
                    full_path = os.path.join(CacheJson.cache_dir, filename)
                    os.remove(full_path)

                return load_cached_json(CacheJson.cache_dir, filename)
            except:
                data = func(*args, **kwargs)
                write_text_to_file(CacheJson.cache_dir, filename, json.dumps(data, indent=2))
                self.update_create_times(filename)
                return data
        return wrapper_cache_json

    def is_expired(
        self,
        filename: str
    ) -> bool:
        full_path = os.path.join(CacheJson.cache_dir, filename)
        if not os.path.exists(full_path):
            return False

        if not self.expires_in:
            return False

        try:
            create_times = load_cached_json(CacheJson.cache_dir, CacheJson.create_times_file)
        except:
            return False

        if filename not in create_times:
            return False

        return create_times[filename] + int(self.expires_in.total_seconds()) <= int(time.time())

    def update_create_times(
        self,
        filename: str
    ) -> None:
        try:
            create_times = load_cached_json(CacheJson.cache_dir, CacheJson.create_times_file)
        except:
            create_times = {}

        create_times[filename] = int(time.time())
        write_text_to_file(CacheJson.cache_dir, CacheJson.create_times_file, json.dumps(create_times, indent=2))


class InvalidatesCache:
    """
    Decorator to wrap functions that update remote state and thus invalidate
    cached data. Checks an optional keyword argument 'product_sku' passed to the
    wrapped function to control the cached file name.

    Cache files are DELETED at either:
    - "{cache_dir}/{product_sku}{file_suffix}"
    - "{cache_dir}/GLOBAL{file_suffix}"
    """
    cache_dir = None

    def __init__(
        self,
        file_suffix: str,
    ) -> ForwardRef('InvalidatesCache'):
        self.file_suffix = file_suffix

    def __call__(self, func):
        @wraps(func)
        def wrapper_invalidate_cache(*args, **kwargs):
            if 'product_sku' in kwargs:
                filename = kwargs['product_sku'] + self.file_suffix
            else:
                filename = 'GLOBAL' + self.file_suffix

            full_path = os.path.join(CacheJson.cache_dir, filename)
            if os.path.exists(full_path):
                os.remove(full_path)

            return func(*args, **kwargs)
        return wrapper_invalidate_cache


@CacheJson(file_suffix='_PriceCharting.json', expires_in=datetime.timedelta(days=1))
def query_pricecharting(
    api_key: str,
    product_sku: str,
) -> Dict[str, Any]:
    """
    Searches PriceCharting.com for a product by ID and makes price recommendations.

    https://www.pricecharting.com/api-documentation#overview
    """

    pricecharting_id = product_sku.split('-')[3]

    uri = f"https://www.pricecharting.com/api/product?t={api_key}&id={pricecharting_id}"

    session = requests.Session()
    response = session.get(uri)

    if response.status_code == 200:
        product_record = response.json()
    else:
        print(f"GET {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))

    return product_record


@CacheJson(file_suffix='_StoreLocations.json')
def get_shopify_store_locations(
    base_url: str,
    username: str,
    password: str,
) -> List[Dict[str, Any]]:
    """
    https://shopify.dev/api/admin-rest/2021-10/resources/location#[get]/admin/api/2021-10/locations.json
    """

    uri = f"{base_url}/admin/api/2021-10/locations.json"

    session = requests.Session()
    response = session.get(uri, auth=(username, password))

    if response.status_code == 200:
        locations = response.json()['locations']
        filtered_response = [ { k:d[k] for k in ['id', 'name'] } for d in locations ]
        return filtered_response
    else:
        print(f"GET {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))


@CacheJson(file_suffix='_ProductVariant.json')
def query_shopify_variants(
    base_url: str,
    username: str,
    password: str,
    product_sku: str,
) -> Dict[str, Any]:
    """
    https://shopify.dev/api/admin-graphql/2021-10/queries/productVariants
    """

    uri = f"{base_url}/admin/api/2021-10/graphql.json"

    graphql_query = {
        'query': '{ productVariants(first: 1, query: "sku:\'' + product_sku + '\'") { edges { node { id sku displayName barcode price } } } }'
    }

    session = requests.Session()
    response = session.post(uri, json=graphql_query, auth=(username, password))

    if response.status_code == 200:
        return response.json()['data']['productVariants']['edges'][0]['node']
    else:
        print(f"GET {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))


@CacheJson(file_suffix='_InventoryLevel.json', expires_in=datetime.timedelta(minutes=15))
def query_shopify_inventory(
    base_url: str,
    username: str,
    password: str,
    location_id: int,
    product_sku: str,
) -> Dict[str, Any]:
    """
    https://shopify.dev/api/admin-graphql/2021-10/queries/inventoryItems
    """

    uri = f"{base_url}/admin/api/2021-10/graphql.json"

    graphql_query = {
        'query': '{ inventoryItems(first: 1, query: "sku:\'' + product_sku + '\'") { edges { node { id sku inventoryLevel(locationId:"gid://shopify/Location/' + str(location_id) + '\'") { id available } } } } }'
    }

    session = requests.Session()
    response = session.post(uri, json=graphql_query, auth=(username, password))

    if response.status_code == 200:
        return response.json()['data']['inventoryItems']['edges'][0]['node']
    else:
        print(f"GET {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))


@InvalidatesCache(file_suffix='_InventoryLevel.json')
def increment_inventory_quantity(
    base_url: str,
    username: str,
    password: str,
    location_id: int,
    inventory_item: Dict[str, str],
    product_sku: str,
) -> None:
    """
    Increments a Shopify inventory quantity by 1.

    Expects a Shopify inventoryItem record. For example:
    {
        "id": "gid://shopify/InventoryItem/43070017601719",
        "sku": "N64-IS-GO-3924",
        "inventoryLevel": {
            "id": "gid://shopify/InventoryLevel/98302853303?inventory_item_id=43070017601719",
            "available": 6
        }
    }

    https://shopify.dev/api/examples/product-inventory#adjust-inventory-levels-by-a-certain-amount
    """

    uri = f"{base_url}/admin/api/2021-10/inventory_levels/adjust.json"

    payload = {
        'location_id': location_id,
        'inventory_item_id': inventory_item['id'].split('/')[-1],
        'available_adjustment': 1,
    }

    session = requests.Session()
    response = session.post(uri, json=payload, auth=(username, password))

    if response.status_code == 200:
        expected_quantity = inventory_item['inventoryLevel']['available'] + 1
        if expected_quantity == response.json()['inventory_level']['available']:
            print(f"Successfully updated {inventory_item['sku']} to {expected_quantity}")
        else:
            print(f"WARNING: failed to update {inventory_item['sku']} to {expected_quantity}")
        return response.json()
    else:
        print(f"POST {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))


@InvalidatesCache(file_suffix='_ProductVariant.json')
def set_inventory_price(
    base_url: str,
    username: str,
    password: str,
    variant_info: Dict[str, str],
    new_price: str,
    product_sku: str,
) -> None:
    """
    Sets a Shopify inventory item price to a new value.

    Expects a Shopify ProductVariant record. For example:
    {
      "id": "gid://shopify/ProductVariant/40973170409655",
      "sku": "N64-IS-GO-3924",
      "displayName": "Super Mario 64 - Nintendo 64 (In Store) - Game Only",
      "barcode": "045496870010",
      "price": "52.99"
    }

    https://shopify.dev/api/admin-rest/2021-10/resources/product-variant#put-variants-variant-id
    """

    inventory_item_id = variant_info['id'].split('/')[-1]

    uri = f"{base_url}/admin/api/2021-10/variants/{inventory_item_id}.json"

    payload = {
        'variant': {
            'id': inventory_item_id,
            'price': new_price,
        }
    }

    session = requests.Session()
    response = session.put(uri, json=payload, auth=(username, password))

    if response.status_code == 200:
        if new_price == response.json()['variant']['price']:
            print(f"Successfully updated {variant_info['sku']} to ${new_price}")
        else:
            print(f"WARNING: failed to update {variant_info['sku']} to ${new_price}")
        return response.json()
    else:
        print(f"PUT {uri} received unexpected response: {response.status_code}")
        raise Exception(json.dumps(response.json(), indent=2))
