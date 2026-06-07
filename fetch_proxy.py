import urllib.request
import json
import re

url = 'https://api.allorigins.win/get?url=https://mcpmarket.com/tools/skills/live2d-character-development'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        html = data.get('contents', '')
        github_urls = re.findall(r'https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', html)
        print("GitHub URLs found:")
        for g in set(github_urls):
            print(g)
except Exception as e:
    print(f"Error: {e}")
