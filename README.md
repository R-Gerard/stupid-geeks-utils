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
The code to execute the `print_label` function is currently disabled. If you wish to enable it you will need to configure your printer appropriately. See the Zebra printer setup guide for more info:

https://developer.zebra.com/docs/printer-setup-sendfiletoprinter

# Usage
The script is an interactive shell. Follow its prompts for instructions:

```sh
python3 ./print_label.py
```

# Troubleshooting
Check the `./cache` directory for JSON files pulled from Shopify to verify they exist and are correct.
