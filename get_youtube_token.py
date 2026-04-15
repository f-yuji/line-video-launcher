"""
YouTube OAuth2 リフレッシュトークン取得スクリプト。
一回だけ実行すればOK。取得したトークンを .env の YOUTUBE_REFRESH_TOKEN に貼り付ける。
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "client_secret_267994755389-sk1oqkp34rq3boho6515csp678ricmt2.apps.googleusercontent.com.json"

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
creds = flow.run_local_server(port=8080)

print("\n=== 取得成功 ===")
print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
print("\n↑ この値を .env の YOUTUBE_REFRESH_TOKEN に貼り付けてください")
