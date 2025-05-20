import os
import json
import csv
import io
import uuid
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

def upload_to_dynamodb(table_name, data):
    try:
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION")
        )
        table = dynamodb.Table(table_name)

        item = {
            'id': str(uuid.uuid4()),
            'summary': data
        }

        table.put_item(Item=item)
        return True, item['id']
    except (BotoCoreError, ClientError) as e:
        return False, str(e)

def publish_to_sns(topic_arn, message, subject="CSV Summary Notification"):
    try:
        sns = boto3.client(
            'sns',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION")
        )
        response = sns.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
        return True, response
    except (BotoCoreError, ClientError) as e:
        return False, str(e)

def standard_response(message, status, data=None, error_code=None, http_status=None):
    response = {
        "message": message,
        "status": status,
        "data": data if status == "success" else None
    }
    if status == "error":
        response["error_code"] = error_code
    return jsonify(response), http_status or (200 if status == "success" else 400)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize():
    file = request.files.get('file')
    if not file:
        return standard_response(
            "No file uploaded.",
            "error",
            error_code="NO_FILE_PROVIDED",
            http_status=400
        )
    if not file.filename.endswith('.csv'):
        return standard_response(
            "Please upload a valid CSV file.",
            "error",
            error_code="INVALID_FILE_TYPE",
            http_status=400
        )

    try:
        text = file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return standard_response(
                "CSV must have at least one header row and one data row.",
                "error",
                error_code="INSUFFICIENT_ROWS",
                http_status=400
            )
    except Exception as e:
        return standard_response(
            f"Failed to parse CSV: {str(e)}",
            "error",
            error_code="CSV_PARSE_ERROR",
            http_status=400
        )

    header = rows[0]
    data_preview = rows[1:6]
    preview_csv = "\n".join([",".join(header)] + [",".join(r) for r in data_preview])

    prompt = (
        "You will be given a preview of a CSV file. Your task is to analyze its structure and content "
        "and summarize the data in a concise, human-readable JSON format.\n\n"
        "Instructions:\n"
        "- Describe the column names and their types (categorical, numerical, text, date, etc.).\n"
        "- Mention interesting patterns or statistics (e.g., frequent values, average, etc.) if observable.\n"
        "- Do not fabricate data or statistics.\n"
        "- Be concise, structured, and clear.\n\n"
        f"CSV Preview:\n{preview_csv}"
    )

    try:
        res = client.chat.completions.create(
            model = MODEL,
            messages = [
                {"role": "system", "content": "You are a helpful CSV analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature = 0.2,
            response_format = {"type": "json_object"},
        )
    except Exception as e:
        return standard_response(
            f"OpenAI API error: {str(e)}",
            "error",
            error_code="OPENAI_API_ERROR",
            http_status=500
        )

    try:
        summary_json = json.loads(res.choices[0].message.content)
    except json.JSONDecodeError:
        return standard_response(
            "OpenAI returned non-JSON output. Please try again.",
            "error",
            error_code="OPENAI_INVALID_RESPONSE",
            http_status=502
        )

    try:
        save_dir = "summaries"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{file.filename}.json")
        with open(save_path, "w") as f:
            json.dump(summary_json, f, indent=2)
    except Exception as e:
        return standard_response(
            f"Failed to save summary: {str(e)}",
            "error",
            error_code="SUMMARY_SAVE_ERROR",
            http_status=500
        )
    
    uploaded, result = upload_to_dynamodb('CSVSummaries', summary_json)
    if not uploaded:
        return standard_response(
            f"Failed to upload to DynamoDB: {result}",
            "error",
            error_code="DYNAMODB_UPLOAD_ERROR",
            http_status=500
        )

    topic_arn = os.getenv("AWS_SNS_TOPIC_ARN")
    sns_message = json.dumps({
        "summary_id": result,
        "filename": f"{file.filename}.json",
        "summary": summary_json
    })

    published, sns_result = publish_to_sns(topic_arn, sns_message)
    if not published:
        return standard_response(
            f"Failed to publish to SNS: {sns_result}",
            "error",
            error_code="SNS_PUBLISH_ERROR",
            http_status=500
        )

    return standard_response(
        "CSV summary generated successfully.",
        "success",
        data={"filename": f"{file.filename}.json"}
    )

@app.route('/download/<filename>')
def download_summary(filename):
    return send_from_directory('summaries', filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
