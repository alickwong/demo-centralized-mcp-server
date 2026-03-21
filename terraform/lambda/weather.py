import json

WEATHER_DATA = {
    "sydney": {"city": "Sydney", "temp_c": 22, "condition": "Partly cloudy", "humidity": 65, "wind_kph": 18},
    "new york": {"city": "New York", "temp_c": 15, "condition": "Clear", "humidity": 45, "wind_kph": 12},
    "london": {"city": "London", "temp_c": 11, "condition": "Overcast", "humidity": 78, "wind_kph": 22},
    "tokyo": {"city": "Tokyo", "temp_c": 19, "condition": "Sunny", "humidity": 55, "wind_kph": 8},
    "singapore": {"city": "Singapore", "temp_c": 31, "condition": "Thunderstorms", "humidity": 88, "wind_kph": 15},
}

def lambda_handler(event, context):
    city = event.get("city", "").lower().strip()
    if city in WEATHER_DATA:
        return {"statusCode": 200, "body": json.dumps(WEATHER_DATA[city])}
    available = list(WEATHER_DATA.keys())
    return {"statusCode": 200, "body": json.dumps({
        "error": f"City '{city}' not found. Available: {available}"
    })}
