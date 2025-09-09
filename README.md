# URL to Deployment Type Mapper - Web Application

This repository contains a Streamlit web application that provides a reliable way to scrape a list of URLs and determine their deployment type based on specific HTML class labels. It is designed as the first step in a two-part content analysis workflow.

## Purpose

The primary goal of this application is to automate the deterministic task of identifying deployment types (Alation Cloud Service, Customer Managed, or both) for a large number of documentation pages.

It generates a clean CSV report containing the Page Title, URL, and the correctly mapped Deployment Type. This report can then be used as a reliable input for a second-stage analysis, where an LLM like Google Gemini can be prompted to perform more complex tasks like keyword generation and contextual metadata mapping.

## Features

- User-Friendly Interface: A simple web UI for uploading files and running the analysis.

- Reliable Scraping: Uses a consistent method to fetch live page data and identify deployment labels.

- Batch Processing: Analyzes a list of URLs from a .txt file in a single run.

- Downloadable Reports: Provides the results in a clean, downloadable CSV format.

## How to Use the Deployed Application

1. Prepare your URL file: Create a `.txt` file that contains the list of URLs you want to analyze. Each URL should be on a new line.

2. Access the App: Open the public URL provided by Streamlit.

3. Upload the file: In the application's sidebar, click "Browse files" and select your .txt file.

4. Run the analysis: Click the "Map Deployment Types" button. The application will show a progress bar as it processes each URL.

5. Download the results: Once the analysis is complete, a table with the results will appear. Click the "Download Report as CSV" button to save the data for your next analysis step.
