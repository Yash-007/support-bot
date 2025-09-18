import requests
import ssl
import os
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['CURL_CA_BUNDLE'] = ''


class APIClient:
    @staticmethod
    def get_smart_invest_data():
        url = "https://coinswitch.co/pro/api/v1/algo-trading/all-strategies"
        headers = {
            "Accept": "application/json",
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        strategies =  response.json().get('data', [])
        profits = {}
        for s in strategies:
            if s.get('Strategy'):
                profits[s['Strategy']['name']] = s['Strategy']['historical_profit']
        
        return profits
