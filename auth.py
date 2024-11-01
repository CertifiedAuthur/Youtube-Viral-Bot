# IMPORTING LIBRARIES
import os
import streamlit as st
import asyncio
from httpx_oauth.oauth2 import GetAccessTokenError
from httpx_oauth.clients.google import GoogleOAuth2
    
# Fetch secrets from Streamlit's secrets
CLIENT_ID = st.secrets["general"]["CLIENT_ID"]
CLIENT_SECRET = st.secrets["general"]["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["general"]["REDIRECT_URI"]


# Asynchronous function to get the Google authorization URL
async def get_authorization_url(client: GoogleOAuth2, redirect_uri: str):
    authorization_url = await client.get_authorization_url(
        redirect_uri,
        scope=[
            "openid",
            "profile",
            "email",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.force-ssl",
            "https://www.googleapis.com/auth/youtubepartner"
        ]
    )
    return authorization_url

# Asynchronous function to get the access token
async def get_access_token(client: GoogleOAuth2, redirect_uri: str, code: str):
    print(f"Getting access token with code: {code}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Client ID: {client.client_id}")
    print(f"Client Secret: {client.client_secret}")
    
    try:
        token = await client.get_access_token(code, redirect_uri)
        print(f"Access Token: {token}")
        return token
    except GetAccessTokenError as e:
        error_response = e.response.json()
        print(f"Error Response: {error_response}")
        if error_response["error"] == "invalid_grant":
            print("Invalid authorization code. Please re-authorize.")
        else:
            print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")


# Asynchronous function to retrieve the user's email
async def get_email(client, access_token):
    try:
        user_info = await client.get_id_email(access_token)
        user_id = user_info["id"]
        user_email = user_info["email"]
        return user_id, user_email
    except Exception as e:
        print(f"Error retrieving email: {e}")
        return None, None


# Display Google login link
def get_login_str():
    client = GoogleOAuth2(CLIENT_ID, CLIENT_SECRET)
    authorization_url = asyncio.run(get_authorization_url(client, REDIRECT_URI))
    return f'<a target="_self" href="{authorization_url}">Google login</a>'


# Display user information after successful login
def display_user():
    client = GoogleOAuth2(CLIENT_ID, CLIENT_SECRET)
    
    # Retrieve the authorization code from the URL
    code_param = st.query_params.get('code')
    print(f"Code Param: {code_param}")
    code = code_param or ""  # Get entire code, not just first character
    print(f"Code: {code}")
    print(f"Code Length: {len(code)}")
    
    if code:  # Check if code is not empty
        # Get access token and user information
        token = asyncio.run(get_access_token(client, REDIRECT_URI, code))
        if token:  # Check if token is not None
            st.session_state.access_token = token['access_token']  # Store access token in session state
            user_id, user_email = asyncio.run(get_email(client, token['access_token']))
            st.write(f"You're logged in as {user_email} with ID {user_id}")
    else:
        st.error("No authorization code found. Please log in again.")


