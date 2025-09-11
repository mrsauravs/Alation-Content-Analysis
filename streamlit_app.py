import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

# --- Utility and Scraping Functions ---

@st.cache_data
def analyze_page_content(url):
    """Fetches and parses a URL for its title and HTML content."""
    try:
        # Standard headers to mimic a browser visit
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
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
    # Check for the presence of specific paragraph tags with predefined classes
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    
    if has_cloud and has_on_prem:
        return "Alation Cloud Service, Customer Managed"
    if has_cloud:
        return "Alation Cloud Service"
    if has_on_prem:
        return "Customer Managed"
    
    return "Tag Not Found" # Return a clear message if no tags are found

def extract_main_content(soup):
    """
    Extracts the main textual content from the parsed HTML by looking for
    <article>, <main>, or <body> tags.
    """
    if not soup:
        return "Content Not Available"
    # Prioritize semantic tags like <article> and <main>, falling back to the entire <body>
    main_content = soup.find('article') or soup.find('main') or soup.body
    if main_content:
        # Get all text, using a space as a separator to prevent words from mashing together
        return main_content.get_text(separator=' ', strip=True)
    return "Main Content Not Found"

# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("📄 Web Content and Tag Scraper")
st.markdown("Upload a `.txt` file containing a list of URLs (one per line). The tool will scrape each URL for its **Deployment Type** (based on HTML tags) and its main **Page Content**.")

with st.sidebar:
    urls_file = st.file_uploader("Upload URLs File (.txt)", type="txt")

if st.button("🚀 Scrape URLs", type="primary"):
    if urls_file:
        urls = [line.strip() for line in io.StringIO(urls_file.getvalue().decode("utf-8")) if line.strip()]
        
        results = []
        progress_bar = st.progress(0, "Starting...")
        
        for i, url in enumerate(urls):
            progress_bar.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}...")
            soup, title = analyze_page_content(url)
            
            if soup:
                # Scrape for deployment type and main content
                deployment_type = get_deployment_type_from_scraping(soup)
                page_content = extract_main_content(soup)
                
                results.append({
                    'Page Title': title,
                    'Page URL': url,
                    'Deployment Type': deployment_type,
                    'Page Content': page_content
                })
            else:
                # Handle cases where the URL could not be fetched
                results.append({
                    'Page Title': title,
                    'Page URL': url,
                    'Deployment Type': 'Fetch Error',
                    'Page Content': 'Fetch Error'
                })
        
        st.session_state.report_df = pd.DataFrame(results)
        st.success("✅ Scraping complete! You can now view and download the report.")
    else:
        st.warning("⚠️ Please upload a URLs file in the sidebar to begin.")

if 'report_df' in st.session_state:
    st.subheader("Scraping Results")
    st.dataframe(st.session_state.report_df)
    
    csv_data = st.session_state.report_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Download Report (CSV)",
        data=csv_data,
        file_name="scraped_content_report.csv",
        mime="text/csv"
    )
