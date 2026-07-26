from mcp.server.fastmcp import FastMCP
import urllib.request
import json

mcp = FastMCP("exchange_rate")

@mcp.tool()
async def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """Get current exchange rate between two currencies.
    
    Args:
        from_currency: Source currency code (e.g., EUR, USD, GBP)
        to_currency: Target currency code (e.g., EUR, USD, GBP)
    """
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        to_curr = to_currency.upper()
        if to_curr not in data['rates']:
            return f"Currency {to_curr} not found"
        
        rate = data['rates'][to_curr]
        return f"1 {from_currency.upper()} = {rate} {to_curr}"
    except Exception as e:
        return f"Error fetching exchange rate: {str(e)}"

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
