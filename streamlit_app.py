import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

# --- Core Analysis Functions ---

@st.cache_data
def analyze_page_for_deployment(url):
    """Fetches and parses a URL for title and deployment type analysis."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').get_text().strip() if soup.find('title') else 'No Title Found'
        return soup, title
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return None, "Fetch Error"

def get_deployment_type(soup):
    """Determines deployment type from parsed HTML based on specific class labels."""
    if not soup: return "Analysis Error"
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    if has_cloud and has_on_prem: return "Alation Cloud Service, Customer Managed"
    if has_cloud: return "Alation Cloud Service"
    if has_on_prem: return "Customer Managed"
    return "" # Return empty string if no label is found

# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("📄 URL to Deployment Type Mapper")

st.markdown("""
This application scrapes a list of URLs to reliably identify their deployment type.
1.  **Upload a `.txt` file** containing one URL per line in the sidebar.
2.  Click the **"Map Deployment Types"** button.
3.  View the results and **download the CSV report** for the next step of your analysis.
""")

# Sidebar for file uploads
with st.sidebar:
    st.header("1. Upload URLs")
    urls_file = st.file_uploader("Upload URLs File (.txt)", type="txt")

# Main application body
st.header("2. Run Analysis")

if st.button("🚀 Map Deployment Types", type="primary"):
    if urls_file:
        urls = [line.strip() for line in io.StringIO(urls_file.getvalue().decode("utf-8")) if line.strip()]

        st.info(f"Found {len(urls)} URLs. Starting analysis... Please wait.")
        
        results = []
        progress_bar = st.progress(0, text="Starting...")

        for i, url in enumerate(urls):
            progress_text = f"Processing URL {i+1}/{len(urls)}: {url.split('/')[-1]}"
            progress_bar.progress((i + 1) / len(urls), text=progress_text)
            
            soup, title = analyze_page_for_deployment(url)
            if soup:
                deployment_type = get_deployment_type(soup)
                results.append({
                    'Page Title': title,
                    'Page URL': url,
                    'Deployment Type': deployment_type,
                })
            else:
                 results.append({
                    'Page Title': title, 
                    'Page URL': url, 
                    'Deployment Type': 'Fetch Error',
                })
        
        # Store results in session state to persist them
        st.session_state.report_df = pd.DataFrame(results)
        progress_bar.empty()
        st.success("✅ Analysis complete!")

    else:
        st.warning("⚠️ Please upload a URLs file in the sidebar.")

# Display results if they exist in the session state
if 'report_df' in st.session_state:
    st.header("3. View and Download Results")
    
    st.dataframe(st.session_state.report_df)
    
    # Convert DataFrame to CSV for downloading
    csv_data = st.session_state.report_df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 Download Report as CSV",
        data=csv_data,
        file_name="deployment_type_report.csv",
        mime="text/csv",
    )
