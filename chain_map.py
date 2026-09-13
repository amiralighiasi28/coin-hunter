"""
نگاشت بین نام چین در CoinGecko و شناسه‌ی چین مورد نیاز GoPlus Security API.
هر پلتفرم/بلاکچین جدیدی که خواستی پشتیبانی کنی رو اینجا اضافه کن.
لیست کامل chain id های GoPlus: https://docs.gopluslabs.io/reference/chainid
"""

# نام platform در CoinGecko -> chain_id عددی GoPlus (برای EVM chains)
COINGECKO_TO_GOPLUS_CHAIN_ID = {
    "ethereum": "1",
    "binance-smart-chain": "56",
    "polygon-pos": "137",
    "arbitrum-one": "42161",
    "optimistic-ethereum": "10",
    "avalanche": "43114",
    "fantom": "250",
    "base": "8453",
}

# چین‌هایی که GoPlus برای‌شون endpoint جداگانه داره (غیر EVM)
NON_EVM_GOPLUS_ENDPOINTS = {
    "solana": "solana",
}


def resolve_chain(platforms: dict):
    """
    از دیکشنری platforms کوینگکو (که چند تا چین ممکنه توش باشه)،
    اولین چینی که GoPlus پشتیبانی می‌کنه رو با آدرس قراردادش برمی‌گردونه.
    خروجی: (chain_type, chain_id_or_name, contract_address) یا None
    """
    if not platforms:
        return None

    for platform_name, address in platforms.items():
        if not address:
            continue
        if platform_name in COINGECKO_TO_GOPLUS_CHAIN_ID:
            return "evm", COINGECKO_TO_GOPLUS_CHAIN_ID[platform_name], address
        if platform_name in NON_EVM_GOPLUS_ENDPOINTS:
            return "solana", NON_EVM_GOPLUS_ENDPOINTS[platform_name], address

    return None
