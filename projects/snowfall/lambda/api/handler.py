import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

class DecimalEncoder(json.JSONEncoder):
    """Helper to convert Decimal to float for JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """API to fetch snowfall data"""
    
    try:
        # Get all stations' latest data
        response = table.scan()
        items = response.get('Items', [])
        
        # Group by station and get latest reading for each
        stations = {}
        for item in items:
            station_id = item['station_id']
            timestamp = int(item['timestamp'])
            
            if station_id not in stations or timestamp > stations[station_id]['timestamp']:
                stations[station_id] = item
        
        # Convert to list
        latest_data = list(stations.values())
        
        # Sort by timestamp descending
        latest_data.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',  # For CORS
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'stations': latest_data,
                'count': len(latest_data)
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }