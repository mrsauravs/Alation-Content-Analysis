import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re # Imported for robust role matching

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

# --- NEW: Role Mapping Function ---
def find_roles_in_text(text, roles):
    """
    Finds which roles from a list are present in a given text.
    Uses a case-insensitive, whole-word search.
    """
    if not isinstance(text, str):
        return "Not Searched" # Handle non-string content
    
    found_roles = []
    for role in roles:
        # Use regex for whole-word, case-insensitive matching to avoid partial matches
        # (e.g., matching 'view' in 'overview' when the role is 'Viewer')
        if re.search(r'\b' + re.escape(role) + r'\b', text, re.IGNORECASE):
            found_roles.append(role)
            
    return ", ".join(found_roles) if found_roles else "No Roles Found"

# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("📄 Web Content and User Role Mapper")
st.markdown("A two-step tool to first scrape web content and then map user roles to that content.")

# --- Step 1: Scrape Content ---
with st.expander("Step 1: Scrape Content from URLs", expanded=True):
    st.markdown("Upload a `.txt` file containing a list of URLs (one per line). The tool will scrape each URL for its **Deployment Type** and main **Page Content**.")
    
    urls_file_step1 = st.file_uploader("Upload URLs File (.txt)", type="txt", key="step1_uploader")

    if st.button("🚀 Scrape URLs", type="primary"):
        if urls_file_step1:
            urls = [line.strip() for line in io.StringIO(urls_file_step1.getvalue().decode("utf-8")) if line.strip()]
            
            results = []
            progress_bar = st.progress(0, "Starting...")
            
            for i, url in enumerate(urls):
                progress_bar.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}...")
                soup, title = analyze_page_content(url)
                
                if soup:
                    deployment_type = get_deployment_type_from_scraping(soup)
                    page_content = extract_main_content(soup)
                    results.append({
                        'Page Title': title, 'Page URL': url,
                        'Deployment Type': deployment_type, 'Page Content': page_content
                    })
                else:
                    results.append({
                        'Page Title': title, 'Page URL': url,
                        'Deployment Type': 'Fetch Error', 'Page Content': 'Fetch Error'
                    })
            
            st.session_state.report_df = pd.DataFrame(results)
            st.success("✅ Step 1 complete! You can now proceed to Step 2.")
        else:
            st.warning("⚠️ Please upload a URLs file to begin.")

# --- Step 2: Map User Roles ---
if 'report_df' in st.session_state:
    with st.expander("Step 2: Map User Roles to Scraped Content", expanded=True):
        st.markdown("Upload your `user_roles.txt` file. The tool will read the roles and add a new column to the report below, showing which roles were found in each page's content.")
        
        roles_file_step2 = st.file_uploader("Upload User Roles File (.txt)", type="txt", key="step2_uploader")
        
        if st.button("🗺️ Map User Roles"):
            if roles_file_step2 and not st.session_state.report_df.empty:
                # Read roles and strip any whitespace
                user_roles = [line.strip() for line in io.StringIO(roles_file_step2.getvalue().decode("utf-8")) if line.strip()]
                
                if user_roles:
                    # Create a copy to avoid modifying the original dataframe in session state directly
                    df_to_map = st.session_state.report_df.copy()
                    
                    # Apply the mapping function
                    df_to_map['User Roles'] = df_to_map['Page Content'].apply(lambda text: find_roles_in_text(text, user_roles))
                    
                    # Store the mapped dataframe in session state
                    st.session_state.mapped_df = df_to_map
                    st.success("✅ Role mapping complete! The table below has been updated.")
                else:
                    st.warning("⚠️ The roles file is empty. Please upload a file with roles.")
            else:
                st.warning("⚠️ Please upload a user roles file.")

# --- Display and Download Results ---
st.markdown("---")
st.subheader("📊 Results")

# Decide which dataframe to show and download
df_to_display = pd.DataFrame()
if 'mapped_df' in st.session_state:
    st.info("Displaying report with mapped user roles.")
    df_to_display = st.session_state.mapped_df
elif 'report_df' in st.session_state:
    st.info("Displaying initial scraping report. Complete Step 2 to add user roles.")
    df_to_display = st.session_state.report_df

if not df_to_display.empty:
    st.dataframe(df_to_display)
    
    csv_data = df_to_display.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Download Full Report (CSV)",
        data=csv_data,
        file_name="web_content_and_roles_report.csv",
        mime="text/csv"
    )
else:
    st.write("Upload a file and click 'Scrape URLs' to generate a report.")
