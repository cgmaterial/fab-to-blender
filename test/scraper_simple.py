import requests

# url = "https://www.fab.com/i/listings/search"
# url = "https://www.fab.com/i/listings/b02cdcb8-a5e8-4e96-8fec-60b5a0c31a9f/asset-formats"
url = "https://www.fab.com/i/listings/b02cdcb8-a5e8-4e96-8fec-60b5a0c31a9f/asset-formats/gltf/files/0b564456-22d7-44bb-aa1d-6c80b16912f7/download-info/binary"

# Referer = "https://www.fab.com/sellers/Quixel"
Referer = "https://www.fab.com/i/listings/b02cdcb8-a5e8-4e96-8fec-60b5a0c31a9f"

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": Referer,
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Alt-Used": "www.fab.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-GPC": "1"
}

response = requests.get(url, headers=headers)

print(response.status_code)

