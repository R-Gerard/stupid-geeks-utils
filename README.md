# Zebra Printer Demo
Fetches product info from Shopify and renders ZPL templates as PNG images.

# Setup
```sh
python3 -m venv ./venv
source ./venv/bin/activate
pip3 install -r requirements.txt
cp example_config.json config.json
```

...then edit `config.json` to populate it with your Shopify and Zebra API keys and secrets.

## Zebra Cloud Printing (Experimental)
The code to execute the `cloud_print_label` function is currently disabled. If you wish to enable it you will need to configure your printer appropriately. See the Zebra printer setup guide for more info:

https://developer.zebra.com/docs/printer-setup-sendfiletoprinter

## Printing Individual Labels (Mac/Linux Only)
The code to execute the `network_print_label` function is currently disabled. When enabled it will spool print jobs via your PC's print queue to print individual labels (either by manually entering one SKU at a time or by loading a TXT file of SKUs). To enable this feature you will also need to set the `NETWORK_PRINTER_NAME` in the `config.json`.

To find the name of your printer, run this command in your terminal:

```sh
lpstat -p
```

# Usage
The script is an interactive shell. Follow its prompts for instructions:

```sh
python3 ./print_label.py
```

# Troubleshooting
Check the `./cache` directory for JSON files pulled from Shopify to verify they exist and are correct.
