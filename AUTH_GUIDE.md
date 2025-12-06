# Authentication Guide

This API supports optional Ed25519 key-based authentication for securing your analytics data.
By default, all stats are public. Once you register a public key for a `site_id`, all data retrieval endpoints for that site will require a valid signature.

## How it Works

There are two ways to set up authentication:

### Method A: QR Code Pairing (Easiest for iOS App)
Simply visit the pairing endpoint in your browser:
`http://localhost:8011/pair/<your-site-id>`

This will:
1.  Generate a new key pair on the server.
2.  Register the public key automatically.
3.  Display a QR code containing the **Private Key**, **Site ID**, and **API URL**.
4.  Scan this with your app to configure it instantly.

### Method B: Manual Setup (For Scripts/Custom Clients)

1.  **Generate a Key Pair**: You generate an Ed25519 key pair (Public + Private) on your client/server.
2.  **Register Public Key**: You send the Public Key (in Hex format) to the API's `/register-key` endpoint.
3.  **Sign Requests**: When fetching stats, you sign the request using your Private Key.

## 1. Generating Keys (Python Example)

You can use the `cryptography` library to generate keys.

```python
from cryptography.hazmat.primitives.asymmetric import ed25519

# Generate private key
private_key = ed25519.Ed25519PrivateKey.generate()

# Get public key
public_key = private_key.public_key()

# Get Hex strings
private_hex = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption()
).hex()

public_hex = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()

print(f"Private Key (Keep Secret): {private_hex}")
print(f"Public Key (Register this): {public_hex}")
```

## 2. Registering the Key

Send a POST request to `/register-key`:

```json
POST /register-key
{
  "site_id": "my-secure-site",
  "public_key_hex": "<your_public_key_hex>"
}
```

## 3. Making Authenticated Requests

To fetch stats, you must include the following headers:

-   `X-Timestamp`: Current Unix timestamp (integer). Must be within 5 minutes of server time.
-   `X-Signature`: Hex-encoded signature of the string `site_id:timestamp`.

### Python Client Example

```python
import time
import requests
from cryptography.hazmat.primitives.asymmetric import ed25519

# Your Private Key (Hex)
private_key_hex = "..." 
site_id = "my-secure-site"
base_url = "http://localhost:8011"

# Load Private Key
private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))

# Create Signature
timestamp = int(time.time())
message = f"{site_id}:{timestamp}".encode()
signature = private_key.sign(message).hex()

# Send Request
headers = {
    "X-Timestamp": str(timestamp),
    "X-Signature": signature
}

response = requests.get(f"{base_url}/stats?site_id={site_id}", headers=headers)
print(response.json())
```
