import streamlit as st
import requests
from bs4 import BeautifulSoup
from auth import *
import pytrends
from googleapiclient.discovery import build
from streamlit_js import st_js, st_js_blocking
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from httpx_oauth.clients.google import GoogleOAuth2
import matplotlib.pyplot as plt
from google_auth_oauthlib import flow
from pytrends.request import TrendReq
import datetime
import pandas as pd
import numpy as np
import pickle
import asyncio
import json

# Helper function to convert large numbers to thousands, millions, etc.
def format_number(number):
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return str(number)

def get_channel_id(Channel_url):
    # Fetch the page content
    response = requests.get(Channel_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find channel ID in the page metadata
    channel_link = soup.find("link", {"rel": "canonical"})
    if channel_link:
        canonical_url = channel_link["href"]
        channel_id = canonical_url.split("/")[-1]
        return channel_id
    else:
        return None
    
def extract_video_id(video_url):
    # Split the URL by slashes and take the last part
    video_id = video_url.split('/')[-1]
    
    # If the video ID contains a query string (e.g., ?si=...)
    if '?' in video_id:
        video_id = video_id.split('?')[0]
    
    return video_id


def get_channel_analytics(Channel_url):
    # Get channel ID
    channel_id = get_channel_id(Channel_url)
    if not channel_id:
        return None
    
    youtube = get_service()
    response = execute_api_request(
        youtube.channels().list,
        part="statistics",
        id=channel_id
    )
    
    if 'items' in response and response['items']:
        stats = response['items'][0]['statistics']
        
        # Create DataFrame
        data = {
            "Metric": ["Subscriber Count", "Total Views", "Total Videos"],
            "Value": [int(stats.get('subscriberCount', 0)), int(stats.get('viewCount', 0)), int(stats.get('videoCount', 0))]
        }
        df = pd.DataFrame(data)
        # Plot
        st.write("### Channel Analytics")
        st.bar_chart(df.set_index("Metric")["Value"])
        return df
    else:
        st.write(f"No data found for channel {channel_id}")
        return None


def get_video_metrics(video_url):
    video_id = extract_video_id(video_url)
    youtube = get_service()
    response = execute_api_request(
        youtube.videos().list,
        part="statistics",
        id=video_id
    )
    
    if 'items' in response and response['items']:
        stats = response['items'][0]['statistics']
        
        # Create DataFrame
        data = {
            "Metric": ["View Count", "Like Count", "Comment Count"],
            "Value": [int(stats.get('viewCount', 0)), int(stats.get('likeCount', 0)), int(stats.get('commentCount', 0))]
        }
        df = pd.DataFrame(data)
        
        # Plot
        st.write("### Video Metrics")
        st.bar_chart(df.set_index("Metric")["Value"])
        
        return df
    else:
        st.write(f"No data found for video {video_id}")
        return None

def search_youtube(query, max_results=5):
    youtube = get_service()
    response = execute_api_request(
        youtube.search().list,
        part="snippet",
        q=query,
        type="video,channel,playlist",
        maxResults=max_results
    )
    
    if 'items' in response:
        data = [{
            "Title": item['snippet']['title'],
            "Type": item['id']['kind'].split('#')[-1],  # Extract video, channel, or playlist
            "Description": item['snippet']['description']
        } for item in response['items']]
        
        df = pd.DataFrame(data)
        return df
    else:
        st.write(f"No results found for query '{query}'")
        return None


def get_channel_info(channel_url):
    channel_id = get_channel_id(channel_url)
    
    youtube = get_service()
    response = execute_api_request(
        youtube.channels().list,
        part="snippet",
        id=channel_id
    )
    
    if 'items' in response:
        snippet = response['items'][0]['snippet']
        data = {
            "Metric": ["Title", "Description", "Published At"],
            "Value": [snippet.get('title'), snippet.get('description'), snippet.get('publishedAt')]
        }
        df = pd.DataFrame(data)
        return df
    else:
        st.write(f"No data found for channel {channel_id}")
        return None


def get_playlists_from_channel(channel_url):
    # Get channel ID from the URL
    channel_id = get_channel_id(channel_url)
    if not channel_id:
        st.write("Channel ID could not be retrieved.")
        return None

    # Get YouTube service
    youtube = get_service()
    
    # Retrieve playlists for the channel
    response = execute_api_request(
        youtube.playlists().list,
        part="snippet",
        channelId=channel_id,
        maxResults=50  # Adjust as needed
    )
    
    if 'items' in response:
        playlists = [{
            "Title": item['snippet']['title'],
            "Playlist ID": item['id']
        } for item in response['items']]
        
        return playlists
    else:
        st.write(f"No playlists found for channel {channel_id}")
        return None

def get_playlist_details(playlist_id):
    youtube = get_service()
    response = execute_api_request(
        youtube.playlists().list,
        part="snippet,contentDetails",
        id=playlist_id
    )
    
    if 'items' in response:
        details = response['items'][0]
        snippet = details['snippet']
        content_details = details['contentDetails']
        
        # Parse publishedAt date
        published_at = datetime.datetime.strptime(snippet.get('publishedAt'), '%Y-%m-%dT%H:%M:%SZ')
        published_at_formatted = published_at.strftime('%B %d, %Y at %I:%M %p')
        
        data = {
            "Metric": [
                "Title",
                "Description",
                "Published At",
                "Video Count"
            ],
            "Value": [
                snippet.get('title'),
                snippet.get('description'),
                published_at_formatted,
                content_details.get('itemCount'),
            ]
        }
        
        
        
        df = pd.DataFrame(data)
        st.write(df)
        
    else:
        st.write(f"No data found for playlist {playlist_id}")
        return None



def get_video_comments(video_url, max_results=10):
    video_id = extract_video_id(video_url)
    youtube = get_service()
    response = execute_api_request(
        youtube.commentThreads().list,
        part="snippet",
        videoId=video_id,
        maxResults=max_results
    )
    
    if 'items' in response:
        comments = [{
            "Comment": item['snippet']['topLevelComment']['snippet']['textDisplay'],
            "Author": item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
            "Published At": item['snippet']['topLevelComment']['snippet']['publishedAt']
        } for item in response['items']]
        
        df = pd.DataFrame(comments)
        return df
    else:
        st.write(f"No comments found for video {video_id}")
        return None


def get_video_details(video_url):
    video_id = extract_video_id(video_url)
    youtube = get_service()
    response = execute_api_request(
        youtube.videos().list,
        part="snippet,statistics,contentDetails",
        id=video_id
    )
    
    if 'items' in response:
        details = response['items'][0]
        snippet = details['snippet']
        statistics = details['statistics']
        content_details = details['contentDetails']
        
        # Parse publishedAt date
        published_at = datetime.datetime.strptime(snippet.get('publishedAt'), '%Y-%m-%dT%H:%M:%SZ')
        published_at_formatted = published_at.strftime('%B %d, %Y at %I:%M %p')
        
        data = {
            "Metric": [
                "Title",
                "Description",
                "Published At",
                "Duration",
                "View Count",
                "Like Count",
                "Dislike Count",
                "Comment Count",
                "Category"
            ],
            "Value": [
                snippet.get('title'),
                snippet.get('description'),
                published_at_formatted,
                content_details.get('duration'),
                statistics.get('viewCount'),
                statistics.get('likeCount'),
                statistics.get('dislikeCount'),
                statistics.get('commentCount'),
                snippet.get('categoryId')
            ]
        }
        
        df = pd.DataFrame(data)
        return df
    else:
        st.write(f"No data found for video {video_id}")

# Function to get view count from a video and estimate earnings
def estimate_earnings(video_url):
    video_id = extract_video_id(video_url)
    youtube = get_service()
    response = execute_api_request(
        youtube.videos().list,
        part="statistics",
        id=video_id
    )
    
    if 'items' in response:
        stats = response['items'][0]['statistics']
        view_count = int(stats.get('viewCount', 0))
        
        # Get average CPI for selected industry
        cpi_min, cpi_max = industries[selected_industry]
        average_cpi = (cpi_min + cpi_max) / 2
        
        # Earnings calculation using CPI
        estimated_earnings = view_count * average_cpi
        
        # Plot earnings as a bar chart
        st.write("### Earnings Estimation")
        st.write(f"Estimated Earnings: ${estimated_earnings:.2f}")
        
        return estimated_earnings
    else:
        st.write(f"No data found for video {video_id}")
        return None

# Function to get video tags and rankings
def get_video_tags(video_url):
    video_id = extract_video_id(video_url)
    youtube = get_service()
    response = execute_api_request(
        youtube.videos().list,
        part="snippet,statistics",
        id=video_id
    )
    
    if 'items' in response:
        item = response['items'][0]
        tags = item['snippet'].get('tags', [])
        view_count = item['statistics'].get('viewCount', 0)
        
        # Create DataFrame
        data = {
            "Tag": tags,
            "Ranking": [i + 1 for i in range(len(tags))],
            "View Count": [format_number(int(view_count))] * len(tags)
        }
        df = pd.DataFrame(data)
        
        st.write("### Video Tags and Rankings")
        return df 
    else:
        st.write(f"No data found for video {video_id}")
        return None
    
# Function to get trending keywords based on region
def get_trending_keywords(country):
    pytrends = TrendReq()
    
    # Get trending searches for the specified region
    trending_searches_df = pytrends.trending_searches(pn=country)
    
    # Simulate search volumes (you can implement your logic here)
    trending_data = {
        "Keyword": trending_searches_df[0].tolist(),
        "Search Volume": [np.random.randint(100_000, 2_000_000) for _ in range(len(trending_searches_df))],
        "Region": [country] * len(trending_searches_df)
    }
    
    df = pd.DataFrame(trending_data)
    df["Search Volume"] = df["Search Volume"].apply(format_number)
    return df

client_secret_json_path = client_secret_json_path = st.sidebar.file_uploader("Upload your client secret JSON file", type=["json"])
if client_secret_json_path:
    client_config = json.loads(client_secret_json_path.read())
redirect_uri = "https://youtube-viral-chatbot-7szrdtxws3dzuyxgaqwoka.streamlit.app"

# Local Storage Functions
def ls_get(key, session_key=None):
    return st_js_blocking(f"return JSON.parse(localStorage.getItem('{key}'));", session_key)

def ls_set(key, value, session_key=None):
    json_data = json.dumps(value, ensure_ascii=False)
    st_js_blocking(f"localStorage.setItem('{key}', JSON.stringify({json_data}));", session_key)

# Initialize session with user info if it exists in local storage
def init_session():
    user_info = ls_get("user_info")
    if user_info:
        st.session_state["user_info"] = user_info

# Authentication flow with Google OAuth
# Updated auth_flow to save credentials
def auth_flow():
    st.write("Welcome to My App!")
    auth_code = st.experimental_get_query_params().get("code", [None])[0]
    flow_instance = flow.Flow.from_client_secrets_file(
        client_config,
        scopes=[
            "https://www.googleapis.com/auth/youtube.force-ssl", 
            "https://www.googleapis.com/auth/userinfo.profile", 
            "https://www.googleapis.com/auth/userinfo.email", 
            "https://www.googleapis.com/auth/youtubepartner", 
            "https://www.googleapis.com/auth/youtube", 
            "openid"
        ],
        redirect_uri=redirect_uri,
    )

    if auth_code:
        flow_instance.fetch_token(code=auth_code)
        credentials = flow_instance.credentials
        st.session_state["credentials"] = credentials  # Save credentials here
        st.write("Login Done")

        user_info_service = build("oauth2", "v2", credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()

        if "email" not in user_info:
            st.error("Email not found in user info.")
            return

        st.session_state["google_auth_code"] = auth_code
        st.session_state["user_info"] = user_info
        ls_set("user_info", user_info)
    else:
        authorization_url, state = flow_instance.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
        )
        st.write(f"[Sign in with Google]({authorization_url})", unsafe_allow_html=True)

# Main app entry point
def main():
    init_session()
    
    if "user_info" not in st.session_state:
        auth_flow()
    else:
        st.write("Welcome back!")
        st.write(f"User: {st.session_state['user_info']['email']}")
    
    if "user_info" in st.session_state:
        st.write("Main App Content")
        
if __name__ == "__main__":
    main()

st.image("https://raw.githubusercontent.com/CertifiedAuthur/Youtube-Viral-Bot/refs/heads/main/YoutubeViralChatbot.png", width=200)
st.title("YouTube Viral ChatBot")

# Updated get_service to handle missing credentials
def get_service():
    if "credentials" not in st.session_state or st.session_state["credentials"] is None:
        st.error("Please sign in first.")
        return None
    try:
        service = build("youtube", "v3", credentials=st.session_state["credentials"])
        return service
    except Exception as e:
        st.error(f"Error building YouTube service: {e}")
        return None
    
def execute_api_request(client_library_function, **kwargs):
    try:
        response = client_library_function(**kwargs).execute()
        return response
    except Exception as e:
        st.error(f"API request failed: {e}")
        return None

# # Load secrets from Streamlit Cloud
# CLIENT_ID = st.secrets["general"]["CLIENT_ID"]
# CLIENT_SECRET = st.secrets["general"]["CLIENT_SECRET"]
# REDIRECT_URI = st.secrets["general"]["REDIRECT_URI"]

# def auth_flow():
#     # Define the scopes
#     scopes = [
#         "https://www.googleapis.com/auth/youtube.force-ssl",
#         "https://www.googleapis.com/auth/userinfo.profile",
#         "https://www.googleapis.com/auth/userinfo.email",
#         "https://www.googleapis.com/auth/youtubepartner",
#         "https://www.googleapis.com/auth/youtube",
#         "openid"
#     ]
    
#     # Set up the OAuth 2.0 flow
#     flow = Flow.from_client_config(
#         {
#             "installed": {
#                 "client_id": CLIENT_ID,
#                 "client_secret": CLIENT_SECRET,
#                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
#                 "token_uri": "https://oauth2.googleapis.com/token",
#                 "redirect_uris": [REDIRECT_URI],  # Use the variable REDIRECT_URI
#             }
#         },
#         scopes=scopes,
#         redirect_uri=REDIRECT_URI,
#     )

#     # Check if we have an authorization code
#     if "code" in st.session_state:
#         auth_code = st.session_state["code"]
#         flow.fetch_token(code=auth_code)
#         credentials = flow.credentials
#         st.session_state["credentials"] = credentials_to_dict(credentials)
#         st.session_state["email"] = get_user_email(credentials)  # Store the user email
#         st.experimental_rerun()
#     else:
#         # Generate the authorization URL
#         auth_url, _ = flow.authorization_url(prompt='consent')
#         st.write("Please [sign in]({}) to continue.".format(auth_url))
#         if st.button("Sign in"):
#             # Get the authorization code from the query params
#             st.session_state["code"] = st.experimental_get_query_params().get("code", [None])[0]
#             st.rerun()

# def get_user_email(credentials):
#     """Fetch user's email using the userinfo endpoint."""
#     from google.oauth2 import service_account
#     from googleapiclient.discovery import build

#     # Build a service for the userinfo API
#     userinfo_service = build("oauth2", "v2", credentials=credentials)
#     user_info = userinfo_service.userinfo().get().execute()
#     return user_info["email"]

# def credentials_to_dict(credentials):
#     """Convert credentials to a dictionary for easy access."""
#     return {
#         "token": credentials.token,
#         "refresh_token": credentials.refresh_token,
#         "token_uri": credentials.token_uri,
#         "client_id": credentials.client_id,
#         "client_secret": credentials.client_secret,
#         "scopes": credentials.scopes,
#     }

# def main():
#     # Initialize session state for credentials
#     if "credentials" not in st.session_state:
#         st.session_state["credentials"] = None
#     if "email" not in st.session_state:
#         st.session_state["email"] = None

#     if st.session_state["credentials"]:
#         # User is authenticated, proceed with API calls
#         credentials = google.oauth2.credentials.Credentials(**st.session_state["credentials"])
#         # Create YouTube API client here using `credentials`
#         youtube = build('youtube', 'v3', credentials=credentials)

#         # Display user email
#         st.write(f"Logged in as: {st.session_state['email']}")
#     else:
#         # Perform authentication
#         auth_flow()

st.image("https://raw.githubusercontent.com/CertifiedAuthur/Youtube-Viral-Bot/refs/heads/main/YoutubeViralChatbot.png", width=200)
st.title("YouTube Viral ChatBot")

# Updated get_service to handle missing credentials
def get_service():
    if "credentials" not in st.session_state or st.session_state["credentials"] is None:
        st.error("Please sign in first.")
        return None
    try:
        service = build("youtube", "v3", credentials=google.oauth2.credentials.Credentials(**st.session_state["credentials"]))
        return service
    except Exception as e:
        st.error(f"Error building YouTube service: {e}")
        return None
    
def execute_api_request(client_library_function, **kwargs):
    try:
        response = client_library_function(**kwargs).execute()
        return response
    except Exception as e:
        st.error(f"API request failed: {e}")
        return None

if __name__ == "__main__":
    main()

# try:
    # CLIENT_ID = st.secrets["general"]["CLIENT_ID"]
    # CLIENT_SECRET = st.secrets["general"]["CLIENT_SECRET"]
    # REDIRECT_URI = st.secrets["general"]["REDIRECT_URI"]

    
#     # Test output
#     st.write("Client ID loaded successfully.")
# except KeyError as e:
#     st.error(f"Missing secret key: {e}")

# # Display Google login link
# def get_login_str():
#     client = GoogleOAuth2(CLIENT_ID, CLIENT_SECRET)
#     authorization_url = asyncio.run(get_authorization_url(client, REDIRECT_URI))
#     return f'<a target="_self" href="{authorization_url}">Google login</a>'

# # Streamlit application
# st.title("Google Sign-In with Streamlit")

# if 'code' in st.query_params:
#     display_user()
# else:
#     st.markdown(get_login_str(), unsafe_allow_html=True)

# st.image("https://raw.githubusercontent.com/CertifiedAuthur/Youtube-Viral-Bot/refs/heads/main/YoutubeViralChatbot.png", width=200)

# st.title("YouTube Viral ChatBot")

# # YouTube API setup
# def get_service():
#     access_token = st.session_state.get('access_token')
#     if access_token:
#         try:
#             creds = credentials.Credentials(token=access_token)
#             return build("youtube", "v3", credentials=creds)
#         except Exception as e:
#             st.error(f"Failed to create YouTube API client: {e}")
#             return None
#     else:
#         st.error("No access token found. Please log in first.")
#         return None


# def execute_api_request(client_library_function, **kwargs):
#     youtube = get_service()  # Get YouTube API service client
#     if youtube:
#         response = client_library_function(**kwargs).execute()
#         return response
#     else:
#         st.error("Failed to execute API request.")

options = [
    "Public Channel Analytics", "Video Metrics", "YouTube Search", "Channel Information", "Playlist Details",
    "Video Comments", "Video Details", "Earnings Estimation", "Video Tags and Rankings", "Trending Keywords"
]

selected_option = st.sidebar.selectbox("Choose an analysis type", options)

# Placeholder for the content based on the selected option
if selected_option:
    st.write(f"You selected: **{selected_option}**")
    
if selected_option == "Public Channel Analytics":
    Channel_url = st.text_input("Enter enter Channel Url", "")
    
if selected_option == "Video Metrics":
    video_url = st.text_input("Enter Video Url", "")
    
if selected_option == "YouTube Search":
    search_query = st.text_input("Enter Search Query", "")
    
if selected_option == "Channel Information":
    channel_url = st.text_input("Enter Channel Url for Info", "")
    
if selected_option == "Playlist Details":
    channel_url = st.text_input("Enter Channel Url", "")
    
if selected_option == "Video Comments":
    video_url = st.text_input("Enter Video Url for Comments", "")
    
if selected_option == "Video Details":
    video_url = st.text_input("Enter Video Url for Details", "")
    
if selected_option == "Earnings Estimation":
    video_url = st.text_input("Enter Video Url for Earnings Estimation", "")
    # cpm = st.number_input("Enter CPM (Cost Per 1000 Impressions)", min_value=0.01, value=2.0, step=0.5)
    
if selected_option == "Trending Keywords":
    country = st.text_input("Enter Region Code (e.g., 'united_states', 'india')")
    
if selected_option  == "Video Tags and Rankings":
    video_url = st.text_input("Enter Video Url for Tags", "")



# Public Channel Analytics
if selected_option == "Public Channel Analytics":
    if st.button("Get Channel Analytics"):
        with st.spinner("Retrieving channel Data..."):
            if Channel_url:
                analytics_df = get_channel_analytics(Channel_url)
                st.success("Retrieval Completed!")
                st.write(analytics_df)

elif selected_option == "Video Metrics":
    if st.button("Get Video Metrics"):
        with st.spinner("Retrieving video metrics..."):
            metrics_df = get_video_metrics(video_url)
            st.success("Retrieval Completed!")
            st.write(metrics_df)

elif selected_option == "YouTube Search":
    if st.button("Search"):
        with st.spinner("Searching..."):
            if search_query:
                results_df = search_youtube(search_query)
                st.success("Searched Successfully!")
                st.write(results_df)

elif selected_option == "Channel Information":
    if st.button("Get Channel Information"):
        with st.spinner("Retrieving channel info..."):
            if channel_url:
                info_df = get_channel_info(channel_url)
                st.success("Retrieval Completed!")
                st.write(info_df)

elif selected_option == "Playlist Details":
    # Initialize session state
    if 'playlists' not in st.session_state:
        st.session_state.playlists = []
    if 'selected_playlist_title' not in st.session_state:
        st.session_state.selected_playlist_title = ''
    if 'selected_playlist_id' not in st.session_state:
        st.session_state.selected_playlist_id = ''


    if st.button("Get Playlists"):
        with st.spinner("Retrieving playlists..."):
            st.session_state.playlists = get_playlists_from_channel(channel_url)


    if st.session_state.playlists:
        # Create a selectbox for playlists
        playlist_titles = [playlist['Title'] for playlist in st.session_state.playlists]
        st.session_state.selected_playlist_title = st.selectbox("Select a Playlist:", playlist_titles)
        
        # Find the ID of the selected playlist
        selected_playlist = next((playlist for playlist in st.session_state.playlists if playlist['Title'] == st.session_state.selected_playlist_title), None)
        if selected_playlist:
            st.session_state.selected_playlist_id = selected_playlist['Playlist ID']
            
            # Retrieve and display playlist details when a playlist is selected
            if st.button("View Playlist Details"):
                playlist_details = get_playlist_details(st.session_state.selected_playlist_id)
                if playlist_details is not None:
                    st.write(playlist_details)

elif selected_option == "Video Comments":
    if st.button("Get Comments"):
        with st.spinner("Retrieving comments..."):
            if video_url:
                comments_df = get_video_comments(video_url)
                st.success("Retrieval Completed!")
                st.write(comments_df)

elif selected_option == "Video Details":
    if st.button("Get Video Details"):
        with st.spinner("Retrieving video details..."):
            if video_url:
                details_df = get_video_details(video_url)
                st.success("Retrieval Completed!")
                st.write(details_df)

elif selected_option == "Earnings Estimation":
    industries = {
        "Retail": (0.10, 0.30),
        "Finance": (0.20, 0.50),
        "Technology": (0.15, 0.40),
        "Healthcare": (0.25, 0.60),
        "Entertainment": (0.05, 0.20)
    }
    
    selected_industry = st.selectbox("Select Industry:", industries.keys())
    if st.button("Estimate Earnings"):
        with st.spinner("Retrieving earnings..."):
            earnings_df = estimate_earnings(video_url)
            st.success("Retrieval Completed!")
            st.write(earnings_df)

elif selected_option == "Trending Keywords":
    if st.button("Get Trending Keywords"):
        with st.spinner("Retrieving treding keywords..."):
            trending_df = get_trending_keywords(country)
            st.success("Retrieval Completed!")
            st.write(trending_df)

elif selected_option == "Video Tags and Rankings":
    if st.button("Get Video Tags"):
        with st.spinner("Retrieving video tags..."):
                tags_df = get_video_tags(video_url)
                st.success("Retrieval Completed!")
                st.write(tags_df)
                

