# Web Content & AI Enrichment Streamlit App

This is a multi-step Streamlit application designed to scrape web content from a list of URLs, map predefined metadata, and use Large Language Models (LLMs) to intelligently enrich the data and fill in any gaps.

The tool provides a full workflow, from initial data scraping and rule-based mapping to advanced, AI-powered content analysis, culminating in a clean, enriched CSV file ready for further use.

---

## Features

* **Step 1: Scrape & Map Deployment Type**: Ingests a list of URLs from a `.txt` file, scrapes the page title and main body content, and maps a `Deployment Type`.
* **Intelligent Scraping**: Automatically removes common boilerplate content like headers, footers, and navigation bars to ensure the analysis is performed only on the core article text.
* **Step 2 & 3: Rule-Based Metadata Mapping**: Maps `User Roles` and `Topics` from user-provided `.txt` files to the scraped content.
* **Step 4: AI-Powered Enrichment**: Connects to an LLM to:
    * Intelligently fill in any blank cells for `Deployment Type`, `User Role`, or `Topics`.
    * Generate a new `Functional Area` column by selecting the single most relevant term.
    * Generate a new `Keywords` column with 20 unique, relevant technical keywords.
* **Multi-Provider AI Support**: Includes a choice of AI providers for the enrichment step:
    * Google Gemini
    * OpenAI (GPT-4)
    * Hugging Face (supports any text-generation model via the Inference API)
* **Secure API Key Handling**: Uses password fields for the secure entry of API keys and tokens.
* **Downloadable Report**: The final, enriched data can be downloaded as a CSV file.

---

## Setup and Installation

To run this application locally, you'll need Python 3.8+ and the libraries listed in `requirements.txt`.

**1. Clone the repository:**
```bash
git clone <your-repository-url>
cd <your-repository-directory>

**2. Create and activate a virtual environment (recommended):**
```bash
# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

```bash
# For Windows
python -m venv venv
venv\Scripts\activate

**3. Install the required dependencies:**
```bash
pip install -r requirements.txt

## How to Use

### Launch the application:

Run the following command in your terminal from the project's root directory:
```bash
streamlit run streamlit_app.py

Your browser will open with the application running.

### Follow the on-screen steps:

  - Step 1: Map Deployment Type

    1. Upload a `.txt` file containing the URLs you want to process (one URL per line).

    2. Click **Scrape URLs**. The app will fetch the content for each URL.

  - Step 2: Map User Roles

    1. Upload a `.txt file` containing your list of user roles (one role per line).

    2. Click **Map User Roles**.

  - Step 3: Map Topics

    1. Upload a `.txt file` containing your list of topics (one topic per line).

    2. Click **Map Topics**.

  - Step 4: Enrich Data with AI

    1. Choose your preferred AI Provider from the dropdown menu.

    2. Enter your API Key or Access Token in the secure text field.

        - If you selected **Hugging Face**, you must also provide a **Model ID** (e.g., mistralai/Mistral-7B-Instruct-v0.2).

    3. Click **Fill Blanks with AI**. The app will process each row and display the final, fully enriched table.

### Download the report:

Once the process is complete, click the **Download Report (CSV)** button to save the results.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
