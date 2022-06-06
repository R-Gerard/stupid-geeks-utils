#!/usr/bin/env python3

from common_utils import *
from typing import Any, Dict, List
import os
import json


if __name__ == "__main__":
    CONFIG = init('config.json')

    print('Store locations:')
    locations = get_shopify_store_locations(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'])
    print(json.dumps(locations, indent=2))
    LOCATION_ID = locations[0]['id']
    print(f"Using locationId {LOCATION_ID}")

    while True:
        skus = []

        print('------------------------------------------------------------')
        print('Type a SKU to increment an inventory quantity by 1.')
        print("Enter 'F'+'Enter' to load a TXT file of SKUs and increment multiple quantities at once.")
        print("Enter 'Q'+'Enter' or 'Ctrl'+'C' to quit.")
        print('> ', end='')
        userinput = input()
        userinput_filename = ''
        if userinput in ['q', 'Q']:
            exit()
        elif userinput in ['f', 'F']:
            print('Enter filename:')
            print('> ', end='')
            userinput_filename = input()

            if not userinput_filename.strip():
                continue

            skus = load_sku_file(userinput_filename)
        elif not userinput.strip():
            continue
        else:
            skus = [ userinput ]

        if skus:
            skus = [ x.upper().strip() for x in skus ]

        for sku in skus:
            print(f"Processing: {sku}...")
            inventory_level = query_shopify_inventory(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], LOCATION_ID, sku)
            write_text_to_file(CONFIG['CACHE_DIR'], sku + '_InventoryLevel.json', json.dumps(inventory_level, indent=2))
            product_update = increment_inventory_quantity(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], LOCATION_ID, inventory_level)
            print(json.dumps(product_update, indent=2))
