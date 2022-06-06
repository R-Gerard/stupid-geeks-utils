#!/usr/bin/env python3

from typing import Any, Dict, List
import os
import json
import requests


def init(
    config_file: str,
) -> Dict[str, Any]:
    if not os.path.exists(config_file):
        print(f"File not found: {config_file}")
        exit(1)

    with open(config_file, 'r') as f:
        config = json.loads(f.read())
        return config


def load_sku_file(
    filename: str,
) -> List[str]:
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return []

    with open(filename, 'r') as f:
        return f.readlines()


def write_text_to_file(
    cache_dir: str,
    filename: str,
    data: str,
) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, filename), 'w') as f:
        f.write(data)


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


def increment_inventory_quantity(
    base_url: str,
    username: str,
    password: str,
    location_id: int,
    inventory_item: Dict[str, str],
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
