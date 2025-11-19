import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

class DecimalEncoder(json.JSONEncoder):
    """
    Helper class to convert DynamoDB Decimal types to standard Python floats
    for JSON serialization.
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    API Handler to fetch latest precipitation data.
    
    Returns:
        JSON response with latest data for all stations.
    """
    
    try:
        # Check for query parameters
        query_params = event.get('queryStringParameters') or {}
        station_param = query_params.get('station')
        
        if station_param:
            # Fetch history for specific station (last 24 hours)
            # Note: Scan is still inefficient. In production, use Query on GSI.
            response = table.scan(
                FilterExpression=Key('station_id').eq(station_param)
            )
            items = response.get('Items', [])
            # Sort by timestamp descending
            items.sort(key=lambda x: x['timestamp'], reverse=True)
            # Limit to last 50 readings
            items = items[:50]
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({
                    'station_id': station_param,
                    'history': items,
                    'count': len(items)
                }, cls=DecimalEncoder)
            }
            
        else:
            # Default: Get latest for all stations
            response = table.scan()
            items = response.get('Items', [])
            
            # Group by station and get latest reading for each
            stations = {}
            for item in items:
                station_id = item['station_id']
                timestamp = int(item['timestamp'])
                
                if station_id not in stations or timestamp > stations[station_id]['timestamp']:
                    stations[station_id] = item
            
            latest_data = list(stations.values())
            latest_data.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({
                    'stations': latest_data,
                    'count': len(latest_data),
                    'metadata': {
                        'source': 'National Weather Service',
                        'type': 'Precipitation Data'
                    }
                }, cls=DecimalEncoder)
            }
        
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal Server Error'})
        }