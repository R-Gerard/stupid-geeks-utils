#!/usr/bin/env python3

from common_utils import init, load_sku_file, write_text_to_file, query_shopify_variants
from string import Template
from typing import Any, Dict
import os
import json
import platform
import textwrap
import itertools
import requests


def cloud_print_label(
    base_url: str,
    api_key: str,
    printer_serial_number: str,
    zpl_data: str,
) -> None:
    """
    https://developer.zebra.com/apis/sendfiletoprinter-model#/SendFileToPrinter/SendFiletoPrinter
    """
    headers = {
        'apikey': api_key,
    }

    payload = {
        'sn': printer_serial_number,
        'zpl_file': zpl_data,
    }

    session = requests.Session()
    response = session.post(base_url, headers=headers, data=payload.encode('utf-8'))

    if response.status_code == 200:
        return response.json()
    else:
        print(f"POST {uri} received unexpected response: {response.status_code}")


def network_print_label(
    printer_name: str,
    file_name: str,
) -> None:
    if platform.system().lower() == 'windows':
        print('Run linux!')
    else:
        os.system(f"lpr -P '{printer_name}' '{file_name}'")


def render_zpl_template(
    template_file: str,
    template_label_line_max_chars: Dict[str, int],
    product_record: Dict[str, str],
) -> str:
    """
    Loads a Python String Template, does variable substitution, and returns back the rendered ZPL.

    Expects a Shopify productVariant record. For example:
    {
      "id": "gid://shopify/ProductVariant/40972869370039",
      "sku": "SNS-IS-GO-13823",
      "displayName": "NBA Live 95 - Super Nintendo (In Store) - Game Only",
      "barcode": "014633073829",
      "price": "0.99"
    }
    """

    full_title = f"{product_record['sku'].split('-')[0]}: {product_record['displayName'].split(' - ')[0]}"
    max_title_chars = template_label_line_max_chars['PRODUCT_TITLE_L1']
    if len(full_title) > max_title_chars:
        wrapped_title = textwrap.wrap(full_title, max_lines=2, width=max_title_chars, placeholder=' (...)')
    else:
        wrapped_title = [ full_title.center(max_title_chars, ' ') ]

    price = f"${product_record['price']}"
    price_type = 'New/Sealed' if product_record['displayName'].endswith('New/Sealed') else 'Pre-Owned'
    centered_price = price.center(template_label_line_max_chars['PRICE_STR'], ' ')
    centered_price_type = price_type.center(template_label_line_max_chars['PRICE_TYPE'], ' ')

    template_context = {
        'PRICE_STR': centered_price,
        'PRICE_TYPE': centered_price_type,
        'PRODUCT_TITLE_L1': wrapped_title[0] if len(wrapped_title) > 1 else '',
        'PRODUCT_TITLE_L2': wrapped_title[1] if len(wrapped_title) > 1 else wrapped_title[0],
        'BARCODE': product_record['barcode'],
        'SKU': product_record['sku'],
    }

    with open(template_file, 'r') as f:
        src = Template(f.read())
        result = src.substitute(template_context)
        return result


def draw_label(
    cache_dir: str,
    filename: str,
    zpl_data: str,
    label_width_inches: int,
    label_height_inches: int,
) -> str:
    """
    http://labelary.com/service.html
    """

    file_format = filename.split('.')[-1].lower()
    if file_format == 'png':
        headers = {}
        index_param = '0/'
    elif file_format == 'pdf':
        headers = {
            'accept': 'application/pdf',
        }
        index_param = ''
    else:
        print(f"Unsupported file format: {file_format}")
        return None

    uri = f"http://api.labelary.com/v1/printers/8dpmm/labels/{label_width_inches}x{label_height_inches}/{index_param}"

    session = requests.Session()
    response = session.post(uri, headers=headers, data=zpl_data.encode('utf-8'))

    if response.status_code == 200:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, filename)
        with open(path, 'wb') as f:
            f.write(response.content)
        return path
    else:
        print(f"POST {uri} received unexpected response: {response.status_code}")
        return None


if __name__ == "__main__":
    CONFIG = init('config.json')

    while True:
        skus = []

        print('------------------------------------------------------------')
        print('Type a SKU to print a single label.')
        print("Enter 'F'+'Enter' to load a TXT file of SKUs and print multiple labels at once.")
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
            skus = load_sku_file(userinput_filename)
        else:
            skus = [ userinput ]

        if skus:
            skus = [ x.upper().strip() for x in skus ]

        all_zpl_data = []
        for sku in skus:
            print(f"Processing: {sku}...")
            variant_info = query_shopify_variants(CONFIG['SHOPIFY_BASE_URL'], CONFIG['SHOPIFY_API_KEY'], CONFIG['SHOPIFY_API_SECRET'], product_sku=sku)
            zpl_data = render_zpl_template(CONFIG['LABEL_TEMPLATE_FILENAME'], CONFIG['LABEL_TEMPLATE_LINE_MAX_CHARS'], variant_info)
            all_zpl_data.append(zpl_data)
            #write_text_to_file(CONFIG['CACHE_DIR'], sku + '.txt', zpl_data)
            #img_file = draw_label(CONFIG['CACHE_DIR'], sku + '.png', zpl_data, CONFIG['LABEL_WIDTH_INCHES'], CONFIG['LABEL_HEIGHT_INCHES'])
            #cloud_print_label(CONFIG['ZEBRA_BASE_URL'], CONFIG['ZEBRA_API_KEY'], CONFIG['PRINTER_SERIAL_NUMBER'], zpl_data)
            #network_print_label(CONFIG['NETWORK_PRINTER_NAME'], img_file)

        if userinput_filename:
            file_stem = os.path.splitext(os.path.basename(userinput_filename))[0]
        else:
            file_stem = skus[0]

        for group_num, zpl_data_chunk in enumerate(itertools.zip_longest(*(iter(all_zpl_data),) * CONFIG['MAX_LABELS_PER_PDF'], fillvalue='')):
            zpl_data = '\n'.join(zpl_data_chunk)
            pdf_file = draw_label(CONFIG['CACHE_DIR'], f"{file_stem}_{group_num}.pdf", zpl_data, CONFIG['LABEL_WIDTH_INCHES'], CONFIG['LABEL_HEIGHT_INCHES'])
            print(f"Rendered PDF: {pdf_file}")
