from mcp.server.fastmcp import FastMCP
import urllib.request
import json

mcp = FastMCP("weather")

@mcp.tool()
async def get_weather(city: str, country: str = "") -> str:
    """Get current weather for a city.
    
    Args:
        city: City name
        country: Optional country code (e.g., 'PT' for Portugal)
    """
    try:
        # Using Open-Meteo free API (no key required)
        # First get coordinates
        location_query = f"{city},{country}" if country else city
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_query}&count=1"
        
        with urllib.request.urlopen(geocode_url) as response:
            geo_data = json.loads(response.read())
        
        if not geo_data.get("results"):
            return f"Could not find location: {location_query}"
        
        location = geo_data["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        name = location["name"]
        country_name = location.get("country", "")
        
        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=auto"
        
        with urllib.request.urlopen(weather_url) as response:
            weather_data = json.loads(response.read())
        
        current = weather_data["current"]
        
        # Weather code descriptions (WMO codes)
        weather_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Foggy with rime",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        
        weather_desc = weather_codes.get(current["weather_code"], "Unknown")
        
        result = f"""Current weather in {name}, {country_name}:
        
Conditions: {weather_desc}
Temperature: {current['temperature_2m']}°C (feels like {current['apparent_temperature']}°C)
Humidity: {current['relative_humidity_2m']}%
Wind Speed: {current['wind_speed_10m']} km/h
Precipitation: {current['precipitation']} mm"""
        
        return result
        
    except Exception as e:
        return f"Error fetching weather: {str(e)}"

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
