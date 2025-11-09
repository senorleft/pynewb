
import json
import os
import time
import boto3
from datetime import datetime
from urllib import request, error
from decimal import Decimal

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Station definitions
STATIONS = {
    'KORD': {'name': "Chicago O'Hare", 'lat': 41.9742, 'lon': -87.9073},
    'KMDW': {'name': 'Chicago Midway', 'lat': 41.7868, 'lon': -87.7522},
    'KPWK': {'name': 'Chicago Executive', 'lat': 42.1142, 'lon': -87.9015},
    'KLOT': {'name': 'Romeoville/Lewis', 'lat': 41.6072, 'lon': -88.0959},
    'KGYY': {'name': 'Gary/Chicago', 'lat': 41.6163, 'lon': -87.4128},
    'KSBN': {'name': 'South Bend', 'lat': 41.7087, 'lon': -86.3173},
    'KBEH': {'name': 'Benton Harbor', 'lat': 42.1286, 'lon': -86.4285},
    'KUGN': {'name': 'Waukegan', 'lat': 42.4222, 'lon': -87.8678},
    'KDPA': {'name': 'DuPage/Naperville', 'lat': 41.9078, 'lon': -88.2486},
    'KMGC': {'name': 'Michigan City', 'lat': 41.7033, 'lon': -86.8211},
}

def get_station_data(station_code):
    """Fetch latest observation from NWS API"""
    url = f'https://api.weather.gov/stations/{station_code}/observations/latest'
    
    try:
        req = request.Request(url)
        req.add_header('User-Agent', 'SnowfallTracker/1.0')
        
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        properties = data.get('properties', {})
        
        # Extract relevant data
        return {
            'temperature': properties.get('temperature', {}).get('value'),
            'snow_depth': properties.get('snowDepth', {}).get('value'),
            'wind_speed': properties.get('windSpeed', {}).get('value'),
            'visibility': properties.get('visibility', {}).get('value'),
            'conditions': properties.get('textDescription', 'Unknown'),
            'timestamp_obs': properties.get('timestamp')
        }
    except Exception as e:
        print(f"Error fetching {station_code}: {str(e)}")
        return None

def lambda_handler(event, context):
    """Main Lambda handler - collects data from all stations"""
    
    timestamp = int(time.time())
    results = []
    
    for station_code, station_info in STATIONS.items():
        print(f"Fetching data for {station_code}...")
        
        weather_data = get_station_data(station_code)
        
        if weather_data:
            # Prepare item for DynamoDB
            item = {
                'station_id': station_code,
                'timestamp': timestamp,
                'station_name': station_info['name'],
                'latitude': Decimal(str(station_info['lat'])),
                'longitude': Decimal(str(station_info['lon'])),
                'temperature_c': Decimal(str(weather_data['temperature'])) if weather_data['temperature'] else None,
                'snow_depth_m': Decimal(str(weather_data['snow_depth'])) if weather_data['snow_depth'] else None,
                'wind_speed_kmh': Decimal(str(weather_data['wind_speed'])) if weather_data['wind_speed'] else None,
                'visibility_m': Decimal(str(weather_data['visibility'])) if weather_data['visibility'] else None,
                'conditions': weather_data['conditions'],
                'observation_time': weather_data['timestamp_obs']
            }
            
            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}
            
            # Write to DynamoDB
            try:
                table.put_item(Item=item)
                results.append({'station': station_code, 'status': 'success'})
                print(f"✓ Saved data for {station_code}")
            except Exception as e:
                results.append({'station': station_code, 'status': 'error', 'error': str(e)})
                print(f"✗ Error saving {station_code}: {str(e)}")
        else:
            results.append({'station': station_code, 'status': 'no_data'})
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'timestamp': timestamp,
            'results': results
        })
    }


