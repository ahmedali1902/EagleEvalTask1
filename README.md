# 📌 Task 1: CSV Summarizer

## ✅ Overview

A Flask web application that:
- Accepts a CSV file upload via web UI.
- Uses OpenAI GPT to analyze and summarize the CSV structure and content.
- Converts the summary into a structured JSON format.
- Saves the summary to an AWS DynamoDB table.
- Triggers an AWS SNS event to send an email notification with relevant summary info.
- Returns a download link to the summarized JSON file for the user.

## 🧪 Example Workflow

1. Upload a `.csv` file via the UI.
2. Backend processes the file and generates a summary.
3. Summary is saved to DynamoDB.
4. SNS sends an email to configured subscribers.
5. UI provides a download link to the summary in JSON format.

## 🔧 Setup Instructions

1. Clone the repository:

    ```bash
    git clone https://github.com/ahmedali1902/EagleEvalTask1.git
    ```

2. Create a `.env` file with the following keys:

    ```env
    OPENAI_API_KEY=your_openai_api_key
    AWS_ACCESS_KEY_ID=your_aws_access_key
    AWS_SECRET_ACCESS_KEY=your_aws_secret_key
    AWS_DEFAULT_REGION=your_aws_region
    AWS_SNS_TOPIC_ARN=arn:aws:sns:your_aws_region:your_aws_id:your_sns_topic
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the app:

    ```bash
    python app.py
    ```