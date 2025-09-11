import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

# --- Utility and Scraping Functions ---

@st.cache_data
def analyze_page_content(url):
    """Fetches and parses a URL for its title and HTML content."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').get_text().strip() if soup.find('title') else 'No Title Found'
        return soup, title
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return None, "Fetch Error"

def get_deployment_type_from_scraping(soup):
    """Determines deployment type from parsed HTML based on specific class labels."""
    if not soup:
        return ""
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    if has_cloud and has_on_prem:
        return "Alation Cloud Service, Customer Managed"
    if has_cloud:
        return "Alation Cloud Service"
    if has_on_prem:
        return "Customer Managed"
    return "Tag Not Found"

def extract_main_content(soup):
    """Extracts the main textual content from the parsed HTML."""
    if not soup:
        return "Content Not Available"
    main_content = soup.find('article') or soup.find('main') or soup.body
    if main_content:
        return main_content.get_text(separator=' ', strip=True)
    return "Main Content Not Found"

# --- Mapping Functions ---

def find_roles_in_text(text, roles):
    """Finds which roles from a list are present in a given text."""
    if not isinstance(text, str):
        return "Not Searched"
    found_roles = []
    for role in roles:
        if re.search(r'\b' + re.escape(role) + r'\b', text, re.IGNORECASE):
            found_roles.append(role)
    return ", ".join(found_roles) if found_roles else "No Roles Found"

def find_primary_functional_area(row, functional_areas):
    """
    Finds the first-mentioned standalone functional area.
    Priority 1: First match in the Page Title.
    Priority 2: First match in the Page Content based on text position.
    """
    title = row.get('Page Title', '')
    content = row.get('Page Content', '')
    
    if not isinstance(title, str): title = ""
    if not isinstance(content, str): content = ""

    def is_standalone_word(text, match):
        start_index = match.start()
        end_index = match.end()
        is_start_valid = (start_index == 0) or (text[start_index - 1].isspace() or text[start_index - 1] in '(),."\'')
        is_end_valid = (end_index == len(text)) or (text[end_index].isspace() or text[end_index] in '(),."\'')
        return is_start_valid and is_end_valid

    # Priority 1: Find the first standalone match in the Page Title
    for area in functional_areas:
        for match in re.finditer(r'\b' + re.escape(area) + r'\b', title, re.IGNORE
