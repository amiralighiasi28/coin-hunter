"""
کلاینت GoPlus Security - فاز ۳ (Risk Scoring در سطح قرارداد).
این API رایگانه و نیاز به کلید نداره: https://gopluslabs.io/
کاری که می‌کنه: قرارداد توکن رو تحلیل می‌کنه و می‌گه آیا honeypot هست،
مالک می‌تونه balance بقیه رو تغییر بده، تمرکز holderها چقدره، و غیره.
"""

import time
import requests

GOPLUS_BASE_URL = "https://api.gopluslabs.io/api/v1"


class GoPlusClient:
    def __init__(self):
        self.session = requests.Session()

    def _get(self, url: str, params: dict, retries: int = 2):
        for attempt in range(retries):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException:
                if attempt == retries - 1:
                    raise
                time.sleep(2)
        return None

    def check_evm_token(self, chain_id: str, contract_address: str) -> dict:
        """بررسی امنیت توکن روی چین‌های EVM (اتریوم، BSC، پالیگان و ...)."""
        url = f"{GOPLUS_BASE_URL}/token_security/{chain_id}"
        params = {"contract_addresses": contract_address.lower()}
        data = self._get(url, params)
        if not data or "result" not in data:
            return {}
        return data["result"].get(contract_address.lower(), {})

    def check_solana_token(self, contract_address: str) -> dict:
        """بررسی امنیت توکن روی سولانا (endpoint جداگانه داره)."""
        url = f"{GOPLUS_BASE_URL}/solana/token_security"
        params = {"contract_addresses": contract_address}
        data = self._get(url, params)
        if not data or "result" not in data:
            return {}
        return data["result"].get(contract_address, {})

    def check_token(self, chain_type: str, chain_id_or_name: str, contract_address: str) -> dict:
        """رَپر یکسان برای EVM و Solana."""
        if chain_type == "evm":
            return self.check_evm_token(chain_id_or_name, contract_address)
        elif chain_type == "solana":
            return self.check_solana_token(contract_address)
        return {}
