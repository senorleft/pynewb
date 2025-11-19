
import json
import os
import time
import boto3
from datetime import datetime
from urllib import request, error
from decimal import Decimal

# DynamoDB setup
# We use boto3 resource API which is higher-level than client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Station definitions
# Selected stations around Lake Michigan to capture lake-effect precipitation
STATIONS = {
    # Chicago Metro
    'KORD': {'name': "Chicago O'Hare", 'lat': 41.9742, 'lon': -87.9073},
    'KMDW': {'name': 'Chicago Midway', 'lat': 41.7868, 'lon': -87.7522},
    'KLOT': {'name': 'Romeoville/Lewis', 'lat': 41.6072, 'lon': -88.0959},
    
    # North Shore & Evanston Area
    'KUGN': {'name': 'Waukegan', 'lat': 42.4222, 'lon': -87.8678},
    
    # West/Southwest Suburbs
    'KDPA': {'name': 'DuPage/Naperville', 'lat': 41.9078, 'lon': -88.2486},
    
    # Indiana
    'KGYY': {'name': 'Gary/Chicago', 'lat': 41.6163, 'lon': -87.4128},
    'KSBN': {'name': 'South Bend', 'lat': 41.7087, 'lon': -86.3173},
    'KMGC': {'name': 'Michigan City', 'lat': 41.7033, 'lon': -86.8211},
    
    # Michigan
    'KBEH': {'name': 'Benton Harbor', 'lat': 42.1286, 'lon': -86.4285},
    'KAZO': {'name': 'Kalamazoo', 'lat': 42.2350, 'lon': -85.5521},
    'KGRR': {'name': 'Grand Rapids', 'lat': 42.8808, 'lon': -85.5228},
    
    # Wisconsin
    'KMKE': {'name': 'Milwaukee', 'lat': 42.9472, 'lon': -87.8965},
    'KGRB': {'name': 'Green Bay', 'lat': 44.4851, 'lon': -88.1296},
}

def get_station_data(station_code):
    """
    Fetch latest observation from National Weather Service (NWS) API.
    
    Args:
        station_code (str): The ICAO station code (e.g., 'KORD')
        
    Returns:
        dict: Parsed weather data or None if fetch fails
    """
    url = f'https://api.weather.gov/stations/{station_code}/observations/latest'
    
    try:
        req = request.Request(url)
        # NWS API requires a User-Agent header
        req.add_header('User-Agent', 'PynewbPrecipitationTracker/1.0')
        
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        properties = data.get('properties', {})
        
        # Extract relevant data using .get() to handle missing fields safely
        # We convert values to appropriate types later
        return {
            'temperature': properties.get('temperature', {}).get('value'),
            'snow_depth': properties.get('snowDepth', {}).get('value'), # May be null if not reported
            'precipitation_1h': properties.get('precipitationLastHour', {}).get('value'),
            'precipitation_3h': properties.get('precipitationLast3Hours', {}).get('value'),
            'wind_speed': properties.get('windSpeed', {}).get('value'),
            'visibility': properties.get('visibility', {}).get('value'),
            'conditions': properties.get('textDescription', 'Unknown'),
            'present_weather': properties.get('presentWeather', []), # List of weather phenomena
            'timestamp_obs': properties.get('timestamp')
        }
    except Exception as e:
        print(f"Error fetching {station_code}: {str(e)}")
        return None

def determine_precip_type(weather_data):
    """
    Determine the type of precipitation based on conditions and temperature.
    """
    conditions = weather_data.get('conditions', '').lower()
    present_weather = weather_data.get('present_weather', [])
    temp_c = weather_data.get('temperature')
    
    # Check explicit weather codes if available
    # NWS presentWeather is a list of dicts, e.g., [{'weather': 'snow', ...}]
    # But sometimes it's just a list of strings in simplified views, but NWS API returns list of objects
    # We'll check the text description first as it's easier
    
    if 'snow' in conditions:
        return 'snow'
    elif 'rain' in conditions:
        return 'rain'
    elif 'sleet' in conditions or 'ice' in conditions:
        return 'sleet'
    elif 'drizzle' in conditions:
        return 'rain'
        
    # Fallback to temperature if precip is reported but type is unclear
    precip_1h = weather_data.get('precipitation_1h')
    if precip_1h and precip_1h > 0:
        if temp_c and temp_c <= 0:
            return 'snow'
        else:
            return 'rain'
            
    return 'none'

def lambda_handler(event, context):
    """
    Main Lambda handler - collects data from all stations.
    Triggered by EventBridge Schedule every 10 minutes.
    """
    
    timestamp = int(time.time())
    results = []
    
    print(f"Starting collection at {timestamp}")
    
    for station_code, station_info in STATIONS.items():
        # print(f"Fetching data for {station_code}...") # Commented out to reduce log noise
        
        weather_data = get_station_data(station_code)
        
        if weather_data:
            precip_type = determine_precip_type(weather_data)
            
            # Prepare item for DynamoDB
            # We use Decimal because DynamoDB requires it for float numbers
            item = {
                'station_id': station_code,
                'timestamp': timestamp,
                'station_name': station_info['name'],
                'latitude': Decimal(str(station_info['lat'])),
                'longitude': Decimal(str(station_info['lon'])),
                'temperature_c': Decimal(str(weather_data['temperature'])) if weather_data['temperature'] is not None else None,
                'snow_depth_m': Decimal(str(weather_data['snow_depth'])) if weather_data['snow_depth'] is not None else None,
                'precip_1h_mm': Decimal(str(weather_data['precipitation_1h'])) if weather_data['precipitation_1h'] is not None else None,
                'precip_3h_mm': Decimal(str(weather_data['precipitation_3h'])) if weather_data['precipitation_3h'] is not None else None,
                'wind_speed_kmh': Decimal(str(weather_data['wind_speed'])) if weather_data['wind_speed'] is not None else None,
                'visibility_m': Decimal(str(weather_data['visibility'])) if weather_data['visibility'] is not None else None,
                'conditions': weather_data['conditions'],
                'precip_type': precip_type,
                'observation_time': weather_data['timestamp_obs']
            }
            
            # Remove None values (DynamoDB doesn't like empty attributes for optional fields)
            item = {k: v for k, v in item.items() if v is not None}
            
            # Write to DynamoDB
            try:
                table.put_item(Item=item)
                results.append({'station': station_code, 'status': 'success'})
                # print(f"✓ Saved data for {station_code}")
            except Exception as e:
                results.append({'station': station_code, 'status': 'error', 'error': str(e)})
                print(f"✗ Error saving {station_code}: {str(e)}")
        else:
            results.append({'station': station_code, 'status': 'no_data'})
    
    # Return summary
    return {
        'statusCode': 200,
        'body': json.dumps({
            'timestamp': timestamp,
            'results_summary': {
                'total': len(results),
                'success': len([r for r in results if r['status'] == 'success']),
                'errors': len([r for r in results if r['status'] == 'error'])
            }
        })
    }
