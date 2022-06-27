#!/usr/bin/env python3

from common_utils import *
from enum import IntEnum
from typing import Any, Dict, List, Tuple
import os
import re
import csv
import json


def cents_to_s(
    price: int,
) -> str:
    """
    Converts an integer monetary value into a dollar string, without the '$'.
    """
    return f"{price//100}.{price%100:02d}"


def dollar_to_i(
    price: str,
) -> int:
    """
    Converts a price string to an integer representation of the monetary value.

    Example 1: dollar_to_i("$19.95") = 1995
    Example 2: dollar_to_i("100") = 10000
    Example 3: dollar_to_i("0.3") = 30
    Example 4: dollar_to_i("twelve") = 0
    """
    if '.' in price:
        dollars, cents = price.split('.')
    else:
        dollars, cents = price, ''

    dollars = int(re.sub(r"\D", '', dollars))
    cents = int(re.sub(r"\D", '', cents).ljust(2, '0')[0:2])
    return 100 * dollars + cents


def percent_to_f(
    percent: str,
) -> float:
    """
    Converts a percent string to a float.

    Example: 70% = 0.7
    """
    return float(re.sub(r"\D", '', percent)) / 100

# Map Shopify's 2/3-letter product type in the SKU to PriceCharting's price key(s)
SKU_PRICE_KEYS = {
    'GO': ['loose-price'],
    'NS': ['new-price'],
    #'GMB': ['cib-price']
    'GMB': ['loose-price', 'manual-only-price', 'box-only-price'],
    'GB': ['loose-price', 'box-only-price'],
    'MO': ['manual-only-price'],
    'BO': ['box-only-price'],
}


def diff_prices(
    variant_info: Dict[str, str],
    pricecharting_info: Dict[str, str],
) -> Tuple[int, int]:
    """
    Computes the relative price difference between Shopify and PriceCharting,
     returns a tuple of the difference and the PriceCharting price (in cents).

    Example 1: PriceCharting "2000" - Shopify "19.99" = (1, 2000)
    Example 2: PriceCharting "1995" - Shopify "19.99" = (-4, 1995)
    Example 3: PriceCharting "100" - Shopify "100.00" = (-9900, 100)

    Expects a Shopify productVariants record. For example:
    {
      "id": "gid://shopify/ProductVariant/40973509787831",
      "sku": "NES-IS-GO-12174",
      "displayName": "A Nightmare on Elm Street - NES (In Store) - Game Only",
      "barcode": "023582051598",
      "price": "78.99"
    }

    Expects a PriceCharting record. For example:
    {
      "box-only-price": 5000,
      "cib-price": 27859,
      "console-name": "NES",
      "genre": "Platformer",
      "id": "12174",
      "loose-price": 6812,
      "manual-only-price": 4995,
      "new-price": 112825,
      "product-name": "A Nightmare on Elm Street",
      "release-date": "1990-10-01",
      "status": "success",
      "upc": "023582051598"
    }
    """
    product_type = variant_info['sku'].split('-')[2]
    current_price = dollar_to_i(variant_info['price'])
    market_value = 0
    for price_key in SKU_PRICE_KEYS[product_type]:
        market_value += int(pricecharting_info[price_key])

    return (market_value - current_price), market_value


def apply_price_matrix(
    price_matrix: Dict[str, Dict[str, Dict[str, str]]],
    premium_titles: Dict[str, List[str]],
    sku: str,
    price_diff_cents: int,
    current_value_cents: int,
) -> Tuple[int, str]:
    """
    Traverses a price matrix according to SKU console_code and current_value to
    locate a price_diff_threshold and suggested_price_step, then generate a new
    suggested price and an explanation string of the logic applied.
    Applies a price "premium" (percentage markup above market value) if the sku
    is identified in the

    Example price matrix:
    {
      "NES": {
        "$5.00": {
          "PRICE_DIFF_THRESHOLD": "$5.00",
          "SUGGESTED_PRICE_STEP": "$1.00"
        },
        "$25.00": {
          "PRICE_DIFF_THRESHOLD": "$5.00",
          "SUGGESTED_PRICE_STEP": "$2.00"
        },
        "$100.00": {
          "PRICE_DIFF_THRESHOLD": "$5.00",
          "SUGGESTED_PRICE_STEP": "$3.00"
        }
      },
      "DEFAULT": {
        "$50.00": {
          "PRICE_DIFF_THRESHOLD": "$5.00",
          "SUGGESTED_PRICE_STEP": "$1.00"
        },
        "$100.00": {
          "PRICE_DIFF_THRESHOLD": "$5.00",
          "SUGGESTED_PRICE_STEP": "$3.00"
        }
      }
    }

    Example premium title list:
    {
      "70%": [
        "N64-IS-GO-3780",
        "N64-IS-GO-3977"
      ]
    }
    """
    comments = ''
    inverted_premium_titles = {}
    for k,l in premium_titles.items():
        for v in l:
            inverted_premium_titles[v] = k

    console_key = (lambda x : x if x in price_matrix else 'DEFAULT')(sku.split('-')[0])
    try:
        temp_price: int = [ x for x in sorted([ dollar_to_i(y) for y in price_matrix[console_key].keys() ]) if x > current_value_cents ][0]
    except:
        temp_price: int = sorted([ dollar_to_i(x) for x in price_matrix[console_key].keys() ])[-1]
    price_tier: str = [ x for x in price_matrix[console_key].keys() if dollar_to_i(x) == temp_price ][0]

    price_diff_threshold_cents = dollar_to_i(price_matrix[console_key][price_tier]['PRICE_DIFF_THRESHOLD'])
    suggested_price_step_cents = dollar_to_i(price_matrix[console_key][price_tier]['SUGGESTED_PRICE_STEP'])
    original_price_cents = current_value_cents - price_diff_cents

    if sku in inverted_premium_titles:
        comments = 'Premium title: '
        premium_markup = 1.0 + percent_to_f(inverted_premium_titles[sku])
        current_value_cents = int(premium_markup * current_value_cents)
        price_diff_cents = current_value_cents - original_price_cents

    if price_diff_cents > price_diff_threshold_cents:
        new_suggested_price_cents = (current_value_cents // suggested_price_step_cents + 1) * suggested_price_step_cents - 1
        return (new_suggested_price_cents, f"{comments}Market increase")
    elif price_diff_cents < 0:
        return (original_price_cents, f"{comments}Market drop")
    else:
        return (
            original_price_cents,
            f"{comments}Price is OK (within ${cents_to_s(price_diff_threshold_cents)})"
        )


class Mode(IntEnum):
    INCREMENT_QUANITY_MODE = (0, 'Type a SKU to increment an inventory quantity by 1.')
    SUGGEST_PRICE_MODE = (1, 'Type a SKU to create a price table (CSV) according to PriceCharting.')
    UPDATE_PRICE_MODE = (2, 'Type a SKU to update its price using a price table (CSV).')

    def __new__(cls, value, description):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj


if __name__ == "__main__":
    CONFIG = init('config.json')

    print('Store locations:')
    locations = get_shopify_store_locations(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'])
    print(json.dumps(locations, indent=2))
    LOCATION_ID = locations[0]['id']
    print(f"Using locationId {LOCATION_ID}")

    current_mode = Mode.SUGGEST_PRICE_MODE

    while True:
        skus = []

        print('------------------------------------------------------------')
        print(current_mode.name + ': ' + current_mode.description)
        print("Enter 'M'+'Enter' to switch to next mode.")
        print("Enter 'F'+'Enter' to load a TXT/CSV file of SKUs and process multiple titles at once.")
        print("Enter 'Q'+'Enter' or 'Ctrl'+'C' to quit.")
        print('> ', end='')
        userinput = input()
        userinput_filename = ''
        if userinput in ['q', 'Q']:
            exit()
        elif userinput in ['m', 'M']:
            current_mode = Mode((int(current_mode) + 1) % len(Mode))
            continue
        elif userinput in ['f', 'F']:
            print('Enter filename:')
            print('> ', end='')
            userinput_filename = input()

            if not userinput_filename.strip():
                continue

            if userinput_filename.endswith('.txt'):
                skus = load_sku_file(userinput_filename)
        elif not userinput.strip():
            continue
        else:
            skus = [ userinput ]

        if skus:
            skus = [ x.upper().strip() for x in skus ]

        if userinput_filename:
            file_stem = os.path.splitext(os.path.basename(userinput_filename))[0]
        elif skus:
            file_stem = skus[0]
        else:
            file_stem = ''

        if file_stem:
            csv_file_path = os.path.join(CONFIG['CACHE_DIR'], file_stem + '.csv')
        else:
            csv_file_path = ''

        if current_mode in [Mode.SUGGEST_PRICE_MODE, Mode.UPDATE_PRICE_MODE]:
            print(f"csv_file_path: {csv_file_path}")

        if current_mode == Mode.INCREMENT_QUANITY_MODE:
            for sku in skus:
                print(f"Processing: {sku}...")
                inventory_level = query_shopify_inventory(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], LOCATION_ID, product_sku=sku)
                product_update = increment_inventory_quantity(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], LOCATION_ID, inventory_level, product_sku=sku)
                print(json.dumps(product_update, indent=2))
        elif current_mode == Mode.SUGGEST_PRICE_MODE:
            if not csv_file_path:
                raise Exception('CSV file not specified')

            if os.path.exists(csv_file_path):
                os.remove(csv_file_path)

            CSV_COL_NAMES = ['SKU', 'Store Title', 'PC Title', 'PC Console', 'Current Price', 'Current Value', 'Suggested Price', 'Qty In Stock', 'Comments']
            with open(csv_file_path, 'w', newline='') as f:
                csv_writer = csv.DictWriter(f, fieldnames=CSV_COL_NAMES)
                csv_writer.writeheader()
                for sku in set(skus):
                    print(f"Processing: {sku}...")
                    variant_info = query_shopify_variants(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], product_sku=sku)
                    pricecharting_info = query_pricecharting(CONFIG['PRICECHARTING_API_KEY'], variant_info, product_sku=sku)
                    inventory_level = query_shopify_inventory(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], LOCATION_ID, product_sku=sku)
                    price_diff_cents, current_value_cents = diff_prices(variant_info, pricecharting_info)
                    suggested_price_cents, comment_str = apply_price_matrix(CONFIG['PRICE_MATRIX'], CONFIG['PREMIUM_TITLES'], sku, price_diff_cents, current_value_cents)

                    csv_row = {
                        'SKU': sku,
                        'Store Title': variant_info['displayName'].split(' - ')[0],
                        'PC Title': pricecharting_info['product-name'],
                        'PC Console': pricecharting_info['console-name'],
                        'Current Price': f"${variant_info['price']}",
                        'Current Value': f"${cents_to_s(current_value_cents)}",
                        'Suggested Price': f"${cents_to_s(suggested_price_cents)}",
                        'Qty In Stock': f"{inventory_level['inventoryLevel']['available']}",
                        'Comments': comment_str,
                    }

                    print(json.dumps(csv_row, indent=2))
                    csv_writer.writerow(csv_row)

            print(f"Pricing data written to: {csv_file_path}")
        elif current_mode == Mode.UPDATE_PRICE_MODE:
            if not csv_file_path:
                raise Exception('CSV file not specified')

            with open(csv_file_path, 'r', newline='') as f:
                csv_reader = csv.DictReader(f)
                for csv_row in csv_reader:
                    sku = csv_row['SKU']
                    if csv_row['Current Price'] == csv_row['Suggested Price']:
                        print(f"Skipping: {sku}...")
                        continue

                    print(f"Processing: {sku}...")
                    variant_info = query_shopify_variants(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], product_sku=sku)
                    new_price = cents_to_s(dollar_to_i(csv_row['Suggested Price']))
                    product_update = set_inventory_price(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], variant_info, new_price, product_sku=sku)
                    print(json.dumps(product_update, indent=2))
        else:
            raise Exception(f"Unsupported Mode: {current_mode.name}")
